"""Edit a v4 copy: preserve tables/images and rewrite only prose and its placement."""
from pathlib import Path
from copy import deepcopy
import json,hashlib,shutil,re,sys
from docx import Document
from docx.shared import Pt,Inches,RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from content_v5 import MAIN,APP,FORMULAE,EXTRA_A,PL
SRC=Path('H:/NTNU_RESEARCH_ARCHIVE/NWAR_report_v4_20261110/NWAR_report_v4.docx')
OUT=Path('H:/NTNU_RESEARCH_ARCHIVE/NWAR_report_v5_20261110')
PREP=Path(__file__).parent
def sha(p):
 with p.open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert sha(SRC)=='9bda9a930b1b9816c907c7bf17416e2065931e57931cc6ec921a7b14232e4d3b'

def make_sketch():
 sys.path.insert(0,'C:/Users/ThinkPad/Documents/ChatGPT/ntnu science/mesh_study_20261030/.deps')
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 from matplotlib.patches import Ellipse
 fig,ax=plt.subplots(figsize=(7,.92));fig.subplots_adjust(0,0,1,1)
 ax.set(xlim=(0,10),ylim=(-.85,1.65));ax.axis('off')
 ax.add_patch(Ellipse((5,-.44),width=2.1,height=.24,color='#c3c8cc',zorder=1))
 ax.text(5,-.72,'Fixed foil',ha='center',fontsize=9)
 origin=(5,-.12)
 # Account for unequal axis scales so lift and inflow are perpendicular on paper.
 sx,sy=7/10,.92/2.5
 inflow_dx=1.15
 inflow_dy=.62*inflow_dx*sx*sx/(1.56*sy*sy)
 ax.annotate('',xy=(5+inflow_dx,origin[1]+inflow_dy),xytext=origin,arrowprops=dict(arrowstyle='-|>',lw=2,color='#007789'))
 ax.text(6.35,1.0,'Incoming flow',fontsize=9,color='#005c68',va='center')
 ax.annotate('',xy=(4.38,1.44),xytext=origin,arrowprops=dict(arrowstyle='-|>',lw=2,color='#0055a0'))
 ax.text(4.10,1.18,'Lift',fontsize=9,color='#0055a0',ha='right',va='center')
 ax.annotate('',xy=(4.38,-.12),xytext=origin,arrowprops=dict(arrowstyle='-|>',lw=2.4,color='#c15b00'))
 ax.plot([4.38,4.38],[-.12,1.44],ls=':',lw=.7,color='#8a8a8a')
 ax.text(3.83,.20,'Forward part',fontsize=9,color='#a54800',ha='right')
 ax.annotate('Vessel forward',xy=(.6,1.0),xytext=(2.4,1.0),ha='center',va='center',fontsize=8.5,arrowprops=dict(arrowstyle='->',lw=1,color='#555'))
 ax.text(9.8,-.67,'One part of the cycle · qualitative sketch',ha='right',fontsize=7.3,color='#555')
 fig.savefig(OUT/'figures/fixed_foil_thrust_sketch.png',dpi=320)
 fig.savefig(OUT/'figures/fixed_foil_thrust_sketch.svg');plt.close(fig)

def text_para(d,text,size=10.5,style=None,bold=False):
 p=d.add_paragraph(style=style);p.paragraph_format.space_after=Pt(4)
 # Bold only the reader-facing section labels, not the whole paragraph.
 match=re.match(r'^(What we found:|Why:|How sure we are:|What to do next:)\s*(.*)$',text)
 if match:
  p.add_run(match[1]+' ').bold=True;p.add_run(match[2])
 else:p.add_run(text).bold=bold
 for r in p.runs:r.font.name='Calibri';r.font.size=Pt(size);r.font.color.rgb=RGBColor(0,0,0)
 return p

