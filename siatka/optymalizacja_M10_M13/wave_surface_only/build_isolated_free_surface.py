"""Exact Cartesian no-foil mesh: dx0.2, dz0.025 near waterline, graded far field, one20mm span."""
import sys,json,shutil,collections,hashlib
from pathlib import Path
Q=Path('F:/ntnu/mesh_screening_20261028/quasi2d_012_20261029');sys.path.insert(0,str(Q/'deps311'))
import h5py,numpy as np
W=Path('E:/ntnu/quasi2d_waves_20261029');out=Path(sys.argv[1]);dz=float(sys.argv[2]);assert dz in (.05,.025,.0125);out.mkdir(exist_ok=False,parents=True)
template=W/'W20_H24_X4_Q2D_r4/mesh.CGNS';target=out/'mesh_exact.CGNS'
def graded(a,b,reverse=False):
 vals=[0.];step=.025
 while vals[-1]+step<b-a-1e-10:vals.append(vals[-1]+step);step=min(.8,step*1.15)
 vals.append(b-a);v=np.array(vals)
 return b-v[::-1] if reverse else a+v
x=np.linspace(-35,45,401);n=round(1.5/dz);assert abs(n*dz-1.5)<1e-10;z=np.unique(np.r_[graded(-22,1.25,True),np.linspace(1.25,2.75,n+1),graded(2.75,8)])
nx=len(x);nz=len(z);base=np.array([[xx,20.,zz] for zz in z for xx in x]);N=len(base);xyz=np.vstack([base,base]);xyz[N:,1]=20.02
polys=[];edges=collections.defaultdict(list)
for j in range(nz-1):
 for i in range(nx-1):
  a=j*nx+i;v=np.array([a,a+1,a+1+nx,a+nx]);ci=len(polys);polys.append(v)
  for a,b in zip(v,np.roll(v,-1)):edges[tuple(sorted((int(a),int(b))))].append((ci,int(a),int(b)))
names=['Polyfaces_fluid','DOMAIN.inlet','DOMAIN.outlet','DOMAIN.bottom','DOMAIN.top','DOMAIN.span_source','DOMAIN.span_target'];groups={n:[] for n in names};edgeidx={}
for key,owners in edges.items():
 ci,a,b=owners[0]
 if len(owners)==2:name='Polyfaces_fluid'
 else:
  p=xyz[[a,b]]
  if np.max(abs(p[:,0]+35))<1e-9:name='DOMAIN.inlet'
  elif np.max(abs(p[:,0]-45))<1e-9:name='DOMAIN.outlet'
  elif np.max(abs(p[:,2]+22))<1e-9:name='DOMAIN.bottom'
  elif np.max(abs(p[:,2]-8))<1e-9:name='DOMAIN.top'
  else:raise RuntimeError('Unknown boundary edge')
 edgeidx[key]=(name,len(groups[name]));groups[name].append(np.array([a,a+N,b+N,b])+1)
groups['DOMAIN.span_source']=[p+1 for p in polys];groups['DOMAIN.span_target']=[p[::-1]+N+1 for p in polys]
ranges={};start=1
for name in names:ranges[name]=(start,start+len(groups[name])-1);start+=len(groups[name])
cells=[]
for ci,v in enumerate(polys):
 fs=[ranges['DOMAIN.span_source'][0]+ci,ranges['DOMAIN.span_target'][0]+ci]
 for a,b in zip(v,np.roll(v,-1)):
  key=tuple(sorted((int(a),int(b))));name,i=edgeidx[key];fid=ranges[name][0]+i;fs.append(fid if edges[key][0][0]==ci else -fid)
 cells.append(np.array(fs,dtype=np.int64))
shutil.copy2(template,target)
with h5py.File(template,'r') as src,h5py.File(target,'r+') as f:
 zz=f['Base/fluid'];ss=src['Base/fluid']
 def data(g,v):
  if ' data' in g:del g[' data']
  g.create_dataset(' data',data=v)
 def nameattr(g,n):g.attrs.modify('name',np.bytes_(n))
 for n in list(zz):
  if isinstance(zz[n],h5py.Group) and (zz[n].attrs.get('label') in [b'Elements_t',b'FlowSolution_t',b'ZoneIterativeData_t',b'ZoneGridConnectivity_t'] or n in ['StarZoneInfo']):del zz[n]
 for n in list(f['Base']):
  if isinstance(f['Base'][n],h5py.Group) and f['Base'][n].attrs.get('label')==b'BaseIterativeData_t':del f['Base'][n]
 data(zz,np.array([[2*N],[len(cells)],[0]],dtype=np.int64))
 for i,a in enumerate('XYZ'):data(zz['GridCoordinates/Coordinate'+a],xyz[:,i])
 for n in list(zz['ZoneBC']):del zz['ZoneBC'][n]
 for name in names+['fluid']:
  src.copy(ss['fluid' if name=='fluid' else 'Polyfaces_fluid'],zz,name=name);g=zz[name];nameattr(g,name)
  pp=cells if name=='fluid' else groups[name];rg=(start,start+len(cells)-1) if name=='fluid' else ranges[name]
  data(g['ElementRange'],np.array(rg,dtype=np.int64));data(g['ElementStartOffset'],np.r_[0,np.cumsum([len(v) for v in pp])].astype(np.int64));data(g['ElementConnectivity'],np.concatenate(pp).astype(np.int64))
  if name not in ['Polyfaces_fluid','fluid']:
   bc0=next(v for v in ss['ZoneBC'].values() if isinstance(v,h5py.Group))
   src.copy(bc0,zz['ZoneBC'],name=name);bc=zz['ZoneBC'][name];nameattr(bc,name);data(bc['PointRange'],np.array(rg,dtype=np.int64).reshape(2,1))
v=np.outer(np.diff(z),np.diff(x))*.02
result={'cells':len(cells),'dx_m':.2,'dz_free_surface_m':dz,'free_surface_z':[1.25,2.75],'dz_far_max_m':float(max(np.diff(z))),'span_m':.02,'bounds':[[-35,20,-22],[45,20.02,8]],'total_volume_m3':float(v.sum()),'min_volume_m3':float(v.min()),'boundary_face_counts':{n:len(g) for n,g in groups.items()},'source':'Analytic rectangle with conforming Cartesian connectivity; no native trimming','sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
(out/'mesh_exact.validation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
