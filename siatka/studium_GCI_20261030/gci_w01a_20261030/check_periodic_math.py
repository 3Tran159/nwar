import wave_analysis as a
import numpy as np
period=.8472673206891129
for dt in [.0001,.00005]:
 t=np.arange(2.,7.,dt);y=3+.7*np.cos(2*np.pi*t/period+.4)+.03*np.cos(4*np.pi*t/period-.2)
 data=[{'physical_time_s':float(x),'value':float(v)} for x,v in zip(t,y)]
 q=a.window(data,'value',3.1,3.1+3*period,period)
 assert abs(q['mean']-3)<1e-7,q
 assert abs(q['amplitude']-.7)<1e-7,q
 assert abs(a.phase_difference(q['phase_deg'],np.degrees(.4)))<1e-4,q
cells=dict(zip(a.MESHES,[10000,19600,40000]));area={m:1. for m in a.MESHES}
q=a.gci([2+3/cells[m] for m in a.MESHES],area,cells)
assert abs(q['observed_p']-2)<1e-8
assert abs(q['extrapolated']-2)<1e-12
assert abs(q['GCI_fine_abs']-1.25*3/40000)<1e-12
print('PASS: phase-matched mean/amplitude/phase at unequal timesteps and unequal-grid GCI')
