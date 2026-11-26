from pathlib import Path
H=Path(__file__).resolve().parent;old=H/'gci_m09_20261030';O=H/'gci_w01a_20261030'
s=(old/'audit_family.py').read_text()
s=s.replace("gci_m09_20261030","gci_w01a_20261030").replace("'G09_M'","'G10_M'").replace("'G09_F'","'G10_F'")
s=s.replace("'M09'","'W01a'")
s=s.replace("(Q/mesh/'mesh.CGNS') if mesh=='W01a'", "(HERE/'gci_w01a_20261030/handoff/mesh_star_export.CGNS') if mesh=='W01a'")
anchor="core={'points_xz_m':pts.tolist(),'nearest_distance_m':dist.tolist(),'sqrt_area_m':np.sqrt(abs(area[idx])).tolist()}"
assert s.count(anchor)==1
extra=r'''
  zone_points={
   'near_foil':[(x,zv) for x in [-.5,.25,.75,1.5,2.5] for zv in [-.4,-.2,.25,.5]],
   'free_surface_core':[(x,zv) for x in [-10,-5,3,8,15,20] for zv in [1.97,2.,2.03]],
   'upstream_strip':[(x,zv) for x in [-32,-27,-20] for zv in [-18,-8,-1,1.97,2.,2.03,6]],
   'downstream_strip':[(x,zv) for x in [33,38,43] for zv in [-18,-8,-1,1.97,2.,2.03,6]],
   'far_vertical':[(x,zv) for x in [-5,5,15,25] for zv in [-20,-16,-10,6]]}
  zone={}
  for key,pp in zone_points.items():
   dd,ix=tree.query(pp);zone[key]={'points_xz_m':pp,'nearest_distance_m':dd.tolist(),'sqrt_area_m':np.sqrt(abs(area[ix])).tolist()}
'''
s=s.replace(anchor,anchor+extra)
s=s.replace("'core_samples':core}","'core_samples':core,'zone_samples':zone}")
anchor="gates[k+'_effective_ratio']=p['effective_r_2d']>1.3"
extra=r'''
 a,b=k.split('/')
 p['zones']={}
 for zone in results[a]['zone_samples']:
  values=np.array(results[a]['zone_samples'][zone]['sqrt_area_m'])/np.array(results[b]['zone_samples'][zone]['sqrt_area_m'])
  p['zones'][zone]=stats(values)
  gates[k+'_'+zone+'_refinement']=.75*r<p['zones'][zone]['median']<1.25*r
'''
assert s.count(anchor)==1
s=s.replace(anchor,anchor+extra)
(O/'audit_family.py').write_text(s,encoding='utf-8')
m=(old/'MapM09Solution.java').read_text().replace('MapM09Solution','MapW01Solution').replace('!=214908','!=317277').replace('start-2.04','start-.02').replace('saved M09 checkpoint','saved W01a checkpoint')
(O/'MapW01Solution.java').write_text(m,encoding='utf-8')
print('Prepared W01a actual geometry, remote strips and free-surface audit, plus warm-start mapping.')
