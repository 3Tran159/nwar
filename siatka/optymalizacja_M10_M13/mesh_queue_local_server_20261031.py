"""Local-only 8772 queue control API for live dashboard, no existing 8771 restart."""
from pathlib import Path
import http.server,json,os,secrets,urllib.parse,uuid,datetime,sys,ctypes
import mesh_queue_control_20261031 as ctrl
HOST="127.0.0.1";PORT=8772;ORIGIN="http://127.0.0.1:8771";TOKEN=secrets.token_urlsafe(32)
LOCK=ctrl.R/"mesh_queue_service.lock"
def time_iso():return datetime.datetime.now().astimezone().isoformat()
class Handler(http.server.BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def send_json(self,data,status=200):
  b=json.dumps(data,ensure_ascii=False,allow_nan=False).encode("utf8")
  self.send_response(status)
  self.send_header("Content-Type","application/json; charset=utf-8")
  self.send_header("Cache-Control","no-store")
  self.send_header("Content-Length",str(len(b)))
  self.send_header("Access-Control-Allow-Origin",ORIGIN)
  self.send_header("Vary","Origin")
  self.send_header("X-Content-Type-Options","nosniff")
  self.end_headers()
  self.wfile.write(b)
 def cors(self):return self.headers.get("Origin")==ORIGIN and self.headers.get("Host")==f"{HOST}:{PORT}"
 def do_OPTIONS(self):
  if not self.cors():return self.send_json(dict(error="forbidden"),403)
  self.send_response(204);self.send_header("Access-Control-Allow-Origin",ORIGIN);self.send_header("Access-Control-Allow-Methods","GET, POST, OPTIONS");self.send_header("Access-Control-Allow-Headers","Content-Type, X-Mesh-Queue-Token");self.send_header("Cache-Control","no-store");self.end_headers()
 def do_GET(self):
  if not self.cors():return self.send_json(dict(error="forbidden"),403)
  if self.path!="/api/mesh-queue":return self.send_json(dict(error="not found"),404)
  try:return self.send_json(dict(**ctrl.snapshot(),csrf=TOKEN,server_time=time_iso()))
  except Exception:return self.send_json(dict(error="queue status error"),500)
 def do_POST(self):
  if not self.cors() or not secrets.compare_digest(self.headers.get("X-Mesh-Queue-Token",""),TOKEN) or self.headers.get("Content-Type","").split(";")[0]!="application/json":
   return self.send_json(dict(error="local protected control required"),403)
  if self.path not in ("/api/mesh-queue/resume","/api/mesh-queue/pause"):return self.send_json(dict(error="not found"),404)
  try:
   n=int(self.headers.get("Content-Length","0"))
   if n<=0 or n>4096:raise ValueError("Invalid request length")
   req=json.loads(self.rfile.read(n))
   if not isinstance(req,dict):raise ValueError("JSON object expected")
   result=(ctrl.resume if self.path.endswith("/resume") else ctrl.pause)(req)
   self.send_json(result,202)
  except (ValueError,KeyError,TypeError) as ex:self.send_json(dict(error=str(ex)),409)
  except Exception as ex:self.send_json(dict(error="Queue control needs review: "+type(ex).__name__),500)
def main():
 if LOCK.exists():raise RuntimeError("Another queue control service lock exists; do not duplicate")
 with LOCK.open("x",encoding="utf8") as f:json.dump(dict(pid=os.getpid(),at=time_iso(),port=PORT),f)
 try:
  server=http.server.ThreadingHTTPServer((HOST,PORT),Handler)
  server.serve_forever()
 finally:
  if ctrl.read(LOCK).get("pid")==os.getpid():LOCK.unlink()
if __name__=="__main__":main()
