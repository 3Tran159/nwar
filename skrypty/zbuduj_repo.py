# Buduje lekkie repo NWAR (KOPIUJE, niczego nie przenosi ani nie kasuje).
# python zbuduj_repo.py [cel]   domyslnie F:\20_DANE_OBLICZEN\NTNU_NWAR\nwar
import shutil, sys, json, csv, re, datetime
from pathlib import Path

NS = Path(r"C:\Users\ThinkPad\Documents\ChatGPT\ntnu science")
FN = Path(r"F:\20_DANE_OBLICZEN\NTNU_NWAR")
HA = Path(r"H:\10_ARCHIWUM_PROJEKTOW\NTNU_RESEARCH_ARCHIVE")
DST = Path(sys.argv[1]) if len(sys.argv) > 1 else FN / "nwar"

LIGHT = {".py", ".java", ".js", ".cjs", ".html", ".css", ".json", ".jsonl", ".csv", ".md", ".txt",
         ".ps1", ".vbs", ".svg", ".png", ".pdf", ".docx", ".properties", ".mp4", ".xlsx"}
HEAVY = {".sim", ".simh", ".sim~", ".zip", ".cgns", ".mat", ".npz", ".dat", ".h5", ".msi", ".gz"}
MAXB = 5 * 2**20
SKIP_DIRS = {"__pycache__", ".mplconfig", ".deps", ".venv", "venv", "site-packages", "profile", "node_modules",
             "compiled", "compiled_global_ramp", ".nwar_patch_backups", "installer_tests", "qa"}
SKIP_NAME = re.compile(r"(hash_cache\.json|\.stale\.|_before_|backup|\.przed_|\.lock|AGENTS\.md)", re.I)

copied = []

def ok(f, base, exts=LIGHT, maxb=MAXB):
    rel = f.relative_to(base)
    if any(p in SKIP_DIRS or p.lower().startswith("backup") or "_backup" in p.lower() for p in rel.parts[:-1]):
        return False
    return f.suffix.lower() in exts and f.stat().st_size <= maxb and not SKIP_NAME.search(f.name)

