"""Create an independent evidence copy for a language-only report revision."""
from pathlib import Path
import hashlib,json,shutil,zipfile
SRC=Path('H:/NTNU_RESEARCH_ARCHIVE/NWAR_report_v4_20261110')
OUT=Path('H:/NTNU_RESEARCH_ARCHIVE/NWAR_report_v5_20261110')
TMP=Path(__file__).parent
def sha(p):
 with p.open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert not OUT.exists(),'Keep any existing v5 release intact'
manifest={str(p.relative_to(SRC)):sha(p)for p in SRC.rglob('*')if p.is_file()}
shutil.copytree(SRC,OUT,ignore=shutil.ignore_patterns('NWAR_report_v4.docx','NWAR_report_v4.pdf','checks.json','__pycache__'))
(OUT/'data/v4_preservation_manifest.json').write_text(json.dumps(dict(source_root=str(SRC),sha256=manifest),indent=2),encoding='utf8')
with zipfile.ZipFile(SRC/'NWAR_report_v4.docx')as z:
 parts={n:dict(bytes=len(z.read(n)),sha256=hashlib.sha256(z.read(n)).hexdigest())for n in z.namelist()}
(TMP/'source_package_parts.json').write_text(json.dumps(parts,indent=2),encoding='utf8')
(TMP/'artifact.md').write_text('''# V5 language revision contract
Reference: H:/NTNU_RESEARCH_ARCHIVE/NWAR_report_v4_20261110/NWAR_report_v4.docx
SHA256: 9bda9a930b1b9816c907c7bf17416e2065931e57931cc6ec921a7b14232e4d3b
Reference render: output/nwar_v4_preparation/render_release, 12 reviewed A4 pages.
One portrait A4 section; 15 mm side margins; 0.58 inch top/bottom margins.
Calibri black; Normal 11 pt, 1.03 line spacing, 6 pt space after.
Title 20 pt; Heading 1 14 pt; Heading 2 11.5 pt. Header/footer 8 pt.
Table fills E9EFF2 / F7F8F9 / white; grey 0.5 pt borders; repeated header.
Preserve all nine table XML subtrees, five existing image assets, and three OMML equations.
Preserve source styles, theme, numbering, bibliography hyperlinks and section geometry.
Editable slots: prose in document.xml, version label in header/footer/core metadata.
Main pages 1-3: replace prose with B2 sentences and definitions; four-step section flow.
Reuse the source table and image blocks in the revised main text.
Add only the user-requested qualitative force-direction sketch. Do not renumber existing figures.
Appendices: simplify prose and move prose formulae to Appendix B; retain every numerical value.
Formulae inside protected table/image objects are retained as the table/figure preservation exception.
Bibliographic titles and DOI strings are reference metadata, not rewritten scientific prose.
No source file, solver, campaign or numerical result may be modified.
Fidelity gates: identical table XML, identical original image bytes, preserved source hashes,
all original numerical values retained, no new scientific values, A4 render of every final page.
PL summary: separate one-page document using the same typography and author/date.
''',encoding='utf8')
print('Created a v5 evidence copy; v4 remains immutable.')
