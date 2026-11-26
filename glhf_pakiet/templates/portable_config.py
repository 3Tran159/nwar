"""Portable paths and installation settings; no host-specific credentials."""
from pathlib import Path
import os, json, re

BASE = Path(os.environ['NWAR_PACKAGE_ROOT']).resolve()
WORK = Path(os.environ['NWAR_WORKSPACE']).resolve()
RELEASE = os.environ['NWAR_STAR_RELEASE']
ASSETS = BASE/'assets/root'


def settings():
    value=json.loads((WORK/'settings.json').read_text(encoding='utf8'))
    if value.get('release') != RELEASE or RELEASE not in ('2602','2606'):
        raise ValueError('Workspace and STAR version do not match.')
    return value


def installation(exe):
    exe=Path(exe).resolve()
    if exe.name.lower()!='starccm+.exe' or not exe.is_file():
        raise ValueError('Select the installed starccm+.exe executable.')
    star=next((p for p in exe.parents if (p/'version_info.properties').is_file()),None)
    if star is None:raise ValueError('STAR installation version could not be verified.')
    text=(star/'version_info.properties').read_text(encoding='utf8')
    version=re.search(r'^base_version=(\S+)',text,re.M)
    version=version.group(1) if version else ''
    release='2602' if version.startswith('21.02.') else '2606' if version.startswith('21.04.') else None
    if release is None:raise ValueError('This package supports STAR-CCM+ 2602 and 2606 only.')
    return dict(executable=str(exe),star=str(star),release=release,build=version)


def relocate(value):
    """Rebase preserved evidence in memory; archived receipt bytes stay unchanged."""
    if isinstance(value,list):return [relocate(v) for v in value]
    if isinstance(value,dict):return {relocate(k):relocate(v) for k,v in value.items()}
    if isinstance(value,str):
        normalized=value.replace('\\','/')
        for old,new in [('E:/ntnu_mesh_optimization_20261030',ASSETS),
                        ('C:/Users/ThinkPad/Documents/ChatGPT/ntnu science/nwar_automation',WORK/'app')]:
            if normalized.lower()==old.lower() or normalized.lower().startswith(old.lower()+'/'):
                return str(new/normalized[len(old):].lstrip('/'))
    return value
