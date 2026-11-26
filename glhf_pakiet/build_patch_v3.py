"""Latest portable delta built in isolation; accepted inputs are base or v2."""
from pathlib import Path
import datetime,json,shutil,zipfile,sys
import build_package as build

ROOT=build.DEST.parent
QA=ROOT/'QA_v3'
CANDIDATE=QA/'candidate'
PATCH=ROOT/'NWAR_patch_v3_GLHF'

def prepare():
    if PATCH.exists():raise ValueError('Existing patch preserved')
    QA.mkdir(exist_ok=True)
    build.DEST=CANDIDATE;build.QA=QA
    build.APPFILES+=['cycle_policy.py','bichromatic.py']
    build.adapt_app()
    # Retain the already verified eight-GiB runtime rather than host-local edits.
    shutil.copy2(ROOT/'QA_v2/patch_candidate/app/portable_runtime.py',CANDIDATE/'app/portable_runtime.py')
    assert 'MIN_FREE_RAM_GIB=8' in (CANDIDATE/'app/portable_runtime.py').read_text()
    build.compile_macro()
    for source,target in [('README_EN.txt','README.txt'),('README_PL.txt','CZYTAJ_NAJPIERW.txt')]:
        text=(build.TEMPLATES/source).read_text(encoding='utf8').replace('NWAR_patch_v2','NWAR_patch_v3_GLHF')
        text+='\nRevision 3: five complete regular-wave cycles; exclude cycle 1 and analyze cycles 2-5. Full raw histories remain preserved. Live cycle countdown, growing force overlays, probe phase controls, atomic progress-file IO recovery, 8 GiB free RAM.\n'
        build.put(CANDIDATE/target,text)
    print(json.dumps(dict(candidate=str(CANDIDATE),prepared=True)))

