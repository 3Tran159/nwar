from pathlib import Path
import sys,json,csv,hashlib,gc,datetime
HERE=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(HERE/'.deps'))
import numpy as np,h5py
from scipy.spatial import cKDTree
Q=Path(r'F:\ntnu\mesh_screening_20261028\quasi2d_012_20261029')
OUT=HERE/'gci_m09_20261030'/'family_audit';OUT.mkdir(exist_ok=True)
DEPTHS=[0,1e-5,1e-4,1e-3,5e-3,1e-2]
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def audit(mesh,nominal):
 path=(Q/mesh/'mesh.CGNS') if mesh=='M09' else HERE/'gci_m09_20261030'/mesh/'mesh.CGNS';before=sha(path)
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
   for kk in range(250):
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

def topology(mesh):
 path=(Q/mesh/'mesh.CGNS') if mesh=='M09' else HERE/'gci_m09_20261030'/mesh/'mesh.CGNS'
 with h5py.File(path,'r') as f:
  z=f['Base/fluid'];cg=z['fluid'];co=abs(cg['ElementConnectivity/ data'][...]);off=cg['ElementStartOffset/ data'][...];off-=off[0]
  counts=[]
  for b in ['Q2D_span_source','Q2D_span_target']:
   lo,hi=z[b]['ElementRange/ data'][...];counts.append(np.add.reduceat(((co>=lo)&(co<=hi)).astype(np.int8),off[:-1]))
  xyz=np.column_stack([z['GridCoordinates/Coordinate'+a+'/ data'][...] for a in 'XYZ'])
  src=xyz[abs(xyz[:,1]-.01)<1e-10][:,[0,2]];tgt=xyz[abs(xyz[:,1]-.03)<1e-10][:,[0,2]]
  dist,ix=cKDTree(src).query(tgt)
  return dict(single_layer_topology=bool(np.all((counts[0]==1)&(counts[1]==1))),cells=len(off)-1,plane_error_m=float(np.minimum(abs(xyz[:,1]-.01),abs(xyz[:,1]-.03)).max()),paired_nodes=len(set(ix)),source_nodes=len(src),target_nodes=len(tgt),max_xz_mismatch_m=float(dist.max()))
def band_h(r,lo,hi):
 edges=np.r_[0,r['distances_m']];h=np.array(r['heights_m'])
 overlap=np.maximum(0,np.minimum(edges[1:],hi)-np.maximum(edges[:-1],lo))
 return float(np.sum(h*overlap)/(hi-lo)) if np.sum(overlap)>=(hi-lo)*.999 else None
def interp(mesh,side,fn,xc):
 rr=sorted([r for r in columns[mesh] if r['side']==side and .05<r['x_c']<.95 and r['layers']>=nominal[mesh] and fn(r) is not None],key=lambda r:r['x_c'])
 return np.interp(xc,[r['x_c'] for r in rr],[fn(r) for r in rr])
nominal={'M09':48,'G09_M':67,'G09_F':94};results={};columns={}
for m,n in nominal.items():
 print('Audit '+m,flush=True);results[m]=audit(m,n);results[m]['topology']=topology(m)
 columns[m]=json.loads((OUT/(m+'_wall_columns.json')).read_text());gc.collect()
 (OUT/(m+'_summary.json')).write_text(json.dumps(results[m],indent=2))
pairs={};bands=[(0,1e-5),(1e-5,1e-4),(1e-4,1e-3),(.001,.005),(.005,.01),(.01,.014),(.014,.0154)]
def stats(a):return {'median':float(np.median(a)),'p10':float(np.quantile(a,.1)),'p90':float(np.quantile(a,.9)),'min':float(np.min(a)),'max':float(np.max(a))}
for a,b in [('M09','G09_M'),('G09_M','G09_F')]:
 nominalr=nominal[b]/nominal[a];bh=[]
 for lo,hi in bands:
  ratios=[]
  for side in ['upper','lower']:
   xc=np.linspace(.1,.9,17);ratios.extend(interp(a,side,lambda r:band_h(r,lo,hi),xc)/interp(b,side,lambda r:band_h(r,lo,hi),xc))
  bh.append(dict(band_m=[lo,hi],**stats(ratios)))
 tangent=[]
 for side in ['upper','lower']:
  xc=np.linspace(.1,.9,17);tangent.extend(interp(a,side,lambda r:r['length_m'],xc)/interp(b,side,lambda r:r['length_m'],xc))
 core=np.array(results[a]['core_samples']['sqrt_area_m'])/np.array(results[b]['core_samples']['sqrt_area_m'])
 pairs[a+'/'+b]=dict(nominal_r=nominalr,effective_r_2d=float(np.sqrt(results[b]['cells']/results[a]['cells'])),wall_bands=bh,tangential=stats(tangent),core=stats(core))
gates={}
for m,res in results.items():
 top=res['topology'];gates[m+'_topology']=top['single_layer_topology'] and top['plane_error_m']<1e-10 and top['max_xz_mismatch_m']<1e-10 and top['paired_nodes']==top['source_nodes']==top['target_nodes']
 gates[m+'_bounds']=res['bounds_m']==results['M09']['bounds_m']
 gates[m+'_domain_area']=abs(res['total_fluid_section_area_m2']/results['M09']['total_fluid_section_area_m2']-1)<1e-5
 gates[m+'_full_layers_midchord']=res['full_layers_midchord_columns']>100
 for label,lo,hi in [('any',1,999),('nominal',nominal[m],999)]:
  res['wall_length_fraction_'+label]=sum(r['length_m'] for r in columns[m] if lo<=r['layers']<=hi)/res['foil_perimeter_m']
for k,p in pairs.items():
 r=p['nominal_r']
 gates[k+'_all_prism_bands']=all(.9*r<x['median']<1.1*r and x['p10']>1.15 for x in p['wall_bands'])
 gates[k+'_core_refinement']=.8*r<p['core']['median']<1.2*r
 gates[k+'_tangential_refinement']=.8*r<p['tangential']['median']<1.2*r
 gates[k+'_effective_ratio']=p['effective_r_2d']>1.3
result=dict(status='geometric_family_passed_pending_flow_yplus_CFL_checks' if all(gates.values()) else 'needs_review',gates=gates,meshes=results,pairs=pairs,criteria_note='Project geometry screening tolerances; not universal ITTC limits. Collapsed corner columns and y+ require explicit local review before final mesh verification.',effective_dimension=2,originals_unchanged=True)
(OUT/'family_audit.json').write_text(json.dumps(result,indent=2))
print(json.dumps(dict(status=result['status'],gates=gates,pairs=pairs),indent=2),flush=True)