def main():
 make_sketch()
 d=Document(SRC);original=list(d.paragraphs);table_blocks=[deepcopy(t._tbl)for t in d.tables]
 image_blocks={i:deepcopy(original[i]._p)for i in [12,15]}
 changes=[]
 for i,text in APP.items():
  p=original[i];before=p.text;p.text=text
  for run in p.runs:run.font.size=Pt(10 if i not in [34,35,36,70,73,74,75,78,110,111,112,114] else 10.5)
  changes.append(dict(source_paragraph=i,before=before,after=text))
 # Rebuild the main-text slots while retaining original table and image subtrees.
 body=d._element.body;anchor=original[30]._p
 for e in list(body):
  if e is anchor:break
  body.remove(e)
 def insert_main(element):body.insert(body.index(anchor),element)
 for kind,value in MAIN:
  if kind=='table':insert_main(deepcopy(table_blocks[value]));continue
  if kind=='image':insert_main(deepcopy(image_blocks[value]));continue
  if kind=='sketch':
   p=d.add_paragraph();p.paragraph_format.space_after=Pt(3);p.add_run().add_picture(str(OUT/'figures/fixed_foil_thrust_sketch.png'),width=Inches(7.0));insert_main(p._p);continue
  if kind in ['title','h2','page']:
   p=d.add_paragraph(str(value),{'title':'Title','h2':'Heading 2','page':'Heading 1'}[kind])
   if kind=='page':p.paragraph_format.page_break_before=True
  else:
   p=text_para(d,str(value),size={'meta':10,'caption':9.3,'terms':9.4,'small':10.2}.get(kind,10.5))
  insert_main(p._p)
 # Restore source scientific details removed from the short main-text explanations.
 b_anchor=original[37]._p
 p=d.add_paragraph('Appendix A continued   Reference and acceptance checks','Heading 1');p.paragraph_format.page_break_before=True;body.insert(body.index(b_anchor),p._p)
 for text in EXTRA_A:
  p=text_para(d,text,10);body.insert(body.index(b_anchor),p._p)
 # Formulae from prose move to Appendix B. Protected tables/figures stay unchanged.
 p=d.add_paragraph('Appendix B   Equations used in the report','Heading 1');body.insert(body.index(b_anchor),p._p)
 # Keep the original three OMML equations and their response-function definitions together.
 for i in range(46,53):body.insert(body.index(b_anchor),original[i]._p)
 for text in FORMULAE:
  p=text_para(d,text,10.5);p.paragraph_format.space_after=Pt(7);body.insert(body.index(b_anchor),p._p)
 original[37].text='Appendix B continued   Case matrix and model results'
 # Update visible version labels without changing the source header/footer design.
 for s in d.sections:
  for container in [s.header,s.footer]:
   for p in container.paragraphs:
    for r in p.runs:r.text=r.text.replace('report v4','report v5').replace('NWAR v4','NWAR v5')
 d.core_properties.subject='NWAR research report v5 — B2 English'
 d.settings.element.append(OxmlElement('w:updateFields'));d.settings.element[-1].set(qn('w:val'),'true')
 dest=OUT/'NWAR_report_v5.docx';d.save(dest)
 # A separate, one-page Polish summary using the retained report typography.
 pl=Document(SRC)
 for child in list(pl._element.body):
  if child.tag!=qn('w:sectPr'):pl._element.body.remove(child)
 for section in pl.sections:
  section.header.paragraphs[0].text='NWAR   |   Streszczenie v5   |   10 listopada 2026'
  for r in section.header.paragraphs[0].runs:r.font.size=Pt(8)
  for p in section.footer.paragraphs:
   for r in p.runs:r.text=r.text.replace('NWAR v4','NWAR v5')
 for kind,text in PL:
  if kind in ['title','h']:pl.add_paragraph(text,'Title'if kind=='title'else'Heading 2')
  else:text_para(pl,text,10 if kind=='meta' else 11)
 pl.core_properties.author='Julian Serkieza';pl.core_properties.title='NWAR — wyniki i następne kroki';pl.core_properties.subject='NWAR v5 Polish summary'
 pl.save(OUT/'NWAR_v5_streszczenie_PL.docx')
 (OUT/'data/language_change_map.json').write_text(json.dumps(dict(appendix_changes=changes,main_blocks=MAIN,relocated_equations=FORMULAE,relocated_reference_details=EXTRA_A),indent=2,ensure_ascii=False),encoding='utf8')
 for name in ['prepare_v5.py','content_v5.py','build_report_v5.py']:
  shutil.copy2(PREP/name,OUT/'scripts'/name)
 print(json.dumps(dict(english=str(dest),polish=str(OUT/'NWAR_v5_streszczenie_PL.docx'),source_unchanged=sha(SRC)=='9bda9a930b1b9816c907c7bf17416e2065931e57931cc6ec921a7b14232e4d3b')))
if __name__=='__main__':main()
