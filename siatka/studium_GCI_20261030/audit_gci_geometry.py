from pathlib import Path
import sys,json,csv,hashlib,gc,datetime
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE/'.deps'))
import numpy as np,h5py
from scipy.spatial import cKDTree
Q=Path(r'F:\ntnu\mesh_screening_20261028\quasi2d_012_20261029')
OUT=HERE/'gci_audit_20261030';OUT.mkdir(exist_ok=True)
DEPTHS=[0,1e-5,1e-4,1e-3,5e-3,1e-2]
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def audit(mesh,nominal):
 path=Q/mesh/'mesh.CGNS';before=sha(path)
 with h5py.File(path,'r') as f:
  z=f['Base/fluid'];xyz=np.column_stack([z['GridCoordinates/Coordinate'+a+'/ data'][...] for a in 'XYZ'])
  g=z['Q2D_span_source'];off=g['ElementStartOffset/ data'][...].astype(np.int64);con=g['ElementConnectivity/ data'][...].astype(np.int64)-1;off-=off[0];lens=np.diff(off);n=len(lens)
  nxt=np.arange(len(con))+1;nxt[off[1:]-1]=off[:-1];cn=con[nxt];base=len(xyz)
  keys=np.minimum(con,cn)*base+np.maximum(con,cn);owner=np.repeat(np.arange(n,dtype=np.int32),lens)
  order=np.argsort(keys);sortedkeys=keys[order];owners=owner[order]
  area=.5*np.add.reduceat(xyz[con,0]*xyz[cn,2]-xyz[con,2]*xyz[cn,0],off[:-1]);cent=np.column_stack([np.add.reduceat(xyz[con,a],off[:-1])/lens for a in [0,2]])
  wall=z['HF_012_wall'];wo=wall['ElementStartOffset/ data'][...];wc=wall['ElementConnectivity/ data'][...]-1;wo=wo-wo[0]
  records=[]
  for ii in range(len(wo)-1):
   ids=wc[wo[ii]:wo[ii+1]];ids=ids[np.abs(xyz[ids,1]-.01)<1e-8];assert len(ids)==2
   mid=xyz[ids][:,[0,2]].mean(axis=0);tangent=xyz[ids[1],[0,2]]-xyz[ids[0],[0,2]];length=np.linalg.norm(tangent);normal=np.array([-tangent[1],tangent[0]])/length
   edge=tuple(map(int,ids));visited=set();hs=[];cum=[];outnorm=None
   for kk in range(100):
    key=min(edge)*base+max(edge);aa=np.searchsorted(sortedkeys,key,'left');bb=np.searchsorted(sortedkeys,key,'right');cs=[int(c) for c in owners[aa:bb] if int(c) not in visited]
    if len(cs)!=1:break
    c=cs[0]
    if lens[c]!=4:break
    poly=con[off[c]:off[c+1]];opp=[int(v) for v in poly if v not in edge]
    if len(opp)!=2:break
    old=xyz[list(edge)][:,[0,2]].mean(axis=0);new=xyz[opp][:,[0,2]].mean(axis=0)
    dd=float(np.dot(new-old,normal))
    if outnorm is None:outnorm=normal*(1 if dd>=0 else -1)
    hs.append(abs(dd));cum.append(float(np.dot(new-mid,outnorm)));visited.add(c);edge=tuple(opp)
   sampled=[]
   for d in DEPTHS:
    j=int(np.searchsorted(cum,d,'right')) if cum else 0
    sampled.append(hs[j] if j<len(hs) else None)
   records.append({'x_c':float(mid[0]/1.19),'z_m':float(mid[1]),'length_m':float(length),'layers':len(hs),'side':'upper' if outnorm is not None and outnorm[1]>0 else 'lower','heights_m':hs,'distances_m':cum,'sampled_heights_m':sampled})
  footprint=sorted({round(float(x),10) for x in xyz[:,1]});assert footprint==[.01,.03]
  sign=np.sign(np.median(area));assert np.all(area*sign>0)
  raw={m:[float(xyz[:,a].min()),float(xyz[:,a].max())] for m,a in [('x',0),('y',1),('z',2)]}
  xx=np.linspace(4,25,15);zz=np.linspace(-8,8,11);pts=np.array([(x,zv) for x in xx for zv in zz if abs(zv-2)>.3]);tree=cKDTree(cent);dist,idx=tree.query(pts)
  core={'points_xz_m':pts.tolist(),'nearest_distance_m':dist.tolist(),'sqrt_area_m':np.sqrt(abs(area[idx])).tolist()}
  full=[r for r in records if r['layers']>=nominal and .05<r['x_c']<.95]
  quant={}
  for j,d in enumerate(DEPTHS):
   vals=np.array([r['sampled_heights_m'][j] for r in full if r['sampled_heights_m'][j] is not None]);quant[str(d)]={'median_m':float(np.median(vals)),'p10_m':float(np.quantile(vals,.1)),'p90_m':float(np.quantile(vals,.9)),'n':len(vals)}
  # Compare matching wall locations, rather than unrelated cell quantiles.
  samples={}
  for side in ['upper','lower']:
   rr=sorted([r for r in full if r['side']==side],key=lambda r:r['x_c'])
   for xc in np.linspace(.1,.9,17):
    samples[f'{side}_{xc:.3f}']={'x_c':float(xc),'heights_m':[float(np.interp(xc,[r['x_c'] for r in rr],[r['sampled_heights_m'][j] for r in rr])) for j in range(len(DEPTHS))]}
  summary={'mesh':mesh,'cells':n,'CGNS_SHA256':before,'bounds_m':raw,'total_fluid_section_area_m2':float(abs(area).sum()),'nonpositive_or_inverted_source_polygons':0,'wall_edges':len(records),'foil_perimeter_m':sum(r['length_m'] for r in records),'nominal_layers':nominal,'full_layers_midchord_columns':len(full),'layer_histogram':{str(k):sum(r['layers']==k for r in records) for k in sorted(set(r['layers'] for r in records))},'midchord_height_stats':quant,'matched_wall_samples':samples,'core_samples':core}
  (OUT/(mesh+'_wall_columns.json')).write_text(json.dumps(records),encoding='utf-8')
 assert sha(path)==before
 return summary
