from pathlib import Path
O=Path(__file__).resolve().parent
cpu=(O/'cpu_calm_study.py').read_text()
tail=cpu[cpu.index(' paths={m:[] for m in LEVELS};summaries={}'):cpu.index("if __name__=='__main__':")]
tail=tail.replace("  p=pilots[m];t=read(p/'completed.json')['time_s']\n  out,d=flow('calm_settle_'+m,p/'final.sim',t,t+3,dt,10,cells[m],settle=True)","  t=start_times[m]\n  out,d=flow('calm_settle_'+m,sources[m],t,t+3,dt,10,cells[m],settle=True)")
tail=tail.replace('gpu=False','gpu=True').replace('calm_CPU_','calm_GPU_')
p=O/'gpu_calm_study.py'
with p.open('a',encoding='utf-8') as f:f.write(tail)
