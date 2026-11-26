"""Reconstruct a one-cell-span CGNS mesh from the unchanged native source-plane polygons."""
import sys,json,shutil,collections,hashlib
from pathlib import Path
sys.path.insert(0,'C:\\Users\\ThinkPad\\Documents\\ChatGPT\\ntnu science\\mesh_study_20261030\\.deps')
import numpy as np,h5py
source=Path(sys.argv[1]);target=Path(sys.argv[2])
if target.exists():raise RuntimeError('Preserve existing extrusion attempt')
with h5py.File(source,'r') as f:
 z=f['Base/fluid'];xyz0=np.column_stack([z['GridCoordinates/Coordinate'+a+'/ data'][...] for a in 'XYZ'])
 def polys(g):
  o=g['ElementStartOffset/ data'][...];c=g['ElementConnectivity/ data'][...]-1
  return [c[o[i]:o[i+1]].copy() for i in range(len(o)-1)]
 original=polys(z['Q2D_span_source']);used=np.unique(np.concatenate(original));N=len(used);C=len(original)
 if np.max(np.abs(xyz0[used,1]-.01))>1e-8:raise RuntimeError('Source plane is not y=0.01')
 remap=np.full(len(xyz0),-1,dtype=np.int64);remap[used]=np.arange(N)
 xyz=np.vstack([xyz0[used],xyz0[used]]);xyz[:N,1]=.01;xyz[N:,1]=.03
 surface=[];areas=[];edges=collections.defaultdict(list);self_crossing=[]
 def cross(a,b):return a[0]*b[1]-a[1]*b[0]
 for ci,v0 in enumerate(original):
  v=remap[v0];p=xyz[v][:,[0,2]]
  if len(set(map(int,v)))!=len(v):raise RuntimeError('Repeated source polygon vertex')
  # Translate before the area calculation to reduce cancellation in tiny prism cells.
  q=p-p[0];area=.5*np.sum(q[:,0]*np.roll(q[:,1],-1)-np.roll(q[:,0],-1)*q[:,1])
  if abs(area)<1e-18:raise RuntimeError('Zero source cell area')
  if area<0:v=v[::-1];p=p[::-1];area=-area
  for i in range(len(p)):
   a,b=p[i],p[(i+1)%len(p)]
   for j in range(i+2,len(p)):
    if i==0 and j==len(p)-1:continue
    c,d=p[j],p[(j+1)%len(p)]
    if cross(b-a,c-a)*cross(b-a,d-a)<0 and cross(d-c,a-c)*cross(d-c,b-c)<0:self_crossing.append(ci)
  surface.append(v);areas.append(area)
  for a,b in zip(v,np.roll(v,-1)):edges[tuple(sorted((int(a),int(b))))].append((ci,int(a),int(b)))
 if self_crossing:raise RuntimeError('Self-intersecting source polygons: '+str(self_crossing[:10]))
 boundary_map={}
 groups=[n for n,g in z.items() if isinstance(g,h5py.Group) and g.attrs.get('label')==b'Elements_t' and int(g[' data'][0])==22]
 for name in groups:
  if name in ['Polyfaces_fluid','Q2D_span_source','Q2D_span_target']:continue
  for v in polys(z[name]):
   for a,b in zip(v,np.roll(v,-1)):
    if remap[a]>=0 and remap[b]>=0:
     key=tuple(sorted((int(remap[a]),int(remap[b]))))
     if key in boundary_map and boundary_map[key]!=name:raise RuntimeError('Boundary labels disagree')
     boundary_map[key]=name
 face_groups={name:[] for name in groups};face_edges={}
 for edge,owners in edges.items():
  if len(owners)==2:
   name='Polyfaces_fluid'
   if owners[0][1:]!=owners[1][1:][::-1]:raise RuntimeError('Source polygons overlap or have inconsistent edge orientation')
  elif len(owners)==1:
   if edge not in boundary_map:raise RuntimeError('Missing source boundary identity for '+str(edge))
   name=boundary_map[edge]
  else:raise RuntimeError('Nonmanifold source edge')
  _,a,b=owners[0];face_edges[edge]=(name,len(face_groups[name]));face_groups[name].append(np.array([a,a+N,b+N,b])+1)
 face_groups['Q2D_span_source']=[v+1 for v in surface]
 face_groups['Q2D_span_target']=[v[::-1]+N+1 for v in surface]
 ranges={};start=1
 for name in groups:
  count=len(face_groups[name])
  if count==0:raise RuntimeError('Unexpected empty boundary group '+name)
  ranges[name]=(start,start+count-1);start+=count
 cellfaces=[]
 for ci,v in enumerate(surface):
  faces=[ranges['Q2D_span_source'][0]+ci,ranges['Q2D_span_target'][0]+ci]
  for a,b in zip(v,np.roll(v,-1)):
   edge=tuple(sorted((int(a),int(b))));name,index=face_edges[edge];fid=ranges[name][0]+index
   faces.append(fid if edges[edge][0][0]==ci else -fid)
  cellfaces.append(np.array(faces,dtype=np.int64))
 result={'cells':C,'source_vertices':N,'source_cells_unchanged':True,'source_xz_coordinates_unchanged':True,'span_m':.02,'minimum_source_area_m2':float(min(areas)),'minimum_reconstructed_volume_m3':float(min(areas)*.02),'total_volume_m3':float(sum(areas)*.02),'negative_or_zero_reconstructed_volumes':0,'self_intersecting_source_cells':0,'nonmanifold_source_edges':0,'same_side_internal_faces':0,'boundary_face_counts':{k:len(v) for k,v in face_groups.items()},'method':'Rebuild all spanwise faces and signed NFACE connectivity from unchanged valid source-plane polygons. Native target projection and its inconsistent pairings are discarded.'}
shutil.copy2(source,target)
with h5py.File(target,'r+') as f:
 z=f['Base/fluid']
 def data(group,values):
  if ' data' in group:del group[' data']
  group.create_dataset(' data',data=values)
 data(z,np.array([[2*N],[C],[0]],dtype=np.int64))
 for i,a in enumerate('XYZ'):data(z['GridCoordinates/Coordinate'+a],xyz[:,i])
 for name in groups+['fluid']:
  pp=face_groups[name] if name!='fluid' else cellfaces
  rg=ranges[name] if name!='fluid' else (start,start+C-1)
  data(z[name+'/ElementRange'],np.array(rg,dtype=np.int64))
  data(z[name+'/ElementStartOffset'],np.r_[0,np.cumsum([len(v) for v in pp])].astype(np.int64))
  data(z[name+'/ElementConnectivity'],np.concatenate(pp).astype(np.int64))
  if name in z['ZoneBC']:data(z['ZoneBC/'+name+'/PointRange'],np.array(rg,dtype=np.int64).reshape(2,1))
 for name in list(z):
  if isinstance(z[name],h5py.Group) and z[name].attrs.get('label') in [b'FlowSolution_t',b'ZoneIterativeData_t']:del z[name]
 for name in list(f['Base']):
  if isinstance(f['Base'][name],h5py.Group) and f['Base'][name].attrs.get('label')==b'BaseIterativeData_t':del f['Base'][name]
result['output_sha256']=hashlib.sha256(target.read_bytes()).hexdigest()
target.with_suffix('.validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True)
