from pathlib import Path
P=Path(__file__).resolve().parent
def patch(name,a,b):
 p=P/name;s=p.read_text(encoding='utf8');assert s.count(a)==1,(name,a[:100],s.count(a));p.write_text(s.replace(a,b),encoding='utf8')
patch('common.py',""" case=choices[case_id];spec=dict""",""" if mode=='extend' and parent_id is None:
  recent=[j for j in jobs() if j['case_id']==case_id and j['status'] in ('completed','needs_review') and not j['spec'].get('smoke') and (Path(j['folder'])/'final_integrity.json').exists()]
  if recent:parent_id=recent[0]['id']
 case=choices[case_id];spec=dict""")
patch('server.py',"""     case_map={c['id']:c for c in catalog()}""","""     case_map={c['id']:c for c in catalog()}
     if data.get('mode')=='extend' and any(x['case_id'] in selected and x['status']=='running' for x in externals()):
      raise ValueError('Wybrana fala ma trwającą kontynuację. Dodatkowe cykle zleć po jej zapisaniu, aby użyć najnowszego stanu.')""")
patch('analysis.py',"""def numeric_rows(path):
 raw=rows(path)
 if not raw:return {}
 fields=[k for k in raw[0] if k]
 return {k:np.array([number(r.get(k)) if number(r.get(k)) is not None else np.nan for r in raw],dtype=float) for k in fields}""","""def numeric_rows(path,with_evidence=False):
 import io,hashlib
 try:content=Path(path).read_bytes()
 except OSError:return ({},{}) if with_evidence else {}
 # Ignore only a trailing line still being written; all interior gaps remain visible.
 if content and not content.endswith(b'\\n'):content=content[:content.rfind(b'\\n')+1]
 raw=list(csv.DictReader(io.StringIO(content.decode('utf-8-sig'))))
 evidence=dict(path=str(path),sha256=hashlib.sha256(content).hexdigest(),snapshot_bytes=len(content),hash_basis='CSV bytes consumed by this analysis snapshot')
 if not raw:return ({},evidence) if with_evidence else {}
 fields=[k for k in raw[0] if k]
 result={k:np.array([number(r.get(k)) if number(r.get(k)) is not None else np.nan for r in raw],dtype=float) for k in fields}
 return (result,evidence) if with_evidence else result""")
patch('analysis.py',"""  data=numeric_rows(Path(folder)/'history.csv')""","""  data,receipt=numeric_rows(Path(folder)/'history.csv',with_evidence=True)""")
patch('analysis.py',"""  evidence.append(dict(path=str(Path(folder)/'history.csv'),sha256=sha(Path(folder)/'history.csv'),samples=int(take.sum())))""","""  evidence.append(dict(receipt,samples=int(take.sum())))""")
patch('worker.py',"""  stage=read(folder/'stage_result.json');done=read(folder/'completed.json')
  if stage.get('exit_code')!=0""","""  stage=read(folder/'stage_result.json');done=read(folder/'completed.json')
  if sha(Path(spec['source']))!=spec['source_sha']:raise ValueError('Źródło nie odpowiada zatwierdzonej tożsamości po obliczeniu.')
  if stage.get('exit_code')!=0""")
patch('report.py',"""     result['legacy_four_cycle_repeatability']=receipt.get('four_cycles_repeated')""","""     result['legacy_four_cycle_repeatability']=receipt.get('four_cycles_repeated')
     result['historical_planning_period_means']={k:receipt.get('metrics',{}).get(k,{}).get('mean') for k in ('CL','CD')}
     result['historical_steps']=receipt.get('total_steps')""")
patch('report.py',"""    allresults.append(result)
    sumrow=""","""    allresults.append(result)
    historical=result.get('historical_planning_period_means',{})
    sumrow=""")
patch('report.py',"""repeatable=cy['repeatable'],health_ok=result['health']['ok'],NWAR_validated=False""","""repeatable=cy['repeatable'],health_ok=result['health']['ok'],historical_CL_planning_windows=historical.get('CL'),historical_CD_planning_windows=historical.get('CD'),phase_probe_x_m=cy['phase_probe_x_m'],NWAR_validated=False""")
# Append missing provenance line to the visible per-run report text.
patch('report.py',"""<p>Średnie po dokładnych granicach cykli: CL='""","""<p>Sonda fazowa: x='+f(cy['phase_probe_x_m'],1)+' m. Historyczne średnie z okien okresu planowanego: CL='+f(historical.get('CL'))+', CD='+f(historical.get('CD'))+'.</p><p>Średnie po dokładnych granicach cykli: CL='""")
print('Latest internal sources, active extension guard, snapshot provenance, and historical means updated.')
