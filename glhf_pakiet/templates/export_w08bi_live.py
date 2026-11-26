"""Read-only export of W08bi force and probe histories, including the seed."""
import argparse
from collections import Counter
from contextlib import closing
import csv
from datetime import datetime
from itertools import groupby
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import zipfile


PROBES = {-69., -50., -30., -15., -6., -.5, 0., 5., 20., 50., 85.}
DT = .0004
TOL = 1e-7
ACTIVE = {'preflight', 'running', 'pausing'}


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def chain(entry, entries, data, seen=None):
    seen = set() if seen is None else seen
    if entry['id'] in seen or entry['case_id'] != 'W08':
        raise ValueError('Nieprawidlowa historia wznowien W08bi.')
    seen.add(entry['id'])
    spec = entry['spec']
    parent = spec.get('parent_id')
    folders = (chain(entries[parent], entries, data, seen) if parent else
               [Path(p).resolve() for p in spec.get('parent_segments', [])])
    folders.append(Path(entry['folder']).resolve())
    if any(not p.is_relative_to(data) for p in folders):
        raise ValueError('Segment poza katalogiem danych GLHF.')
    return folders


def snapshot(path):
    if not path.is_file():
        return [], []
    with path.open('rb') as stream:
        stream.seek(0, 2)
        size = stream.tell()
        stream.seek(0)
        raw = stream.read(size)
    complete, _, _ = raw.rpartition(b'\n')
    reader = csv.DictReader(io.StringIO(complete.decode('utf-8-sig')))
    rows = list(reader)
    if any(None in row or None in row.values() for row in rows):
        raise ValueError(f'Niepelny rekord w {path.name}. Uruchom eksport jeszcze raz.')
    return reader.fieldnames or [], rows


def csv_bytes(fields, rows):
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fields)
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode('utf8')


def read_jobs(data):
    queue = data/'queue.sqlite'
    with closing(sqlite3.connect(queue.as_uri()+'?mode=ro', uri=True, timeout=10)) as db:
        db.row_factory = sqlite3.Row
        return [dict(row, spec=json.loads(row['spec'])) for row in
                db.execute("SELECT * FROM jobs WHERE case_id='W08' ORDER BY created DESC")]


def collect_history(folders, through=None):
    force_fields, gauge_fields = [], []
    forces, probes, segments = [], [], []
    last_force = last_probe = float('-inf')
    for index, folder in enumerate(folders):
        # Read probe frames first so an appended frame cannot outrun the captured forces.
        g_fields, g_rows = snapshot(folder/'gauges.csv')
        h_fields, h_rows = snapshot(folder/'history.csv')
        if not h_rows:
            if index != len(folders)-1:
                raise ValueError('Brakuje zapisanego segmentu historii.')
            break
        if (force_fields and h_fields != force_fields) or (gauge_fields and g_fields and g_fields != gauge_fields):
            raise ValueError('Rozne formaty CSV w segmentach W08bi.')
        force_fields = h_fields
        gauge_fields = g_fields or gauge_fields
        start = float(h_rows[0]['time_s'])
        if index and abs(start-last_force)>TOL:
            raise ValueError('Brak zgodnosci czasu na granicy wznowienia.')
        segments.append(dict(index=index, name=folder.name, begin_s=start))
        for row in h_rows:
            t = float(row['time_s'])
            if t > (through if through is not None else float('inf'))+TOL:
                break
            if index and abs(t-start)<=TOL:
                continue
            if forces and abs(t-last_force-DT)>TOL:
                raise ValueError('Luka w historii sil W08bi.')
            forces.append(row)
            last_force = t
        for stamp, rows in groupby(g_rows, key=lambda row: row['time_s']):
            t = float(stamp)
            frame = list(rows)
            if (last_probe+TOL < t <= last_force+TOL
                    and Counter(float(row['x_m']) for row in frame)==Counter(PROBES)):
                probes.extend(frame)
                last_probe = t
        if through is not None and last_force >= through-DT-TOL:
            break
    if not forces or not probes:
        raise ValueError('Za malo danych do eksportu sil i sond.')
    return force_fields, forces, gauge_fields, probes, segments


def export(base, output, through=None):
    config = read_json(base/'launcher.json')
    data = (Path(config['workspace_root'])/config['release']).resolve()/'data'
    jobs = read_jobs(data)
    candidates = [j for j in jobs if j['spec'].get('wave_kind')=='bichromatic'
                  and not j['spec'].get('smoke') and j['status'] not in {'queued','deferred','cancelled'}]
    entry = next((j for j in candidates if j['status'] in ACTIVE), None)
    if entry is None:
        entry = next((j for j in candidates if (Path(j['folder'])/'history.csv').is_file()), None)
    if entry is None:
        raise ValueError('Brak W08bi w kolejce GLHF.')
    folders = chain(entry, {j['id']:j for j in jobs}, data)
    force_fields, forces, gauge_fields, probes, segments = collect_history(folders, through)
    last_probe = float(probes[-1]['time_s'])
    # Export one common, fully written endpoint for both series.
    forces = [row for row in forces if float(row['time_s'])<=last_probe+TOL]
    if abs(float(forces[-1]['time_s'])-last_probe)>TOL:
        raise ValueError('Czas ostatniej kompletnej probki sond nie pasuje do historii sil.')
    meta = dict(kind='w08bi_live_diagnostic_snapshot', final=False, checkpoint_included=False,
                case_id='W08', display_id='W08bi', job_id=entry['id'], job_status=entry['status'],
                captured_at=datetime.now().astimezone().isoformat(), time_s=last_probe,
                requested_through_s=through, force_samples=len(forces), probe_samples=len(probes),
                components=entry['spec']['components'], segments=[s for s in segments if s['begin_s']<=last_probe+TOL],
                dt_s=DT)
    if output.is_relative_to(data):
        raise ValueError('Wybierz folder eksportu poza danymi solvera.')
    output.mkdir(parents=True, exist_ok=True)
    archive = output/f"GLHF_W08bi_preview_{last_probe:.4f}s_{datetime.now():%Y%m%d_%H%M%S_%f}.zip"
    with tempfile.TemporaryDirectory(prefix='w08bi_export_', dir=output) as temporary:
        staged = Path(temporary)/archive.name
        with zipfile.ZipFile(staged, 'x', compression=zipfile.ZIP_DEFLATED) as bundle:
            bundle.writestr('manifest.json', json.dumps(meta, ensure_ascii=False, indent=2))
            bundle.writestr('history.csv', csv_bytes(force_fields, forces))
            bundle.writestr('gauges.csv', csv_bytes(gauge_fields, probes))
        with zipfile.ZipFile(staged) as bundle:
            if bundle.testzip() is not None:
                raise ValueError('Weryfikacja ZIP nie powiodla sie.')
        staged.rename(archive)
    print(f'W08bi: eksport do {last_probe:.4f} s ({len(forces)} probek sil).')
    print(f'Gotowy ZIP do przeniesienia na ThinkPad:\n{archive}')
    return archive


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--package-root', type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--through', type=float)
    args = parser.parse_args()
    try:
        base = args.package_root.resolve()
        export(base, (args.output or base/'GLHF_exports').resolve(), args.through)
    except (OSError, ValueError, KeyError, sqlite3.Error) as error:
        parser.exit(1, f'Eksport przerwany: {error}\n')
