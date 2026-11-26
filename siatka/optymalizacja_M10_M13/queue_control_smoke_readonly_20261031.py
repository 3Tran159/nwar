import urllib.request,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(r"E:\ntnu_mesh_optimization_20261030")))
import mesh_queue_control_20261031 as c
url="http://127.0.0.1:8772/api/mesh-queue"
req=urllib.request.Request(url,headers={"Origin":"http://127.0.0.1:8771"})
r=json.load(urllib.request.urlopen(req,timeout=10))
print("QUEUE_API",json.dumps({k:v for k,v in r.items() if k!="csrf"},ensure_ascii=False)[:1500],"token_length",len(r.get("csrf","")))
assert r["can_resume"] and "M11" in r["job"]
try:
 req=urllib.request.Request(url,headers={"Origin":"https://not-trusted.example"})
 urllib.request.urlopen(req,timeout=4)
 raise AssertionError("CORS origin not checked")
except urllib.error.HTTPError as e:
 print("WRONG_ORIGIN_DENIED",e.code);assert e.code==403
assert not c.LOCK.exists()
try:
 c.resume(dict(generation="stale_m12"))
 raise AssertionError("Stale generation accepted")
except ValueError as e:print("STALE_GENERATION_REJECTED",str(e)[:150])
print("OK")
