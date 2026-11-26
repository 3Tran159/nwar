"""Local W04b runner. Windows owns the complete STAR process tree as one job."""
from contextlib import ExitStack
import ctypes
from ctypes import wintypes
import re
import shutil
import socket
import subprocess
import threading

from common import ROOT, STOPS, now, os, read, sha, tail, time, write


class _BasicLimits(ctypes.Structure):
    _fields_ = [('process_time', ctypes.c_longlong), ('job_time', ctypes.c_longlong),
                ('flags', wintypes.DWORD), ('min_working_set', ctypes.c_size_t),
                ('max_working_set', ctypes.c_size_t), ('process_limit', wintypes.DWORD),
                ('affinity', ctypes.c_size_t), ('priority', wintypes.DWORD),
                ('scheduling', wintypes.DWORD)]


class _ExtendedLimits(ctypes.Structure):
    _fields_ = [('basic', _BasicLimits), ('io', ctypes.c_ulonglong * 6),
                ('process_memory_limit', ctypes.c_size_t), ('job_memory_limit', ctypes.c_size_t),
                ('peak_process_memory', ctypes.c_size_t), ('peak_job_memory', ctypes.c_size_t)]


class _ThreadEntry(ctypes.Structure):
    _fields_ = [(name, wintypes.DWORD) for name in
                ('size', 'usage', 'tid', 'pid', 'base_priority', 'delta_priority', 'flags')]


class _JobProcessList(ctypes.Structure):
    _fields_ = [('assigned',wintypes.DWORD),('count',wintypes.DWORD),('pids',ctypes.c_size_t*128)]


def _api(name, result, *arguments):
    function = getattr(ctypes.WinDLL('kernel32', use_last_error=True), name)
    function.restype = result
    function.argtypes = arguments
    return function


def _check(result):
    if not result:
        raise ctypes.WinError(ctypes.get_last_error())
    return result


_close = _api('CloseHandle', wintypes.BOOL, wintypes.HANDLE)


