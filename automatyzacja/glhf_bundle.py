"""Portable, read-only exchange of GLHF wave evidence."""
import hashlib
import json
from pathlib import Path, PurePosixPath

SCHEMA = 'nwar-glhf-wave-v1'
C01 = '9af4857b948e0494088b5421f8ede100e66344fc2631cc00030406640d7cc295'
PRE = 'd86beded68b41f5e6ce324a93cea39177dbe93fff516af10d33a71761528b85a'
CASES = {'W05': 20., 'W07': 40.}
EVIDENCE = {
    'history.csv', 'gauges.csv', 'wave_setup_audit.json', 'source_identity.json',
    'native_C01_rho_readback.json', 'wave_density_audit.json', 'stage_result.json',
    'completed.json', 'final_integrity.json', 'latest_checkpoint.json',
    'stopping_policy.json', 'progress.json', 'monitor.json', 'macro_error.json',
    'controller_failure.json', 'independent_cycle_review.json', 'glhf_resume.json',
}


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def path_under(root, relative):
    path = PurePosixPath(relative)
    if path.is_absolute() or '..' in path.parts or '\\' in relative or ':' in relative:
        raise ValueError('Invalid transfer path: ' + relative)
    target = Path(root).joinpath(*path.parts)
    if not target.resolve().is_relative_to(Path(root).resolve()):
        raise ValueError('Transfer path leaves the bundle')
    return target


def load_manifest(root, verify=True):
    root = Path(root)
    m = json.loads((root/'manifest.json').read_text(encoding='utf-8-sig'))
    case = m.get('case_id')
    if (m.get('schema') != SCHEMA or case not in CASES
            or m.get('C01_sha256') != C01 or m.get('PRE_sha256') != PRE
            or m.get('H_m') != 1. or m.get('lambda_m') != CASES[case]
            or m.get('dt_s') != .0004 or m.get('release') not in ('2602', '2606')):
        raise ValueError('Unsupported GLHF case, solver release or reference')
    segments = m['segments']
    if not segments or segments != [f'segments/{i:03}' for i in range(len(segments))]:
        raise ValueError('Invalid segment inventory')
    files = m['files']
    checkpoint = m['checkpoint']['path']
    if checkpoint != 'checkpoint/latest.sim' or checkpoint not in files:
        raise ValueError('Missing checkpoint inventory')
    anchor = m['checkpoint'].get('segment', segments[-1])
    history_only = m.get('history_only_after_checkpoint') is True
    if anchor not in segments or (history_only and (anchor == segments[-1] or m['checkpoint'].get('final_save_verified') is not True)) or (not history_only and anchor != segments[-1]):
        raise ValueError('Invalid checkpoint segment')
    for index, folder in enumerate(segments):
        required = ['history.csv', 'gauges.csv']
        if not history_only or index <= segments.index(anchor):
            required.append('wave_setup_audit.json')
        if any(f'{folder}/{name}' not in files for name in required):
            raise ValueError('Missing history or wave setup')
    for relative, item in files.items():
        part = PurePosixPath(relative)
        if (relative not in (checkpoint, 'validation.json')
                and (part.parent.as_posix() not in segments or part.name not in EVIDENCE)):
            raise ValueError('Unexpected transfer file')
        path = path_under(root, relative)
        if not path.is_file() or path.stat().st_size != item['bytes']:
            raise ValueError('Missing or truncated transfer file: ' + relative)
        if verify and digest(path) != item['sha256']:
            raise ValueError('Transfer checksum mismatch: ' + relative)
    if files[checkpoint]['sha256'] != m['checkpoint']['sha256']:
        raise ValueError('Inconsistent checkpoint checksum')
    return m
