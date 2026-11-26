from pathlib import Path
import runpy,json,zipfile
from pypdf import PdfReader
HERE=Path(__file__).resolve().parent
p=HERE/'make_report.py';s=p.read_text(encoding='utf-8').replace("['Siatka',","['ID',");p.write_text(s,encoding='utf-8')
runpy.run_path(str(p),run_name='__main__')
r=PdfReader(HERE/'mesh_study_PL.pdf');assert len(r.pages)==6
print(json.dumps({'pages':len(r.pages),'page_text_lengths':[len(p.extract_text()) for p in r.pages],'linked_references':sum(len(p.get('/Annots',[])) for p in r.pages)}))
with zipfile.ZipFile(HERE/'mesh_study_package.zip','w',zipfile.ZIP_DEFLATED) as z:
 for n in ['mesh_study_PL.pdf','mesh_comparison.png','mesh_comparison.svg','mesh_variants_history.png','mesh_variants_history.svg','mesh_comparison_values.csv','evidence.json']:z.write(HERE/n,n)
print('Final report and deliverable package ready.')
