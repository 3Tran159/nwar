"""Verify language revision fidelity, numbers, readability, and final render geometry."""
from pathlib import Path
from collections import Counter
from decimal import Decimal
import re,json,hashlib,zipfile,csv
from lxml import etree
from docx import Document
from pypdf import PdfReader
SRC=Path('H:/NTNU_RESEARCH_ARCHIVE/NWAR_report_v4_20261110')
OUT=Path('H:/NTNU_RESEARCH_ARCHIVE/NWAR_report_v5_20261110')
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','m':'http://schemas.openxmlformats.org/officeDocument/2006/math'}
def sha(p):
 with p.open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def norm(t):return re.sub(r'\s+',' ',t).strip()
def source_text(root):return ' '.join(root.xpath('//w:t/text()|//m:t/text()',namespaces=NS))
def numeric_values(text,polish=False):
 # Scientific values, not case IDs, variable indices, version labels or file names.
 t=text.replace('−','-')
 if polish:t=re.sub(r'(?<=\d),(?=\d)','.',t)
 t=re.sub(r'\b(?:W\d+[a-z]*|C01|M\d+|HF_012_wall|v[345])\b',' ',t)
 t=re.sub(r'\b[\w_]+\.(?:py|json|csv|txt|docx|pdf)\b',' ',t)
 t=re.sub(r'(?<=[A-Za-zα-ω])\d+','',t)
 sup=str.maketrans('⁻⁰¹²³⁴⁵⁶⁷⁸⁹','-0123456789')
 def sci(m):return format(Decimal(m[1])*(Decimal(10)**int(m[2].translate(sup))),'f')
 t=re.sub(r'(-?\d+(?:\.\d+)?)\s*×\s*10([⁻⁰¹²³⁴⁵⁶⁷⁸⁹]+)',sci,t)
 return Counter(str(Decimal(m).normalize())for m in re.findall(r'(?<![A-Za-z0-9])-?\d+(?:\.\d+)?',t))
def main_paragraphs(d,include_captions=False):
 result=[]
 for p in d.paragraphs:
  if p.text.startswith('Appendix A'):break
  if p.style.name!='Normal' or not p.text or p.text.startswith('Julian'):continue
  if p._p.xpath('.//w:drawing'):continue
  if not include_captions and p.text.startswith(('Figure ','Table ')):continue
  result.append(p.text)
 return result
def split_sentences(paras):
 result=[]
 for t in paras:
  t=re.sub(r'^(What we found:|Why:|How sure we are:|What to do next:)\s*','',t)
  t=re.sub(r'^(?:Figure|Table) \d+\.\s*','',t)
  t=re.sub(r'\[[\d–, -]+\]','',t)
  t=re.sub(r'(?<=\d)\.(?=\d)','<DECIMAL>',t)
  result.extend(s.replace('<DECIMAL>','.')for s in re.split(r'(?<=[.!?])\s+',t.strip())if s.strip())
 return result
def metrics(paras):
 sentences=split_sentences(paras);counts=[len(s.split())for s in sentences]
 return dict(sentence_count=len(sentences),word_count=sum(counts),mean_words=sum(counts)/len(counts),maximum_words=max(counts),sentences_over_20=sum(n>20 for n in counts),sentences=[dict(text=s,words=n)for s,n in zip(sentences,counts)])

