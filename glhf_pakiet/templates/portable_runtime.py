"""Owned serial STAR launcher. Never attaches to, kills, or borrows another solver."""
from pathlib import Path
import os,sys,json,time,hashlib,shutil,ctypes,subprocess,threading,re
from types import SimpleNamespace
from common import DATA,RUNS,HERE,STOPS,birth,read,write,sha,tail,now
from portable_config import BASE,WORK,RELEASE,settings,installation

GIB=2**30
MIN_FREE_RAM_GIB=8


def processes():
    from ctypes import wintypes as W
    class Entry(ctypes.Structure):
        _fields_=[('dwSize',W.DWORD),('cntUsage',W.DWORD),('th32ProcessID',W.DWORD),('th32DefaultHeapID',ctypes.c_size_t),('th32ModuleID',W.DWORD),('cntThreads',W.DWORD),('th32ParentProcessID',W.DWORD),('pcPriClassBase',W.LONG),('dwFlags',W.DWORD),('szExeFile',W.WCHAR*260)]
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.CreateToolhelp32Snapshot.argtypes=[W.DWORD,W.DWORD];k.CreateToolhelp32Snapshot.restype=W.HANDLE
    k.Process32FirstW.argtypes=[W.HANDLE,ctypes.POINTER(Entry)];k.Process32NextW.argtypes=[W.HANDLE,ctypes.POINTER(Entry)];k.CloseHandle.argtypes=[W.HANDLE]
    handle=k.CreateToolhelp32Snapshot(2,0)
    if handle==ctypes.c_void_p(-1).value:raise RuntimeError('Cannot inspect active solver processes.')
    out={};entry=Entry();entry.dwSize=ctypes.sizeof(entry)
    try:
        ok=k.Process32FirstW(handle,ctypes.byref(entry))
        while ok:
            out[entry.th32ProcessID]=(entry.th32ParentProcessID,entry.szExeFile)
            ok=k.Process32NextW(handle,ctypes.byref(entry))
    finally:k.CloseHandle(handle)
    return out


def free_memory():
    class Memory(ctypes.Structure):
        _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(k,ctypes.c_ulonglong) for k in ('total','free','page_total','page_free','virtual_total','virtual_free','extended')]
    m=Memory();m.length=ctypes.sizeof(m)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):raise RuntimeError('Cannot inspect available RAM.')
    return m.free


def redact(text):
    key=os.environ.get('NWAR_POD_KEY','')
    if key:text=text.replace(key,'[REDACTED]')
    return re.sub(r'(?i)(-podkey\s+|pod[_ -]?key\s*[:=]\s*)\S+',r'\1[REDACTED]',text)


guard=SimpleNamespace(processes=processes,free_memory=free_memory,redact=redact)


def resource_problem():
    if any(p.exists() for p in STOPS+[DATA/'PAUSE']):return 'Pause/STOP is present.'
    if free_memory()<MIN_FREE_RAM_GIB*GIB:return f'At least {MIN_FREE_RAM_GIB} GiB free RAM is required.'
    if shutil.disk_usage(WORK).free<25*GIB:return 'At least 25 GiB free workspace storage is required.'
    return None


def launch_arguments(source,macro,workers=1,gpu=True):
    if workers!=1 or gpu is not True:raise ValueError('This package uses one solver process and one GPU.')
    config=settings();installed=installation(config['executable'])
    if installed['release']!=RELEASE:raise ValueError('Selected STAR version differs from this workspace.')
    args=[installed['executable'],'-np','1','-gpgpu','auto:1']
    mode=config.get('license_mode','system')
    if mode=='server':
        address=config.get('license_server','').strip()
        if not address or '\n' in address:raise ValueError('Configure the local license server first.')
        args+=['-licpath',address]
        if config.get('power_session'):args+=['-power']
    elif mode=='pod':
        key=os.environ.get('NWAR_POD_KEY','')
        if not key:raise ValueError('Restart Start NWAR and enter the Power-on-Demand key for this session.')
        args+=['-power','-podkey',key]
    elif mode!='system':raise ValueError('Unsupported license setting.')
    return args+['-batch',str(macro),str(source)],installed


