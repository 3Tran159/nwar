"""Explicit, identity-pinned CPU coexistence for the PRE observation only."""
import hashlib
import json
import subprocess
from common import HERE, birth, read, now

APPROVAL = HERE / 'qa/pre_w04_cpu_coexistence.json'
NATIVE = ('starccm+', 'star-ccm+', 'mpiexec')

class ActiveSolverError(RuntimeError):
    """A STAR/MPI process prevents a new launch."""


def snapshot():
    # Command lines may contain license credentials: never return or log them.
    command = ('Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,'
               'Name,ExecutablePath,CommandLine | ConvertTo-Json -Depth 3 -Compress')
    result = subprocess.run(['powershell', '-NoProfile', '-Command', command],
        capture_output=True, text=True, timeout=20, creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise RuntimeError('Process inventory unavailable')
    records = json.loads(result.stdout)
    records = records if isinstance(records, list) else [records]
    out = {}
    for r in records:
        pid = int(r['ProcessId'])
        command_line = r.get('CommandLine') or ''
        out[pid] = dict(pid=pid, parent=int(r['ParentProcessId']), name=r['Name'],
            exe=r.get('ExecutablePath'), birth=birth(pid), has_command=bool(command_line),
            gpu_flag='-gpgpu' in command_line.lower(),
            command_sha256=hashlib.sha256(command_line.encode('utf8')).hexdigest())
    return out


def classify(processes, approval):
    """Unknown, GPU, reused-PID and untraceable processes fail closed."""
    if approval.get('authorized') is not True or approval.get('scope') != 'PRE_W04_observation_CPU_coexistence':
        raise ValueError('Explicit PRE CPU coexistence authorization missing')
    roots = {}
    for root in approval.get('cpu_roots', []):
        current = processes.get(root['pid'])
        if not current:
            continue
        if (current['name'].lower() == 'starccm+.exe' and current['has_command']
            and not current['gpu_flag'] and current['birth']
            and all(current.get(k) == root.get(k) for k in ('birth', 'command_sha256', 'exe'))):
            roots[root['pid']] = root
    allowed, blocked = [], []
    for pid, proc in processes.items():
        if not proc['name'].lower().startswith(NATIVE):
            continue
        visited, cur, found = set(), pid, False
        while cur in processes and cur not in visited:
            visited.add(cur)
            node = processes[cur]
            if not node['birth'] or not node['has_command'] or node['gpu_flag']:
                break
            if cur in roots:
                found = True
                break
            parent = processes.get(node['parent'])
            if not parent or not parent['birth'] or int(parent['birth']) > int(node['birth']):
                break
            cur = node['parent']
        (allowed if found else blocked).append(dict(pid=pid, name=proc['name'], birth=proc['birth']))
    return dict(at=now(), allowed_cpu=allowed, blockers=blocked)


def check(*, launch=True):
    processes = snapshot()
    result = classify(processes, read(APPROVAL))
    if result['blockers']:
        raise ActiveSolverError('GPU or unverified STAR/MPI process active: ' + str([p['pid'] for p in result['blockers']]))
    if launch:
        from worker import rt
        problem = rt.resource_problem()
        if problem:
            raise RuntimeError(problem)
        query = subprocess.run(['nvidia-smi', '--query-compute-apps=pid,process_name',
            '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW)
        if query.returncode:
            raise RuntimeError('GPU process inventory unavailable')
        gpu_pids = {int(line.split(',', 1)[0]) for line in query.stdout.splitlines()
                    if line.split(',', 1)[0].strip().isdigit()}
        native_on_gpu = [p['pid'] for p in result['allowed_cpu'] if p['pid'] in gpu_pids]
        if native_on_gpu:
            raise RuntimeError('An approved CPU solver is using GPU: ' + str(native_on_gpu))
        query = subprocess.run(['nvidia-smi', '--query-gpu=memory.free,utilization.gpu,temperature.gpu',
            '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW)
        if query.returncode:
            raise RuntimeError('GPU resource inventory unavailable')
        free, load, temperature = map(float, query.stdout.splitlines()[0].split(','))
        if free < 4000 or load >= 45 or temperature >= 85:
            raise RuntimeError('GPU busy or insufficient GPU resources')
        result.update(gpu_free_MiB=free, gpu_load_pct=load, gpu_temperature_C=temperature,
                      free_RAM_GiB=rt.guard.free_memory()/2**30)
    return result
