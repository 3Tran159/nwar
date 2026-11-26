"""Full continuation history for display; raw solver files remain unchanged."""
from common import Path, read, EXISTING
from analysis import numeric_rows, segment_chain
import numpy as np
import threading

_CACHE = {}
_LOCK = threading.RLock()

def run_chain(entry):
 if entry.get('legacy'):return [Path(entry['folder'])]
 if entry.get('imported'):
  return [Path(p) for p in entry['spec']['parent_segments']]+[Path(entry['folder'])]
 if entry.get('external'):
  parent=entry.get('spec',{}).get('parent_folder') or EXISTING[entry['case_id']]
  return [Path(parent),Path(entry['folder'])]
 return segment_chain(entry)

def _history(folder):
 path=Path(folder)/'history.csv'
 cutoff=read(Path(folder)/'history_cutoff.json').get('time_s')
 try:
  stat=path.stat();signature=(stat.st_size,stat.st_mtime_ns,cutoff)
 except OSError:return np.empty((0,3))
 with _LOCK:
  cached=_CACHE.get(str(path))
  if cached and cached[0]==signature:return cached[1]
  data=numeric_rows(path)
  keys=('time_s','CD_total','CL_hydrodynamic')
  values=np.column_stack([data[k] for k in keys]) if all(k in data for k in keys) else np.empty((0,3))
  if cutoff is not None:values=values[values[:,0]<=float(cutoff)+1e-9]
  _CACHE[str(path)]=(signature,values)
  return values

def envelope_indices(values,budget=1800):
 """Retain both force extrema per time bin, plus first and latest samples."""
 if len(values)<=budget:return np.arange(len(values))
 indices={0,len(values)-1}
 for chunk in np.array_split(np.arange(len(values)),max(1,(budget-2)//4)):
  for col in (1,2):
   indices.add(int(chunk[np.argmin(values[chunk,col])]))
   indices.add(int(chunk[np.argmax(values[chunk,col])]))
 return np.array(sorted(indices))

def history_view(folders,budget=1800):
 segments=[];markers=[];warnings=[];previous=None;sample_count=0
 for i,folder in enumerate(folders):
  if read(Path(folder)/'completed.json').get('status')=='scene_prepared':continue
  values=_history(folder)
  if not len(values):
   warnings.append('Waiting for history: '+Path(folder).name)
   continue
  finite=np.isfinite(values).all(axis=1)
  if not finite.all():warnings.append('Incomplete values in history: '+Path(folder).name)
  values=values[finite]
  if not len(values):continue
  start=float(values[0,0])
  if i:
   contiguous=previous is not None and abs(start-previous)<.00008
   markers.append(dict(time_s=start,label='Resume '+str(len(markers)+1),contiguous=contiguous,folder=str(folder)))
   if not contiguous:warnings.append('History gap or overlap at resume t='+format(start,'.4f')+' s; segments have not been connected.')
  # Split also inside a segment: never draw across absent or reversed samples.
  splits=np.where((np.diff(values[:,0])>.0013)|(np.diff(values[:,0])<=0))[0]+1
  if len(splits):warnings.append('Sample gap: '+Path(folder).name)
  for chunk in np.split(values,splits):
   points=chunk[envelope_indices(chunk,budget)].tolist()
   segments.append(dict(folder=str(folder),points=points))
  sample_count+=len(values)-(1 if i and markers[-1]['contiguous'] else 0)
  previous=float(values[-1,0])
 series=[point for segment in segments for point in segment['points']]
 return dict(series=series,history_segments=segments,resume_markers=markers,
             history_samples=sample_count,history_start_s=series[0][0] if series else None,
             history_end_s=series[-1][0] if series else None,history_warnings=warnings,
             display_sampling='CL/CD extrema retained for display; full samples in CSV.')
