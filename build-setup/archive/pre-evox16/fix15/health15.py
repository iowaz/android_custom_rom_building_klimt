"""Read-only build health sample: build subtree CPU including reaped children."""
import json, os, re, time
from pathlib import Path
L=Path('/mnt/wsl/evox/logs'); log=L/'evox15.log'
R=Path('/mnt/c/XiaomiBuilds/debug/noise15/health15.jsonl')
procs={}
for p in Path('/proc').iterdir():
 if not p.name.isdigit():continue
 try:
  stat=(p/'stat').read_text().rsplit(')',1)[1].split()
  cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
  procs[int(p.name)]={'parent':int(stat[1]),'cpu':sum(int(stat[i]) for i in [11,12,13,14]),'cmd':cmd}
 except (FileNotFoundError,PermissionError,ProcessLookupError):pass
roots=[pid for pid,p in procs.items() if re.search(r'^bash /mnt/c/XiaomiBuilds/build-setup/evox/build.sh evox15 updatepackage\s*$',p['cmd'])]
seen=set(roots)
while True:
 more={pid for pid,p in procs.items() if p['parent'] in seen}-seen
 if not more:break
 seen.update(more)
stat=log.stat(); tail=log.read_bytes()[-12000:].decode(errors='replace')
steps=re.findall(r'\[\s*\d+%\s+(\d+/\d+)[^\]]*\]',tail)
sample={'time':int(time.time()),'step':steps[-1] if steps else None,'log_bytes':stat.st_size,
 'log_mtime':stat.st_mtime,'build_cpu_seconds':round(sum(procs[p]['cpu'] for p in seen)/os.sysconf('SC_CLK_TCK'),2),
 'processes':len(seen),'exit':(L/'evox15.exit').read_text().strip() if (L/'evox15.exit').exists() else None}
history=[]
if R.exists():
 for line in R.read_text().splitlines():
  try:history.append(json.loads(line))
  except json.JSONDecodeError:pass
with R.open('a') as f:f.write(json.dumps(sample)+'\n')
print(json.dumps(sample))
if history:
 prior=history[-1]
 print('delta:',{k:round(sample[k]-prior[k],2) for k in ['time','log_bytes','build_cpu_seconds']})
 unchanged=lambda p:all(p.get(k)==sample.get(k) for k in ['step','log_bytes','build_cpu_seconds'])
 prior_changed=next((p for p in reversed(history) if not unchanged(p)),None)
 first=prior_changed or history[0]
 if not sample['exit'] and unchanged(history[-1]) and sample['time']-first['time']>=1800:
  print('POSSIBLE FREEZE: step, log and build-subtree CPU unchanged for at least 30 minutes')
