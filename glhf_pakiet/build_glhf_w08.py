"""Build a continuation patch for the existing clean GLHF 2606 installation."""
import csv
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

from build_package import DEST, LIVE, TEMPLATES, replace

ROOT = DEST.parent
ENGINE = ROOT/'NWAR_GLHF_Transfer_v4/engine'
OUTPUT = ROOT/'NWAR_GLHF_W08bi_Resume_2606_v3'
RUN = Path('E:/ntnu_mesh_optimization_20261030/nwar_automation_20261102/runs/W08_20261105_101441_28cb7c')
BACKUP = Path('H:/NTNU_RESEARCH_ARCHIVE/NWAR_SIM_FINALS/checkpoints/W08bi_28cb7c_checkpoint_t10.6000.sim')
TIME = 10.600000000004671
SHA = '3b28035594c92910122ac30c30e8bea9fd6649ddb42cf5ae0df0824ad1c18010'
PRE = 'd86beded68b41f5e6ce324a93cea39177dbe93fff516af10d33a71761528b85a'
VERSION = '21.04.009'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path, content):
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2)+'\n', encoding='utf8')


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def make_seed(dest):
    dest.mkdir()
    if sha(BACKUP) != SHA or read(RUN/'source_identity.json')['sha256'] != PRE:
        raise ValueError('Unexpected source or checkpoint fingerprint.')
    shutil.copy2(BACKUP, dest/'checkpoint.sim')
    summary = {}
    for name in ('history.csv', 'gauges.csv'):
        last = None
        count = 0
        with (RUN/name).open(encoding='utf-8-sig', newline='') as stream, (dest/name).open('w', encoding='utf8', newline='') as out:
            rows = csv.DictReader(stream)
            writer = csv.DictWriter(out, rows.fieldnames)
            writer.writeheader()
            for row in rows:
                t = float(row['time_s'])
                if t > TIME + 1e-8:
                    break
                if last is not None and (t < last or name == 'history.csv' and abs(t-last-.0004)>1e-7):
                    raise ValueError('The archived series has a time gap.')
                writer.writerow(row)
                last = t
                count += 1
            if last is None or abs(last-TIME)>1e-8 or name == 'history.csv' and count != 12001:
                raise ValueError('The archived series does not end at the verified save.')
            summary[name] = count
    names = ['wave_setup_audit.json', 'bichromatic_setup.json', 'native_C01_rho_readback.json', 'source_identity.json']
    for name in names:
        shutil.copy2(RUN/name, dest/name)
    provenance = dest/'original_stop'
    provenance.mkdir()
    for name in ('macro_error.json', 'stage_result.json'):
        if (RUN/name).exists():
            shutil.copy2(RUN/name, provenance/name)
    write(dest/'seed.json', dict(job_id='28cb7c64d2f04420', sha256=SHA, time_s=TIME, step=12000,
          source_release='2602', target_release='2606', pre_sha256=PRE, rows=summary,
          history_sha256={name: sha(dest/name) for name in ['history.csv', 'gauges.csv', *names]}))


def make_macro(dest):
    code = (LIVE/'NwarBichromatic.java').read_text(encoding='utf8')
    if 'caseId.equals("W08"))?1.5:1.0;' not in code:
        raise ValueError('The W08bi gauge guard must be ±1.5 m.')
    start = code.index('  Files.exists(Paths.get("E:/')
    end = code.index('\n   throw new IllegalStateException("STOP requested");}', start)
    code = code[:start]+'''  Files.exists(Paths.get(Objects.requireNonNull(System.getenv("NWAR_GLOBAL_STOP")))))
'''.rstrip()+code[end:]
    start = code.index('   String isolate=')
    end = code.index('    throw new IllegalStateException("Disposable M13', start)
    code = code[:start]+'''   Path isolate=Paths.get(Objects.requireNonNull(System.getenv("NWAR_RUN_ROOT"))).toAbsolutePath().normalize();
   if(!out.startsWith(isolate)||out.equals(isolate)||!Paths.get(s.getSessionPath()).toAbsolutePath().normalize().equals(out.resolve("input.sim")))
'''+code[end:]
    macro = dest/'NwarBichromatic.java'
    macro.write_text(code, encoding='utf8')
    proof = read(LIVE/'bichromatic_w08.json')
    if [(c['baseline'], c['H_m'], c['lambda_m'], c['phase_deg']) for c in proof['components']] != [
            ('W01', .5, 20., 0), ('W06', 1., 30., 0)]:
        raise ValueError('Unexpected W08bi components.')
    jdk = Path('C:/Program Files/Eclipse Adoptium/jdk-25.0.3.9-hotspot/bin/javac.exe')
    classpath = f'E:/Program Files/Siemens/{VERSION}-R8/STAR-CCM+{VERSION}-R8/star/lib/java/platform/modules/ext/*'
    with tempfile.TemporaryDirectory(dir=dest.parent) as temp:
        subprocess.run([str(jdk), '-encoding', 'UTF-8', '-classpath', classpath,
                        '-d', temp, str(macro)], check=True, timeout=120)
    proof.update(versions=[dict(build=VERSION, passed=True)], compiled=True, native_tested=False, macro_sha256=sha(macro))
    write(dest/'bichromatic_w08.json', proof)


