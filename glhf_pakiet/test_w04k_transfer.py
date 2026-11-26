"""CPU-only transfer tests; never start or attach to STAR."""
from pathlib import Path
import csv,importlib.util,json,math,os,sys,tempfile,unittest
from unittest.mock import patch

PATCH=Path('E:/NWAR_portable_20261103/NWAR_GLHF_W04k_Resume_20261109')
sys.path.insert(0,str(PATCH/'engine'))
from transfer_native import prepare_history,saved_header
from analysis import analyze
from cycle_policy import accepted_cycles
from common import read,period

spec=importlib.util.spec_from_file_location('transfer_test',Path(__file__).parent/'templates/w04k_transfer.py')
transfer=importlib.util.module_from_spec(spec);spec.loader.exec_module(transfer)
transfer.PATCH=PATCH

class TransferTests(unittest.TestCase):
 def test_glhf_wddm_desktop_contexts_are_allowed_but_compute_is_not(self):
  names=['steamwebhelper.exe','CrossDeviceResume.exe','iCUE.exe','msteams.exe','LEDKeeper2.exe',
         'SystemSettings.exe','StorageMonitor.exe','iCloudHome.exe','LogonUI.exe','AdskAccessUIHost.exe',
         'TabTip.exe','lghub_system_tray.exe','EpicWebHelper.exe','EpicGamesLauncher.exe',
         'WhatsApp.Root.exe','OverwolfBrowser.exe','Overwolf.exe','RtkUWP.exe','WidgetBoard.exe','remoting_desktop.exe']
  names+=['python.exe','star-ccm+.exe','unknown_compute.exe']
  xml='<nvidia_smi_log><gpu><processes>'+''.join(f'<process_info><pid>{i+1}</pid><type>C+G</type><process_name>{name}</process_name></process_info>'for i,name in enumerate(names))+'</processes></gpu></nvidia_smi_log>'
  records=transfer.parse_gpu_xml(xml,{})
  self.assertEqual([r['name']for r in records if r['blocks']],names[-3:])

 def test_xml_separates_graphics_from_compute_and_allows_desktop(self):
  xml='<nvidia_smi_log><gpu><processes><process_info><pid>1</pid><type>G</type><process_name>renderer.exe</process_name></process_info><process_info><pid>2</pid><type>C+G</type><process_name>msedgewebview2.exe</process_name></process_info><process_info><pid>3</pid><type>C</type><process_name>python.exe</process_name></process_info></processes></gpu></nvidia_smi_log>'
  records=transfer.parse_gpu_xml(xml,{})
  self.assertEqual([r['pid']for r in records if r['blocks']],[3])
  with self.assertRaisesRegex(ValueError,'no GPU'):transfer.parse_gpu_xml('<nvidia_smi_log/>',{})

 def test_transient_gpu_process_can_exit_during_settling(self):
  import transfer_runtime
  from types import SimpleNamespace
  busy='<nvidia_smi_log><gpu><processes><process_info><pid>3</pid><type>C</type><process_name>python.exe</process_name></process_info></processes></gpu></nvidia_smi_log>'
  clear='<nvidia_smi_log><gpu><processes/></gpu></nvidia_smi_log>'
  responses=[SimpleNamespace(returncode=0,stdout=x,stderr='')for x in(busy,clear,clear)]
  with tempfile.TemporaryDirectory()as tmp,patch.object(transfer,'PATCH',Path(tmp)),patch.object(transfer.shutil,'which',return_value='nvidia-smi'),patch.object(transfer.subprocess,'run',side_effect=responses),patch.object(transfer_runtime,'processes',return_value={}),patch.object(transfer.time,'sleep'):
   self.assertEqual(transfer.gpu_preflight()['blocking'],[])
   self.assertTrue((Path(tmp)/'state/gpu_preflight.json').is_file())

 def test_desktop_gpu_contexts_are_not_solver_conflicts(self):
  table={1:(0,'explorer.exe'),2:(0,'Photos.exe'),3:(0,'other_solver.exe')}
  self.assertEqual(transfer.gpu_conflicts('1\n2\n3\n',table),[3])
  self.assertEqual(transfer.gpu_conflicts('1\n2\n',table),[])
  self.assertEqual(transfer.gpu_conflicts('999\n',table),[999])

 def test_real_seed_header_and_pinned_payload(self):
  m=transfer.verify_payload()
  step,t,scenes=saved_header(PATCH/'seed/checkpoint.sim')
  self.assertEqual((step,scenes),(35160,30));self.assertAlmostEqual(t,14.064,7)
  self.assertEqual(m['initial_step'],14500)
  self.assertTrue(read(PATCH/'qa/compile.json')['passed'])
  self.assertTrue(all(Path(r['file']).is_file()for r in m['archived_field_history']))

 def test_manifest_cannot_escape_patch(self):
  with tempfile.TemporaryDirectory()as tmp:
   root=Path(tmp);(root/'manifest.json').write_text(json.dumps(dict(case_id='W04k',H_m=.25,lambda_m=15.,files={'../secret':dict(bytes=1,sha256='no')})))
   original=transfer.PATCH;transfer.PATCH=root
   try:
    with self.assertRaisesRegex(ValueError,'checksum'):transfer.verify_payload()
   finally:transfer.PATCH=original

 def test_complete_native_monitor_export_and_five_cycle_policy(self):
  with tempfile.TemporaryDirectory()as tmp:
   folder=Path(tmp);export=folder/'native_monitors';export.mkdir()
   origin=5.8;dt=.0004;begin=14500;end=35660;T=period(15);eligible=origin+2*T+69.5*T/15
   times={s:origin+(s-begin)*dt for s in range(begin+1,end+1)}
   channels=dict(Fx_N=lambda t:26+2*math.sin(math.tau*(t-eligible)/T),Fz_N=lambda t:1240+200*math.cos(math.tau*(t-eligible)/T),
    Fx_pressure_N=lambda t:25+2*math.sin(math.tau*(t-eligible)/T),Fx_viscous_N=lambda t:1,max_CFL=lambda t:2,interface_CFL=lambda t:1,
    max_speed_m_s=lambda t:19,alpha_min=lambda t:0,alpha_max=lambda t:1,p_min_Pa=lambda t:-100,p_max_Pa=lambda t:100000,water_volume_m3=lambda t:76.82,
    eta_0=lambda t:.125*math.sin(math.tau*(t-eligible)/T))
   for name,f in channels.items():
    with(export/(name+'.csv')).open('w',newline='')as out:
     w=csv.writer(out);w.writerow(['sample_x','value']);w.writerows((s,f(t))for s,t in times.items())
    (export/(name+'.axis')).write_text('Time Step')
   plan=dict(start_s=origin,dt_s=dt,probe_positions_m='[-0.5]',surface_limit_m=None)
   prepare_history(folder,export,times,begin,plan)
   (folder/'wave_setup_audit.json').write_text(json.dumps(dict(t0=origin,probe_distance_m=69.5)))
   review,data,gauge=analyze(dict(id='W04k',H=.25,L=15.),[folder])
   self.assertTrue(review['health']['ok']);self.assertTrue(accepted_cycles(review['cycles']))
   self.assertAlmostEqual(review['time_s'],14.264,7)
   self.assertEqual(review['cycles']['analyzed_cycle_numbers'],[2,3,4,5])
   # A missing native step must be rejected, never interpolated into the history.
   bad=times.copy();bad.pop(begin+5)
   with self.assertRaisesRegex(ValueError,'continuity'):prepare_history(folder,export,bad,begin,plan)

 def test_zero_step_macro_contains_all_field_channels(self):
  code=(PATCH/'engine/NwarNativeResume.java').read_text(encoding='utf8')
  for name in('Velocity','VorticityVector','Pressure','VolumeFractionwater','seed_monitors','steps_advanced'):
   self.assertIn(name,code)
  self.assertIn('getWaveHeight().getSIValue()-.25',code)
  self.assertNotIn('.step(',code)

if __name__=='__main__':unittest.main(verbosity=2)
