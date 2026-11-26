"""Derived-only exact-boundary cycle analysis; no solver control or force phase fitting."""
import bisect,math,statistics

def interpolate(series,t,col,times=None,max_gap=.05):
 if not series:return None
 ts=times if times is not None else [r[0] for r in series]
 i=bisect.bisect_left(ts,t)
 if i<len(ts) and abs(ts[i]-t)<1e-10:return series[i][col]
 if i==0 or i==len(ts):return None
 a,b=series[i-1],series[i];gap=b[0]-a[0]
 if gap<=0 or gap>max_gap or a[col] is None or b[col] is None:return None
 return a[col]+(b[col]-a[col])*(t-a[0])/gap

def segment(series,a,b,cols,times=None,max_gap=.05):
 ts=times if times is not None else [r[0] for r in series]
 left=[interpolate(series,a,c,ts,max_gap) for c in cols];right=[interpolate(series,b,c,ts,max_gap) for c in cols]
 if None in left+right:return []
 inner=series[bisect.bisect_right(ts,a):bisect.bisect_left(ts,b)]
 result=[[a,*left],*[[r[0],*[r[c] for c in cols]] for r in inner],[b,*right]]
 if any(y[0]-x[0]>max_gap for x,y in zip(result,result[1:])):return []
 return result

def time_mean(rows,col):
 duration=rows[-1][0]-rows[0][0]
 return sum((b[0]-a[0])*(a[col]+b[col])/2 for a,b in zip(rows,rows[1:]))/duration

def square_phase_rms(a,b,col):
 if len(a)!=len(b) or any(abs(x[0]-y[0])>1e-9 for x,y in zip(a,b)):return None
 v=[[x[0],x[col]-y[col]] for x,y in zip(a,b)]
 return math.sqrt(sum((y[0]-x[0])*(x[1]**2+x[1]*y[1]+y[1]**2)/3 for x,y in zip(v,v[1:]))/(v[-1][0]-v[0][0]))

def crossings(series,period):
 if len(series)<10:return []
 center=statistics.median(v[1] for v in series);result=[]
 for a,b in zip(series,series[1:]):
  if a[1]<=center<b[1] and 0<b[0]-a[0]<.05:
   t=a[0]+(center-a[1])/(b[1]-a[1])*(b[0]-a[0])
   if not result or t-result[-1]>.5*period:result.append(t)
 return result

def analyze_cycles(force,gauges,config):
 T=float(config.get('wave_period_s') or .847027);origin=float(config.get('original_inlet_activation_s',3.899199999999636))
 chosen='-0.5';g=gauges.get(chosen,[])
 base={'status':'awaiting_full_cycles','count':0,'overlays':[],'gauge_x':-.5,'method':'Fixed x=-0.5m upward crossings; interpolate full history at endpoints; time-integrated means; no force-phase fitting.','acceptance':False,'phase_reference':'fixed upstream gauge; propagation and analysis-start assessment separate','twenty_cycle_rule':'diagnostic ceiling, not minimum required','analysis_start_status':'estimated_ramp_and_arrival_exclusion_not_certified','period_ramp_estimate_s':T,'period_STAR_s':None,'period_measured_s':None,'analysis_version':'20261101_exact_boundaries_v2'}
 if len(g)<20 or len(force)<50:return base
 ramp=float(config.get('ramp_s') or 1.694054);earliest=origin+ramp+34.5/23.612
 earliest=max(earliest,float(config.get('setting_change_exclusion_end_s') or earliest))
 base['analysis_not_before_s']=earliest
 g=[r for r in g if r[0]>=earliest]
 if len(g)<30 or g[-1][0]-g[0][0]<T:return base
 if max(v for _,v in g)-min(v for _,v in g)<.05:return dict(base,status='insufficient_wave_amplitude')
 cross=crossings(g,T);valid=[];ts=[r[0] for r in force]
 for a,b in zip(cross,cross[1:]):
  if not .65*T<=b-a<=1.35*T:continue
  sub=segment(force,a,b,[1,2],ts,max_gap=.005)
  if len(sub)<100:continue
  local=[v for t,v in g if a<=t<=b]
  if len(local)<5 or max(local)-min(local)<.05:continue
  points=[]
  for j in range(121):
   phase=j/120;t=a+phase*(b-a)
   cl,cd=interpolate(force,t,1,ts,.005),interpolate(force,t,2,ts,.005)
   if cl is None or cd is None:break
   points.append([phase,cl,cd])
  if len(points)!=121:continue
  c={'number':len(valid)+1,'start':a,'end':b,'T':b-a,'points':points,'CL_mean':time_mean(sub,1),'CD_mean':time_mean(sub,2),'CL_ptp':max(r[1] for r in sub)-min(r[1] for r in sub),'CD_ptp':max(r[2] for r in sub)-min(r[2] for r in sub),'integration':'trapezoidal on original time samples plus exact interpolated boundaries','phase_point_count':121}
  if valid:
   prev=valid[-1]
   for key,col in [('CL',1),('CD',2)]:
    c[key+'_cycle_RMS_abs']=square_phase_rms(prev['points'],points,col);c[key+'_mean_delta']=c[key+'_mean']-prev[key+'_mean']
  valid.append(c)
 base['count']=len(valid);base['overlays']=valid[-4:];base['review_due_20']=len(valid)>=20
 base['status']='four_cycles_available_diagnostic_only' if len(valid)>=4 else 'awaiting_four_full_cycles'
 base['period_measured_s']=statistics.fmean(c['T'] for c in valid[-4:]) if valid else None
 base['cycle_summaries']=[{k:v for k,v in c.items() if k!='points'} for c in valid]
 if len(valid)>=4:
  block=segment(force,valid[-4]['start'],valid[-1]['end'],[1,2],ts,.005)
  base['four_cycle_time_mean']={'start_s':block[0][0],'end_s':block[-1][0],'CL':time_mean(block,1),'CD':time_mean(block,2)}
 return base