def make_app(dest):
    dest.mkdir()
    code = (ENGINE/'common.py').read_text(encoding='utf8')
    code = replace(code, 'mpi_processes=None,glhf_recovery=None):', 'mpi_processes=None,glhf_recovery=None,w08_seed=False):')
    code = replace(code, " if glhf_recovery:\n", """ if case_id=='W08' and (mode!='resume' or smoke or glhf_recovery or (not w08_seed and not parent_id)):
  raise ValueError('W08bi requires the verified transfer or a saved W08bi pause.')
 if w08_seed:
  from w08_portable import REQUEST,seed_spec
  if case_id!='W08' or parent_id or request_key!=REQUEST:raise ValueError('Invalid W08bi transfer request.')
  spec.update(seed_spec())
 elif glhf_recovery:
""")
    code = replace(code, ' id=uuid.uuid4().hex[:16];folder=RUNS/', """ if case_id=='W08':
  from w08_portable import resume_policy
  resume_policy(spec)
 id=uuid.uuid4().hex[:16];folder=RUNS/""")
    (dest/'common.py').write_text(code, encoding='utf8')

    code = (ENGINE/'worker.py').read_text(encoding='utf8')
    start = code.index(" if spec.get('wave_kind')=='bichromatic':")
    end = code.index(' if type(spec.get', start)
    code = code[:start]+""" if spec.get('wave_kind')=='bichromatic':
  from w08_portable import verify_job
  verify_job(j)
"""+code[end:]
    current = (LIVE/'worker.py').read_text(encoding='utf8')
    start = code.index("  if done['status']=='paused_saved':")
    end = code.index(' except Exception as e:', start)
    code = code[:start]+current[current.index('  diagnostic='):current.index(' except ActiveSolverError as exc:',current.index('  diagnostic='))]+code[end:]
    code = replace(code, "  if not diagnostic and verification['run_verification']=='failed' and state=='completed':",
                   "  if verification['run_verification']=='failed' and state=='completed':")
    (dest/'worker.py').write_text(code, encoding='utf8')

    code = (ENGINE/'bichromatic.py').read_text(encoding='utf8')
    current = (LIVE/'bichromatic.py').read_text(encoding='utf8')
    start = current.index('def case():')
    end = current.index('\ndef duration', start)
    code = code[:code.index('def case():')]+current[start:end]+code[code.index('\ndef duration'):]
    (dest/'bichromatic.py').write_text(code, encoding='utf8')

    code = (ENGINE/'server.py').read_text(encoding='utf8')
    code = replace(code, "dict(**c,display_id=cr.get('display_id',c['id']),result=",
                   "dict({**c,'display_id':c.get('display_id') or cr.get('display_id',c['id'])},result=")
    (dest/'server.py').write_text(code, encoding='utf8')
    code = (LIVE/'wave_view.py').read_text(encoding='utf8')
    (dest/'wave_view.py').write_text(replace(code, "result, require_full_history=True)", "result)"), encoding='utf8')
    shutil.copy2(LIVE/'wave_view.js', dest)

    code = (ENGINE/'validation.py').read_text(encoding='utf8')
    code = replace(code, "  done=read(folder/'completed.json');", "  diagnostic=case.get('wave_kind')=='bichromatic'\n  done=read(folder/'completed.json');")
    code = replace(code, "   if (part/'checkpoint_recovery.json').exists():", """   if diagnostic and (part/'seed.json').is_file():
    from w08_portable import SEED,seed_spec
    seed=seed_spec()
    if part.resolve()!=SEED.resolve() or origin.get('sha256')!=actual_parent:
     raise ValueError('W08bi seed does not descend from the approved PRE.')
    links[-1].update(ok=True, verified_transfer=read(part/'seed.json'))
    lineage_ok=all(link['ok'] for link in links)
    previous=Path(seed['source'])
   elif (part/'checkpoint_recovery.json').exists():""")
    code = replace(code, "wrho.get('FifthOrder_water_rho')==1000 and wrho.get('FifthOrder_air_rho')==1.2", """wrho.get('Superposition_water_rho' if diagnostic else 'FifthOrder_water_rho')==1000 and wrho.get('Superposition_air_rho' if diagnostic else 'FifthOrder_air_rho')==1.2""")
    start = code.index("  cy=result['cycles'];")
    end = code.index('  for key,title,criterion', start)
    code = code[:start]+"""  if diagnostic:
   from w08_portable import END
   saved=done.get('status')=='bichromatic_diagnostic_saved'
   add('diagnostic_horizon','Bichromatic diagnostic horizon',status(endpoint and END<=t[-1]<=END+.0004+1e-7,saved),
       'Physical-time target for the two-component diagnostic. Regular-wave Q and cycle acceptance do not apply.',
       dict(target_s=END),[folder/'completed.json'])
  else:
"""+''.join(' '+line for line in code[start:end].splitlines(keepends=True))+code[end:]
    code = replace(code, "  outcome,project_accepted=acceptance(checks,spec.get('smoke',0))", """  outcome,project_accepted=acceptance(checks,spec.get('smoke',0))
  if diagnostic:
   statuses={check['status'] for check in checks if check['group']=='run'}
   outcome='failed' if 'failed' in statuses else 'pending' if 'pending' in statuses else 'passed'
   project_accepted=False""")
    (dest/'validation.py').write_text(code, encoding='utf8')
    shutil.copy2(TEMPLATES/'w08_portable.py', dest)
    make_macro(dest)


