"""Verify the saved PRE chain for both supported fresh-start methods."""
from common import Path, read, sha
from pre_w04 import calm_checkpoint


def prepared_lineage(prepared, folders, digest=sha):
    folders = list(map(Path, folders))
    if not folders:
        raise ValueError('Missing PRE history chain')
    method = prepared.get('initialization')
    root = folders[0]
    setup = read(root/'setup.json')
    if method == 'whole_domain_momentum_ramp':
        origin = read(root/'source_identity.json')
        if not origin.get('path'):
            raise ValueError('Missing fresh PRE source identity')
        previous = Path(origin['path'])
        valid = (digest(previous) == origin.get('sha256')
                 and setup.get('initialization') == method
                 and setup.get('fresh_fields') is True
                 and setup.get('start_time_s') == 0)
        removed = read(folders[-1]/'global_ramp_completed.json')
        valid &= (removed.get('momentum_source_option') == 'NONE'
                  and removed.get('extra_force_active') is False
                  and prepared.get('gates', {}).get('startup_momentum_source_removed') is True)
    elif method == 'fresh_from_rest':
        previous = Path(prepared['geometry_source'])
        valid = digest(previous) == prepared.get('geometry_source_sha256')
    else:
        raise ValueError('Unknown PRE initialization method')
    links = []
    for part in folders:
        origin = read(part/'source_identity.json')
        actual = digest(previous)
        ok = bool(origin.get('path') and Path(origin['path']).resolve() == previous.resolve()
                  and origin.get('sha256') == actual
                  and read(part/'stage_result.json').get('source_unchanged') is True)
        links.append(dict(folder=str(part), source=origin.get('path'),
                          expected_sha256=origin.get('sha256'), actual_sha256=actual, ok=ok))
        valid &= ok
        previous = calm_checkpoint(part)
        recovery = read(part/'history_cutoff.json')
        if recovery:
            valid &= digest(previous) == recovery.get('checkpoint_sha256')
    return previous, bool(valid), links
