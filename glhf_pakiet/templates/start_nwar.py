"""Windows launcher. Opening the dashboard never starts a solver."""
from pathlib import Path
import os,sys,json,shutil,subprocess,socket,time,urllib.request,webbrowser,argparse,hashlib

BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE/'lib'))
os.environ['PYTHONUTF8']='1'
os.environ['PYTHONHOME']=str(BASE/'runtime')
os.environ['PYTHONNOUSERSITE']='1'
for name,pattern in [('TCL_LIBRARY','tcl8.*'),('TK_LIBRARY','tk8.*')]:
    candidates=list((BASE/'runtime/tcl').glob(pattern))
    if candidates:os.environ[name]=str(candidates[0])


def read(path):
    try:return json.loads(Path(path).read_text(encoding='utf8'))
    except (OSError,ValueError):return {}


def write(path,value):
    path=Path(path);path.parent.mkdir(exist_ok=True,parents=True)
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2),encoding='utf8');tmp.replace(path)


def inspect_installation(exe):
    import re
    exe=Path(exe).resolve()
    if not exe.is_file() or exe.name.lower()!='starccm+.exe':raise ValueError('Select the installed starccm+.exe executable.')
    star=next((p for p in exe.parents if (p/'version_info.properties').is_file()),None)
    if star is None:raise ValueError('Cannot identify this STAR installation.')
    m=re.search(r'^base_version=(\S+)',(star/'version_info.properties').read_text(encoding='utf8'),re.M)
    version=m.group(1) if m else ''
    release='2602' if version.startswith('21.02.') else '2606' if version.startswith('21.04.') else None
    if not release:raise ValueError('Only STAR-CCM+ 2602 / 2606 are supported by this package.')
    return dict(executable=str(exe),release=release,build=version)


def installations():
    found=[]
    for drive in 'CDEFGHIJKLMNOPQRSTUVWXYZ':
        root=Path(drive+':/Program Files/Siemens')
        try:available=root.is_dir()
        except OSError:available=False  # Unmounted/locked removable volumes are normal.
        if available:
            for exe in root.glob('*/STAR-CCM+*/star/lib/win64/*/lib/starccm+.exe'):
                try:found.append(inspect_installation(exe))
                except ValueError:pass
    return found


def configure(saved=None):
    import tkinter as tk
    from tkinter import ttk,filedialog,messagebox
    saved=saved or {};options=installations();result={}
    root=tk.Tk();root.title('NWAR · Windows setup');root.geometry('760x660');root.minsize(720,640)
    frame=ttk.Frame(root,padding=24);frame.pack(fill='both',expand=True)
    ttk.Label(frame,text='Start your NWAR dashboard',font=('Segoe UI',18,'bold')).pack(anchor='w')
    ttk.Label(frame,text='STAR-CCM+ 2602 / 2606 · one solver process with GPU').pack(anchor='w',pady=(4,16))
    exe=tk.StringVar(value=saved.get('executable',options[0]['executable'] if options else ''))
    ttk.Label(frame,text='Installed STAR-CCM+ executable').pack(anchor='w')
    row=ttk.Frame(frame);row.pack(fill='x',pady=(4,12))
    combo=ttk.Combobox(row,textvariable=exe,values=[o['executable'] for o in options]);combo.pack(side='left',fill='x',expand=True)
    ttk.Button(row,text='Browse',command=lambda:exe.set(filedialog.askopenfilename(title='Select starccm+.exe',filetypes=[('STAR executable','starccm+.exe')]) or exe.get())).pack(side='right',padx=(8,0))
    workspace=tk.StringVar(value=saved.get('workspace_root',str(BASE/'workspaces')))
    ttk.Label(frame,text='Folder for new calculations (separate 2602 and 2606 subfolders)').pack(anchor='w')
    row=ttk.Frame(frame);row.pack(fill='x',pady=(4,12));ttk.Entry(row,textvariable=workspace).pack(side='left',fill='x',expand=True)
    ttk.Button(row,text='Browse',command=lambda:workspace.set(filedialog.askdirectory(title='Calculation workspace') or workspace.get())).pack(side='right',padx=(8,0))
    modes=['system','server','pod'];mode=tk.StringVar(value=saved.get('license_mode','system'))
    ttk.Label(frame,text='License: system = existing installation settings; pod = Power-on-Demand').pack(anchor='w')
    ttk.Combobox(frame,textvariable=mode,values=modes,state='readonly').pack(anchor='w',pady=(4,10))
    server=tk.StringVar(value=saved.get('license_server',''));power=tk.BooleanVar(value=saved.get('power_session',False))
    ttk.Label(frame,text='License server (server mode only; for example port@server)').pack(anchor='w')
    ttk.Entry(frame,textvariable=server).pack(fill='x',pady=(4,4))
    ttk.Checkbutton(frame,text='Use Power Session with this license server',variable=power).pack(anchor='w')
    key=tk.StringVar(value=os.environ.get('NWAR_POD_KEY',''))
    ttk.Label(frame,text='Power-on-Demand key (pod mode only; used for this session, never saved)').pack(anchor='w',pady=(10,0))
    ttk.Entry(frame,textvariable=key,show='•').pack(fill='x',pady=(4,12))
    ttk.Label(frame,text='Opening the dashboard does not start calculations.\nC01 and PRE are preserved; new runs use disposable copies.').pack(anchor='w')
    def save():
        try:
            config=inspect_installation(exe.get());destination=Path(workspace.get()).resolve()
            if destination==BASE or any(destination.is_relative_to(BASE/n) for n in ('assets','app','runtime','lib')):
                raise ValueError('Choose a separate folder for calculation workspaces.')
            destination.mkdir(exist_ok=True,parents=True)
            if mode.get()=='server' and not server.get().strip():raise ValueError('Enter a license server.')
            if mode.get()=='pod' and not key.get().strip():raise ValueError('Enter a Power-on-Demand key for this session.')
            config.update(workspace_root=str(destination),license_mode=mode.get(),license_server=server.get().strip(),power_session=power.get())
            if mode.get()=='pod':os.environ['NWAR_POD_KEY']=key.get().strip()
            result.update(config);write(BASE/'launcher.json',config);root.destroy()
        except Exception as ex:messagebox.showerror('NWAR setup',str(ex),parent=root)
    ttk.Button(frame,text='Save and open dashboard',command=save).pack(anchor='e',pady=(16,0))
    root.mainloop();return result