def build():
    OUTPUT.mkdir(exist_ok=True)
    make_seed(OUTPUT/'seed')
    make_app(OUTPUT/'app')
    shutil.copy2(TEMPLATES/'install_glhf_w08.py', OUTPUT)
    for name in ('Resume W08bi.cmd', 'CZYTAJ_NAJPIERW.txt'):
        shutil.copy2(TEMPLATES/name, OUTPUT)
    files = {p.relative_to(OUTPUT).as_posix(): sha(p) for p in OUTPUT.rglob('*') if p.is_file()}
    originals = {p.name: [sha(ENGINE/p.name)] for p in (OUTPUT/'app').iterdir() if (ENGINE/p.name).is_file()}
    for patch in ('NWAR_GLHF_UI_hotfix', 'NWAR_GLHF_UI_hotfix_v2'):
        originals['wave_view.js'].extend(sha(path) for path in (ROOT/patch).rglob('wave_view.js'))
    write(OUTPUT/'manifest.json', dict(files=files, originals=originals))
    archive = OUTPUT.with_suffix('.zip')
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for path in sorted(p for p in OUTPUT.rglob('*') if p.is_file()):
            bundle.write(path, path.relative_to(OUTPUT.parent),
                         compress_type=zipfile.ZIP_STORED if path.suffix=='.sim' else zipfile.ZIP_DEFLATED)
    with zipfile.ZipFile(archive) as bundle:
        for name, digest in files.items():
            with bundle.open(f'{OUTPUT.name}/{name}') as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != digest:
                    raise ValueError('Archive readback failed for '+name)
    archive.with_suffix('.zip.sha256').write_text(sha(archive)+'  '+archive.name+'\n', encoding='ascii')
    print(archive, archive.stat().st_size, flush=True)


if __name__ == '__main__':
    build()
