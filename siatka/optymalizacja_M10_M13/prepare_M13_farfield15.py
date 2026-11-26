"""Prepare a new isolated M13 geometry experiment; do not start any solver here."""
from pathlib import Path
from datetime import datetime
import json,os,hashlib,shutil,uuid,re
ROOT=Path(r'E:\ntnu_mesh_optimization_20261030')
S=Path(r'C:\Users\ThinkPad\Documents\ChatGPT\ntnu science\mesh_study_20261030\gci_w01a_20261030')
F=Path(r'F:\ntnu\mesh_screening_20261028\force_stabilization_20261029')
SOURCE=F.parent/'quasi2d_012_20261029/M10_FS020_r1_build/mesh_before_audit.sim'
DEST=ROOT/'M13_farfield15_20261031'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
def once(s,a,b):
 assert s.count(a)==1,'Template mismatch: '+a[:100]
 return s.replace(a,b,1)
assert SOURCE.is_file()
assert not DEST.exists(),'Candidate already exists; preserve it'
assert not any(x.name.startswith('M13') for x in ROOT.iterdir()),'M13 already registered'
reg=json.loads((F/'campaign_registry.json').read_text(encoding='utf-8-sig'))
assert all(c.get('id')!='M13' for c in reg['cases'])
assert shutil.disk_usage(str(ROOT)).free>25*2**30
DEST.mkdir();raw=DEST/'raw';raw.mkdir();final=DEST/'geometry';final.mkdir()
# Native controls retained from M10. Only outer BaseSize changes, all absolute
# protected controls are restored explicitly instead of leaving relative sizes.
text=(S/'MeshG10_M.java').read_text(encoding='utf-8')
text=text.replace('MeshG10_M','MeshM13Farfield15')
text=once(text,(S/'G10_M_raw').as_posix(),raw.as_posix())
for a,b in {
 'double base=0.17910447761194032;':'double base=0.2875;',
 '0.00025586353944562906/base':'0.0003571428571428572/base',
 'setValue(1.0722177362717153e-06)':'setValue(1.530612244897959e-06)',
 'setNumLayers(67)':'setNumLayers(48)',
 '0.0020469083155650325/base':'0.0028571428571428576/base',
 '0.00020469083155650323/base':'0.00028571428571428574/base',
 '0.0063965884861407266/base':'0.00892857142857143/base',
 '0.014328358208955226/base':'0.02/base',
 '0.10234541577825162/base':'0.14285714285714288/base',
 (S/'AuditRawG10_M.java').as_posix():(DEST/'AuditRawM13.java').as_posix(),
}.items():text=once(text,a,b)
text=once(text,'Files.createDirectories(out);s.getSolution().clearSolutionWithoutMeshReset();',
 'if(!Paths.get(s.getSessionPath()).toAbsolutePath().normalize().equals(out.resolve("input.sim").toAbsolutePath().normalize()))throw new IllegalStateException("Disposable M13 input mismatch");\nif(s.getNumberOfGpgpus()!=0)throw new IllegalStateException("Geometry preparation is CPU only");\nFiles.createDirectories(out);s.getSolution().clearSolutionWithoutMeshReset();')
(DEST/'MeshM13Farfield15.java').write_text(text,encoding='utf-8')
for orig,cls,out in [('AuditRawG10_M.java','AuditRawM13',raw),('AuditFinalG10_M.java','AuditFinalM13',final)]:
 text=(S/orig).read_text(encoding='utf-8').replace(orig[:-5],cls)
 text=once(text,(S/('G10_M_raw' if 'Raw' in orig else 'G10_M')).as_posix(),out.as_posix())
 text=once(text,'"case_id","G10_M"','"case_id","M13"')
 (DEST/(cls+'.java')).write_text(text,encoding='utf-8')
# A reviewed exact-span reconstruction preserves the regenerated native polygons.
text=(S/'extrude.py').read_text(encoding='utf-8')
text=text.replace('C:\\\\Users\\\\ThinkPad\\\\Documents\\\\ChatGPT\\\\ntnu science\\\\mesh_study_20261030\\\\.deps',
 'F:\\\\ntnu\\\\mesh_screening_20261028\\\\quasi2d_012_20261029\\\\deps311')
text=text.replace("'source_mesh':'M09'","'source_mesh':'M13 native far-field+15%'")
(DEST/'extrude_exact.py').write_text(text,encoding='utf-8')
text=(S/'FinalizeG10_M.java').read_text(encoding='utf-8').replace('FinalizeG10_M','FinalizeM13')
text=once(text,(S/'G10_M').as_posix()+'"',final.as_posix()+'"')
text=once(text,(S/'G10_M_raw/mesh_exact.CGNS').as_posix(),(raw/'mesh_exact.CGNS').as_posix())
text=once(text,'if(fv.getCellCount()!=595285)',
 'if(fv.getCellCount()!=Long.parseLong(Objects.requireNonNull(System.getenv("NTNU_M13_EXPECTED_CELLS"))))')
text=once(text,(S/'AuditFinalG10_M.java').as_posix(),(DEST/'AuditFinalM13.java').as_posix())
(DEST/'FinalizeM13.java').write_text(text,encoding='utf-8')
design={
 'id':'M13','created_at':datetime.now().astimezone().isoformat(),'status':'prepared_not_built',
 'reference':'M10 / W01a','purpose':'One-variable cost-reduction experiment, not a systematic GCI extension',
 'source':str(SOURCE),'source_sha256':sha(SOURCE),'directory':str(DEST),
 'change':{'outer_base_m_before':.25,'outer_base_m_after':.2875,'size_increase_pct':15},
 'preserved':{'foil_target_m':.0028571428571428576,'foil_min_m':.00028571428571428574,
 'global_min_m':.0003571428571428572,'near_foil_m':.00892857142857143,'free_surface_m':.02,
 'protected_middle_m':.14285714285714288,'layers':48,'first_layer_m':1.530612244897959e-6,
 'total_prism_m':.01546,'span_m':.02,'x_bounds_m':[-35,45],'z_bounds_m':[-22,8],'extension_dx_max_m':.2},
 'unknown_until_build':['actual_cells','prism_coverage','quality','actual_cost','settled_CL_CD'],
 'acceptance':{'primary_stability_pct':.5,'window_s':.2,'two_checks':True,
 'exploratory_cross_mesh_budget_pct':5,'cross_mesh_condition':'User accepts around 5% only if mesh/cost reduction is material; not a formal uncertainty',
 'timestep':'Keep comparison settings fixed against M10; any dt adaptation is separately checked'},
 'build_only':True,'flow_solver_started':False,'existing_M10_queue_untouched':True,
 'source_files':{p.name:sha(p) for p in [S/'MeshG10_M.java',S/'FinalizeG10_M.java',S/'extrude.py']}
}
(DEST/'candidate.json').write_text(json.dumps(design,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(ROOT/'next_mesh_candidate.json').write_text(json.dumps({'id':'M13','plan':str(DEST/'candidate.json'),'directory':str(DEST),'status':'prepared_not_built'},indent=2),encoding='utf-8')
with (ROOT/'decisions.jsonl').open('a',encoding='utf-8') as f:
 f.write(json.dumps({'at':design['created_at'],'event':'M13_geometry_preparation_authorized','candidate':str(DEST),'only_change':'outer base +15%','flow_started':False,'M10_untouched':True},ensure_ascii=False)+'\n')
print(json.dumps({'prepared':True,'candidate':str(DEST),'base_m':.2875,'native_source':str(SOURCE),'solver_started':False},ensure_ascii=False))
