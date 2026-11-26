"""Project acceptance and Q for the user-defined qualitative stage."""
from common import *
from cycle_policy import accepted_cycles, POLICY_ID
COEFFICIENT_DENOMINATOR=3855.6

def c01_force_reference(entry=None):
 """The one accepted calm reference, with the campaign's hydrodynamic lift convention."""
 if (entry or {}).get('spec',{}).get('reference_id'):
  from calm_reference import force_reference_for
  return force_reference_for(entry)
 accepted=read(CALM/'C01_final_acceptance_20261101.json')
 if not accepted.get('project_primary_settled') or accepted.get('checkpoint_sha256')!=SOURCE_SHA:
  raise ValueError('Accepted original C01 force reference is unavailable')
 cl=number(accepted.get('normalized_CL_hydro'));cd=number(accepted.get('normalized_CD_total'))
 if cl is None or cd is None or not math.isfinite(cl) or not math.isfinite(cd):raise ValueError('Invalid C01 coefficients')
 return dict(name='C01',reference_id='C01_original',CL=cl,CD=cd,L_N=cl*COEFFICIENT_DENOMINATOR,D_N=cd*COEFFICIENT_DENOMINATOR,
             coefficient_denominator_N=COEFFICIENT_DENOMINATOR,checkpoint_sha256=SOURCE_SHA,lift_convention='hydrodynamic_lift_v1')

def policy():return read(HERE/'project_policy.json')

def force_difference_rows(audit):
 """Combine accepted regular waves and the completed diagnostic for display."""
 drag=list(audit.get('Q_data',[]))
 lift=list(audit.get('lift_trend',[]))
 diagnostic=audit.get('w08bi_snapshot')
 if diagnostic and diagnostic.get('final'):
  wave=dict(case=diagnostic['case'],display_id=diagnostic['display_id'],diagnostic_only=True,
            averaging=f"GLHF diagnostic · {diagnostic['beat_period_count']} beat periods")
  drag.append(dict(wave,D_wave_N=diagnostic['D_wave_N'],Q_CD=diagnostic['delta_CD'],
                   delta_D_N=diagnostic['delta_D_N'],relative_change_pct=diagnostic['drag_change_pct']))
  lift.append(dict(wave,L_wave_N=diagnostic['L_wave_N'],delta_CL=diagnostic['delta_CL'],
                   delta_L_N=diagnostic['delta_L_N'],relative_change_pct=diagnostic['lift_change_pct']))
 return drag,lift

def acceptance(checks,smoke=0):
 required=[c for c in checks if c['group']=='run']
 outcome='failed' if any(c['status']=='failed' for c in required) else 'pending' if not required or any(c['status']!='passed' for c in required) else 'passed'
 return outcome, bool(outcome=='passed' and not smoke)

def q_result(result,validation,reference):
 if not validation.get('project_accepted') or not reference.get('project_primary_settled') or not accepted_cycles(result.get('cycles',{})):return None
 wave=number(result.get('cycles',{}).get('CD_mean'));calm=number(reference.get('normalized_CD_total'))
 if wave is None or calm is None or not result['cycles'].get('window'):return None
 q=wave-calm
 return dict(Q_CD=q,delta_D_N=q*COEFFICIENT_DENOMINATOR,CD_wave=wave,CD_C01=calm,
             D_wave_N=wave*COEFFICIENT_DENOMINATOR,D_C01_N=calm*COEFFICIENT_DENOMINATOR,
             relative_change_pct=100*q/calm if calm else None,sign='reduction' if q<0 else 'increase' if q>0 else 'unchanged',
             wave_window_s=result['cycles']['window'],cycle_count_used=4,cycle_numbers_used=[2,3,4,5],cycle_policy_id=POLICY_ID,
             C01_window_s=[reference['physical_time_s']-reference['reference_window_s'] if 'reference_window_s' in reference else reference['physical_time_s']-.2,reference['physical_time_s']],
             C01_checkpoint_sha256=reference['checkpoint_sha256'],scope=policy()['scope'],
             definition=policy()['Q_definition'],uncertainty_estimated=False)