def environment(config):
    release=config['release'];work=Path(config['workspace_root'])/release
    return dict(os.environ,NWAR_PACKAGE_ROOT=str(BASE),NWAR_WORKSPACE=str(work),NWAR_STAR_RELEASE=release,PYTHONHOME=str(BASE/'runtime'),PYTHONNOUSERSITE='1',PYTHONPATH=str(BASE/'lib'),PYTHONUTF8='1')


def prepare(config):
    installed=inspect_installation(config['executable'])
    if installed['release']!=config['release']:raise ValueError('Installation and workspace version differ.')
    env=environment(config);work=Path(env['NWAR_WORKSPACE']);app=work/'app';app.mkdir(parents=True,exist_ok=True)
    # Existing workspace application files are preserved; this package initializes new workspaces.
    for source in (BASE/'app').iterdir():
        if source.is_file() and not (app/source.name).exists():shutil.copy2(source,app/source.name)
    settings_path=work/'settings.json';existing=read(settings_path)
    if existing and existing!=config:
        # Never change a live server/worker's configuration from under it.
        probe=subprocess.run([str(BASE/'runtime/python.exe'),'-c',"from common import *; import json; print(json.dumps(any((lambda o:o.get('birth') and birth(o.get('pid'))==o['birth'])(read(DATA/n)) for n in ('server.json','worker.lock'))))"],cwd=app,env=env,capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
        if probe.returncode or probe.stdout.strip()=='true':raise ValueError('This workspace is active. Close its dashboard service after saving any run before changing its settings.')
    write(settings_path,config)
    return app,env


def verify_files():
    manifest=read(BASE/'package_manifest.json');fail=[]
    for item in manifest.get('files',[]):
        path=BASE/item['path']
        if not path.is_file() or path.stat().st_size!=item['bytes']:fail.append(item['path']);continue
        h=hashlib.sha256()
        with path.open('rb') as f:
            for block in iter(lambda:f.read(8*1024**2),b''):h.update(block)
        if h.hexdigest()!=item['sha256']:fail.append(item['path'])
    if not manifest.get('files'):fail.append('package_manifest.json')
    result=dict(passed=not fail,checked=len(manifest.get('files',[])),failed=fail,solver_started=False)
    print(json.dumps(result));return result


def launch(config,open_browser=True,port=None):
    app,env=prepare(config)
    # Ask the workspace's PID/birth-aware helper about its existing server.
    query="from common import *; import json; o=read(DATA/'server.json'); print(json.dumps(o if o.get('birth') and birth(o.get('pid'))==o['birth'] else {}))"
    probe=subprocess.run([str(BASE/'runtime/python.exe'),'-c',query],cwd=app,env=env,capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
    if probe.returncode:raise RuntimeError('Workspace could not load; run Verify package and see launcher-error.txt.')
    owner=json.loads(probe.stdout)
    if owner.get('url'):
        if open_browser:webbrowser.open(owner['url'])
        return dict(url=owner['url'],pid=owner['pid'],already_running=True)
    selected=None
    for candidate in [port] if port else range(8782,8820):
        try:
            with socket.socket() as sock:sock.bind(('127.0.0.1',candidate))
            selected=candidate;break
        except OSError:continue
    if selected is None:raise RuntimeError('No free local dashboard port.')
    env['NWAR_PORT']=str(selected);logpath=Path(env['NWAR_WORKSPACE'])/'dashboard.log'
    with logpath.open('a',encoding='utf8') as log:
        p=subprocess.Popen([str(BASE/'runtime/python.exe'),str(app/'server.py')],cwd=app,env=env,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
    url=f'http://127.0.0.1:{selected}'
    for _ in range(80):
        if p.poll() is not None:raise RuntimeError('Dashboard stopped during startup. See '+str(logpath))
        try:
            with urllib.request.urlopen(url+'/api/status',timeout=2) as response:response.read()
            break
        except Exception:time.sleep(.25)
    else:raise RuntimeError('Dashboard is still starting. See '+str(logpath))
    with logpath.open('a',encoding='utf8') as log:
        subprocess.Popen([str(BASE/'runtime/python.exe'),str(app/'report.py')],cwd=app,env=env,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
    if open_browser:webbrowser.open(url)
    return dict(url=url,pid=p.pid,release=config['release'],solver_started=False)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--configure',action='store_true');parser.add_argument('--verify',action='store_true');parser.add_argument('--headless',action='store_true');parser.add_argument('--prepare-only',action='store_true');parser.add_argument('--stop-dashboard',action='store_true');parser.add_argument('--port',type=int)
    args=parser.parse_args()
    if args.verify:
        result=verify_files();return 0 if result['passed'] else 1
    config=read(BASE/'launcher.json')
    if args.stop_dashboard:
        if not config:raise ValueError('There is no configured dashboard to close.')
        app,env=prepare(config)
        query="from common import *; import json; o=read(DATA/'server.json'); print(json.dumps(o if o.get('birth') and birth(o.get('pid'))==o['birth'] else {}))"
        probe=subprocess.run([str(BASE/'runtime/python.exe'),'-c',query],cwd=app,env=env,capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
        if probe.returncode:raise RuntimeError('Could not verify dashboard ownership.')
        owner=json.loads(probe.stdout)
        if not owner:return 0
        import re
        url=owner['url']
        if not re.fullmatch(r'http://127\.0\.0\.1:[0-9]+',url):raise ValueError('Invalid local dashboard address.')
        with urllib.request.urlopen(url+'/',timeout=10) as response:page=response.read().decode('utf8')
        token=re.search(r'name="nwar-token" content="([^"]+)"',page).group(1)
        request=urllib.request.Request(url+'/api/close-dashboard',data=b'{}',headers={'Content-Type':'application/json','X-NWAR-Token':token,'Origin':url})
        try:
            with urllib.request.urlopen(request,timeout=15) as response:print(response.read().decode('utf8'))
        except urllib.error.HTTPError as ex:
            raise ValueError(json.loads(ex.read()).get('error','Dashboard could not be closed.')) from None
        return 0
    try:valid=bool(config and inspect_installation(config['executable'])['release']==config['release'])
    except (OSError,ValueError,KeyError):valid=False
    need_key=config.get('license_mode')=='pod' and not os.environ.get('NWAR_POD_KEY')
    if args.configure or not valid or need_key:
        if args.headless:raise ValueError('Configure a local STAR installation first.')
        config=configure(config)
    if not config:return 0
    if args.prepare_only:
        app,_=prepare(config);print(json.dumps(dict(app=str(app),solver_started=False)));return 0
    print(json.dumps(launch(config,not args.headless,args.port)));return 0


if __name__=='__main__':
    try:sys.exit(main())
    except Exception as ex:
        message=str(ex)
        if os.environ.get('NWAR_POD_KEY'):message=message.replace(os.environ['NWAR_POD_KEY'],'[REDACTED]')
        (BASE/'launcher-error.txt').write_text(message,encoding='utf8')
        if '--headless' in sys.argv:print(message,file=sys.stderr)
        else:
            import tkinter as tk
            from tkinter import messagebox
            root=tk.Tk();root.withdraw();messagebox.showerror('NWAR',message);root.destroy()
        sys.exit(1)