a=Document(SRC/'NWAR_report_v4.docx');b=Document(OUT/'NWAR_report_v5.docx')
old_checks=read(SRC/'checks.json');checks=dict(source_version='v4',output_version='v5',language_only=True,new_solver_processes=0,new_solver_steps=0,new_scientific_results=False)
with zipfile.ZipFile(SRC/'NWAR_report_v4.docx')as za,zipfile.ZipFile(OUT/'NWAR_report_v5.docx')as zb:
 ra=etree.fromstring(za.read('word/document.xml'));rb=etree.fromstring(zb.read('word/document.xml'))
 ta=ra.xpath('//w:tbl',namespaces=NS);tb=rb.xpath('//w:tbl',namespaces=NS)
 assert len(ta)==len(tb)==9
 assert [etree.tostring(v)for v in ta]==[etree.tostring(v)for v in tb]
 checks['tables']={'count':9,'all_XML_identical':True}
 media=[n for n in za.namelist()if n.startswith('word/media/')]
 assert len(media)==5 and all(za.read(n)==zb.read(n)for n in media)
 assert len([n for n in zb.namelist()if n.startswith('word/media/')])==6
 checks['figures']={'original_figures_identical':5,'new_qualitative_sketch':1,'original_media_SHA256':{n:hashlib.sha256(za.read(n)).hexdigest()for n in media}}
 protected=['word/styles.xml','word/theme/theme1.xml','word/numbering.xml','word/fontTable.xml']
 checks['template_fidelity']={n:za.read(n)==zb.read(n)for n in protected if n in za.namelist()}
 assert all(checks['template_fidelity'].values())
 oldmath=ra.xpath('//m:oMath',namespaces=NS);newmath=rb.xpath('//m:oMath',namespaces=NS)
 assert len(oldmath)==len(newmath)==3 and [etree.tostring(v)for v in oldmath]==[etree.tostring(v)for v in newmath]
 texta,textb=source_text(ra),source_text(rb);na,nb=numeric_values(texta),numeric_values(textb)
 missing=sorted(set(na)-set(nb));extra=sorted(set(nb)-set(na))
 checks['numeric_value_inventory']={'source_unique_values':len(na),'v5_unique_values':len(nb),'missing_values':missing,'new_values':extra,'identical_values':not missing and not extra,'method':'Exact Decimal value-set comparison across all body text, tables and OMML. Case IDs, variable indices and file/version names excluded. Repetition counts may change with prose consolidation.'}
 assert not missing and not extra,checks['numeric_value_inventory']
 # Every previously checked displayed number is still present in v5.
 flattened=norm(textb);display_checks=[]
 for claim in old_checks['numerical_claims']:
  rendered=norm(claim['rendered']);present=rendered in flattened
  # Numeric inventory also handles equivalent regrouping in moved equations.
  values=numeric_values(rendered);retained=set(values)<=set(nb)
  assert present or retained,claim
  display_checks.append(dict(source=claim['source'],v4_text=claim['rendered'],v4_recomputed_value=claim['value'],retained=True,exact_display_string_present=present,display_value_tolerance=0,comparison_basis='Exact displayed value; unchanged source CSV/JSON retains full precision.'))
 checks['v4_numerical_claims_retained']=display_checks;checks['v4_numerical_claim_count']=len(display_checks)
 # Every editable equation and all relocated prose formulae lie inside Appendix B.
 section=None;equation_sections=[];outside=[]
 for child in rb.xpath('/w:document/w:body/*',namespaces=NS):
  if child.tag=='{'+NS['w']+'}tbl':continue # Explicit unchanged-table exception.
  text=''.join(child.xpath('.//w:t/text()',namespaces=NS))
  if text.startswith('Appendix '):section=text.split()[1]
  if child.xpath('.//m:oMath',namespaces=NS):equation_sections.append(section)
  if section!='B' and any(x in text for x in ['αeff =','Cparallel =','Cnormal =','ΔFx(κ) =','Di =','Qx =','ΔFx = sθa²']):outside.append(text)
 assert equation_sections==['B','B','B'] and not outside
 checks['equations']={'original_OMML_preserved':3,'all_editable_equations_in_Appendix_B':True,'prose_formulae_outside_B':outside,'preservation_exception':'Formulae/labels inside the nine unchanged tables and five original images are preserved as requested.'}

readability={}
for name,d in [('v4',a),('v5',b)]:
 readability[name]=metrics(main_paragraphs(d));readability[name+'_including_captions']=metrics(main_paragraphs(d,True))
