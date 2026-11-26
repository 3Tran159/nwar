from pathlib import Path
H=Path(__file__).resolve().parent;O=H/'gci_m09_20261030'
s=(H/'audit_gci_geometry.py').read_text()
s=s[:s.index('results={}')]
s=s.replace("HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE/'.deps'))","HERE=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(HERE/'.deps'))")
s=s.replace("OUT=HERE/'gci_audit_20261030';OUT.mkdir(exist_ok=True)","OUT=HERE/'gci_m09_20261030'/'family_audit';OUT.mkdir(exist_ok=True)")
s=s.replace("path=Q/mesh/'mesh.CGNS';before=sha(path)","path=(Q/mesh/'mesh.CGNS') if mesh=='M09' else HERE/'gci_m09_20261030'/mesh/'mesh.CGNS';before=sha(path)")
s=s.replace('range(100)','range(250)')
s+=r'''
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
pairs={};bands=[(0,1e-5),(1e-5,1e-4),(1e-4,1e-3),(.001,.005),(.005,.01)]
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
'''
(O/'audit_family.py').write_text(s,encoding='utf-8')
print('Prepared actual-mesh family audit')
