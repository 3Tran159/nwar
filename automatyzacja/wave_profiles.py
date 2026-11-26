"""Case-specific access to the expanded mesh, conditional on PRE W04 evidence."""
from common import *
from pre_w04 import PRE,CALM_RUN,calm_folders
from prepare_w04_geometry import OUT

ALLOWED={'W04':(1.5,38.99857691441418),'W04c':(1.5,20.),'W04e':(1.5,15.),'W04f':(1.5,30.),'W04g':(1.5,25.),'W04h':(.75,15.),'W04k':(.25,15.),'W05':(1.,20.),'W06':(1.,30.),'W07':(1.,40.),'W08':(1.,30.)}
SHORT_DIAGNOSTIC='W04b'
RERUN_ALLOWED={'W01':(.5,20.),'W02':(.25,20.),'W03':(.5,30.)}
PROFILE='M13_W04_20261102'

def approved_profile(case_id,verify=False):
 from calm_reference import prepared_reference,local_reference_enabled,REFERENCE_FILE,REFERENCE_ID
 use_prepared=local_reference_enabled()
 from custom_waves import parameters
 custom=parameters(case_id) if case_id.startswith('CUSTOM') else None
 if custom and use_prepared:raise ValueError('Custom waves require the original C01 reference policy.')
 if case_id==SHORT_DIAGNOSTIC and use_prepared:raise ValueError('The short-wave diagnostic requires original C01.')
 if case_id not in ALLOWED and case_id!=SHORT_DIAGNOSTIC and not custom and not (use_prepared and case_id in RERUN_ALLOWED):return None
 calm=read(PRE/'calm_receipt.json');geometry=read(OUT/'geometry_receipt.json');protected=read(OUT/'protected_receipt.json')
 if use_prepared:
  calm=prepared_reference(verify) or {}
 build=read(HERE/'compile_receipt.json')
 if not (calm.get('passed') is True and geometry.get('passed') is True and protected.get('passed') is True
         and build.get('expanded_profile')==PROFILE and build.get('ok') is True):return None
 checkpoint=Path(calm['checkpoint']) if use_prepared and calm.get('checkpoint') else calm_folders()[-1]/'final.sim'
 if not checkpoint.is_file() or checkpoint.stat().st_size<400_000_000:return None
 if calm.get('original_C01_sha256')!=SOURCE_SHA or (not use_prepared and calm.get('no_new_Q_reference') is not True):return None
 if calm.get('mesh_sha256')!=geometry.get('mesh_sha256') or protected.get('mesh_sha256')!=geometry.get('mesh_sha256'):return None
 if calm.get('cells')!=572176 or geometry.get('cells')!=572176:return None
 if Path(calm.get('checkpoint','')).resolve()!=checkpoint.resolve():return None
 origin=number(calm.get('checkpoint_time_s'))
 if origin is None or origin<1.7999 or calm.get('initialization') not in ('fresh_from_rest','whole_domain_momentum_ramp'):return None
 if calm.get('initialization')=='whole_domain_momentum_ramp':
  if calm.get('gates',{}).get('startup_momentum_source_removed') is not True:return None
 if verify:
  if sha(SOURCE)!=SOURCE_SHA or sha(checkpoint)!=calm.get('checkpoint_sha256'):raise ValueError('PRE W04 or original C01 checkpoint identity changed.')
  if sha(OUT/'geometry/mesh.CGNS')!=geometry['mesh_sha256']:raise ValueError('Expanded mesh identity changed.')
  if sha(HERE/'NwarWave.java')!=build.get('macro_sha256'):raise ValueError('Wave macro differs from its approved build.')
 result=dict(id=PROFILE,cells=572176,source=str(checkpoint),source_sha=calm['checkpoint_sha256'],source_time=origin,
             wave_origin_s=origin,probe_distance_m=69.5,inlet_x_m=-70.,outlet_x_m=90.,forcing_length_m=40.,damping_length_m=40.,
             water_min_m3=76.,water_max_m3=78.,mesh_sha256=geometry['mesh_sha256'],
             original_C01_sha256=SOURCE_SHA,initialization=calm['initialization'],calm_receipt=str(REFERENCE_FILE if use_prepared else PRE/'calm_receipt.json'))
 if use_prepared:result['reference_id']=REFERENCE_ID
 return result

def verify_spec(case_id,spec):
 profile=approved_profile(case_id,verify=True)
 if not profile or spec.get('mesh_profile')!=profile:raise ValueError('Expanded mesh requires the verified PRE W04 calm gate.')
 from custom_waves import parameters
 if case_id==SHORT_DIAGNOSTIC:
  allowed=any(c.get('queue_label')==case_id and c.get('launch_authorized') is True
              for c in read(HERE/'short_wave_scan.json').get('cases',[]))
  if not allowed or spec.get('short_wave_diagnostic') is not True:
   raise ValueError('W04b requires the explicitly authorized diagnostic scope.')
  H,L=1.5,10.
 else:H,L=parameters(case_id) if case_id.startswith('CUSTOM') else (ALLOWED|RERUN_ALLOWED)[case_id]
 if spec['H']!=H or abs(spec['L']-L)>1e-8 or spec['dt']!=.0004:raise ValueError('Wave does not match its reviewed expanded-mesh profile.')
 if spec['mode']=='fresh' and (spec['source']!=profile['source'] or spec['source_sha']!=profile['source_sha'] or spec['source_time']!=profile['source_time']):raise ValueError('Fresh wave must start from the verified PRE W04 checkpoint.')
 return profile
