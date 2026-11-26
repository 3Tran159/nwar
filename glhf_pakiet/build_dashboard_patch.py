"""Build the small v2 delta, retaining the original full distribution ZIP."""
from pathlib import Path
import datetime, json, shutil
import build_package as build

BASE=build.DEST
QA=BASE.parent/'QA_v2'
PATCH=BASE.parent/'NWAR_patch_v2'
old_manifest=QA/'before_update/package_manifest.json'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


if __name__=='__main__':
    if PATCH.exists():raise ValueError('Existing patch is preserved.')
    # Assemble only the tested delta. The unpacked distribution may be edited
    # independently; never overwrite it or absorb unrelated local changes.
    CANDIDATE=QA/'patch_candidate'
    CANDIDATE.mkdir(exist_ok=True)
    old_compile=read(QA/'before_update/app/compile_receipt.json')
    assert old_compile['macro_sha256']==build.digest(QA/'workspaces/2602/app/NwarWave.java')
    names=['app/index.html','app/style.css','app/wave_view.py','app/wave_view.js','app/portable_runtime.py']
    for name in names:
        source=QA/'workspaces/2602'/name
        assert build.digest(source)==build.digest(QA/'workspaces/2606'/name)
        target=CANDIDATE/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    assert 'MIN_FREE_RAM_GIB=8' in (CANDIDATE/'app/portable_runtime.py').read_text(encoding='utf8')
    shutil.copy2(build.TEMPLATES/'README_EN.txt',CANDIDATE/'README.txt')
    shutil.copy2(build.TEMPLATES/'README_PL.txt',CANDIDATE/'CZYTAJ_NAJPIERW.txt')
    checks=dict(browser=read(QA/'browser_checks.json'),launcher=read(QA/'launcher_checks.json'))
    for release in ('2602','2606'):
        checks[release]=dict(offline=read(QA/'workspaces'/release/'offline_checks.json'),runtime_fake_only=read(QA/'workspaces'/release/'runtime_checks.json'),rolling_cycles=read(QA/('rolling_cycle_'+release+'.json')),cycle_unit_tests='7 passed')
    for item in checks.values():
        if 'passed' in item:assert item['passed']
        else:assert all(v.get('passed') is True for v in item.values() if isinstance(v,dict))
    build.put(CANDIDATE/'validation_summary.json',dict(passed=True,revision=2,at=datetime.datetime.now().astimezone().isoformat(),scope='Offline dashboard and runtime checks for 2602/2606; no native solver was started.',checks=checks,native_solver_execution_tested=False,free_RAM_min_GiB=8,scientific_asset_changes=False))
    before={x['path']:x for x in read(old_manifest)['files']}
    after=dict(before)
    for p in CANDIDATE.rglob('*'):
        if p.is_file() and p.name!='package_manifest.json':
            name=p.relative_to(CANDIDATE).as_posix();after[name]=dict(path=name,bytes=p.stat().st_size,sha256=build.digest(p))
    changed=[p for p in after if p not in before or before[p]['sha256']!=after[p]['sha256']]
    allowed={'app/index.html','app/style.css','app/wave_view.py','app/wave_view.js','app/portable_runtime.py','README.txt','CZYTAJ_NAJPIERW.txt','validation_summary.json'}
    assert set(changed)<=allowed,changed
    manifest=read(old_manifest)
    manifest.update(created=datetime.datetime.now().astimezone().isoformat(),revision=2,files=list(after.values()),total_bytes=sum(x['bytes'] for x in after.values()))
    build.put(CANDIDATE/'package_manifest.json',manifest)
    changed.append('package_manifest.json')
    records=[]
    for name in changed:
        source=CANDIDATE/name;target=PATCH/'payload'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
        prior=build.digest(old_manifest) if name=='package_manifest.json' else before.get(name,{}).get('sha256')
        records.append(dict(path=name,before_sha256=prior,sha256=build.digest(source),bytes=source.stat().st_size))
    build.put(PATCH/'patch_manifest.json',dict(id='nwar_dashboard_cycles_ram8_20261103_v2',created=datetime.datetime.now().astimezone().isoformat(),base_package='NWAR Windows 2602/2606 (2026-11-03)',allowed_package_manifest_sha256=[build.digest(old_manifest),build.digest(CANDIDATE/'package_manifest.json')],files=records,asset_changes=False,free_RAM_min_GiB=8))
    shutil.copy2(build.TEMPLATES/'apply_dashboard_patch.py',PATCH/'apply_dashboard_patch.py')
    build.put(PATCH/'Apply patch.cmd','@echo off\nsetlocal\nif not exist "%~dp0..\\runtime\\python.exe" (\n echo Extract NWAR_patch_v2 inside your original NWAR folder, beside app, assets and runtime.\n pause\n exit /b 1\n)\nset "PYTHONHOME=%~dp0..\\runtime"\nset "PYTHONPATH="\nset "PYTHONNOUSERSITE=1"\n"%~dp0..\\runtime\\python.exe" "%~dp0apply_dashboard_patch.py"\nset "PATCH_EXIT=%ERRORLEVEL%"\npause\nexit /b %PATCH_EXIT%\n')
    build.put(PATCH/'CZYTAJ_PATCH.txt','''NWAR — mała poprawka v2 / Windows / STAR-CCM+ 2602 i 2606

ZMIANY
Odliczanie do każdego kolejnego pełnego cyklu. Bieżący cykl dorysowuje się
przerywaną linią z zapisanych próbek; po zamknięciu staje się ciągły.
Automatyczne odświeżanie i ten sam układ dla kolejnych fal.
Wymagane wolne RAM w paczce: 8 GiB zamiast 16 GiB.
Fizyka, siatka, kryteria akceptacji i inne zabezpieczenia pozostają bez zmian.

INSTALACJA
1. Rozpakuj folder NWAR_patch_v2 DO dotychczasowego folderu paczki,
   np. D:\\NWAR\\NWAR_Windows_2602_2606\\NWAR_patch_v2.
   Folder poprawki musi leżeć obok app, assets, runtime i Start NWAR.cmd.
2. Na komputerze DOCELOWYM środowisko paczki musi być bezczynne:
   zapisz trwające tam obliczenia, anuluj oczekujące zlecenia i użyj
   Close dashboard.cmd. Nie uruchamiaj niczego podczas nakładania poprawki.
   NIE zatrzymuj bieżącego W04 na komputerze źródłowym — jest niezależny.
3. Uruchom NWAR_patch_v2\\Apply patch.cmd. Instalator niczego nie zatrzymuje;
   odmówi działania, jeśli wykryje aktywny serwer, solver lub kolejkę.
4. Po sukcesie uruchom zwykłe Start NWAR.cmd i odśwież kartę dashboardu.

Aktualizowane są pliki paczki oraz jej domyślne i aktualnie skonfigurowane
foldery wyników 2602/2606. Dodatkowy, wcześniej używany folder wyników można
wskazać z terminala (przykład z głównego folderu paczki):
runtime\\python.exe NWAR_patch_v2\\apply_dashboard_patch.py --workspace-root "D:\\inne_wyniki"
Opcja --check sprawdza możliwość aktualizacji bez zmieniania plików.
Ponowne uruchomienie tej samej poprawki jest bezpieczne i nie dubluje zmian.
Oryginalne podmieniane pliki są zachowywane w .nwar_patch_backups; nie usuwa
się wyników, scen ani checkpointów. C01 i PRE nie są dołączone ponownie ani
modyfikowane. Sam patch wymaga poprzedniej pełnej paczki z 03.11.2026.

Weryfikacja: testy dashboardu, cykli, granicy 8 GiB i sterowania na obu
wariantach 2602/2606. Makro kompiluje się z bibliotekami obu wersji.
Natywnego solvera z paczki nie uruchamiano, aby zachować bieżący W04.
''')
    print(json.dumps(dict(patch=str(PATCH),payload_files=len(records),payload_bytes=sum(r['bytes'] for r in records),files=[r['path'] for r in records]),indent=2))
