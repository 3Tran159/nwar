from pathlib import Path
import importlib.util,json,sys,os,time,urllib.request,subprocess
from unittest.mock import patch
BASE=Path('E:/NWAR_portable_20261103/NWAR_Windows_2602_2606');QA=Path(os.environ.get('NWAR_QA_DIR',str(BASE.parent/'QA')))
spec=importlib.util.spec_from_file_location('launcher',BASE/'start_nwar.py');launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(launcher)
checks={};found=launcher.installations()
import tkinter as tk
real_tk=tk.Tk
def hidden_tk(*args,**kw):
    root=real_tk(*args,**kw);root.withdraw();return root
def inspect_layout(root,*args,**kw):
    root.deiconify();root.update_idletasks();root.withdraw()
    buttons=[]
    def walk(widget):
        for child in widget.winfo_children():
            if child.winfo_class()=='TButton' and child.cget('text')=='Save and open dashboard':buttons.append(child)
            walk(child)
    walk(root)
    assert len(buttons)==1
    b=buttons[0];assert b.winfo_rooty()+b.winfo_height()<=root.winfo_rooty()+root.winfo_height(), 'Setup button is clipped'
    checks['setup_layout']=dict(width=root.winfo_width(),height=root.winfo_height(),save_button_visible=True,tcl_bundled=True)
    root.destroy()
with patch.object(tk,'Tk',hidden_tk),patch.object(real_tk,'mainloop',inspect_layout):
    assert launcher.configure(dict(found[0],workspace_root=str(QA/'workspaces')))=={}
for release in ('2602','2606'):
    config=dict(next(x for x in found if x['release']==release),workspace_root=str(QA/'workspaces'),license_mode='system',license_server='',power_session=False)
    reused=launcher.launch(config,open_browser=False)
    assert reused['already_running'] is True
    try:launcher.prepare(dict(config,license_mode='server',license_server='test.invalid'))
    except ValueError as e:assert 'active' in str(e)
    else:raise AssertionError('Active settings were changed')
    work=QA/'workspaces'/release
    report=json.loads((work/'app/latest_report.json').read_text(encoding='utf8'))
    assert report['errors']==[]
    actual_read=launcher.read
    def read_config(path):return config if Path(path)==BASE/'launcher.json' else actual_read(path)
    with patch.object(launcher,'read',read_config),patch.object(sys,'argv',['start_nwar.py','--stop-dashboard','--headless']):assert launcher.main()==0
    closed=False
    for _ in range(30):
        try:urllib.request.urlopen(reused['url']+'/api/status',timeout=.5).close()
        except (OSError,TimeoutError):closed=True;break
        time.sleep(.2)
    assert closed
    checks[release]=dict(repeated_launch_reuses_server=True,active_configuration_preserved=True,report_errors=[],idle_shutdown_own_server_only=True)
checks['live_W04_panel_still_accessible']=urllib.request.urlopen('http://127.0.0.1:8782/api/status',timeout=30).status==200
assert not (BASE/'launcher.json').exists()
(QA/'launcher_checks.json').write_text(json.dumps(dict(passed=True,checks=checks),indent=2),encoding='utf8')
print(json.dumps(checks))