def cp(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(src, dst)
    except PermissionError:
        print('ZAJETY (pominiety):', src); return
    copied.append([str(dst.relative_to(DST)), str(src), src.stat().st_size])

def take(src, dst, recursive=True, exts=LIGHT, maxb=MAXB, java_to_makra=True):
    if not src.exists():
        print("BRAK", src); return
    files = src.rglob("*") if recursive else src.iterdir()
    for f in files:
        if not f.is_file() or not ok(f, src, exts, maxb):
            continue
        if java_to_makra and f.suffix == ".java":
            cp(f, DST / "star" / "makra" / f.name)
        else:
            cp(f, dst / f.relative_to(src))

# 1. automatyzacja kampanii fal (kontroler, analiza, dashboard) + makra STAR
take(NS / "nwar_automation", DST / "automatyzacja", recursive=False)
take(NS / "nwar_automation" / "reviews", DST / "wyniki" / "przeglady_kampanii")
for f in [NS / "output" / "NwarDragPhaseFields.java",
          NS / "output" / "nwar_v3_preparation" / "NwarSavedMethodAudit.java"]:
    if f.exists(): cp(f, DST / "star" / "makra" / "diagnostyka" / f.name)
# 2. pakiet przenosny GLHF (STAR-CCM+ 2606 na zdalnej maszynie)
take(NS / "nwar_portable", DST / "glhf_pakiet")
for f in FN.joinpath("NWAR_portable_20261103").glob("*.ps1"):
    cp(f, DST / "glhf_pakiet" / "instalatory" / f.name)
for f in FN.joinpath("NWAR_portable_20261103").glob("*/README.txt"):
    cp(f, DST / "glhf_pakiet" / "wydania" / f.parent.name / "README.txt")
# 3. studium siatki (GCI) i optymalizacja siatki M10-M13
take(NS / "mesh_study_20261030", DST / "siatka" / "studium_GCI_20261030")
mo = FN / "ntnu_mesh_optimization_20261030"
take(mo, DST / "siatka" / "optymalizacja_M10_M13", recursive=False, java_to_makra=False)
for sub in ["results_catalog", "report_export_20261101", "approved_wave_plan_20261101", "wave_campaign_20261101",
            "wave_surface_only", "cfd_review_20261031_0933", "M13_wave_direct_20261031"]:
    take(mo / sub, DST / "siatka" / "optymalizacja_M10_M13" / sub,
         exts={".md", ".json", ".txt", ".py", ".java", ".csv", ".png", ".svg", ".pdf"}, maxb=2 * 2**20, java_to_makra=False)
take(FN / "ntnu_siatki_i_fale_2026-10" / "handoffs", DST / "siatka" / "siatki_i_fale_2026-10" / "handoffs")
for f in FN.joinpath("ntnu_siatki_i_fale_2026-10").rglob("README_INSPECTION.txt"):
    cp(f, DST / "siatka" / "siatki_i_fale_2026-10" / "inspekcje" / f.parent.name / f.name)
take(FN / "ntnu_cfd_night_20261028" / "visualisations_20261029", DST / "siatka" / "noc_CFD_20261028")
# 4. wyniki koncowe (sprawdzone kopie) + pakiet danych raportu
take(NS / "WYNIKI_KONCOWE" / "02_SIATKA_M13", DST / "wyniki" / "siatka_M13")
take(NS / "WYNIKI_KONCOWE" / "03_FALE_DANE_I_WYKRESY", DST / "wyniki" / "fale")
take(HA / "NWAR_final_reports" / "final_20261109_220322_207069", DST / "wyniki" / "pakiet_final_20261109")
# 5. raporty
take(NS / "WYNIKI_KONCOWE" / "01_RAPORTY", DST / "raporty")
take(HA / "NWAR_onepage_v4_20261116", DST / "raporty" / "onepage_v4_20261116")
take(NS / "output" / "nwar_v5_preparation", DST / "raporty" / "zrodla_v5")
for f in [NS / "output" / "NWAR_Godo_NDLL_to_URANS_control.md"]:
    if f.exists(): cp(f, DST / "docs" / f.name)

# 6. inwentarz ciezkich danych (wszystko, co nie trafia do repo i jest duze)
CASE = re.compile(r"(PRE_W04|C01|W0\d[a-z]{0,2}|CUSTOM\d{3}|M1[0-3]|G\d\d_[A-Z])", re.I)
inv = []
roots = [FN] + [p for p in HA.glob("NWAR*") if p.is_dir()] + [Path(r"H:\10_ARCHIWUM_PROJEKTOW\NTNU_T_archiwa\NWAR_report_tools")]
for r in roots:
    for f in r.rglob("*"):
        if not f.is_file() or f.is_relative_to(DST):
            continue
        s = f.stat().st_size
        if f.suffix.lower() in HEAVY or s > MAXB:
            m = CASE.search(str(f.relative_to(r)))
            inv.append([str(r), m.group(1) if m else "", f.suffix.lower(), str(f), round(s / 2**30, 4),
                        datetime.date.fromtimestamp(f.stat().st_mtime).isoformat()])
inv.sort(key=lambda x: -x[4])
(DST / "skrypty").mkdir(parents=True, exist_ok=True)
with open(DST / "ARCHIWUM_DANYCH_inwentarz.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh); w.writerow(["korzen", "przypadek", "typ", "plik", "GB", "data"]); w.writerows(inv)
with open(DST / "skrypty" / "pochodzenie_plikow.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh); w.writerow(["w_repo", "zrodlo", "bajty"]); w.writerows(sorted(copied))
cp(Path(__file__), DST / "skrypty" / "zbuduj_repo.py")
tot = sum(f.stat().st_size for f in DST.rglob("*") if f.is_file() and ".git" not in f.parts)
print(json.dumps({"repo": str(DST), "MB": round(tot / 2**20, 1), "plikow": len(copied),
                  "ciezkich": len(inv), "ciezkie_GB": round(sum(r[4] for r in inv), 1)}, ensure_ascii=False))
