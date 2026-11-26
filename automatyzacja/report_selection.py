"""One current saved result per wave, with lineage kept in source files."""
from common import HERE, Path, read, tail, number

def active_entries(entries):
 from calm_reference import local_reference_enabled,REFERENCE_ID
 if not local_reference_enabled():return entries
 return [e for e in entries if e.get('spec',{}).get('reference_id')==REFERENCE_ID]

def final_report_root():
 configured=read(HERE/'report_storage.json').get('final_directory')
 if not configured:return None
 path=Path(configured)
 if not path.is_absolute():raise ValueError('Final report directory must be absolute.')
 return path

def report_entries(entries, *, final_only=False):
 selected={}
 for entry in active_entries(entries):
  if entry.get('spec',{}).get('smoke'):continue
  reviewed_partial=entry.get('imported') and entry.get('reviewed_partial') and entry['status']=='saved'
  if not reviewed_partial and entry['status'] not in (('completed',) if final_only else ('completed','paused','needs_review')):continue
  history=tail(Path(entry['folder'])/'history.csv')
  end=number(history[-1].get('time_s')) if history else None
  if end is None:continue
  case=entry['case_id']
  if case not in selected or end>selected[case][0]:selected[case]=(end,entry)
 return [selected[k][1] for k in sorted(selected)]

def display_id(entry):
 return entry['case_id']