results={}
for m,n in [('M04',40),('M06',44),('M07',48)]:
 print('Auditing '+m,flush=True);results[m]=audit(m,n);gc.collect();print(json.dumps({'mesh':m,'depth_stats':results[m]['midchord_height_stats']}),flush=True)
pairs={}
for a,b in [('M04','M06'),('M06','M07')]:
 rat=[]
 for j,d in enumerate(DEPTHS):
  vals=np.array([results[a]['matched_wall_samples'][k]['heights_m'][j]/results[b]['matched_wall_samples'][k]['heights_m'][j] for k in results[a]['matched_wall_samples']]);rat.append({'wall_distance_m':d,'median_ratio':float(np.median(vals)),'p10_ratio':float(np.quantile(vals,.1)),'p90_ratio':float(np.quantile(vals,.9)),'min_ratio':float(vals.min()),'max_ratio':float(vals.max())})
 core=np.array(results[a]['core_samples']['sqrt_area_m'])/np.array(results[b]['core_samples']['sqrt_area_m'])
 pairs[a+'/'+b]={'wall_normal_ratios':rat,'core_sqrt_area_ratio_median':float(np.median(core)),'core_ratio_p10':float(np.quantile(core,.1)),'core_ratio_p90':float(np.quantile(core,.9))}
result={'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'method':'Read-only CGNS source-plane polygon connectivity. Trace opposite edges of consecutive quads along each wall column; project cell thickness on original local wall normal. Compare by interpolating at 17 fixed x/c locations per surface, 0.1 to 0.9, at six common physical wall distances. Core uses fixed point nearest-cell area diagnostics only.','depths_m':DEPTHS,'meshes':results,'pairs':pairs,'launch_decision':'pending_review','source_meshes_unchanged':True}
(OUT/'geometry_audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({'pairs':pairs,'areas':{m:results[m]['total_fluid_section_area_m2'] for m in results}},indent=2),flush=True)
