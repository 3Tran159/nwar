"""Run the 2602 native-solve pilot after the active overnight job releases GPU."""
import re
import subprocess

from common import (DATA, HERE, STOPS, SOLVER_LOCKS, OTHER_LOCKS, Path, birth, job, jobs,
                    now, read, sha, time, uuid, write)
from worker import OWNER, W04B_CPU_MASK, owned_lock, queue_wait_reason, rt
from w04b_controller import run


SOURCE_JOB = '42a2dc2b2c6f5072'
PILOT = DATA/'qa/native_pilot_2602_20261106_r2'


def stop_present():
    return any(p.exists() for p in STOPS+[DATA/'STOP', DATA/'PAUSE'])


def wait_for_slot():
    while True:
        if stop_present():
            raise RuntimeError('A stop or pause is present.')
        owner = read(OWNER)
        if owner and birth(owner.get('pid')) != owner.get('birth'):
            raise RuntimeError('The queue lock has no verified live owner.')
        active = any(j['status'] in ('running','preflight','pausing') for j in jobs())
        if not OWNER.exists() and not active and not queue_wait_reason({'allow_approved_cpu':True}):
            return
        write(PILOT/'pilot_status.json',dict(at=now(),status='waiting_for_gpu'))
        time.sleep(15)


def sim_info(path):
    info = subprocess.run([str(rt.guard.STAR),'-info',str(path)],capture_output=True,text=True,timeout=60)
    match = re.search(r'\bStep\s+(\d+)\s+Time\s+([0-9.Ee+-]+)', info.stdout)
    if info.returncode or not match:
        raise ValueError('Cannot read native step and time from '+path.name)
    return int(match.group(1)),float(match.group(2))


def verify_solve(source, solve, digest):
    stage=read(solve/'stage_result.json')
    if stage.get('exit_code')!=0 or stage.get('source_unchanged') is not True or sha(source)!=digest:
        raise ValueError('Native solve did not finish cleanly or source integrity differs.')
    start,_=sim_info(source)
    log=(solve/'star.log').read_text(encoding='utf-8')
    step_times={int(step):float(t) for step,t in re.findall(r'\bTimeStep\s+(\d+):\s+Time\s+([0-9.Ee+-]+)',log)}
    snapshots=[]
    for path in solve.glob('*.sim'):
        if path.name=='input.sim' or path.stat().st_size<400_000_000:
            continue
        step,_=sim_info(path)
        if step in step_times:
            snapshots.append((step,path))
    if {step for step,_ in snapshots}!={start+10,start+20}:
        raise ValueError('The native autosave files do not match steps 10 and 20.')
    end_step,final=max(snapshots)
    end=step_times[end_step]
    if abs(end-5.808)>1e-7:
        raise ValueError('Native stop does not match the configured physical time.')
    return dict(at=now(),status='passed',source_sha256=digest,steps=20,
        final=str(final),final_sha256=sha(final),time_s=end,autosave_verified=True,
        scientific_acceptance=False)


def main():
    PILOT.mkdir(parents=True,exist_ok=False)
    locks = []
    token = uuid.uuid4().hex
    try:
        wait_for_slot()
        owned_lock(OWNER,token,'nwar_native_pilot')
        locks.append(OWNER)
        if stop_present() or queue_wait_reason({'allow_approved_cpu':True}):
            raise RuntimeError('Solver resources changed before the pilot.')
        for path in SOLVER_LOCKS:
            owned_lock(path,token,'nwar_native_pilot')
            locks.append(path)

        entry = job(SOURCE_JOB)
        folder = Path(entry['folder'])
        checkpoint = read(folder/'latest_checkpoint.json')
        source = folder/'wave_bound_pre_step.sim'
        if (entry['status']!='failed' or checkpoint.get('file')!=source.name
                or checkpoint.get('step')!=0 or checkpoint.get('healthy') is not True
                or abs(checkpoint['time_s']-5.8)>1e-7 or source.stat().st_size<400_000_000
                or read(folder/'stage_result.json').get('ownership')!='windows_job_closed'):
            raise ValueError('Expected saved W04c setup was not verified.')
        digest = sha(source)
        if abs(sim_info(source)[1]-5.8)>1e-7 or '21.02.007' not in str(rt.guard.STAR):
            raise ValueError('Unexpected native pilot source time or STAR version.')
        macro = HERE/'NwarNativePilot.java'
        options = rt.guard.saved_options(1)
        setup = PILOT/'setup'
        setup.mkdir()
        prepared = setup/'native_ready.sim'
        kwargs = dict(executable=rt.guard.STAR, options=options, mask=W04B_CPU_MASK,
                      budget=600, redact=rt.guard.redact, free_memory=rt.guard.free_memory)
        write(PILOT/'pilot_status.json',dict(at=now(),status='preparing',source_sha256=digest))
        run(setup,source,macro,env={'NWAR_NATIVE_PILOT_OUT':str(prepared)},phase='NWAR_native_setup',
            watch_progress=True,**kwargs)
        if sim_info(prepared)!=sim_info(source) or stop_present():
            raise ValueError('Unexpected configured time or stop before native solve.')

        solve = PILOT/'solve'
        solve.mkdir()
        write(PILOT/'pilot_status.json',dict(at=now(),status='native_batch',source_sha256=digest))
        run(solve,prepared,macro,env={},phase='NWAR_native_run',native_batch=True,**kwargs)
        write(PILOT/'pilot_status.json',verify_solve(source,solve,digest))
    except Exception as exc:
        write(PILOT/'pilot_status.json',dict(at=now(),status='hold',reason=rt.guard.redact(str(exc))))
        raise
    finally:
        for path in reversed(locks):
            if read(path).get('token')==token:
                path.unlink()


if __name__=='__main__':
    main()
