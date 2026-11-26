"""Build a separate, reproducible Windows distribution; never touch the live campaign."""
from pathlib import Path
import os,sys,json,shutil,hashlib,re,subprocess,datetime,argparse,zipfile

HERE=Path(__file__).resolve().parent
LIVE=HERE.parent/'nwar_automation'
ORIGINAL=Path('E:/ntnu_mesh_optimization_20261030')
DEST=Path('E:/NWAR_portable_20261103/NWAR_Windows_2602_2606')
QA=DEST.parent/'QA'
PYTHON=Path(sys.executable).parent
DEPS=HERE.parent/'mesh_study_20261030/.deps'
TEMPLATES=HERE/'templates'
APPFILES='common.py analysis.py english.py history_view.py project_results.py response_plots.py comparison_plots.py phase_alignment.py report_selection.py report_page.py report.py pre_w04.py pre_balance.py pre_lineage.py calm_reference.py wave_profiles.py validation.py custom_waves.py wave_view.py worker.py server.py NwarWave.java index.html style.css app.js wave_view.js history_chart.js convergence_chart.js project_policy.json wave_plan.json'.split()
APPFILES+=['glhf_import.py','glhf_bundle.py']

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(8*1024**2),b''):h.update(block)
    return h.hexdigest()

def put(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if not isinstance(value,str):value=json.dumps(value,indent=2,ensure_ascii=False)
    path.write_text(value,encoding='utf8')

def replace(text,old,new):
    assert text.count(old)==1,(old[:100],text.count(old))
    return text.replace(old,new)

def adapt_app():
    app=DEST/'app';app.mkdir(exist_ok=True,parents=True)
    for name in APPFILES:shutil.copy2(LIVE/name,app/name)
    for name in ('portable_config.py','portable_runtime.py'):shutil.copy2(TEMPLATES/name,app/name)
    shutil.copy2(TEMPLATES/'start_nwar.py',DEST/'start_nwar.py')
    p=app/'common.py';s=p.read_text(encoding='utf8')
    s=replace(s,"ROOT=Path('E:/ntnu_mesh_optimization_20261030')","from portable_config import BASE,WORK,RELEASE,ASSETS,relocate\nROOT=ASSETS")
    s=replace(s,"DATA=ROOT/'nwar_automation_20261102'","DATA=WORK/'data'")
    s=replace(s,"PYTHON=Path('C:/Users/ThinkPad/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe')","PYTHON=BASE/'runtime/python.exe'")
    s=replace(s,"DEP=WORKSPACE/'mesh_study_20261030/.deps'","DEP=BASE/'lib'")
    start=s.index('EXISTING={');end=s.index('def now():',start)
    s=s[:start]+"EXISTING={}\nSTOPS=[BASE/'STOP_ALL',DATA/'STOP',DATA/'STOP_ALL']\nSOLVER_LOCKS=[BASE/'solver.lock',DATA/'solver.lock']\nOTHER_LOCKS=[]\n"+s[end:]
    s=replace(s,"json.loads(Path(p).read_text(encoding='utf-8-sig'))","relocate(json.loads(Path(p).read_text(encoding='utf-8-sig')))")
    s=replace(s,"if c.get('kind')!='wave':continue","if c.get('kind')!='wave' or c.get('id') not in ('W04','W05','W06','W07'):continue")
    s=replace(s,"mpi_processes not in (1,2)","mpi_processes!=1")
    s=s.replace('Reviewed GPU process count is 1 or 2.','This package uses one GPU solver process.')
    s=s.replace('Waiting for W04–W07 acceptance before serial launch.','Waiting for serial launch.')
    s=s.replace('After W04–W07 acceptance; then one GPU solver process.','Waiting for serial launch; one GPU solver process.').replace('Oczekuje w kolejce','Waiting in the queue')
    put(p,s)
    for name in ('pre_w04.py','calm_reference.py'):
        p=app/name;s=p.read_text(encoding='utf8');s=s.replace("DATA/'PRE_W04_20261102'","ROOT/'nwar_automation_20261102/PRE_W04_20261102'")
        if name=='pre_w04.py':
            s=replace(s,"active=bool(state.get('birth') and state['birth']==birth(state.get('pid')))","active=False  # Immutable, completed preparation archive.")
            s=replace(s,'def export():','def export():\n return  # Preserved plots and history are shipped with the immutable PRE archive.')
        put(p,s)
    put(app/'prepare_w04_geometry.py',"from common import ROOT\nOUT=ROOT/'nwar_automation_20261102/mesh_W04_20261102'\n")
    put(app/'pre_resume.py',"from pre_w04 import PRE,calm_folders\nfrom common import read\ndef checkpoint_info():\n r=read(PRE/'calm_receipt.json');return dict(available=False,starting=False,reason='Accepted PRE is preserved. Start a new wave from it.',folder=str(calm_folders()[-1]),checkpoint=r.get('checkpoint'),time_s=r.get('checkpoint_time_s'),sha256=r.get('checkpoint_sha256'))\ndef resume(*args,**kwargs):\n raise ValueError('The accepted PRE archive cannot be resumed or overwritten.')\n")
    p=app/'worker.py';s=p.read_text(encoding='utf8')
    s=replace(s,'import owned_experiment_runtime_20261031 as rt','import portable_runtime as rt')
    s=replace(s,"spec.get('mpi_processes',1) not in (1,2)","spec.get('mpi_processes',1)!=1")
    s=replace(s,'mask=WAVE_CPU_MASK','mask=None')
    a=s.index(' if spec.get(\'allow_approved_cpu\'):',s.index('def resource_processes'))
    b=s.index('\ndef queue_wait_reason',a)
    s=s[:a]+" if native():raise ValueError('Another STAR/MPI solver is active.')\n"+s[b:]
    s=replace(s,' spec=j[\'spec\']\n'," spec=j['spec']\n rt.launch_arguments(Path(spec['source']),MACRO)  # Validate the chosen local installation and license settings.\n")
    put(p,s)
    p=app/'server.py';s=p.read_text(encoding='utf8');s=replace(s,'PORT=8782',"PORT=int(os.environ.get('NWAR_PORT','8782'))")
    s=s.replace('shutil.disk_usage(ROOT)','shutil.disk_usage(WORK)')
    s=replace(s,"if any(job(id)['status']=='queued' for id in ids):ensure_worker()","if any(job(id)['status']=='queued' for id in ids):ensure_worker();enable_report_updates()")
    s=s.replace('It starts after W04–W07 are accepted and the solver is free.','It starts when the solver is free and the queue is continued.')
    s=replace(s,"    if self.path=='/api/enqueue':","    if self.path=='/api/close-dashboard':\n     owner=read(DATA/'worker.lock')\n     if any(j['status'] in ('queued','preflight','running','pausing','deferred') for j in jobs()) or (owner.get('birth') and birth(owner.get('pid'))==owner['birth']):raise ValueError('Save the active run and cancel waiting requests before closing this service.')\n     self.send({'ok':True,'message':'Dashboard service closed. Saved results remain available.'})\n     threading.Thread(target=self.server.shutdown,daemon=True).start();return\n    if self.path=='/api/enqueue':")
    s=replace(s,"replace(b'__TOKEN__',TOKEN.encode())","replace(b'__TOKEN__',TOKEN.encode()).replace(b'__STAR_RELEASE__',RELEASE.encode())")
    put(p,s)
    for name in ('index.html','app.js','common.py'):
        p=app/name;s=p.read_text(encoding='utf8').replace('Add to queue after W04–W07','Add to queue').replace("deferred:'After W04–W07'","deferred:'Waiting for resources'").replace('Free E:','Free storage:')
        if name=='index.html':s=s.replace('NTNU · M13 · COMPUTATIONAL CAMPAIGN','NWAR PORTABLE · STAR-CCM+ __STAR_RELEASE__ · M13')
        put(p,s)
    p=app/'NwarWave.java';s=p.read_text(encoding='utf8')
    a=s.index(' void stopCheck()');b=s.index(' double[] forces()',a)
    s=s[:a]+''' void stopCheck(){if(Files.exists(out.resolve("STOP"))||Files.exists(out.getParent().resolve("STOP"))||Files.exists(out.getParent().resolve("STOP_ALL"))||
  Files.exists(Paths.get(Objects.requireNonNull(System.getenv("NWAR_GLOBAL_STOP")))))
   throw new IllegalStateException("STOP requested");}
'''+s[b:]
    a=s.index('   String isolate=');b=s.index('    throw new IllegalStateException("Disposable M13',a)
    s=s[:a]+'''   Path isolate=Paths.get(Objects.requireNonNull(System.getenv("NWAR_RUN_ROOT"))).toAbsolutePath().normalize();
   if(!out.startsWith(isolate)||out.equals(isolate)||!Paths.get(s.getSessionPath()).toAbsolutePath().normalize().equals(out.resolve("input.sim")))
'''+s[b:]
    put(p,s)
    put(app/'campaign_followup.json',dict(enabled=False,id=None,reference_mode='original',reference_id='C01_original',allow_approved_cpu=False))
    put(app/'compile_receipt.json',dict(ok=False,expanded_profile='M13_W04_20261102',macro_sha256=digest(app/'NwarWave.java')))

def copy_asset(path):
    path=Path(path);destination=DEST/'assets/root'/path.relative_to(ORIGINAL)
    if not path.is_file():raise FileNotFoundError(path)
    if path.suffix=='.json':
        # Selected scientific evidence must not contain a launcher or license credential.
        raw=path.read_text(encoding='utf-8-sig')
        if re.search(r'(?i)(-podkey\s+|"(?:password|pod_key|podkey|license_key|command_line|commandline)"\s*:)',raw):
            raise ValueError('Sensitive launch metadata excluded: '+path.name)
    destination.parent.mkdir(parents=True,exist_ok=True)
    if not destination.exists() or destination.stat().st_size!=path.stat().st_size:shutil.copy2(path,destination)
    original_hash=digest(path);copied_hash=digest(destination)
    if original_hash!=copied_hash:raise ValueError('Asset copy checksum mismatch: '+path.name)
    return dict(path=str(path.relative_to(ORIGINAL)).replace('\\','/'),bytes=path.stat().st_size,sha256=original_hash)

def assets():
    sys.path.insert(0,str(LIVE))
    from common import SOURCE,CALM,read
    from pre_w04 import PRE,calm_folders,calm_checkpoint
    selected=[SOURCE,CALM/'history.csv',CALM/'C01_final_acceptance_20261101.json',ORIGINAL/'results_catalog/mesh_comparison.json',ORIGINAL/'wave_campaign_20261101/campaign.json']
    selected += [PRE/n for n in ('calm_receipt.json','continuation.json','state.json','history.csv','convergence.csv')]
    selected+=list(PRE.glob('PRE_W04_*.png'))+list(PRE.glob('PRE_W04_*.svg'))
    folders=calm_folders();selected += [Path(read(folders[0]/'source_identity.json')['path'])]
    metadata='source_identity.json stage_result.json setup.json completed.json latest_checkpoint.json global_ramp_completed.json history_cutoff.json baseline_inventory_audit.json field_guard.json calm_gate.json'.split()
    for folder in folders:
        selected.append(calm_checkpoint(folder))
        selected += [folder/n for n in metadata if (folder/n).is_file()]
        selected += list(folder.glob('*.csv'))
    mesh=ORIGINAL/'nwar_automation_20261102/mesh_W04_20261102'
    selected += [mesh/n for n in ('geometry/mesh.CGNS','geometry_receipt.json','protected_receipt.json','design.json')]
    evidence=[]
    for p in dict.fromkeys(selected):
        if p.suffix in ('.sim','.CGNS'):print('Copy and verify asset:',p.parent.name+'/'+p.name,flush=True)
        evidence.append(copy_asset(p))
    put(DEST/'asset_provenance.json',dict(created=datetime.datetime.now().astimezone().isoformat(),original_C01_sha256=digest(SOURCE),accepted_PRE_sha256=digest(calm_checkpoint(folders[-1])),files=evidence,originals_modified=False))

def runtime():
    target=DEST/'runtime';target.mkdir(exist_ok=True,parents=True)
    for name in ('Lib','DLLs','tcl'):
        shutil.copytree(PYTHON/name,target/name,dirs_exist_ok=True,ignore=shutil.ignore_patterns('site-packages','__pycache__','*.pyc','test','tests','idle_test'))
    for p in PYTHON.iterdir():
        if p.is_file() and (p.suffix.lower() in ('.exe','.dll') or p.name.startswith('LICENSE')):shutil.copy2(p,target/p.name)
    shutil.copytree(DEPS,DEST/'lib',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.whl','tests','test','bin'))

def compile_macro():
    result={};javac=Path('C:/Program Files/Eclipse Adoptium/jdk-25.0.3.9-hotspot/bin/javac.exe')
    for release,build in [('2602','21.02.007'),('2606','21.04.009')]:
        star=Path(f'E:/Program Files/Siemens/{build}-R8/STAR-CCM+{build}-R8/star')
        output=QA/('compile_'+release);output.mkdir(exist_ok=True,parents=True)
        run=subprocess.run([str(javac),'-encoding','UTF-8','-classpath',str(star/'lib/java/platform/modules/ext/*'),'-d',str(output),str(DEST/'app/NwarWave.java')],capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
        result[release]=dict(build=build,compiled=run.returncode==0,native_solver_tested=False,compiler='OpenJDK 25.0.3',diagnostics=run.stderr.replace(str(DEST),'PACKAGE'))
        print('Macro compile',release,run.returncode,flush=True)
        if run.returncode:raise RuntimeError(run.stderr)
    receipt=dict(ok=True,expanded_profile='M13_W04_20261102',macro_sha256=digest(DEST/'app/NwarWave.java'),origin_macro_sha256=digest(LIVE/'NwarWave.java'),portable_change='Filesystem isolation and STOP paths only; equations and numerical guards unchanged.',compiled_at=datetime.datetime.now().astimezone().isoformat(),versions=result,native_solver_tested=False)
    put(DEST/'app/compile_receipt.json',receipt);put(QA/'macro_compatibility.json',receipt)

def documents():
    prefix='@echo off\ncd /d "%~dp0"\nset "PYTHONHOME=%~dp0runtime"\nset "PYTHONPATH=%~dp0lib"\nset "PYTHONNOUSERSITE=1"\n'
    for name,args in [('Start NWAR',''),('Configure NWAR','--configure'),('Close dashboard','--stop-dashboard')]:
        put(DEST/(name+'.cmd'),prefix+'start "" "%~dp0runtime\\pythonw.exe" "%~dp0start_nwar.py" '+args+'\n')
    put(DEST/'Verify package.cmd',prefix+'"%~dp0runtime\\python.exe" "%~dp0start_nwar.py" --verify\npause\n')
    shutil.copy2(TEMPLATES/'README_PL.txt',DEST/'CZYTAJ_NAJPIERW.txt')
    shutil.copy2(TEMPLATES/'README_EN.txt',DEST/'README.txt')

def manifest():
    entries=[]
    for p in sorted(DEST.rglob('*')):
        if not p.is_file() or p.name=='package_manifest.json' or '__pycache__' in p.parts or p.suffix=='.pyc':continue
        if p.parts[len(DEST.parts)] in ('workspaces',) or p.name in ('launcher.json','launcher-error.txt'):continue
        entries.append(dict(path=p.relative_to(DEST).as_posix(),bytes=p.stat().st_size,sha256=digest(p)))
    put(DEST/'package_manifest.json',dict(package='NWAR Windows 2602/2606',created=datetime.datetime.now().astimezone().isoformat(),files=entries,total_bytes=sum(x['bytes'] for x in entries),native_solver_tested=False))
    return entries

def archive(output=None):
    entries=manifest();output=Path(output) if output else DEST.with_suffix('.zip')
    if output.exists():raise ValueError('Existing archive is preserved; select a new name.')
    with zipfile.ZipFile(output,'w',allowZip64=True) as z:
        for item in entries+[dict(path='package_manifest.json')]:
            p=DEST/item['path'];method=zipfile.ZIP_STORED if p.suffix in ('.sim','.CGNS') else zipfile.ZIP_DEFLATED
            z.write(p,DEST.name+'/'+item['path'],compress_type=method,compresslevel=1)
    checksum=digest(output)
    put(output.with_suffix('.zip.sha256'),checksum+'  '+output.name+'\n')
    print(json.dumps(dict(archive=str(output),bytes=output.stat().st_size,sha256=checksum)),flush=True)

if __name__=='__main__':
    if os.name=='nt':
        import ctypes
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(),0x4000)
    parser=argparse.ArgumentParser();parser.add_argument('--archive',action='store_true');parser.add_argument('--app-only',action='store_true');parser.add_argument('--output',type=Path);a=parser.parse_args()
    if a.archive:archive(a.output)
    else:
        DEST.mkdir(exist_ok=True,parents=True);QA.mkdir(exist_ok=True,parents=True)
        adapt_app();documents();compile_macro()
        if not a.app_only:
            print('Copy portable Python and scientific libraries',flush=True);runtime();assets()
        manifest();print('Package files ready for isolated tests',flush=True)
