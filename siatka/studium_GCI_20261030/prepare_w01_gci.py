from pathlib import Path
import zipfile,json,hashlib
H=Path(__file__).resolve().parent;O=H/'gci_w01a_20261030';O.mkdir(exist_ok=True)
zpath=Path(r'E:\ntnu\handoffs\W01a_domain_settings_20261030_120423.zip')
dest=O/'handoff';dest.mkdir(exist_ok=True)
with zipfile.ZipFile(zpath) as z:
 for e in z.infolist():
  p=(dest/e.filename).resolve()
  if p.parent!=dest.resolve() or e.file_size>150_000_000:raise RuntimeError('Unexpected archive entry')
  if p.exists():raise RuntimeError('Preserve existing handoff copy')
  p.write_bytes(z.read(e))
manifest=json.loads((dest/'source_manifest.json').read_text(encoding='utf-8-sig'))
for entry in manifest:
 if entry.get('export_name'):
  p=dest/entry['export_name']
  assert hashlib.sha256(p.read_bytes()).hexdigest()==entry['sha256']
(O/'handoff_verified.json').write_text(json.dumps({'archive':str(zpath),'archive_sha256':hashlib.sha256(zpath.read_bytes()).hexdigest(),'all_packaged_manifest_hashes_match':True,'scope':'Current W01a, not historical calm M09'},indent=2))
t=(H/'build_m09_gci.py').read_text()
t=t.replace("OUT=HERE/'gci_m09_20261030'","OUT=HERE/'gci_w01a_20261030'")
t=t.replace("'G09_M'","'G10_M'").replace("'G09_F'","'G10_F'")
t=t.replace("free_surface_m=.028571428571428574/ref","free_surface_m=.02/ref")
t=t.replace("reference='M09'","reference='W01a_M10_FS020_80m'")
t=t.replace("Verify the light M09 mesh; finer levels are accuracy references for later cost reduction.","Verify the lightweight current W01a M10_FS020 mesh; finer grids are references for later cost reduction.")
t=t.replace("extrusion=(R/'extrude_source_mesh.py').read_text()","extrusion=(R/'extend_m09_wave_domain.py').read_text().replace('dxmax=.2','dxmax=float(sys.argv[5])')")
t=t.replace("source=Q/'M09_build/mesh.sim';h=sha(source)","source=(HERE/'gci_m09_20261030/G09_M_raw/mesh.sim') if name=='G10_M' else Q/'M10_FS020_r1_build/mesh.sim';h=sha(source)")
old="run_py(OUT/'extrude.py',[raw/'mesh.CGNS',raw/'mesh_exact.CGNS'],raw/'extrusion.log')"
assert old in t
t=t.replace(old,"run_py(OUT/'extrude.py',[raw/'mesh.CGNS',raw/'mesh_exact.CGNS'],raw/'extrusion.log')") # explicit replacement below
t=t.replace("[raw/'mesh.CGNS',raw/'mesh_exact.CGNS'],raw/'extrusion.log'","[raw/'mesh.CGNS',raw/'mesh_exact.CGNS',-35,45,.2/d['linear_refinement_vs_M09']],raw/'extrusion.log'")
t=t.replace("shutil.copy2(raw/'mesh.sim',out/'input_raw_copy.sim')","cells=read(raw/'mesh_exact.validation.json')['cells']\n  shutil.copy2(raw/'mesh.sim',out/'input_raw_copy.sim')")
t=t.replace("write(out/'basic_audit.json',result);results.append(result)","result['scope']='Geometry-only artifact; production physics and fields must come from the current W01a saved checkpoint via mesh replacement.'\n  write(out/'basic_audit.json',result);results.append(result)")
(H/'build_w01_gci.py').write_text(t,encoding='utf-8')
print('W01a handoff hashes verified; new 80 m family builder prepared.')
