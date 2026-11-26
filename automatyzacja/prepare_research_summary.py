"""CPU-only evidence snapshot and editable research summary; never launches STAR."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','1')
from common import *
import shutil
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import h5py
from docx import Document
from docx.shared import Inches,Pt,RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT,WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

OUT=Path('H:/NTNU_RESEARCH_ARCHIVE/NWAR_research_summary_20261109')
AOA=DATA/'analyses/W04e_aoa_20261107'

def csvfile(path,rows):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def pictures(source,audit):
    figdir=OUT/'figures';figdir.mkdir(exist_ok=True)
    q=audit['Q_data'];styles={'W01':'o','W02':'o','W03':'o'}
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(1,2,figsize=(10.6,3.65),layout='constrained')
    series=sorted([r for r in q if r['H_m']==1.5],key=lambda r:r['lambda_m'])
    axes[0].plot([r['lambda_m']for r in series],[r['delta_D_N']for r in series],color='#007789',lw=1.2)
    for r in series:
        axes[0].scatter(r['lambda_m'],r['delta_D_N'],marker='s',color='#007789',s=42,zorder=3)
        axes[0].annotate(r['case'],(r['lambda_m'],r['delta_D_N']),xytext=(0,9),textcoords='offset points',ha='center',fontsize=9)
    axes[0].set(title='H = 1.5 m',xlabel='Wavelength [m]',ylabel='Mean ΔFx from C01 [N]',ylim=(-11,0),xlim=(12,42))
    for lam,color in[(15,'#9467bd'),(20,'#0072b2'),(30,'#d55e00')]:
        ss=sorted([r for r in q if r['lambda_m']==lam],key=lambda r:r['H_m'])
        axes[1].plot([r['H_m']for r in ss],[r['delta_D_N']for r in ss],label=f'λ = {lam} m',color=color,lw=1.2)
        for r in ss:
            axes[1].scatter(r['H_m'],r['delta_D_N'],marker=styles.get(r['case'],'s'),color=color,s=40,zorder=3)
    axes[1].set(title='Height series at fixed wavelength',xlabel='Wave height H [m]',ylabel='Mean ΔFx from C01 [N]',ylim=(-11,0),xticks=[.25,.5,.75,1,1.25,1.5])
    axes[1].legend(frameon=False,fontsize=9)
    for ax in axes:ax.grid(alpha=.2);ax.axhline(0,color='#667777',lw=.7)
    for ext in ('png','svg'):fig.savefig(figdir/('regular_trends.'+ext),dpi=240)
    plt.close(fig)
    raw=rows(AOA/'W04e_aoa_force_phase_cycles.csv');ph=np.array(sorted({float(r['phase_deg'])for r in raw}))
    keys=('delta_Fx_N','delta_pressure_Fx_N','delta_viscous_Fx_N','aoa_deg')
    values={k:np.array([np.mean([float(r[k])for r in raw if float(r['phase_deg'])==v])for v in ph])for k in keys}
    fig,axs=plt.subplots(2,1,figsize=(10,5.25),sharex=True,layout='constrained',gridspec_kw={'height_ratios':[1.5,1.]})
    for key,label,color,ls in [('delta_Fx_N','Total ΔFx','#202d35','-'),('delta_pressure_Fx_N','Pressure part','#0072b2','--'),('delta_viscous_Fx_N','Viscous part','#d55e00',':')]:
        axs[0].plot(ph,values[key],label=label,color=color,ls=ls,lw=1.6)
    axs[0].set(ylabel='Force difference [N]');axs[0].legend(frameon=False,ncol=3,loc='lower left',bbox_to_anchor=(0,1.02),fontsize=9)
    axs[1].plot(ph,values['aoa_deg'],color='#008574',lw=1.5);axs[1].set(ylabel='Local inflow angle α [°]',xlabel='Wave phase at x = 0 [°]',xticks=[0,90,180,270,360],xlim=(0,360))
    for ax in axs:ax.axvspan(100,270,color='#e3e8e8',zorder=0);ax.axhline(0,color='#667777',lw=.6);ax.grid(alpha=.2)
    for ext in ('png','svg'):fig.savefig(figdir/('W04e_phase_mechanism.'+ext),dpi=220)
    plt.close(fig)
    for name in ('force_wave_comparison.png','force_wave_comparison.svg','force_wave_comparison_interactive.html','W08bi_time_history.png','W08bi_quasi_steady.png'):
        shutil.copy2(source/name,figdir/name)

def table(doc,headers,body,widths=None,size=10):
    t=doc.add_table(rows=1,cols=len(headers));t.alignment=WD_TABLE_ALIGNMENT.CENTER;t.autofit=False
    for i,h in enumerate(headers):t.rows[0].cells[i].text=h
    for row in body:
        for c,value in zip(t.add_row().cells,row):c.text=str(value)
    for row_idx,row in enumerate(t.rows):
        for i,c in enumerate(row.cells):
            if widths:c.width=Inches(widths[i])
            c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            pr=c._tc.get_or_add_tcPr();b=OxmlElement('w:tcBorders')
            for edge in ('top','left','bottom','right'):
                e=OxmlElement('w:'+edge);e.set(qn('w:val'),'single');e.set(qn('w:sz'),'4');e.set(qn('w:color'),'D9D9D9');b.append(e)
            pr.append(b);margin=OxmlElement('w:tcMar')
            for edge,n in [('top',65),('bottom',65),('left',80),('right',80)]:
                e=OxmlElement('w:'+edge);e.set(qn('w:w'),str(n));e.set(qn('w:type'),'dxa');margin.append(e)
            pr.append(margin)
            if row_idx==0:
                sh=OxmlElement('w:shd');sh.set(qn('w:fill'),'E8EEF1');pr.append(sh)
            for p in c.paragraphs:
                p.paragraph_format.space_after=Pt(0);p.paragraph_format.space_before=Pt(0);p.paragraph_format.line_spacing=1.05
                if i>0:p.alignment=WD_ALIGN_PARAGRAPH.CENTER
                for r in p.runs:r.font.size=Pt(size);r.bold=row_idx==0
        trpr=row._tr.get_or_add_trPr();split=OxmlElement('w:cantSplit');trpr.append(split)
    repeat=OxmlElement('w:tblHeader');t.rows[0]._tr.get_or_add_trPr().append(repeat)
    return t

def para(doc,text,bold=False):
    p=doc.add_paragraph();p.add_run(text).bold=bold;return p

def image(doc,name,width=6.5):
    p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    run=p.add_run();run.add_picture(str(OUT/'figures'/name),width=Inches(width))
    for node in run._element.xpath('.//wp:docPr'):node.set('descr',name.replace('_',' ').rsplit('.',1)[0])
    p.paragraph_format.space_after=Pt(3)

def caption(doc,text):
    p=doc.add_paragraph(text,style='Caption');p.paragraph_format.space_after=Pt(9)

def heading(doc,text,new=False):
    if new:doc.add_page_break()
    doc.add_heading(text,level=1)

def build():
    OUT.mkdir(parents=True,exist_ok=True);evidence=OUT/'evidence';evidence.mkdir(exist_ok=True)
    published=read(HERE/'latest_report.json');source=Path(published['directory']);audit=read(source/'audit.json')
    regular=[r for r in audit['results']if r.get('project_accepted')];q=audit['Q_data'];lift={r['case']:r for r in audit['lift_trend']}
    assert len(q)==len(regular) and all(r['Q_CD']<0 for r in q)
    metrics=read(AOA/'W04e_aoa_metrics.json');bi=audit['w08bi_snapshot'];pre=read(DATA/'PRE_W04_20261102/calm_receipt.json')
    accepted={r['case']:r for r in regular};matrix=[];inventory=[]
    for item in q:
        r=accepted[item['case']];setup=read(Path(r['folder'])/'wave_setup_audit.json');cells=setup.get('cells')
        if cells is None:
            for receipt in r.get('source_segments',[]):
                cells=read(Path(receipt.get('path','')).parent/'wave_setup_audit.json').get('cells')
                if cells:break
        row=dict(case=r['case'],H_m=r['H'],lambda_m=r['L'],Q_Cx=item['Q_CD'],delta_Fx_N=item['delta_D_N'],
                 delta_Fx_pct=item['relative_change_pct'],delta_Fz_N=lift[r['case']]['delta_L_N'],measured_cycles=r['cycles']['count'],
                 analyzed_cycles='2 3 4 5',end_time_s=r['time_s'],mesh_cells=cells,run_id=r['id'],
                 mean_window_start_s=item['window_start_s'],mean_window_end_s=item['window_end_s'],phase_probe_x_m=item['phase_probe_x_m'])
        matrix.append(row)
        checkpoint=r.get('validation',{}).get('checkpoint')
        if not checkpoint:checkpoint=str(Path(r['folder'])/('wave_pilot_extended_final.sim'if r.get('external')else'wave_pilot_final.sim'))
        inventory.append(dict(case=r['case'],run_id=r['id'],final_SIM_path=checkpoint,physical_SIM_path=str(Path(checkpoint).resolve()),
                              exists=Path(checkpoint).is_file(),checksum_scope='Published verification receipt; no new full-SIM hash scan',
                              SHA256=r.get('validation',{}).get('checkpoint_sha256')or read(Path(r['folder'])/'final_integrity.json').get('sha256','')))
    csvfile(evidence/'accepted_case_matrix.csv',matrix);csvfile(evidence/'final_SIM_inventory.csv',inventory)
    snapshot={k:audit[k]for k in ('generated_at','C01','project_policy','mesh','Q_data','lift_trend','w08bi_snapshot','force_wave_comparison')}
    snapshot['case_results']=[{k:r.get(k)for k in ('case','id','folder','H','L','time_s','project_accepted','health','cycles','force_wave_response','validation')}for r in regular]
    write(evidence/'campaign_snapshot.json',snapshot)
    for name in ('W04e_aoa_metrics.json','W04e_aoa_evidence.json','W04e_phase_sector_metrics.csv','W04e_same_aoa_different_force.csv','W04e_aoa_force_phase_cycles.csv'):
        shutil.copy2(AOA/name,evidence/name)
    shutil.copy2(HERE/'project_policy.json',evidence/'project_policy.json')
    jobs_now=jobs();k=next(j for j in jobs_now if j['case_id']=='W04k');kmon=read(Path(k['folder'])/'monitor.json')
    transfer=read(Path('E:/NWAR_portable_20261103/NWAR_GLHF_W04k_Resume_20261109/manifest.json'))
    transferred=bool(transfer.get('checkpoint_sha256') and read(Path(k['folder'])/'native_solve/stage_result.json').get('controller_reason')=='user_stop')
    kstatus='Stopped by user; healthy checkpoint prepared for GLHF' if transferred else k['status']
    ktime=transfer['time_s'] if transferred else kmon.get('time_s',0)
    from glhf_custom_import import imported_entries
    imported={item['case_id']:item for item in imported_entries()}
    def import_status(case):
        item=imported.get(case)
        if not item:return 'Final GLHF export and independent review pending'
        receipt=item['validation']
        return (('Accepted after independent native-save and cycle review' if receipt['project_accepted'] else
                 'Saved diagnostic; acceptance '+receipt['run_verification'])+
                f"; {receipt['measured_cycles']} complete measured cycles; final SIM t = {receipt['time_s']:.4f} s")
    pending=dict(snapshot_at=now(),ThinkPad_W04k=dict(status=kstatus,time_s=ktime,job_id=k['id'],GLHF_native_start_verified=False),
                 GLHF_W04i=import_status('W04i'),
                 GLHF_W04j=import_status('W04j'),
                 further_ThinkPad_jobs=[j['case_id']for j in jobs_now if j['status']in('queued','deferred')])
    write(evidence/'pending_results.json',pending)
    pictures(source,audit)
    den=3855.6;fx0=audit['C01']['CD']*den;fz0=audit['C01']['CL']*den
    pressure_share=metrics['exact_time_window_means']['delta_pressure_Fx_N']/metrics['exact_time_window_means']['delta_Fx_N']*100
    sectors=[dict(s,phase_fraction=(s['end_deg']-s['start_deg'])/360,mean_contribution_N=s['delta_Fx_mean_N']*(s['end_deg']-s['start_deg'])/360)for s in metrics['sectors']]
    csvfile(evidence/'phase_sector_contributions.csv',sectors)
    doc=Document();sec=doc.sections[0];sec.page_width=Inches(8.5);sec.page_height=Inches(11)
    sec.top_margin=Inches(.7);sec.bottom_margin=Inches(.65);sec.left_margin=sec.right_margin=Inches(1.)
    for name in ('Normal','Title','Subtitle','Heading 1','Heading 2','Caption'):
        st=doc.styles[name];st.font.name='Calibri';st.font.color.rgb=RGBColor(0,0,0)
    normal=doc.styles['Normal'];normal.font.size=Pt(11);normal.paragraph_format.space_after=Pt(7);normal.paragraph_format.line_spacing=1.08
    doc.styles['Title'].font.size=Pt(25);doc.styles['Heading 1'].font.size=Pt(17);doc.styles['Heading 1'].paragraph_format.space_after=Pt(10)
    doc.styles['Heading 2'].font.size=Pt(12);doc.styles['Caption'].font.size=Pt(9)
    doc.core_properties.title='NWAR hydrofoil campaign research summary';doc.core_properties.author='NWAR research project'
    doc.add_paragraph('NWAR hydrofoil campaign',style='Title')
    doc.add_paragraph('Research summary and evidence for the next analysis stage',style='Subtitle')
    para(doc,'Evidence snapshot 9 November 2026',True)
    para(doc,f'The {len(regular)} project-accepted regular-wave cases show a lower mean horizontal force than the original calm-water reference. The reductions range from {min(abs(r["delta_D_N"])for r in q):.2f} to {max(abs(r["delta_D_N"])for r in q):.2f} N, or {min(abs(r["relative_change_pct"])for r in q):.2f} to {max(abs(r["relative_change_pct"])for r in q):.2f}%. These are differential results for a fixed, quasi-two-dimensional foil. They establish a repeatable trend within the campaign acceptance policy; they do not constitute a validated vessel-level efficiency prediction.')
    para(doc,'The strongest mechanistic evidence comes from W04e. Its mean force reduction is dominated by the pressure contribution. The broad 100–270° portion is flatter but still adds horizontal force relative to C01. Negative contributions in the remaining phases outweigh that penalty. Local inflow angle alone does not uniquely determine the horizontal force.')
    para(doc,'The bichromatic result extends the observed negative mean shift to a two-component diagnostic. A supplied quasi-steady model predicts the sign of the horizontal change but overpredicts its magnitude and predicts the wrong sign for the vertical mean change. A causal explanation therefore remains open.')
    heading(doc,'Scope and measurement conventions')
    table(doc,['Quantity','Campaign definition'],[
        ['Configuration','Fixed foil; quasi-2D URANS–VOF; STAR-CCM+ 2602/2606'],
        ['Current and geometry','U = 18 m/s; chord ≈ 1.19 m; span 0.02 m; foil depth 2 m; water depth 24 m'],
        ['Force axes','Fx and Fz follow fixed domain x and z axes'],
        ['Regular-wave analysis','Record at least 5 complete measured cycles; discard cycle 1; evaluate cycles 2–5'],
        ['Force normalization','Cx = Fx / 3855.6 N; Cz = (Fz − 22.718189 N) / 3855.6 N'],
        ['Added horizontal force','Qx = mean Cx in cycles 2–5 − Cx,C01; ΔFx = 3855.6 Qx N']], [1.35,5.15],10)
    para(doc,f'C01 has Fx = {fx0:.5f} N and buoyancy-corrected Fz = {fz0:.5f} N. Mean Fx remains positive in every accepted regular case. Negative added resistance is a reduction of the calm reference, not a demonstration of negative mean total resistance.',False)

    heading(doc,'Accepted regular wave results',True)
    para(doc,'The table uses the published cycle windows and the same immutable C01 for all cases. Negative ΔFx denotes reduced horizontal force. ΔFz is the change in the fixed vertical direction; it is not lift resolved normal to the instantaneous inflow.')
    headers=['Case','H\n[m]','λ\n[m]','1000 Qx','ΔFx\n[N]','ΔFx\n[%]','ΔFz\n[N]','Cycles\nsaved']
    table(doc,headers,[[r['case'],f"{r['H_m']:.2f}",f"{r['lambda_m']:.2f}",f"{r['Q_Cx']*1000:.3f}",f"{r['delta_Fx_N']:.2f}",f"{r['delta_Fx_pct']:.2f}",f"{r['delta_Fz_N']:.2f}",r['measured_cycles']]for r in matrix], [.72,.5,.64,.8,.85,.85,.85,.85],10)
    caption(doc,'Table 1. Only project-accepted regular cases are included. W04e and W04h recorded six cycles; the reported means still use cycles 2–5. Full precision, source IDs, mesh counts and time windows are in accepted_case_matrix.csv.')
    para(doc,'The original M13 cases W01–W03 use 309,441 cells. Expanded PRE-based cases use 572,176 cells while retaining the M13 foil-resolution family. Total cell count and domain extent therefore differ across part of the matrix. This distinction matters when interpreting small differences between cases.')
    heading(doc,'Results still outside this table')
    table(doc,['Case','Condition','Status at this snapshot'],[
        *[[name,condition,import_status(name)] for name,condition in [('W04i','1.00 m / 15 m'),('W04j','0.50 m / 15 m')]
          if name not in accepted],
        ['W04k','0.25 m / 15 m',f"{kstatus}; saved time {ktime:.4f} s; target 14.2640 s"],
        ['W08bi','0.50 m / 20 m + 1.00 m / 30 m','Completed diagnostic; separate averaging policy']], [.65,1.65,4.2],9.5)
    para(doc,'W04a, W04b and W04d remain outside the accepted matrix because forcing checks or interrupted runs were not resolved into accepted production results. A planned case and a saved diagnostic are not counted as completed evidence.')

    heading(doc,'Dependence on height and wavelength',True)
    image(doc,'regular_trends.png')
    caption(doc,'Figure 1. Accepted mean horizontal-force differences. Circles identify the original 309,441-cell cases; squares identify expanded PRE-based cases. Lines connect available points for readability and are not fitted models. No uncertainty intervals have been established.')
    para(doc,'At H = 1.5 m, the mean reduction grows from 5.02 N at λ = 15 m to 7.17 N at 20 m, 8.54 N at 25 m, 9.36 N at 30 m and 10.06 N near 39 m. This is a monotonic trend over the tested points, with a smaller incremental change at the long-wave end. It does not establish an optimum outside the tested range.')
    series15=sorted([r for r in matrix if r['lambda_m']==15],key=lambda r:r['H_m'])
    values15='; '.join(f"H = {r['H_m']:.2f} m: ΔFx = {r['delta_Fx_N']:.2f} N" for r in series15)
    para(doc,'At λ = 20 m, increasing H from 0.25 to 1.50 m changes the mean reduction from 0.77 to 7.17 N. At λ = 30 m, the available H = 0.50, 1.00 and 1.50 m cases give reductions of 1.56, 5.06 and 9.36 N. The accepted λ = 15 m amplitude series is '+values15+'. W04k remains outside that series until its final evidence passes review. A universal height-squared scaling is not inferred from this matrix.')
    para(doc,f"Across the accepted cases, the mean vertical-force change ranges from {min(r['delta_Fz_N'] for r in matrix):.2f} to {max(r['delta_Fz_N'] for r in matrix):.2f} N. These cases are not matched to exactly equal mean vertical force. Any future claim of resistance reduction at constant load needs a comparison that adjusts the calm or wave trim to the same mean load.")
    heading(doc,'Phase comparison')
    para(doc,'The companion interactive comparison retains all four panels: horizontal and vertical force versus wave phase, and force versus surface-elevation loops. Each curve is a four-cycle mean. Phase is tied to the upward crossing of the wave reference at x = 0, without fitting the force phase. Where direct x = 0 data are incomplete, recorded upstream probes provide the documented propagation reconstruction.')
    para(doc,'The full comparison is preserved in figures/force_wave_comparison_interactive.html. Changes in amplitude, phase and harmonic content should be compared together; a loop shape alone does not identify the energy-transfer mechanism.')

    heading(doc,'What the flattened horizontal response means',True)
    image(doc,'W04e_phase_mechanism.png',6.2)
    caption(doc,'Figure 2. W04e, H = 1.5 m and λ = 15 m. The grey phase sector is 100–270°. The lower curve is α = atan2(Uz,Ux) minus the chord-line angle at the recorded upstream probe x = −0.9 m. It includes foil-induced flow.')
    table(doc,['Phase sector','Mean ΔFx [N]','Contribution to phase mean [N]'],[[f"{s['start_deg']}–{s['end_deg']}°",f"{s['delta_Fx_mean_N']:.2f}",f"{s['mean_contribution_N']:.2f}"]for s in sectors], [1.35,1.65,3.5],10)
    para(doc,'The flattened sector contributes about +3.95 N to the phase mean, while the other two sectors contribute about −8.98 N together. The resulting phase mean is about −5.03 N. This is a descriptive partition of the recorded waveform, not an independent causal test.')
    para(doc,f"In the exact AoA-analysis window, ΔFx = {metrics['exact_time_window_means']['delta_Fx_N']:.3f} N, with pressure {metrics['exact_time_window_means']['delta_pressure_Fx_N']:.3f} N and viscous {metrics['exact_time_window_means']['delta_viscous_Fx_N']:.3f} N. Pressure accounts for about {pressure_share:.1f}% of the net change. This window is 10.92269–13.52384 s at x = 0; the campaign Q window is 10.90199–13.50152 s at x = −0.5 m, so their means must not be mixed.")
    para(doc,'At the same local α = 1.5°, ΔFx is −15.70 N near 57.7° phase but +6.11 N near 236.4°. Ux differs as well, about 18.11 versus 17.03 m/s. This rejects an AoA-only description; speed variation and possible unsteady/free-surface effects remain entangled. The exact force-axis projection identity does not by itself establish causality.')

    heading(doc,'Bichromatic diagnostic and quasi steady model',True)
    para(doc,'W08bi superposes first-order native components W01 (H = 0.50 m, λ = 20 m) and W06 (H = 1.00 m, λ = 30 m), both with zero input phase. The regular-wave production cases use fifth-order forcing. W08bi is therefore a separate diagnostic, not another accepted regular-wave point.')
    image(doc,'W08bi_time_history.png',5.6)
    caption(doc,'Figure 3. Recorded foil-probe elevation and fixed-axis forces, with C01 reference lines. Force differences in the table use 17.13983–25.68000 s, three beat periods of approximately 2.84672 s. This is not a common exact wave period or the regular five-cycle acceptance window.')
    qs=bi['quasi_steady'];table(doc,['Model or record','Mean ΔFx [N]','Mean ΔFz [N]'],[
        ['CFD diagnostic',f"{bi['delta_D_N']:.3f}",f"{bi['delta_L_N']:.3f}"],
        ['Quasi-steady nominal components',f"{qs['nominal']['delta_D_N']:.3f}",f"{qs['nominal']['delta_L_N']:.3f}"],
        ['Quasi-steady probe-fitted components',f"{qs['probe']['delta_D_N']:.3f}",f"{qs['probe']['delta_L_N']:.3f}"]], [3.2,1.65,1.65],10)
    para(doc,'The surface-elevation component fit has R² = 0.9924; fitted heights are 0.475 and 0.986 m. The model was not fitted to CFD forces. Its probe-based horizontal prediction is 4.06 N more negative than CFD, and its vertical change has the opposite sign. It captures a qualitative negative shift, but it does not quantitatively validate the mechanism. Extending the finite averaging window may also change the reported diagnostic means.')

    heading(doc,'Numerical credibility and limits of the claims',True)
    para(doc,'Project acceptance combines source lineage, checkpoint integrity, numerical health and repeatability. The four analysed cycles must pass mean spread ≤ 1%, amplitude spread ≤ 8% and phase RMS ≤ 5%. These are internal gates, not experimental validation or a quantified numerical uncertainty.')
    table(doc,['Mesh','Cells','Δt [ms]','Calm Cx','Cx vs M12 [%]'],[[m['mesh'],f"{m['cells']:,}",f"{m['dt_s']*1000:.1f}",f"{m['settled']['CD']:.7f}",f"{m['delta_CD_pct']:.2f}"]for m in audit['mesh']], [.65,1.15,1.,1.7,2.],10)
    caption(doc,'Table 4. Existing calm mesh comparison. Time step and residual settling differ between cases; these data cannot be used as a formal grid-convergence index.')
    para(doc,'The M13 calm Cx differs by about 4.06% from M12. This is not an uncertainty bound, but it shows why the smallest force reductions require controlled mesh and time-step checks before being treated as quantitatively resolved. The expanded PRE reached C01 compatibility within 0.5% in two consecutive windows; its final Cx offset was about −0.371% and Cz offset about −0.225%. That compatibility gate does not establish identical numerical error in waves.')
    para(doc,'Wave forcing, propagation and reflection have not been fully quantified. A high nominal steepness or a healthy solver does not demonstrate a physically correct incident wave. The short-wave W04a/b/d work is retained as diagnostic evidence rather than folded into the accepted trend.')
    para(doc,'Water inventory checks are distinct from complete wave-period mass-flux closure. The precise PRE balance is evidence for its preparation, not a substitute for a wave-case conservation study. No formal time-step uncertainty, finite-span correction, experimental comparison or energy-flux budget is complete.')
    para(doc,'The fixed-domain Fx/Fz convention must be maintained in every figure and table. Legacy CSV fields named CD_total and CL_hydrodynamic are normalized fixed-axis coefficients Cx and Cz. Calling them instantaneous inflow-aligned drag and lift coefficients would misstate the force frame.')
    para(doc,'Local AoA evidence uses one clipped midspan history and a probe close to the foil. The range is approximately −0.38° to 3.41° in W04e; it is not an independent incident-wave AoA measurement. Field-history coverage also differs between cases and continuation segments.')

    heading(doc,'Preparation for the research discussion',True)
    para(doc,'The current evidence supports three bounded conclusions. First, the accepted matrix has a repeatable negative mean added horizontal force relative to C01. Second, the tested height and wavelength sweeps show systematic trends within the selected configuration. Third, W04e links the response shape primarily to pressure and demonstrates that local AoA alone is insufficient. These statements can form the results section of a short research report.')
    heading(doc,'Questions that remain open')
    para(doc,'The mechanism discussion should test whether changes in local speed, force projection, pressure distribution and unsteady/free-surface response explain the phase asymmetry together. A useful test is a matched local-inflow model using the recorded Ux and Uz, compared with pressure and viscous force at the same phases. Same-AoA samples should be compared at matched speed before interpreting the loop as a memory effect.')
    para(doc,'Useful CPU-only follow-up work is to quantify phase-sector contributions and harmonics for every accepted case; compare the available field histories at common foil-relative locations; separate incident-wave measurements from foil-induced velocity; and reconcile the slightly different Q and x = 0 mechanism windows. No new solver run is needed to prepare these analyses.')
    heading(doc,'How to structure the final account')
    para(doc,'A practical sequence is configuration and reference definition, case matrix and acceptance policy, mean-force trends, phase-resolved pressure and velocity evidence, the bichromatic model comparison, then numerical limitations and the next discriminating experiment. Active-flap and flight-control studies belong in the motivation and future-work discussion unless separately analysed data are introduced.')
    para(doc,'Godø and co-authors studied active wave-energy extraction with flight control in a different hydrofoil-vessel model [1]. Their control and energy outcomes should not be transferred numerically to this fixed-foil campaign. Nonlinear dynamic lifting-line work [2] is relevant background for model development, not validation of the present URANS–VOF results.')
    heading(doc,'Evidence and completion status')
    para(doc,'The evidence folder contains the case matrix, mean windows, final-SIM locations, the archived audit snapshot, W04e phase/AoA records and pending-result status. Original C01 SHA-256 begins 9af4857b948e0494; accepted PRE begins d86beded68b41f5e. Full hashes are retained in the snapshot and source receipts. SIM and per-segment field data remain in the backup repository.')
    import_brief='; '.join(name+(': accepted' if name in accepted else ': review pending') for name in ('W04i','W04j'))
    para(doc,'GLHF import status: '+import_brief+'. W04k remains outside the comparison. Its healthy 14.0640 s autosave and three field-history segments are on backup. A native STAR 2606 continuation package is prepared; its subsequent remote start is unverified. This report update starts no solver.')
    para(doc,'[1] Godø et al. (2024). Active wave energy extraction by hydrofoil vessels through deep reinforcement learning-based flight control. Ocean Engineering 312, 119236. https://doi.org/10.1016/j.oceaneng.2024.119236')
    para(doc,'[2] Godø and Steen (2023). An Efficient Method for Unsteady Hydrofoil Simulations, based on Non-Linear Dynamic Lifting Line Theory. Ocean Engineering 288, 116001. https://doi.org/10.1016/j.oceaneng.2023.116001')
    path=OUT/'NWAR_research_summary.docx';doc.save(path)
    write(OUT/'preparation_manifest.json',dict(at=now(),source_report=str(source),source_audit_sha256=sha(source/'audit.json'),accepted_regular_cases=len(regular),document=str(path),pending=pending,numerical_policy=audit['project_policy']['id'],GPU_solver_started_by_this_task=False))
    print(json.dumps(dict(document=str(path),cases=len(regular),snapshot_at=now(),pending_K=pending['ThinkPad_W04k']),ensure_ascii=False))

if __name__=='__main__':build()
