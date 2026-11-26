"""Propagate a measured wave signal to a shared position using wave-only evidence."""
from common import period,T0
from analysis import gauge_series
import numpy as np

REFERENCE_X=0.
FOIL_X=REFERENCE_X

def pair_delay(upstream,downstream,T,expected_delay,start):
 end=min(upstream[-1,0],downstream[-1,0]);begin=max(start,upstream[0,0],downstream[0,0],end-4*T)
 if end-begin<2*T:return None
 for data in (upstream,downstream):
  selected=data[(data[:,0]>=begin-.012)&(data[:,0]<=end+.012)]
  if len(selected)<30 or not np.isfinite(selected).all() or np.max(np.diff(selected[:,0]))>.012:return None
 tt=np.linspace(begin,end,min(4000,max(100,int((end-begin)/.004))))
 omega=2*np.pi/T;phase=omega*(tt-tt.mean());A=np.column_stack((np.sin(phase),np.cos(phase),np.ones(len(tt))))
 fits=[]
 for data in (upstream,downstream):
  yy=np.interp(tt,data[:,0],data[:,1]);coef=np.linalg.lstsq(A,yy,rcond=None)[0];residual=yy-A@coef
  r2=1-float(np.mean(residual**2))/max(float(np.var(yy)),1e-15)
  fits.append(dict(phase_rad=float(np.arctan2(coef[1],coef[0])),fundamental_R2=r2,amplitude_m=float(np.hypot(coef[0],coef[1]))))
 raw=(fits[0]['phase_rad']-fits[1]['phase_rad'])/omega
 delay=min((raw+k*T for k in range(-2,3)),key=lambda v:abs(v-expected_delay))
 if not (.5*expected_delay<delay<1.5*expected_delay and min(f['fundamental_R2'] for f in fits)>.90):return None
 return dict(measured_delay_s=float(delay),calibration_window_s=[float(begin),float(end)],fits=fits,period_s=T)

def align_to_position(folders,source_x,result,target_x=REFERENCE_X,*,require_full_history=False):
 """Never use force data to select the lag or shift a force history."""
 direct=gauge_series(folders,target_x)
 source=gauge_series(folders,source_x) if require_full_history else None
 partial_direct=bool(require_full_history and len(direct) and len(source) and
                     (direct[0,0]>source[0,0]+.012 or direct[-1,0]<source[-1,0]-.012))
 if len(direct) and not partial_direct:return direct,dict(method='direct_measurement',source_probe_x_m=target_x,target_x_m=target_x,time_shift_s=0.,phase_shift_deg=0.,estimated=False,force_shift_s=0.,force_data_used_for_alignment=False)
 if source is None:source=gauge_series(folders,source_x)
 if not len(source):return source,dict(method='missing_wave_history',estimated=True,source_probe_x_m=source_x,target_x_m=target_x,time_shift_s=None,force_shift_s=0.)
 T=result['cycles'].get('period_measured_s') or period(result['L'])
 predicted_speed=result['L']/T;start=result['cycles'].get('analysis_not_before_s',result.get('wave_origin_s',T0)+2*T)
 evidence=None
 # Closest upstream partner first. Both probes must precede the foil.
 for x in sorted([x for x in (-34.,-25.,-15.,-10.,-6.,-.5) if x<source_x],reverse=True):
  upstream=gauge_series(folders,x)
  if not len(upstream):continue
  trial=pair_delay(upstream,source,T,(source_x-x)/predicted_speed,start)
  if trial:
   speed=(source_x-x)/trial['measured_delay_s'];shift=(target_x-source_x)/speed
   evidence=dict(method='measured_wave_propagation',calibration_upstream_x_m=x,calibration_downstream_x_m=source_x,
                 propagation_speed_m_s=float(speed),**trial);break
 else:
  shift=(target_x-source_x)/predicted_speed
  evidence=dict(method='wavelength_period_estimate',propagation_speed_m_s=predicted_speed,
                note='No reliable overlapping upstream probe pair. Translation uses wavelength / measured period; it is an estimate.')
 aligned=source.copy();aligned[:,0]+=shift
 evidence.update(source_probe_x_m=source_x,target_x_m=target_x,time_shift_s=float(shift),phase_shift_deg=float(360*shift/T),
                 estimated=True,force_shift_s=0.,force_data_used_for_alignment=False,
                 reconstruction='Phase-preserving propagation extrapolation of the measured wave; no force fitting or amplitude rescaling.',
                 assumption='Measured propagation speed remains applicable between the source probe and target position; local wave distortion is not reconstructed.')
 if partial_direct:
  evidence.update(partial_direct_history=True,direct_history_range_s=[float(direct[0,0]),float(direct[-1,0])],
                  note='The x = 0 probe was added during a continuation. The full legacy probe history is translated consistently for this display; partial direct measurements are not spliced into it. Acceptance uses its original fixed probe.')
 return aligned,evidence

def align_to_foil(folders,source_x,result):
 return align_to_position(folders,source_x,result,target_x=FOIL_X)
