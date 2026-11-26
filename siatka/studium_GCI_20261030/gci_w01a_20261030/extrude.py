"""Reconstruct a one-cell-span CGNS mesh from the unchanged native source-plane polygons."""
import sys,json,shutil,collections,hashlib
from pathlib import Path
sys.path.insert(0,'C:\\Users\\ThinkPad\\Documents\\ChatGPT\\ntnu science\\mesh_study_20261030\\.deps')
import numpy as np,h5py
source=Path(sys.argv[1]);target=Path(sys.argv[2]);xmin=float(sys.argv[3]);xmax=float(sys.argv[4]);dxmax=float(sys.argv[5])
source_sha=hashlib.sha256(source.read_bytes()).hexdigest()
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
 # Append orthogonal remote strips. Every original polygon and coordinate remains unchanged.
 original_cells=C;original_nodes=N;original_volume=sum(areas)*.02
 old_xmin=float(xyz[:N,0].min());old_xmax=float(xyz[:N,0].max())
 zmin=float(xyz[:N,2].min());zmax=float(xyz[:N,2].max())
 if not (xmin<old_xmin and xmax>old_xmax and abs(zmin+22)<1e-8 and abs(zmax-8)<1e-8):raise RuntimeError('Unexpected extension bounds')
 points=xyz[:N].tolist();extensions=[]
 def bname(suffix):
  found=[k for k in groups if k.endswith('.'+suffix)]
  if len(found)!=1:raise RuntimeError('Ambiguous boundary '+suffix)
  return found[0]
 for side,old,new in [('inlet',old_xmin,xmin),('outlet',old_xmax,xmax)]:
  name=bname(side);wall_edges=[edge for edge,label in boundary_map.items() if label==name]
  ids=sorted({v for edge in wall_edges for v in edge},key=lambda v:points[v][2])
  if len(ids)!=len(wall_edges)+1 or {tuple(sorted(x)) for x in zip(ids[:-1],ids[1:])}!=set(wall_edges):raise RuntimeError('Remote boundary is not a simple vertical chain')
  if max(abs(points[v][0]-old) for v in ids)>1e-8:raise RuntimeError('Remote plane mismatch')
  cols=int(np.ceil(abs(new-old)/dxmax));prev=ids
  for xx in np.linspace(old,new,cols+1)[1:]:
   current=[]
   for v in ids:
    current.append(len(points));points.append([float(xx),.01,float(points[v][2])])
   for lo in range(len(ids)-1):
    a,b=prev[lo:lo+2];c,d=current[lo:lo+2]
    poly=np.array([c,a,b,d] if new<old else [a,c,d,b],dtype=np.int64)
    area=abs(float(xx)-points[a][0])*(points[b][2]-points[a][2])
    if area<=0:raise RuntimeError('Nonpositive extension cell')
    ci=len(surface);surface.append(poly);areas.append(area)
    for aa,bb in zip(poly,np.roll(poly,-1)):edges[tuple(sorted((int(aa),int(bb))))].append((ci,int(aa),int(bb)))
   boundary_map[tuple(sorted((prev[0],current[0])))]=bname('bottom')
   boundary_map[tuple(sorted((prev[-1],current[-1])))]=bname('top')
   prev=current
  for aa,bb in zip(prev[:-1],prev[1:]):boundary_map[tuple(sorted((aa,bb)))]=name
  extensions.append({'side':side,'old_x_m':old,'new_x_m':new,'columns':cols,'max_dx_m':abs(new-old)/cols,'boundary_vertical_segments':len(ids)-1})
 N=len(points);C=len(surface);xyz=np.vstack([np.array(points),np.array(points)]);xyz[:N,1]=.01;xyz[N:,1]=.03
 expected_volume=original_volume+((xmax-xmin)-(old_xmax-old_xmin))*(zmax-zmin)*.02
 if abs(sum(areas)*.02-expected_volume)>1e-8:raise RuntimeError('Extension volume mismatch')
 if not np.array_equal(xyz[:original_nodes][:,[0,2]],xyz0[used][:,[0,2]]):raise RuntimeError('Protected coordinates changed')
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
result.update({'purpose':'M09-derived 4-lambda wave-domain mesh preparation; not a new accepted flow result','source_mesh':'M09','source_sha256':source_sha,'original_cells':original_cells,'added_cells':C-original_cells,'original_cell_polygons_preserved':True,'original_coordinates_preserved':True,'extensions':extensions,'expected_volume_m3':expected_volume,'x_bounds_m':[xmin,xmax],'z_bounds_m':[zmin,zmax],'wave_depth_m':24,'pending':['Independent STAR mesh import/quality/boundary checks','Matched calm run on this domain','Wave propagation/time/domain validation'],'method':'Preserve all M09 source polygons; append conforming orthogonal strips at the original inlet and outlet, then rebuild exact one-cell-span connectivity'})
if hashlib.sha256(source.read_bytes()).hexdigest()!=source_sha:raise RuntimeError('Source mesh changed')
result['output_sha256']=hashlib.sha256(target.read_bytes()).hexdigest()
target.with_suffix('.validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True)
