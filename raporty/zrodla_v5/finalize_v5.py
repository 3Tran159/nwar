"""Package the reviewed language revision without starting any solver."""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys
P=Path(__file__).parent
O=Path('H:/NTNU_RESEARCH_ARCHIVE/NWAR_report_v5_20261110')
S=Path('H:/NTNU_RESEARCH_ARCHIVE/NWAR_report_v4_20261110')
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
reviewed={}
for language,count in [('en',13),('pl',1)]:
    old=P/('render_final2_'+language)
    new=P/('render_final3_'+language)
    pages=sorted(new.glob('page-*.png'))
    assert len(pages)==count
    for n in range(1,count+1):
        name=f'page-{n}.png'
        same=sha(old/name)==sha(new/name)
        assert same or (language=='en' and n in [1,6])
        reviewed[f'{language}/{name}']={'sha256':sha(new/name),'review':'Viewed final page directly' if not same else 'Identical to visually reviewed final2 page'}
for stem,language in [('NWAR_report_v5','en'),('NWAR_v5_streszczenie_PL','pl')]:
    shutil.copy2(P/('render_final3_'+language)/(stem+'.pdf'),O/(stem+'.pdf'))
names=['NWAR_report_v5.docx','NWAR_report_v5.pdf','NWAR_v5_streszczenie_PL.docx','NWAR_v5_streszczenie_PL.pdf']
review={'status':'passed','english_pages_reviewed':13,'polish_pages_reviewed':1,'main_pages':3,'A4':True,'no_clipped_text_or_overlaps':True,'page_images':reviewed,'final_artifact_SHA256':{name:sha(O/name)for name in names},'scope':'All pages reviewed. Tables and original plots retain the v4 content. The new unnumbered sketch is qualitative; lift and inflow are perpendicular in the rendered drawing.'}
(O/'data/v5_visual_review.json').write_text(json.dumps(review,indent=2),encoding='utf8')
shutil.copy2(S/'README.txt',O/'data/README_v4_reference.txt')
readme='''NWAR report v5 | 10 November 2026

AUTHOR: Julian Serkieza
PURPOSE: B2 English language revision of the immutable v4 release.

DELIVERABLES
NWAR_report_v5.docx / .pdf: 3 main pages plus appendices, 13 A4 pages total.
NWAR_v5_streszczenie_PL.docx / .pdf: one-page Polish summary.
checks.json: exact numeric comparison, readability, preservation and rendering checks.

SCOPE AND PRESERVATION
No solver was started. No new solver steps or scientific results were generated.
All nine original tables and five original figures are unchanged.
The unnumbered first-page sketch only explains the force directions.
Prose equations were moved to Appendix B. Formula labels in unchanged tables and
original figures remain in place to preserve those objects exactly.
The v4 source folder is unchanged; data/v4_preservation_manifest.json records its hashes.
All source CSV and JSON evidence is retained without changes.
data/lineage.json retains scientific source paths and hashes.
data/language_change_map.json records the prose changes and relocated details.
data/v5_visual_review.json records the reviewed pages and final artifact hashes.
data/README_v4_reference.txt retains the original data history and reproduction notes.

REPRODUCTION
Use the bundled Python environment with python-docx, lxml, pypdf and Matplotlib.
scripts/content_v5.py contains the language revision.
scripts/build_report_v5.py edits a copy of the source DOCX and draws the sketch.
Render the DOCX files using the bundled render_docx.py and LibreOffice.
scripts/verify_report_v5.py compares numbers, tables, images, equations and source data.
The numerical comparison normalizes displayed numeric notation; it allows prose
consolidation to change repetition counts. All 473 distinct displayed numeric values
and all 551 previously checked numerical claims remain present.
Readability uses the same sentence/word rules for v4 and v5. It excludes titles,
headings, author/date, tables, figures and captions from the main prose metric.
An additional metric includes captions. Full sentence inventories are in checks.json.
Run the verifier after rendering. A changed artifact requires a new visual review.
'''
(O/'README.txt').write_text(readme,encoding='utf8')
for name in ['verify_report_v5.py','finalize_v5.py']:
    shutil.copy2(P/name,O/'scripts'/name)
subprocess.run([sys.executable,str(P/'verify_report_v5.py')],check=True)
c=json.loads((O/'checks.json').read_text(encoding='utf8'))
assert c['checks_passed'] and c['layout_review']['status']=='passed'
print(json.dumps({'done':True,'before':c['readability']['v4']['mean_words'],'after':c['readability']['v5']['mean_words'],'max_before':c['readability']['v4']['maximum_words'],'max_after':c['readability']['v5']['maximum_words'],'all_pages_reviewed':True}))