def stage(folder,source,macro,env=None,workers=1,gpu=True,mask=None,budget_s=43200,protect_main=False,phase='NWAR'):
    folder,source,macro=map(Path,(folder,source,macro))
    if not folder.resolve().is_relative_to(RUNS.resolve()) or folder.resolve()==RUNS.resolve():raise ValueError('Run directory is outside this workspace.')
    if (folder/'star.log').exists():raise ValueError('Existing run is preserved.')
    problem=resource_problem()
    if problem:raise ValueError(problem)
    if any(n.lower().startswith(('starccm+','star-ccm+','mpiexec')) for _,n in processes().values()):raise ValueError('Another STAR/MPI process is active; waiting for resources.')
    folder.mkdir(parents=True,exist_ok=True)
    digest=sha(source);inputpath=folder/'input.sim';localmacro=folder/macro.name
    if inputpath.exists() or localmacro.exists():raise ValueError('Existing input files are preserved.')
    shutil.copy2(source,inputpath);shutil.copy2(macro,localmacro)
    if sha(inputpath)!=digest:raise ValueError('Copied input checksum failed.')
    args,installed=launch_arguments(inputpath,localmacro,workers,gpu)
    actual_env=dict(os.environ,**(env or {}),NWAR_RUN_ROOT=str(RUNS.resolve()),NWAR_GLOBAL_STOP=str(DATA/'STOP'),PYTHONUTF8='1')
    # Recheck after copying: a manual pause or another solver may have appeared.
    problem=resource_problem()
    if problem:raise ValueError(problem)
    if any(n.lower().startswith(('starccm+','star-ccm+','mpiexec')) for _,n in processes().values()):raise ValueError('Another solver appeared before launch.')
    write(folder/'source_identity.json',dict(path=str(source),sha256=digest,original_preserved=True))
    write(folder/'identity.json',dict(phase=phase,source=str(source),source_sha256=digest,macro_sha256=sha(macro),workers=1,cpu_workers=1,gpu=True,release=RELEASE,build=installed['build'],created=now()))
    started=time.monotonic();reason=None
    with (folder/'star.log').open('x',encoding='utf8') as log:
        proc=subprocess.Popen(args,cwd=folder,env=actual_env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
        write(folder/'process.json',dict(pid=proc.pid,birth=birth(proc.pid),controller_pid=os.getpid(),controller_birth=birth(os.getpid()),workers=1,gpu=True,at=now(),release=RELEASE))
        def drain():
            for line in proc.stdout:log.write(redact(line));log.flush()
        thread=threading.Thread(target=drain,daemon=True);thread.start();lastcheck=0
        while proc.poll() is None:
            if time.monotonic()-lastcheck>=10:
                lastcheck=time.monotonic();reason=reason or resource_problem()
                if time.monotonic()-started>budget_s:reason=reason or 'wall_budget'
                if (folder/'STOP').exists():reason=reason or 'user_stop'
                if reason:(folder/'STOP').touch(exist_ok=True)
                rr=tail(folder/'history.csv');last=rr[-1] if rr else {}
                write(folder/'monitor.json',dict(at=now(),phase=phase,status='stop_requested' if reason else 'running' if rr else 'loading',reason=reason,pid=proc.pid,last_step=last.get('step'),time_s=last.get('time_s'),elapsed_wall_s=time.monotonic()-started,main_timing=[]))
            time.sleep(2)
        thread.join(20)
    result=dict(exit_code=proc.returncode,source_unchanged=sha(source)==digest,controller_reason=reason,completed=read(folder/'completed.json'),phase=phase,at=now(),wall_s=time.monotonic()-started,release=RELEASE)
    write(folder/'stage_result.json',result)
    if proc.returncode!=0 or result['source_unchanged'] is not True:raise ValueError('Solver failed; checkpoint and logs preserved for review.')
    return folder,result