def archive():
    original=ROOT/'NWAR_Windows_2602_2606.zip'
    with zipfile.ZipFile(original) as z:
        raw=z.read('NWAR_Windows_2602_2606/package_manifest.json');base=json.loads(raw)
    (QA/'original_package_manifest.json').write_bytes(raw)
    v2=json.loads((ROOT/'QA_v2/patch_candidate/package_manifest.json').read_text(encoding='utf8'))
    before={x['path']:x for x in base['files']};v2files={x['path']:x for x in v2['files']}
    build.put(CANDIDATE/'validation_summary.json',dict(passed=True,revision=3,at=datetime.datetime.now().astimezone().isoformat(),scope='Offline and browser QA for 2602 and 2606, isolated from live W04',checks=json.loads((QA/'verification.json').read_text()),native_solver_execution_tested=False,asset_changes=False,free_RAM_min_GiB=8))
    after=dict(before)
    for path in CANDIDATE.rglob('*'):
        if not path.is_file() or path.name=='package_manifest.json' or '__pycache__' in path.parts:continue
        name=path.relative_to(CANDIDATE).as_posix();after[name]=dict(path=name,bytes=path.stat().st_size,sha256=build.digest(path))
    manifest=dict(base,created=datetime.datetime.now().astimezone().isoformat(),revision=3,files=list(after.values()),total_bytes=sum(x['bytes'] for x in after.values()))
    build.put(CANDIDATE/'package_manifest.json',manifest)
    changed=[name for name in after if name not in before or after[name]['sha256']!=before[name]['sha256'] or after[name]['sha256']!=v2files.get(name,{}).get('sha256')]
    changed.append('package_manifest.json');records=[]
    for name in changed:
        assert name.startswith('app/') or name in ['README.txt','CZYTAJ_NAJPIERW.txt','validation_summary.json','package_manifest.json'],name
        source=CANDIDATE/name;target=PATCH/'payload'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
        if name=='package_manifest.json':allowed=[build.digest(QA/'original_package_manifest.json'),build.digest(ROOT/'QA_v2/patch_candidate/package_manifest.json')]
        else:allowed=list(dict.fromkeys([before.get(name,{}).get('sha256'),v2files.get(name,{}).get('sha256')]))
        records.append(dict(path=name,before_sha256=allowed[0],allowed_before_sha256=allowed,sha256=build.digest(source),bytes=source.stat().st_size))
    build.put(PATCH/'patch_manifest.json',dict(id='nwar_GLHF_dashboard_v3_20261103',created=datetime.datetime.now().astimezone().isoformat(),allowed_package_manifest_sha256=[build.digest(QA/'original_package_manifest.json'),build.digest(ROOT/'QA_v2/patch_candidate/package_manifest.json'),build.digest(CANDIDATE/'package_manifest.json')],files=records,asset_changes=False,free_RAM_min_GiB=8))
    shutil.copy2(build.TEMPLATES/'apply_dashboard_patch.py',PATCH/'apply_dashboard_patch.py')
    cmd=(ROOT/'NWAR_patch_v2/Apply patch.cmd').read_text(encoding='utf8').replace('NWAR_patch_v2','NWAR_patch_v3_GLHF')
    build.put(PATCH/'Apply patch.cmd',cmd)
    build.put(PATCH/'CZYTAJ_PATCH.txt','''NWAR GLHF — patch v3, STAR-CCM+ 2602 i 2606

Rozpakuj NWAR_patch_v3_GLHF do istniejącego folderu NWAR, obok app,
assets, runtime i Start NWAR.cmd. Działa bezpośrednio z paczką z 03.11
oraz z paczką po patchu v2; v2 nie trzeba instalować osobno.

Na GLHF zapisz trwające obliczenia, anuluj oczekujące zadania i zamknij
usługę przez Close dashboard.cmd. Uruchom NWAR_patch_v3_GLHF/Apply patch.cmd,
następnie Start NWAR.cmd i odśwież przeglądarkę (Ctrl+F5).
Instalator odmówi aktualizacji aktywnego środowiska i nie zatrzymuje solvera.
Nie uruchamiaj instalatora na aktywnej kampanii źródłowej W04.

Zmiany: odliczanie do kolejnego cyklu, dorysowywanie bieżącego cyklu,
porównanie dwóch sond i ręczna faza, pięć pełnych cykli regularnej fali,
pominięcie cyklu 1 i analiza 2–5 także dla starszych wyników. Krótsze
wyniki zachowują historię i wykresy, ale nie pełne zaliczenie/Q.
Poprawka odporności progress.json na chwilową blokadę Windows. Minimum
wolnego RAM pozostaje 8 GiB. Fizyka i siatka bez zmian.

Automatyczna nocna trasa W04→W06 i eksperyment W08 z komputera źródłowego
nie są przenoszone. Wybór instalacji, licencja i folder wyników GLHF pozostają.
C01/PRE, pliki .sim, sceny, CSV i ustawienia nie są ponownie pakowane.
Kopie podmienianych plików trafiają do .nwar_patch_backups.
Lokalnie zmienione pliki są chronione przed nadpisaniem.
Opcja --check sprawdza aktualizację bez zapisu; --workspace-root pozwala
wskazać dodatkowy katalog wyników. Powtórna instalacja jest idempotentna.
''')
    output=ROOT/'NWAR_Windows_2602_2606_GLHF_patch_v3.zip'
    if output.exists():raise ValueError('Existing ZIP preserved')
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for path in PATCH.rglob('*'):
            if path.is_file():z.write(path,'NWAR_patch_v3_GLHF/'+path.relative_to(PATCH).as_posix())
    build.put(output.with_suffix('.zip.sha256'),build.digest(output)+'  '+output.name+'\n')
    print(json.dumps(dict(archive=str(output),bytes=output.stat().st_size,sha256=build.digest(output),files=len(records))))

if __name__=='__main__':
    if '--archive' in sys.argv:archive()
    else:prepare()
