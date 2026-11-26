"""Read-only comparison of the expanded mesh with the accepted M13 geometry."""
from common import *
from prepare_w04_geometry import BASE,OUT,REVIEW
import numpy as np,h5py

def polygons(path):
 with h5py.File(path,'r') as f:
  z=f['Base/fluid'];xyz=np.column_stack([z['GridCoordinates/Coordinate'+a+'/ data'][...] for a in 'XYZ'])
  g=z['Q2D_span_source'];off=g['ElementStartOffset/ data'][...].astype(np.int64);off-=off[0]
  con=g['ElementConnectivity/ data'][...].astype(np.int64)-1;lens=np.diff(off)
  p=xyz[con][:,[0,2]];low=np.minimum.reduceat(p,off[:-1]);high=np.maximum.reduceat(p,off[:-1])
  center=np.add.reduceat(p,off[:-1])/lens[:,None]
 return p,off,center,high-low

def band(center,size,lo,hi):
 mask=(center[:,1]>lo)&(center[:,1]<hi)
 result={}
 for name,xlo,xhi in [('core',-10,30),('inlet',-69,-32),('outlet',33,89)]:
  a=size[mask&(center[:,0]>xlo)&(center[:,0]<xhi)]
  result[name]={'cells':len(a),'dx_median':float(np.median(a[:,0])),'dz_median':float(np.median(a[:,1])),
                'dz_p95':float(np.quantile(a[:,1],.95)),'dx_max':float(a[:,0].max()),'dz_max':float(a[:,1].max())}
 return result

def audit():
 dest=OUT/'protected_audit';dest.mkdir(exist_ok=True)
 sourcefile=WORKSPACE/'mesh_study_20261030/gci_w01a_20261030/audit_family.py'
 source=sourcefile.read_text(encoding='utf8').split("nominal={'W01a':48",1)[0]
 old="(HERE/'gci_w01a_20261030/handoff/mesh_star_export.CGNS') if mesh=='W01a' else HERE/'gci_w01a_20261030'/mesh/'mesh.CGNS'"
 assert source.count(old)==2
 source=source.replace(old,'PATHS[mesh]').replace("OUT=HERE/'gci_w01a_20261030'/'family_audit';OUT.mkdir(exist_ok=True)",'OUT=DEST;OUT.mkdir(exist_ok=True)')
 mesh=OUT/'geometry/mesh.CGNS';original=BASE/'geometry/mesh.CGNS'
 a=read(BASE/'protected_audit/M13_summary.json');assert sha(original)==a['CGNS_SHA256']
 space={'__file__':str(sourcefile),'PATHS':{'W04':mesh},'DEST':dest};exec(compile(source,'reviewed_mesh_auditor','exec'),space)
 b=space['audit']('W04',48);t=space['topology']('W04');b['topology']=t
 cols=read(dest/'W04_wall_columns.json');original_cols=read(BASE/'protected_audit/M13_wall_columns.json')
 coverage=lambda cols,summary:sum(r['length_m'] for r in cols if r['layers']>=48)/summary['foil_perimeter_m']
 ca,cb=coverage(original_cols,a),coverage(cols,b)
 first_ratio=b['midchord_height_stats']['0']['median_m']/a['midchord_height_stats']['0']['median_m']
 ratios=np.array([np.array(b['matched_wall_samples'][k]['heights_m'])/a['matched_wall_samples'][k]['heights_m'] for k in a['matched_wall_samples']])
 _,_,ac,asz=polygons(original);p,off,bc,bsz=polygons(mesh)
 oldband=band(ac,asz,1.7,2.3);newband=band(bc,bsz,1.15,2.85)
 gates=dict(one_cell_span=t['single_layer_topology'],paired_planes=t['max_xz_mismatch_m']<1e-10 and t['plane_error_m']<1e-10,
            expanded_bounds=b['bounds_m']=={'x':[-70.,90.],'y':[.01,.03],'z':[-22.,8.]},
            expanded_fluid_area=abs(b['total_fluid_section_area_m2']-a['total_fluid_section_area_m2']-2400)<.001,
            foil_geometry_preserved=abs(b['foil_perimeter_m']/a['foil_perimeter_m']-1)<1e-8,
            first_layer_preserved=abs(first_ratio-1)<.02,prism_coverage_preserved=cb>=ca-.001,
            protected_wall_grading=bool(np.all(np.abs(np.median(ratios,axis=0)-1)<.1)))
 for name in newband:
  old,new=oldband[name],newband[name]
  gates[name+'_expanded_wave_resolution']=new['dz_median']<=old['dz_median']*1.05 and new['dz_p95']<=old['dz_p95']*1.1
  if name!='core':gates[name+'_unchanged_max_dx']=new['dx_max']<=.200001
 result=dict(passed=all(gates.values()),gates=gates,original_mesh_sha256=sha(original),mesh_sha256=sha(mesh),cells=b['cells'],
             first_layer_ratio=first_ratio,original_prism_coverage=ca,new_prism_coverage=cb,
             wall_grading_ratios=np.median(ratios,axis=0).tolist(),original_band=oldband,expanded_band=newband,
             scope='Geometry, protected foil layers and wave-envelope resolution; original C01 remains the reference.')
 write(dest/'W04_summary.json',b);write(OUT/'protected_receipt.json',result);write(REVIEW/'protected_receipt.json',result)
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 from matplotlib.collections import PolyCollection
 fig,axs=plt.subplots(2,1,figsize=(13,7),gridspec_kw={'height_ratios':[1,2]})
 for ax,xlimits,zlimits in [(axs[0],(-70,90),(-22,8)),(axs[1],(-8,8),(.8,3.2))]:
  mask=(bc[:,0]>xlimits[0])&(bc[:,0]<xlimits[1])&(bc[:,1]>zlimits[0])&(bc[:,1]<zlimits[1])
  indices=np.flatnonzero(mask);stride=max(1,len(indices)//35000);indices=indices[::stride]
  ax.add_collection(PolyCollection([p[off[i]:off[i+1]] for i in indices],facecolors='none',edgecolors='#507881',linewidths=.15))
  ax.axhspan(1,3,color='#087f8c',alpha=.12);ax.axhline(2,color='#087f8c',ls='--');ax.set_xlim(xlimits);ax.set_ylim(zlimits);ax.set_xlabel('x [m]');ax.set_ylabel('z [m]')
 axs[0].set_title('Expanded domain: −70 to 90 m · unchanged cell-size controls')
 axs[1].set_title('W04 wave envelope inside the expanded 1–3 m refinement band')
 axs[1].axhline(1.25,color='#b15f24',ls=':');axs[1].axhline(2.75,color='#b15f24',ls=':')
 fig.suptitle('PRE W04 · mesh review');fig.tight_layout();fig.savefig(REVIEW/'W04_mesh_review.png',dpi=160);plt.close(fig)
 print(json.dumps(result),flush=True)
 assert result['passed'],'Protected mesh or expanded wave envelope requires review'
 return result

if __name__=='__main__':audit()
