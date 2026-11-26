"""Narrow chart patch: retain GLHF's locally customized main app.js."""
from pathlib import Path
import base64,json,re,hashlib
ROOT=Path('E:/NWAR_portable_20261103')
source=(ROOT/'Update-NWAR-Dashboard-UI2.ps1').read_text(encoding='utf-8-sig')
match=re.search(r"\$uiSpec='([^']+)'",source);spec=json.loads(base64.b64decode(match.group(1)))
spec['id']='GLHF_chart_only_UI3_20261103'
spec['files']=[item for item in spec['files'] if item['name'] in ('index.html','style.css','wave_view.js')]
for item in spec['files']:
 before=base64.b64decode(item['data']);item['allowed_before_sha256'].append(hashlib.sha256(before).hexdigest())
 after=before.decode('utf8').replace('20261103.2','20261103.3').replace('20261103-ui2','20261103-ui3').encode('utf8')
 item.update(data=base64.b64encode(after).decode(),sha256=hashlib.sha256(after).hexdigest(),bytes=len(after))
encoded=base64.b64encode(json.dumps(spec).encode()).decode()
s=source[:match.start(1)]+encoded+source[match.end(1):]
s=s.replace("$allowed=@('index.html','style.css','app.js','wave_view.js','history_chart.js','convergence_chart.js')","$allowed=@('index.html','style.css','wave_view.js')")
s=s.replace('20261103.2','20261103.3').replace('20261103-ui2','20261103-ui3').replace('ui2_served','ui3_served')
s=s.replace("Write-Host 'Done. Press Ctrl+F5", "Write-Host 'GLHF app.js and existing solver-status controls were preserved.'\nWrite-Host 'Done. Press Ctrl+F5")
output=ROOT/'Update-NWAR-Charts-UI3.ps1';assert not output.exists(),'Existing script preserved'
output.write_text(s,encoding='utf-8-sig')
(ROOT/'QA_frontend/ui3_manifest.json').write_text(json.dumps(spec,indent=2),encoding='utf8')
print(json.dumps(dict(script=str(output),bytes=output.stat().st_size,files=[x['name'] for x in spec['files']])))