def solve(matrix,rhs):
 m=[list(row)+[v] for row,v in zip(matrix,rhs)];n=len(m)
 for i in range(n):
  pivot=max(range(i,n),key=lambda j:abs(m[j][i]));m[i],m[pivot]=m[pivot],m[i]
  if abs(m[i][i])<1e-12:raise ValueError('Singular harmonic fit')
  p=m[i][i];m[i]=[v/p for v in m[i]]
  for j in range(n):
   if j==i:continue
   q=m[j][i];m[j]=[a-q*b for a,b in zip(m[j],m[i])]
 return [m[i][-1] for i in range(n)]

def harmonic_metrics(series,a,b,period,cycle_bounds):
 sample=segment(series,a,b,[1],max_gap=.05)
 if len(sample)<30:return None
 omega=2*math.pi/period;dim=11;A=[[0.]*dim for _ in range(dim)];B=[0.]*dim
 weights=[]
 for i,r in enumerate(sample):weights.append(((sample[i+1][0]-r[0]) if i==0 else (r[0]-sample[i-1][0]) if i==len(sample)-1 else sample[i+1][0]-sample[i-1][0])/2)
 features=[]
 for (t,y),weight in zip(sample,weights):
  f=[1.]
  for h in range(1,6):f.extend([math.cos(h*omega*t),math.sin(h*omega*t)])
  features.append(f)
  for i in range(dim):
   B[i]+=weight*f[i]*y
   for j in range(dim):A[i][j]+=weight*f[i]*f[j]
 coef=solve(A,B);amps=[math.hypot(coef[2*h-1],coef[2*h]) for h in range(1,6)]
 periods=[];heights=[];means=[]
 for lo,hi in cycle_bounds:
  v=segment(series,lo,hi,[1],max_gap=.05)
  if v:periods.append(hi-lo);heights.append(max(r[1] for r in v)-min(r[1] for r in v));means.append(time_mean(v,1))
 residual=sum(w*(row[1]-sum(c*f for c,f in zip(coef,feature)))**2 for w,row,feature in zip(weights,sample,features))/sum(weights)
 return {'H1_m':2*amps[0],'Hpp_m':statistics.fmean(heights) if heights else None,'Hpp_per_reference_cycle_m':heights,'Hpp_whole_block_m':max(r[1] for r in sample)-min(r[1] for r in sample),'mean_eta_m':time_mean(sample,1),'mean_eta_per_reference_cycle_m':means,'harmonic_amplitudes_1_to_5_m':amps,'fundamental_phase_rad':math.atan2(-coef[2],coef[1]),'fit_RMS_m':math.sqrt(residual),'period_fit_from_fixed_probe_s':period,'samples':len(sample),'window_s':[a,b],'H1_is_not_Hpp':True}
