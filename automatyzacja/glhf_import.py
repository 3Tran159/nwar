"""Register verified GLHF exports as read-only dashboard history."""
import argparse
import shutil
import uuid
import zipfile
import json
from pathlib import Path

from common import DATA, catalog, read, sha, write
from glhf_bundle import load_manifest, path_under

IMPORTS = DATA/'glhf_imports'


def import_w08bi_final(source):
    """Publish the verified diagnostic histories without a resumable queue entry."""
    with zipfile.ZipFile(source) as bundle:
        manifest_bytes = bundle.read('manifest.json')
        manifest = json.loads(manifest_bytes)
        components = [(c['baseline'],c['H_m'],c['lambda_m'],c['phase_deg']) for c in manifest['components']]
        if (manifest.get('kind')!='w08bi_final_diagnostic' or manifest.get('final') is not True
                or manifest.get('case_id')!='W08' or components!=[('W01',.5,20.,0),('W06',1.,30.,0)]):
            raise ValueError('Expected the completed W08bi diagnostic export.')
        from hashlib import sha256
        key = sha256(manifest_bytes).hexdigest()
        target = IMPORTS/('W08bi_'+key[:20])
        if target.exists():
            if sha(target/'manifest.json')!=key or not (target/'dashboard_import.json').is_file():
                raise ValueError('Existing W08bi import differs from its manifest.')
            return target
        temp = target.with_name(target.name+'.partial-'+uuid.uuid4().hex[:8])
        segments = [f'segments/{i:03}' for i in range(len(manifest['segments']))]
        if not segments:
            raise ValueError('Missing W08bi history segments.')
        for part in segments:
            for name in ('history.csv','gauges.csv','wave_setup_audit.json','bichromatic_setup.json'):
                member = f'{part}/{name}'
                if name=='bichromatic_setup.json' and member not in manifest['files']:
                    continue  # A clean resume inherits the seed's wave setup.
                record = manifest['files'][member]
                raw = bundle.read(member)
                if record!=dict(bytes=len(raw),sha256=sha256(raw).hexdigest()):
                    raise ValueError('W08bi history checksum mismatch: '+member)
                path = path_under(temp,member)
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(raw)
        (temp/'manifest.json').write_bytes(manifest_bytes)
        write(temp/'dashboard_import.json',dict(manifest_sha256=key,segments=segments))
        temp.rename(target)
    return target


def import_bundle(source):
    from analysis import analyze
    source = Path(source).resolve()
    manifest = load_manifest(source)
    case = next(c for c in catalog() if c['id']==manifest['case_id'])
    if case['H']!=manifest['H_m'] or case['L']!=manifest['lambda_m']:
        raise ValueError('The local dashboard has different wave conditions')
    folders = [path_under(source, part) for part in manifest['segments']]
    result, _, _ = analyze(case, folders)
    if (not result['health']['ok'] or abs(result['time_s']-manifest['history_end_s'])>1e-7
            or manifest['checkpoint']['time_s']>result['time_s']+1e-7):
        raise ValueError('GLHF history is unhealthy or differs from its manifest')
    from analysis import numeric_rows
    anchor = manifest['checkpoint'].get('segment', manifest['segments'][-1])
    times = numeric_rows(path_under(source, anchor)/'history.csv')['time_s']
    if not any(abs(times-manifest['checkpoint']['time_s'])<=1e-7):
        raise ValueError('The transferred checkpoint has no exact force-history row')
    checksum = sha(source/'manifest.json')
    name = 'GLHF_'+case['id']+'_'+checksum[:20]
    target = IMPORTS/name
    if target.exists():
        load_manifest(target)
        return target
    temp = IMPORTS/(name+'.partial-'+uuid.uuid4().hex[:8])
    temp.mkdir(parents=True)
    for name in manifest['files']:
        p = path_under(temp,name)
        p.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path_under(source,name),p)
    shutil.copy2(source/'manifest.json',temp/'manifest.json')
    if sha(temp/'manifest.json')!=checksum:
        raise ValueError('Manifest changed during copy')
    load_manifest(temp)
    write(temp/'dashboard_import.json', dict(manifest_sha256=checksum, health_ok=True,
          recorded_cycles=result['cycles']['count'], last_time_s=result['time_s']))
    temp.rename(target)
    return target


def imported_entries():
    from glhf_custom_import import imported_entries as custom_entries
    entries = custom_entries()
    for path in sorted(IMPORTS.glob('GLHF_*')):
        receipt = read(path/'dashboard_import.json')
        try:
            if '.partial-' in path.name or not receipt.get('health_ok') or sha(path/'manifest.json')!=receipt.get('manifest_sha256'):
                continue
            manifest = load_manifest(path,verify=False)
            folders = [str(path_under(path, part)) for part in manifest['segments']]
            validation = read(path/'saved_result_review.json')
            if (validation.get('manifest_sha256')!=receipt['manifest_sha256']
                    or validation.get('time_s')!=manifest['history_end_s']
                    or validation.get('project_accepted') is not True):
                validation = {}
            if validation:
                try:
                    stat = Path(validation['checkpoint']).stat()
                    if (stat.st_size,stat.st_mtime_ns)!=(validation['checkpoint_bytes'],validation['checkpoint_mtime_ns']):
                        validation = {}
                except OSError:
                    validation = {}
            entries.append(dict(id=path.name, case_id=manifest['case_id'], imported=True, validation=validation,
                  external=True, status='completed' if validation else 'saved', folder=folders[-1], updated=manifest['exported_at'],
                  reference_id='C01_original',spec=dict(parent_segments=folders[:-1]),
                  message=('Accepted imported GLHF save · STAR-CCM+ '+manifest['release'] if validation else
                           'Read-only GLHF history · new samples after the verified checkpoint'
                           if manifest.get('history_only_after_checkpoint') else
                           'Read-only GLHF history · STAR-CCM+ '+manifest['release']),
                  import_checkpoint_time_s=validation.get('time_s',manifest['checkpoint']['time_s']),
                  import_recorded_cycles=receipt['recorded_cycles']))
        except (OSError,ValueError,KeyError,TypeError):
            continue
    for path in sorted(IMPORTS.glob('W08bi_*')):
        if '.partial-' in path.name or not path.is_dir():
            continue
        try:
            receipt=read(path/'dashboard_import.json');manifest=read(path/'manifest.json')
            if receipt.get('manifest_sha256')!=sha(path/'manifest.json') or not receipt.get('segments'):
                continue
            folders=[str(path_under(path,part)) for part in receipt['segments']]
            entries.append(dict(id=path.name,case_id='W08',imported=True,external=True,status='saved',validation={},
                folder=folders[-1],updated=manifest['captured_at'],reference_id='C01_original',
                spec=dict(parent_segments=folders[:-1],components=manifest['components'],wave_kind='bichromatic'),
                message='Completed GLHF bichromatic diagnostic',import_checkpoint_time_s=manifest['time_s'],
                import_recorded_cycles=None))
        except (OSError,ValueError,KeyError,TypeError):
            continue
    return entries


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('folder',type=Path)
    args = parser.parse_args()
    print(import_bundle(args.folder))
