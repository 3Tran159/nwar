"""Read-only transfer of a completed GLHF W08bi diagnostic run."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import zipfile

from export_w08bi_live import DT, TOL, chain, collect_history, csv_bytes, read_jobs, read_json


COMPONENTS = [('W01', .5, 20., 0), ('W06', 1., 30., 0)]
EVIDENCE = ('history.csv', 'gauges.csv', 'seed.json', 'bichromatic_setup.json', 'wave_setup_audit.json',
            'native_C01_rho_readback.json', 'source_identity.json', 'stopping_policy.json',
            'latest_checkpoint.json', 'stage_result.json', 'completed.json', 'final_integrity.json',
            'independent_cycle_review.json', 'wake_history_config.json', 'wake_history.json')


def matching_run(entry):
    spec = entry['spec']
    components = [(c.get('baseline'), c.get('H_m'), c.get('lambda_m'), c.get('phase_deg'))
                  for c in spec.get('components', [])]
    return (spec.get('wave_kind') == 'bichromatic' and not spec.get('smoke')
            and components == COMPONENTS)


def final_save(folder):
    done, stage, checkpoint, integrity, review = (read_json(folder/name) for name in
        ('completed.json', 'stage_result.json', 'latest_checkpoint.json', 'final_integrity.json',
         'independent_cycle_review.json'))
    sim = folder/'wave_pilot_final.sim'
    end = float(done['time_s'])
    if (done.get('status') != 'bichromatic_diagnostic_saved' or stage.get('exit_code') != 0
            or stage.get('source_unchanged') is not True or stage.get('controller_reason') is not None
            or integrity.get('source_unchanged') is not True or review.get('health', {}).get('ok') is not True
            or checkpoint.get('healthy') is not True or checkpoint.get('file') != sim.name
            or int(checkpoint['step']) != int(done['steps'])
            or not all(abs(float(item['time_s'])-end) <= TOL for item in (checkpoint, integrity, review))
            or any((folder/name).exists() for name in ('macro_error.json', 'macro_error.txt'))
            or not sim.is_file() or sim.stat().st_size != integrity['bytes']):
        raise ValueError('Koncowy SIM, stan solvera i zapis diagnostyczny nie przeszly weryfikacji.')
    return sim, end, int(checkpoint['step']), integrity


def add_file(bundle, path, member, method):
    before = path.stat()
    digest = hashlib.sha256()
    record = zipfile.ZipInfo(member)
    record.compress_type = method
    size = 0
    with path.open('rb') as source, bundle.open(record, 'w', force_zip64=True) as target:
        for block in iter(lambda: source.read(4*1024*1024), b''):
            target.write(block)
            digest.update(block)
            size += len(block)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or size != before.st_size:
        raise ValueError('Plik zmienil sie podczas eksportu: '+path.name)
    return dict(bytes=size, sha256=digest.hexdigest())


def export_final(base, output, run_id=None):
    config = read_json(base/'launcher.json')
    release = config['release']
    data = (Path(config['workspace_root'])/release/'data').resolve()
    jobs = read_jobs(data)
    candidates = [j for j in jobs if matching_run(j) and (run_id is None or j['id']==run_id)]
    entry = next((j for j in candidates if j['status']=='completed'), None)
    if entry is None:
        latest = candidates[0]['status'] if candidates else 'brak przebiegu'
        raise ValueError('Brak zakonczonej diagnostyki W08bi. Status ostatniej proby: '+latest)
    folders = chain(entry, {j['id']:j for j in jobs}, data)
    sim, end, step, integrity = final_save(folders[-1])
    h_fields, forces, g_fields, probes, segments = collect_history(folders, end)
    probe_end = float(probes[-1]['time_s'])
    if (abs(float(forces[-1]['time_s'])-end)>TOL or int(forces[-1]['step'])!=step
            or not 0 <= end-probe_end+TOL <= 10*DT+2*TOL or len(segments)!=len(folders)):
        raise ValueError('Koncowy krok SIM nie odpowiada pelnej historii sil i sond.')
    if output.is_relative_to(data):
        raise ValueError('Wybierz folder eksportu poza danymi solvera.')
    output.mkdir(parents=True, exist_ok=True)
    paths = {}
    for index, folder in enumerate(folders):
        members = [folder/name for name in EVIDENCE if (folder/name).is_file()]
        members.extend(path for path in sorted(folder.glob('*.simh')) if path.is_file())
        for path in members:
            if path.resolve().parent != folder:
                raise ValueError('Plik segmentu wskazuje poza katalog przebiegu: '+path.name)
            paths[f'segments/{index:03}/{path.name}'] = path
    final_member = 'checkpoint/W08bi_final.sim'
    paths[final_member] = sim
    if shutil.disk_usage(output).free < sum(p.stat().st_size for p in paths.values())+64*1024**2:
        raise ValueError('Za malo wolnego miejsca na koncowy eksport.')

    captured = datetime.now().astimezone()
    manifest = dict(kind='w08bi_final_diagnostic', final=True, diagnostic_only=True,
                    checkpoint_included=True, case_id='W08', display_id='W08bi', job_id=entry['id'],
                    job_status=entry['status'], release=release, captured_at=captured.isoformat(),
                    time_s=end, probe_end_s=probe_end, force_samples=len(forces), probe_samples=len(probes),
                    components=entry['spec']['components'], segments=segments, dt_s=DT,
                    checkpoint=dict(path=final_member, time_s=end, step=step, sha256=integrity['sha256']), files={})
    archive = output/f'GLHF_W08bi_FINAL_{end:.4f}s_{captured:%Y%m%d_%H%M%S_%f}.zip'
    print(f'W08bi zakonczone przy t = {end:.4f} s. Pakowanie...', flush=True)
    with tempfile.TemporaryDirectory(prefix='w08bi_final_', dir=output) as temp:
        staged = Path(temp)/archive.name
        with zipfile.ZipFile(staged, 'x', compression=zipfile.ZIP_DEFLATED, allowZip64=True) as bundle:
            for name, fields, rows in (('history.csv',h_fields,forces), ('gauges.csv',g_fields,probes)):
                content = csv_bytes(fields,rows)
                bundle.writestr(name,content)
                manifest['files'][name] = dict(bytes=len(content),sha256=hashlib.sha256(content).hexdigest())
            for member, path in paths.items():
                method = zipfile.ZIP_STORED if path.suffix.lower() in ('.sim', '.simh') else zipfile.ZIP_DEFLATED
                manifest['files'][member] = add_file(bundle, path, member, method)
            if manifest['files'][final_member] != dict(bytes=integrity['bytes'],sha256=integrity['sha256']):
                raise ValueError('SHA-256 koncowego SIM rozni sie od zapisu solvera.')
            bundle.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
        with zipfile.ZipFile(staged) as bundle:
            if bundle.testzip() is not None:
                raise ValueError('Weryfikacja ZIP nie powiodla sie.')
        staged.rename(archive)
    print(f'Gotowy ZIP do przeniesienia na ThinkPad:\n{archive}')
    return archive


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package-root', type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--run-id')
    args = parser.parse_args()
    try:
        base = args.package_root.resolve()
        export_final(base, (args.output or base/'GLHF_exports').resolve(), args.run_id)
    except (OSError, ValueError, KeyError, sqlite3.Error) as error:
        parser.exit(1, f'Eksport przerwany: {error}\n')
