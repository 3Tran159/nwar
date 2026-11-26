from pathlib import Path
P=Path(__file__).resolve().parent
def patch(name,a,b):
 p=P/name;s=p.read_text(encoding='utf8');assert s.count(a)==1,(name,a[:60],s.count(a));p.write_text(s.replace(a,b),encoding='utf8')
patch('common.py',"request_key=None,smoke=0):","request_key=None,smoke=0,conn=None):")
patch('common.py',""" with connection() as c:
  c.execute('BEGIN IMMEDIATE')
  previous=c.execute""",""" c=conn or connection()
 try:
  if conn is None:c.execute('BEGIN IMMEDIATE')
  previous=c.execute""")
patch('common.py',"""  c.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?,?)',(id,now(),now(),'queued',case_id,json.dumps(spec),str(folder),'Oczekuje w kolejce',None,None,key))
 event('queued',id=id,case=case_id,mode=mode)
 return id""","""  c.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?,?)',(id,now(),now(),'queued',case_id,json.dumps(spec),str(folder),'Oczekuje w kolejce',None,None,key))
  if conn is None:c.commit()
 except BaseException:
  if conn is None:c.rollback()
  raise
 finally:
  if conn is None:c.close()
 event('queued',id=id,case=case_id,mode=mode)
 return id""")
patch('server.py',"""     ids=[enqueue(c,mode=data.get('mode','fresh'),extra_cycles=data.get('extra_cycles',1),request_key=key+'_'+c) for c in selected]
     ensure_worker();return self.send(dict(ids=ids,paused=(DATA/'PAUSE').exists()),202)""","""     with connection() as conn:
      conn.execute('BEGIN IMMEDIATE')
      ids=[enqueue(c,mode=data.get('mode','fresh'),extra_cycles=data.get('extra_cycles',1),request_key=key+'_'+c,conn=conn) for c in selected]
     ensure_worker();return self.send(dict(ids=ids,paused=(DATA/'PAUSE').exists()),202)""")
patch('worker.py',""" update(id,status='preflight',controller_pid=os.getpid(),controller_birth=birth(os.getpid()),message='Sprawdzanie źródła, kompilacji i zasobów')
 try:""",""" with connection() as c:
  c.execute('BEGIN IMMEDIATE')
  claimed=c.execute("UPDATE jobs SET status='preflight',updated=?,controller_pid=?,controller_birth=?,message=? WHERE id=? AND status='queued'",(now(),os.getpid(),birth(os.getpid()),'Sprawdzanie źródła, kompilacji i zasobów',id)).rowcount
 if not claimed:return
 try:""")
patch('worker.py',"""  if native():raise ValueError('Solver uruchomił się podczas rezerwacji; oczekiwanie na zasoby.')
  folder.mkdir""","""  if native():raise ValueError('Solver uruchomił się podczas rezerwacji; oczekiwanie na zasoby.')
  if (DATA/'PAUSE').exists():
   update(id,status='queued',message='Kolejka wstrzymana przed startem solvera.');return
  folder.mkdir""")
patch('worker.py',"""  if state in ('paused','needs_review'):(DATA/'PAUSE').touch()""","""  if state in ('paused','needs_review'):(DATA/'PAUSE').touch()
  if state=='completed' and not spec.get('smoke'):
   from analysis import analyze,segment_chain
   result,_,_=analyze(spec,segment_chain(job(id)))
   write(folder/'independent_cycle_review.json',result)
   if not result['health']['ok'] or not result['cycles']['repeatable']:
    update(id,status='needs_review',message='Wynik zapisany, ale niezależna kontrola 4 cykli wymaga sprawdzenia.')
    (DATA/'PAUSE').touch()""")
patch('worker.py',"""   result,_,_=analyze(spec,segment_chain(job(id)))""","""   result,_,_=analyze(dict(spec,id=j['case_id']),segment_chain(job(id)))""")
# A STOP received while loading must reach a saved zero-step pause after bindings.
patch('build_macro.py',"""# Require four actual complete fixed-gauge cycles;""","""replace('   stopCheck();reg=s.getRegionManager().getRegion("fluid");','   reg=s.getRegionManager().getRegion("fluid");')
# Require four actual complete fixed-gauge cycles;""")
# No stale 'report_failed' indication after a successful build.
patch('report.py',"""  event('report_generated',directory=str(out),cases=len(allresults))""","""  (DATA/'report_error.json').unlink(missing_ok=True)
  event('report_generated',directory=str(out),cases=len(allresults))""")
# Do not silently claim terminal output is healthy when an existing source is corrupted.
patch('common.py',"""   src=folder/ck['file']
   spec['parent_id']=parent_id""","""   src=folder/ck['file']
   integrity=read(folder/'final_integrity.json')
   if integrity.get('sha256')!=sha(src):raise ValueError('Suma kontrolna zapisu nie odpowiada potwierdzeniu integralności.')
   spec['parent_id']=parent_id""")
print('Hardened atomic queue selection, claim/cancel race, pause during loading, and independent cycle gate.')
