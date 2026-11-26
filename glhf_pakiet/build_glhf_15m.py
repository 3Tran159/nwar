"""Build the small GLHF wavelength-range patch and validate local macro builds."""
from pathlib import Path
import datetime
import hashlib
import importlib.util
import json
import shutil
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]
LOCAL=ROOT/'nwar_automation'
DEST=Path('E:/NWAR_portable_20261103/NWAR_GLHF_15m_Waves_v2')
QA=LOCAL/'qa/custom_15m_20261108'
JAVAC='C:/Program Files/Eclipse Adoptium/jdk-25.0.3.9-hotspot/bin/javac.exe'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True,exist_ok=True)
    if isinstance(data,dict):
        data=json.dumps(data,indent=2,ensure_ascii=False).encode('utf8')
    if isinstance(data,str):
        data=data.encode('utf8')
    path.write_bytes(data)


def main():
    DEST.mkdir(parents=True,exist_ok=True)
    QA.mkdir(parents=True,exist_ok=True)
    import sys
    sys.path.insert(0,str(ROOT/'nwar_portable/templates'))
    from patch_glhf_all_surface_caps import transform
    old_zip=DEST.parent/'NWAR_GLHF_All_Waves_No_Surface_Cap.zip'
    with zipfile.ZipFile(old_zip) as z:
        variants=json.loads(z.read('glhf_all_surface_caps_manifest.json'))['variants']
    originals={
        'NwarWave.java':DEST.parent/'NWAR_GLHF_Transfer_v4/engine/NwarWave.java',
        'NwarBichromatic.java':DEST.parent/'NWAR_GLHF_W08bi_Resume_2606/app/NwarBichromatic.java'}
    for name,source in originals.items():
        source_bytes=source.read_bytes()
        assert digest(source_bytes) in variants
        uncapped=transform(source_bytes.decode('utf8')).encode('utf8')
        assert digest(uncapped)==variants[digest(source_bytes)]['patched_sha256']
        old='caseId.matches("CUSTOM[0-9]{3,}")&&H>=.25&&H<=1.5&&lambda>=20&&lambda<=40'
        assert uncapped.decode('utf8').count(old)==1
        revised=uncapped.decode('utf8').replace(old,old.replace('lambda>=20','lambda>=15')).encode('utf8')
        write(DEST/'payload'/name,revised)
        entry=dict(macro=name,patched_sha256=digest(revised),releases=['2602','2606'])
        for sha,record in list(variants.items()):
            if record['macro']==name:
                variants[sha]=entry.copy()
        variants[digest(uncapped)]=entry.copy()
        variants[digest(revised)]=entry.copy()
    results=[]
    for build,release in [('21.02.007','2602'),('21.04.009','2606')]:
        cp=f'E:/Program Files/Siemens/{build}-R8/STAR-CCM+{build}-R8/star/lib/java/platform/modules/ext/*'
        for location,label in [(LOCAL,'ThinkPad'),(DEST/'payload','GLHF')]:
            output=QA/'classes'/label/release
            output.mkdir(parents=True,exist_ok=True)
            sources=[str(location/name) for name in originals]
            proc=subprocess.run([JAVAC,'-cp',cp,'-d',str(output),*sources],capture_output=True,text=True,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
            results.append(dict(target=label,release=release,passed=proc.returncode==0,messages=proc.stderr))
            write(QA/'compile.json',dict(results=results))
            if proc.returncode:
                raise RuntimeError('Compilation failed: '+label+' '+release+' '+proc.stderr[-2000:])
            print('Compiled',label,release,flush=True)
    stamp=datetime.datetime.now().astimezone().isoformat()
    for name,receipt in [('NwarWave.java','compile_receipt.json'),('NwarBichromatic.java','bichromatic_w08.json')]:
        path=LOCAL/receipt
        info=json.loads(path.read_text(encoding='utf8'))
        info.update(macro_sha256=digest((LOCAL/name).read_bytes()),compiled_at=stamp,
                    custom_wavelength_range_m=[15,40],custom_range_verification=str(QA/'compile.json'))
        write(path,info)
    write(DEST/'manifest.json',dict(id='glhf_custom_15m_20261108_v2',variants=variants,compiled=results[1::2]))
    for name in ('patch_glhf_15m.py',):
        shutil.copy2(ROOT/'nwar_portable/templates'/name,DEST/name)
    cmd='''@echo off
setlocal
set "PYTHONUTF8=1"
set "nwar_log=%TEMP%\\NWAR_GLHF_15m_Waves.log"
echo GLHF 15-40 m wavelength patch >"%nwar_log%"
set "nwar_root=%~dp0."
if not exist "%nwar_root%\\runtime\\python.exe" set "nwar_root=%~dp0.."
if not exist "%nwar_root%\\runtime\\python.exe" set "nwar_root=%~dp0..\\.."
if not exist "%nwar_root%\\runtime\\python.exe" goto missing
if not exist "%nwar_root%\\launcher.json" goto missing
"%nwar_root%\\runtime\\python.exe" "%~dp0patch_glhf_15m.py" "%nwar_root%" >>"%nwar_log%" 2>&1
set "nwar_result=%errorlevel%"
goto finish
:missing
echo HOLD: Extract inside the GLHF NWAR folder, beside app and runtime. >>"%nwar_log%"
set "nwar_result=1"
:finish
type "%nwar_log%"
start "" notepad.exe "%nwar_log%"
pause
exit /b %nwar_result%
'''
    write(DEST/'Apply GLHF 15m waves.cmd',cmd.replace('\n','\r\n'))
    write(DEST/'CZYTAJ.txt','''GLHF: własne fale o długości 15–40 m, wysokość nadal 0,25–1,50 m.

1. Poczekaj na zakończenie bieżącego przebiegu albo użyj Pause and save.
2. Zamknij dashboard przez Close dashboard.cmd; instalator wymaga nieaktywnej kolejki.
   Nie kasuje kolejki ani wyników. Przy aktywnych lub oczekujących zleceniach wyświetli HOLD.
3. Rozpakuj folder NWAR_GLHF_15m_Waves_v2 do folderu GLHF zawierającego app i runtime.
4. Otwórz Apply GLHF 15m waves.cmd. Powinien wypisać APPLIED albo Already applied.
   Okno pozostaje otwarte, a log otwiera się w Notatniku.
5. Uruchom ponownie dashboard przez Start NWAR.cmd i odśwież Ctrl+F5.
   Możesz dodać H=1,00 m, długość=15 m. Patch sam nie uruchamia obliczeń.

Patch aktualizuje formularz, walidację i makra STAR 2602/2606, zachowując pięć
mierzonych cykli i analizę 2–5. Zgodnie z wcześniejszą zgodą wyłącza próg amplitudy
dla wszystkich fal GLHF; pozostałe kontrole numeryczne pozostają aktywne.
Oryginalne zmieniane pliki trafiają do backup-glhf-15m_... w folderze instalacji.
Nieznana wersja makra lub inna suma kontrolna powoduje HOLD bez zmiany aplikacji.
''')
    archive=DEST.with_suffix('.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in DEST.rglob('*'):
            if p.is_file():
                z.write(p,DEST.name+'/'+p.relative_to(DEST).as_posix())
    print('Patch archive',str(archive),'bytes',archive.stat().st_size)


if __name__=='__main__':
    main()