class _OwnedJob:
    def __enter__(self):
        create = _api('CreateJobObjectW', wintypes.HANDLE, wintypes.LPVOID, wintypes.LPCWSTR)
        self.handle = _check(create(None, None))
        limits = _ExtendedLimits()
        limits.basic.flags = 0x2000  # KILL_ON_JOB_CLOSE, with no permitted breakaway.
        configure = _api('SetInformationJobObject', wintypes.BOOL, wintypes.HANDLE,
                         ctypes.c_int, wintypes.LPVOID, wintypes.DWORD)
        try:
            _check(configure(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)))
        except OSError:
            _close(self.handle)
            raise
        return self

    def attach(self, proc, mask):
        attach = _api('AssignProcessToJobObject', wintypes.BOOL, wintypes.HANDLE, wintypes.HANDLE)
        affinity = _api('SetProcessAffinityMask', wintypes.BOOL, wintypes.HANDLE, ctypes.c_size_t)
        _check(attach(self.handle, int(proc._handle)))
        _check(affinity(int(proc._handle), mask))

    def terminate(self):
        terminate = _api('TerminateJobObject', wintypes.BOOL, wintypes.HANDLE, wintypes.UINT)
        _check(terminate(self.handle, 1))

    def owns_pid(self, pid):
        open_process = _api('OpenProcess', wintypes.HANDLE, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        member = _api('IsProcessInJob', wintypes.BOOL, wintypes.HANDLE, wintypes.HANDLE,
                      ctypes.POINTER(wintypes.BOOL))
        handle = open_process(0x1000, False, pid)
        if not handle:
            return False
        try:
            inside = wintypes.BOOL()
            return bool(member(handle, self.handle, ctypes.byref(inside)) and inside.value)
        finally:
            _close(handle)

    def native_ranks(self):
        query=_api('QueryInformationJobObject',wintypes.BOOL,wintypes.HANDLE,wintypes.INT,
                   wintypes.LPVOID,wintypes.DWORD,ctypes.POINTER(wintypes.DWORD))
        listing=_JobProcessList()
        _check(query(self.handle,3,ctypes.byref(listing),ctypes.sizeof(listing),None))
        open_process=_api('OpenProcess',wintypes.HANDLE,wintypes.DWORD,wintypes.BOOL,wintypes.DWORD)
        image=_api('QueryFullProcessImageNameW',wintypes.BOOL,wintypes.HANDLE,wintypes.DWORD,
                   wintypes.LPWSTR,ctypes.POINTER(wintypes.DWORD))
        for pid in listing.pids[:listing.count]:
            handle=open_process(0x1000,False,pid)
            if not handle:
                continue
            try:
                name=ctypes.create_unicode_buffer(1024)
                size=wintypes.DWORD(len(name))
                if image(handle,0,name,ctypes.byref(size)) and name.value.lower().endswith('\\star-ccm+.exe'):
                    return True
            finally:
                _close(handle)
        return False

    def __exit__(self, *_):
        _close(self.handle)


def _resume(pid):
    snapshot = _api('CreateToolhelp32Snapshot', wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD)
    first = _api('Thread32First', wintypes.BOOL, wintypes.HANDLE, ctypes.POINTER(_ThreadEntry))
    next_thread = _api('Thread32Next', wintypes.BOOL, wintypes.HANDLE, ctypes.POINTER(_ThreadEntry))
    open_thread = _api('OpenThread', wintypes.HANDLE, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    resume = _api('ResumeThread', wintypes.DWORD, wintypes.HANDLE)
    handle = snapshot(4, 0)  # TH32CS_SNAPTHREAD
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        entry = _ThreadEntry(size=ctypes.sizeof(_ThreadEntry))
        found = first(handle, ctypes.byref(entry))
        while found:
            if entry.pid == pid:
                thread = _check(open_thread(2, False, entry.tid))  # THREAD_SUSPEND_RESUME
                try:
                    if resume(thread) == 0xffffffff:
                        raise ctypes.WinError(ctypes.get_last_error())
                finally:
                    _close(thread)
                return
            found = next_thread(handle, ctypes.byref(entry))
        raise OSError('Suspended STAR launcher thread was not found.')
    finally:
        _close(handle)


def _stop_reason(folder, started, budget, free_memory):
    if any(path.exists() for path in STOPS) or any(
            path.exists() for path in (folder/'STOP', folder.parent/'STOP', folder.parent/'STOP_ALL')):
        return 'user_stop'
    gib = 2**30
    from resource_limits import memory_reason
    memory = memory_reason(free_memory)
    if memory:
        return memory
    if shutil.disk_usage('C:/').free < 15*gib or shutil.disk_usage(ROOT).free < 25*gib:
        return 'disk_guard'
    if time.monotonic()-started > budget:
        return 'wall_budget'


def _wait_for_owned_listener(port, launcher, owned):
    deadline = time.monotonic()+90
    while launcher.poll() is None and time.monotonic()<deadline:
        result = subprocess.run(['netstat', '-ano', '-p', 'tcp'], capture_output=True, text=True,
                                timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
        for line in result.stdout.splitlines():
            fields = line.split()
            if len(fields)==5 and fields[1].rsplit(':',1)[-1]==str(port) and fields[3]=='LISTENING':
                if owned.owns_pid(int(fields[-1])):
                    return
                raise RuntimeError('The selected STAR listener belongs to another process.')
        time.sleep(1)
    raise RuntimeError('The owned STAR listener did not become available.')


def _finish_stream(proc, reader):
    proc.wait(timeout=15)
    reader.join()
    proc.stdout.close()


def latest_native_step(folder):
    steps = []
    for path in folder.glob('input*@*.sim'):
        # Batch-final input@<iteration>.sim uses a different counter from the
        # rolling input_<n>@<time-step>.sim snapshots.
        match = re.fullmatch(r'input_\d+@(\d+)\.sim', path.name)
        if not match:
            continue
        try:
            snapshot = path.stat()
        except FileNotFoundError:  # STAR may rotate the older snapshot during enumeration.
            continue
        if snapshot.st_size >= 400_000_000 and time.time() - snapshot.st_mtime >= 2:
            steps.append(int(match.group(1)))
    return max(steps, default=None)


def run(folder, source, macro, *, executable, options, env, mask, budget, redact, free_memory,
        loopback_port=None, phase='NWAR_W04b', watch_progress=False, native_batch=False, status_dir=None,
        native_initial_step=None, native_initial_time=None, native_dt=.0004, native_target_step=None):
    if loopback_port and native_batch:
        raise ValueError('Native batch and the separate batch client are mutually exclusive.')
    initial_digest = sha(source)
    working = folder/'input.sim'
    local_macro = folder/macro.name
    if working.exists() or local_macro.exists():
        raise ValueError('W04b working files already exist.')
    shutil.copy2(source, working)
    if sha(working) != initial_digest:
        raise ValueError('W04b source copy did not match.')
    shutil.copy2(macro, local_macro)
    write(folder/'source_identity.json', dict(path=str(source), sha256=initial_digest, original_preserved=True))
    write(folder/'identity.json', dict(phase=phase, source=str(source), source_sha256=initial_digest,
          macro_sha256=sha(macro), workers=1, cpu_workers=1, gpu=True, created=now()))
    args = [str(executable), *options, '-gpgpu', 'auto:1']
    args.extend(['-server', '-loc', str(working)] if loopback_port
                else ['-batch', 'run' if native_batch else str(local_macro), str(working)])
    reset = threading.Event()
    started = time.monotonic()
    reason = None
    reset_started = None
    job_terminated_after_reset = False
    status_dir=status_dir or folder
    with (folder/'star.log').open('x', encoding='utf-8') as log:
        with ExitStack() as cleanup, _OwnedJob() as owned:
            log_lock = threading.Lock()
            def start(command):
                proc = subprocess.Popen(command, cwd=folder, env=dict(os.environ, **env), stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace',
                                        creationflags=subprocess.CREATE_NO_WINDOW | 0x4)  # CREATE_SUSPENDED
                try:
                    owned.attach(proc, mask)
                    _resume(proc.pid)
                except Exception:
                    proc.kill()
                    proc.wait()
                    proc.stdout.close()
                    raise
                def drain():
                    for line in proc.stdout:
                        with log_lock:
                            log.write(redact(line))
                            log.flush()
                        if line.strip() in ('Connection reset','Connection reset by peer'):
                            reset.set()
                reader = threading.Thread(target=drain, daemon=True)
                reader.start()
                # The job closes before draining its remaining stdout handles.
                cleanup.callback(_finish_stream, proc, reader)
                return proc

            if loopback_port:
                with socket.socket() as probe:
                    probe.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
                    probe.bind(('127.0.0.1',loopback_port))
            launcher = start(args)
            proc = launcher
            info = dict(pid=launcher.pid, controller_pid=os.getpid(), workers=1, gpu=True,
                        at=now(), mask=mask, ownership='windows_job')
            write(folder/'process.json', info)
            if loopback_port:
                _wait_for_owned_listener(loopback_port,launcher,owned)
                proc = start([str(executable),'-loc','-host',f'127.0.0.1:{loopback_port}',
                              '-batch',str(local_macro)])
                write(folder/'process.json',dict(info,batch_client_pid=proc.pid,loopback_port=loopback_port))
            last_check = 0
            progress_at, progress_step = started, None
            native_origin=native_initial_step
            latest_native_row = {}
            native_client_lowered = False
            stop_at = None
            while proc.poll() is None or native_batch and owned.native_ranks():
                tick = time.monotonic()
                if loopback_port and launcher.poll() is not None:
                    owned.terminate()
                    proc.wait(timeout=15)
                    break
                if reset.is_set() and reset_started is None:
                    reset_started = tick
                    write(folder/'transport_disconnect.json', dict(at=now(), launcher_pid=proc.pid,
                                                                   elapsed_wall_s=tick-started))
                if not native_batch and reset_started is not None and tick-reset_started >= 25:
                    owned.terminate()
                    job_terminated_after_reset = True
                    proc.wait(timeout=15)
                    break
                if tick-last_check >= 5:
                    last_check = tick
                    if native_batch and not native_client_lowered and proc.poll() is None and owned.native_ranks():
                        set_priority = _api('SetPriorityClass', wintypes.BOOL, wintypes.HANDLE, wintypes.DWORD)
                        _check(set_priority(int(proc._handle), 0x4000))  # BELOW_NORMAL, after the rank inherited Normal.
                        native_client_lowered = True
                        write(folder/'client_priority_review.json', dict(at=now(), pid=proc.pid,
                              client_priority='BelowNormal', solver_priority='Normal', cpu_mask=mask,
                              reason='Keep the batch console from starving its owned native solver on their shared core.'))
                    external_reason = _stop_reason(folder, started, budget, free_memory)
                    if not reason or native_batch and reason == 'night_progress_timeout':
                        reason = external_reason or reason
                    if reason and not (native_batch and reason == 'night_progress_timeout'):
                        (folder/'STOP').touch()
                        if native_batch and stop_at is None:
                            stop_at=tick
                    recent = tail(folder/'history.csv')
                    row = recent[-1] if recent else {}
                    if native_batch:
                        with (folder/'star.log').open('rb') as stream:
                            stream.seek(max(0,stream.seek(0,2)-65536))
                            matches=re.findall(rb'\bTimeStep\s+(\d+):\s+Time\s+([0-9.Ee+-]+)',stream.read())
                        if matches:
                            if native_origin is None:native_origin=int(matches[0][0])-1
                            step,t=matches[-1]
                            row=dict(step=int(step)-native_origin,time_s=float(t))
                        step = latest_native_step(folder)
                        if step is not None and native_origin is not None:
                            if step-native_origin>row.get('step',-1):
                                initial_time = native_initial_time
                                if initial_time is None:
                                    initial_time = native_origin*native_dt
                                row = dict(step=step-native_origin,
                                           time_s=initial_time+(step-native_origin)*native_dt)
                        if row.get('step', -1) > latest_native_row.get('step', -1):
                            latest_native_row = row
                        row = latest_native_row
                        if (not reason and native_target_step is not None
                                and latest_native_step(folder) == native_target_step):
                            reason = 'native_target_saved'
                            write(folder/'native_target_saved.json', dict(at=now(), step=native_target_step,
                                  time_s=row.get('time_s'), final_monitor_review_required=True))
                            owned.terminate()
                            proc.wait(timeout=15)
                            break
                    if watch_progress and (not reason or native_batch and reason == 'night_progress_timeout'):
                        step = row.get('step')
                        if step != progress_step:
                            progress_step,progress_at=step,tick
                            if reason == 'night_progress_timeout':
                                reason, stop_at = None, None
                        if tick-progress_at > (600 if step is None else 300):
                            reason='night_progress_timeout'
                            if stop_at is None:
                                stop_at=tick
                            if not native_batch:
                                (folder/'STOP').touch()
                    grace = 600 if native_batch and reason == 'night_progress_timeout' else 150
                    if stop_at is not None and tick-stop_at >= grace:
                        owned.terminate()
                        proc.wait(timeout=15)
                        break
                    try:
                        write(status_dir/'monitor.json', dict(at=now(), phase=phase, reason=reason, pid=proc.pid,
                              status='stop_requested' if reason else 'running' if row else 'loading',
                              last_step=row.get('step'), time_s=row.get('time_s'), elapsed_wall_s=tick-started,
                              transport_disconnected=reset_started is not None))
                    except PermissionError:
                        pass  # A dashboard reader can briefly hold the old snapshot open.
                time.sleep(1)
    result = dict(exit_code=proc.returncode, source_unchanged=sha(source)==initial_digest,
                  controller_reason=reason, completed=read(folder/'completed.json'), phase=phase,
                  at=now(), wall_s=time.monotonic()-started, timing=[],
                  ownership='windows_job_closed', job_terminated_after_reset=job_terminated_after_reset,
                  transport_disconnected=reset.is_set())
    write(folder/'stage_result.json', result)
    target_saved = native_batch and reason == 'native_target_saved'
    if not result['source_unchanged'] or (proc.returncode or reason) and not target_saved:
        raise AssertionError('W04b solver stage failed or stopped. Original evidence preserved.')
