import study_controller as s
import math
# Unequal 2D refinements with an independent exact second-order error law.
cells=dict(zip(s.MESHES,[10000,19600,40000]));area={m:1.0 for m in s.MESHES}
values=[2.0+3.0/cells[m] for m in s.MESHES]
r=s.gci(values,area,cells)
assert abs(r['observed_p']-2)<1e-8
assert abs(r['extrapolated']-2)<1e-12
assert abs(r['GCI_fine_abs']-1.25*3/40000)<1e-12
assert abs(r['GCI_M09_abs']-1.25*3/10000)<1e-12
assert 'oscillatory' in s.gci([1.1,.9,1.0],area,cells)['status']
assert s.gci([1.,1.,1.],area,cells)['status']=='differences_unresolved'
print('PASS: unequal refinement, observed order, extrapolation, fine/coarse uncertainty and oscillation rejection')
