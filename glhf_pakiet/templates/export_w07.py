"""Export a settled GLHF W07 run without opening a solver or writing the queue."""
import argparse
from contextlib import closing
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import zipfile


def json_file(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def read_jobs(database):
    with closing(sqlite3.connect(database.as_uri()+'?mode=ro', uri=True, timeout=15)) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row, spec=json.loads(row['spec'])) for row in
                conn.execute('SELECT * FROM jobs ORDER BY created DESC')]


def export_w07(base, work, output, run_id):
    data = work/'data'
    database = data/'queue.sqlite'
    if not database.is_file():
        raise ValueError('Brak kolejki NWAR w wybranym workspace.')
    release = json_file(work/'settings.json')['release']
    if release not in ('2602', '2606'):
        raise ValueError('Wymagany workspace STAR-CCM+ 2602 lub 2606.')
    os.environ.update(NWAR_PACKAGE_ROOT=str(base), NWAR_WORKSPACE=str(work), NWAR_STAR_RELEASE=release)
    os.environ.setdefault('MPLCONFIGDIR', tempfile.gettempdir())
    sys.path.extend([str(work/'app'), str(base/'app'), str(base/'lib')])

    import analysis
    from common import birth, read
    from glhf_bundle import load_manifest
    from glhf_transfer import checkpoint_for, export, read_case

    jobs = read_jobs(database)
    by_id = {row['id']: row for row in jobs}
    entry = next((row for row in jobs
                  if row['case_id']=='W07' and not row['spec'].get('smoke')
                  and (run_id is None or row['id']==run_id)
                  and (Path(row['folder'])/'history.csv').is_file()), None)
    if entry is None:
        raise ValueError('Brak zapisanego przebiegu W07 w tym workspace.')
    if entry['status'] in ('queued', 'deferred', 'preflight', 'running', 'pausing'):
        raise ValueError('W07 nadal pracuje lub zapisuje. Uruchom eksport po zapisaniu checkpointu.')

    folder = Path(entry['folder']).resolve()
    if not folder.is_relative_to(data.resolve()):
        raise ValueError('Folder W07 nie nalezy do wybranego workspace.')
    process = read(folder/'process.json')
    for pid, recorded in ((entry.get('controller_pid'), entry.get('controller_birth')),
                          (process.get('pid'), process.get('birth'))):
        active = birth(pid)
        if active and (not recorded or active==recorded):
            raise ValueError('Proces wybranego W07 jeszcze sie nie zakonczyl.')

    # The common lineage walker normally looks up parents through the writable app connection.
    # Resolve parent IDs from the same read-only queue snapshot instead.
    analysis.job = by_id.__getitem__
    chain, result = read_case(entry)
    sim, checkpoint = checkpoint_for(entry)
    if not result['health']['ok']:
        raise ValueError('Kontrola historii W07 wykryla blad numeryczny.')
    if output.is_relative_to(data.resolve()):
        raise ValueError('Wybierz folder eksportu poza danymi solvera.')
    output.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(output).free < 2*sim.stat().st_size+64*1024**2:
        raise ValueError('Za malo wolnego miejsca na kopie checkpointu i ZIP.')

    archive = output/f"GLHF_W07_{entry['id']}_{datetime.now():%Y%m%d_%H%M%S_%f}.zip"
    print(f"Checkpoint {checkpoint['time_s']:.4f} s, historia {result['time_s']:.4f} s. Pakowanie...", flush=True)
    with tempfile.TemporaryDirectory(prefix='W07_export_', dir=output) as temporary:
        temporary = Path(temporary)
        bundle = export(entry, chain, result, sim, checkpoint, temporary)
        manifest = load_manifest(bundle, verify=False)
        candidate = temporary/archive.name
        with zipfile.ZipFile(candidate, 'x', allowZip64=True) as z:
            for relative in ['manifest.json', *sorted(manifest['files'])]:
                method = zipfile.ZIP_STORED if relative.endswith('.sim') else zipfile.ZIP_DEFLATED
                z.write(bundle/relative, f'{bundle.name}/{relative}', compress_type=method)
        with zipfile.ZipFile(candidate) as z:
            if z.testzip() is not None:
                raise ValueError('Weryfikacja ZIP nie powiodla sie.')
        candidate.rename(archive)
    print(f'Gotowe. Przenies ten ZIP na ThinkPad:\n{archive}')
    print(f"Zmierzone cykle w historii: {manifest['measured_cycles']}.")
    return archive


def main():
    parser = argparse.ArgumentParser(description='Eksport danych W07 z GLHF')
    parser.add_argument('--package-root', type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--workspace', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--run-id')
    args = parser.parse_args()
    base = args.package_root.resolve()
    if args.workspace is None:
        config = json_file(base/'launcher.json')
        work = (Path(config['workspace_root'])/config['release']).resolve()
    else:
        work = args.workspace.resolve()
    export_w07(base, work, (args.output or base/'GLHF_exports').resolve(), args.run_id)


if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        print(f'Eksport przerwany: {exc}', file=sys.stderr)
        raise SystemExit(1)