assert readability['v5']['mean_words']<=20 and readability['v5']['maximum_words']<=22
abstract=b.paragraphs[2].text
assert len(split_sentences([abstract]))==5 and split_sentences([abstract])[-1].startswith('Next, test W05')
checks['readability']=readability
checks['readability_method']='Whitespace-delimited words; decimals protected from sentence splitting. Main prose excludes titles, author/date, headings, tables, images and captions. Reader-facing labels excluded. A second metric includes captions, using the same method for v4 and v5.'
checks['abstract_sentence_count']=5
# Repeated uncertainties remain in Table 2, with one labelled uncertainty statement per main section.
checks['main_section_flow']={'what_we_found':sum(p.text.startswith('What we found:')for p in b.paragraphs),'why':sum(p.text.startswith('Why:')for p in b.paragraphs),'how_sure':sum(p.text.startswith('How sure we are:')for p in b.paragraphs),'next':sum(p.text.startswith('What to do next:')for p in b.paragraphs)}
assert checks['main_section_flow']==dict(what_we_found=6,why=6,how_sure=6,next=6)

pl=Document(OUT/'NWAR_v5_streszczenie_PL.docx');plvalues=numeric_values(' '.join(p.text for p in pl.paragraphs if not p.text.startswith('Julian')),True)
assert set(plvalues)<=set(nb),sorted(set(plvalues)-set(nb))
checks['polish_summary']={'all_numeric_values_from_report':True,'numeric_values':sorted(plvalues),'no_equations':not any('='in p.text for p in pl.paragraphs)}
manifest=read(OUT/'data/v4_preservation_manifest.json');unchanged={n:sha(Path(manifest['source_root'])/n)==v for n,v in manifest['sha256'].items()}
assert all(unchanged.values());checks['v4_entire_release_unchanged']=True
checks['data_files_unchanged']={str(p.relative_to(SRC)):sha(p)==sha(OUT/p.relative_to(SRC))for p in SRC.rglob('*')if p.is_file() and p.suffix in ['.csv','.json'] and p.name!='checks.json'}
assert all(checks['data_files_unchanged'].values())
for name in ['NWAR_report_v5','NWAR_v5_streszczenie_PL']:
 pdf=PdfReader(OUT/(name+'.pdf'));texts=[p.extract_text()for p in pdf.pages]
 assert all(abs(float(p.mediabox.width)-210/25.4*72)<1 and abs(float(p.mediabox.height)-297/25.4*72)<1 for p in pdf.pages)
 assert all('TBD'not in t for t in texts)
 if name=='NWAR_report_v5':
  assert 'Appendix A' in texts[3] and all('Appendix A'not in t for t in texts[:3])
  checks['english_pages']=len(pdf.pages);checks['main_pages']=3
 else:assert len(pdf.pages)==1;checks['polish_summary']['pages']=1
checks['final_artifacts']={name:dict(sha256=sha(OUT/name),bytes=(OUT/name).stat().st_size)for name in ['NWAR_report_v5.docx','NWAR_report_v5.pdf','NWAR_v5_streszczenie_PL.docx','NWAR_v5_streszczenie_PL.pdf']}
checks['checks_passed']=True;checks['layout_review']='pending final visual inspection'
review_file=OUT/'data/v5_visual_review.json'
if review_file.exists():
 review=read(review_file)
 current={name:item['sha256'] for name,item in checks['final_artifacts'].items()}
 if review.get('final_artifact_SHA256')==current:
  checks['layout_review']=review
(OUT/'checks.json').write_text(json.dumps(checks,indent=2,ensure_ascii=False),encoding='utf8')
print(json.dumps(dict(passed=True,mean_v4=readability['v4']['mean_words'],mean_v5=readability['v5']['mean_words'],max_v4=readability['v4']['maximum_words'],max_v5=readability['v5']['maximum_words'],source_numbers_preserved=True,english_pages=checks['english_pages'],polish_pages=1)))
