#!/usr/bin/env python3
"""Seven fail-closed post-build producer/artifact checks. No build or device actions.

Exit 0 = stated static checks passed; 1 = artifact/source invariant defect;
2 = tooling/evidence/unsupported-codegen failure; 3 = unexpected checker error.
Raw commands, input hashes, individual assertions and limitations survive failure.
"""
import argparse,hashlib,json,os,re,shlex,shutil,struct,subprocess,sys,time,traceback,zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

MODES={'policy','patch_packaging','private_compatibility','health_semantics','gms_themes_apps','doze_packaging','install_integrity'}
KERNEL_MODULE_FILE=re.compile(r'(?:vendor|system|odm)_dlkm/lib/modules/(?:[^/]+\.ko|modules\.(?:alias|dep|load|softdep|blocklist|options|load\.recovery|load\.charger))')
REF_SHA='cb444f1020791291bb72f3e80523c0c795653e25cd6014396528effffbb0376f'
S=Path('/mnt/wsl/evox/src');P=S/'out/target/product/klimt'
class Defect(RuntimeError):pass
class ToolFailure(RuntimeError):pass
def sha(p):
 if not p.is_file():raise ToolFailure('Required file missing: '+str(p))
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
def parse_modules(text):
 records=[]
 for b in text.split('include $(CLEAR_VARS)'):
  f=dict(re.findall(r'^([A-Z0-9_]+) := (.*)$',b,re.M))
  if f.get('LOCAL_MODULE'):records.append(f)
 return records
def parse_query(text):
 lines=text.splitlines();inputs=[];active=False
 for l in lines[1:]:
  if l.startswith('  input:'):active=True;continue
  if l.startswith('  outputs:'):active=False
  elif active and l.startswith('    '):inputs.append(re.sub(r'^\s*\|\|?\s*','',l.strip()))
 return inputs
def same_zip_payload(a,b):
 """Prebuilt APK signing/alignment may change; compiled payload must not."""
 with zipfile.ZipFile(a) as x,zipfile.ZipFile(b) as y:
  wanted=[n for n in x.namelist() if re.fullmatch(r'classes\d*\.dex',n) or n in ('resources.arsc','AndroidManifest.xml')]
  if not wanted or set(wanted)!={n for n in y.namelist() if re.fullmatch(r'classes\d*\.dex',n) or n in ('resources.arsc','AndroidManifest.xml')}:return False
  return all(hashlib.sha256(x.read(n)).digest()==hashlib.sha256(y.read(n)).digest() for n in wanted)
def obsolete_artifacts_present(fs,records):
 """Known reviewed retired installation paths; any file/link at the path fails."""
 found=[]
 for record in records:
  rel=record['relative'];parts=Path(rel).parts
  if not parts or Path(rel).is_absolute() or '..' in parts:raise ToolFailure('Invalid bound obsolete artifact path')
  candidates=[fs/rel]
  if parts[0]=='system':candidates.insert(0,fs/'system/system'/Path(*parts[1:]))
  if any(p.exists() or p.is_symlink() for p in candidates):found.append(record)
 return found
def duplicate_apk_packages(records):
 packages={}
 for record in records:
  if record.get('package'):packages.setdefault(record['package'],[]).append(record)
 return {name:paths for name,paths in sorted(packages.items()) if len(paths)>1}
def unexpected_duplicates(duplicates,allowed):
 """A duplicate package is allowed only with exactly the reviewed evox15 path set."""
 return {name:sorted(r['relative'] for r in records) for name,records in duplicates.items()
         if sorted(r['relative'] for r in records)!=sorted(allowed.get(name,[]))}
def image_relative(relative):
 """Extracted system-as-root keeps /system under fs/system/system; staging has it at system/."""
 parts=Path(relative).parts
 return str(Path(*parts[1:])) if parts[:2]==('system','system') else relative
def stray_staged(staged,installable):
 """Staged files the product does not install. Kernel module trees are copied outside it."""
 stray=sorted(set(staged)-set(installable))
 return [s for s in stray if not KERNEL_MODULE_FILE.fullmatch(s)],[s for s in stray if KERNEL_MODULE_FILE.fullmatch(s)]
def prop_map(text):
 result={}
 for line in text.splitlines():
  line=line.strip()
  if line and not line.startswith('#') and '=' in line:
   k,v=line.split('=',1)
   if k in result and result[k]!=v:raise Defect('Conflicting duplicate property '+k)
   result[k]=v
 return result
def manifest_true(text,name):
 return bool(re.search(re.escape(name)+r'[^\n]*=(?:\(type 0x12\))?(?:0xffffffff|true)\b',text))
def manifest_attr(text,name,default=None):
 matches=re.findall(r'\b'+re.escape(name)+r'(?:\(0x[0-9a-f]+\))?=(?:\(type 0x[0-9a-f]+\))?("[^"\n]*"|[^\s\n]+)',text)
 if len(matches)>1:raise ToolFailure('Compiled manifest attribute ambiguous: '+name)
 return matches[0].strip('"') if matches else default
def overlay_order_config(path):
 rootdir=path.parent.resolve();seen=set()
 def parse(p,depth):
  if depth>5 or p in seen:raise ToolFailure('Overlay config merge cycle/depth')
  seen.add(p);p.resolve().relative_to(rootdir)
  root=ET.parse(p).getroot()
  if root.tag!='config':raise ToolFailure('Unexpected packaged overlay config root')
  items=[]
  for n in root:
   if n.tag=='merge':items.extend(parse(rootdir/n.attrib['path'],depth+1))
   elif n.tag=='overlay':items.append({'package':n.attrib['package'],'enabled':n.get('enabled','false')=='true','mutable':n.get('mutable','true')=='true'})
   else:raise ToolFailure('Unsupported overlay config element: '+n.tag)
  return items
 return parse(path,0),sorted(seen)
def order_overlays(overlays,configured):
 if configured is None:return sorted([o for o in overlays if o['static']],key=lambda o:(o['priority'],o['path']))
 by={o['package']:o for o in overlays}
 return [by[o['package']] for o in configured if o['enabled'] and o['package'] in by]
def resource_values(text,name):
 """Only unqualified/default values; translated/configured entries aren't defaults."""
 blocks=re.split(r'(?=^\s*resource 0x)',text,flags=re.M)
 matches=[b for b in blocks if re.search(r'\b(?:bool|string|integer)/'+re.escape(name)+r'\b',b.splitlines()[0] if b.splitlines() else '')]
 if len(matches)!=1:raise ToolFailure('Resource missing/ambiguous in aapt2 dump: '+name)
 lines=re.findall(r'^\s*\(\)\s*(.+)$',matches[0],re.M)
 if len(lines)!=1:raise ToolFailure('Default resource missing/ambiguous: '+name)
 return lines[0].strip().strip('"')
def parse_instructions(dis):
 ins=[]
 for l in dis.splitlines():
  m=re.match(r'\s*([0-9a-f]+):\s+[0-9a-f]{8}\s+(\S+)\s*(.*?)\s*(?://.*)?$',l)
  if m:ins.append((int(m[1],16),m[2],m[3].split('//')[0].strip()))
 if not ins:raise ToolFailure('No AArch64 instructions decoded')
 return ins
def health_update_eval(dis,raw):
 """Interpret the actual short AArch64 UpdateHealthInfo body, fail on new opcodes.

 Current HealthInfo layout is 0x24 current-now, 0x50 current-average, 0x90 TTF.
 The source/ABI identity and exact observed layout are separately bound in report.
 """
 ins=parse_instructions(dis);by={i[0]:n for n,i in enumerate(ins)};regs={'x1':0x100000};mem={0x24:raw&0xffffffff,0x50:123,0x90:456};equal=False
 def val(a):
  a=a.strip()
  if a in ('wzr','xzr'):return 0
  if a.startswith('#'):return int(a[1:],0)
  key='x'+a[1:] if a.startswith('w') else a
  if key not in regs:raise ToolFailure('Unknown AArch64 register '+a)
  return regs[key]&((1<<32)-1 if a.startswith('w') else (1<<64)-1)
 def put(a,v):regs['x'+a[1:] if a.startswith('w') else a]=v&((1<<32)-1 if a.startswith('w') else (1<<64)-1)
 pc=0;steps=0
 while pc<len(ins):
  steps+=1
  if steps>100:raise ToolFailure('Health evaluator instruction budget')
  _,op,args=ins[pc];a=[x.strip() for x in args.split(',')];pc+=1
  if op=='ret':return mem
  if op in ('nop','bti'):continue
  if op=='mov':put(a[0],val(a[1]))
  elif op in ('ldr','str'):
   m=re.fullmatch(r'(\w+),\s*\[x1(?:,\s*#(0x[0-9a-f]+|\d+))?\]',args)
   if not m:raise ToolFailure('Unsupported Health memory instruction '+args)
   offset=int(m[2] or '0',0)
   if offset not in mem:raise ToolFailure('HealthInfo layout/codegen changed: '+hex(offset))
   if op=='ldr':put(m[1],mem[offset])
   else:mem[offset]=val(m[1])
  elif op=='neg':put(a[0],-val(a[1]))
  elif op=='cmp':equal=val(a[0])==val(a[1])
  elif op in ('csel','csneg'):
   if a[3] not in ('eq','ne'):raise ToolFailure('Unsupported Health condition '+a[3])
   selected=equal if a[3]=='eq' else not equal
   put(a[0],val(a[1]) if selected else (-val(a[2]) if op=='csneg' else val(a[2])))
  elif op in ('b.eq','b.ne'):
   take=equal if op=='b.eq' else not equal
   if take:
    target=int(a[0].split()[0],16)
    if target not in by:raise ToolFailure('Health branch outside inspected function')
    pc=by[target]
  else:raise ToolFailure('Unsupported Health AArch64 instruction: '+op+' '+args)
 raise ToolFailure('Health function did not return')

class Check:
 def __init__(self,mode):
  self.mode=mode;self.rows=[];self.raw=[];self.identities={};self.query_cache={};self.counter=0
  self.report=Path(os.environ['EVOX_REPORT']);self.tmp=Path(os.environ['EVOX_TMP'])/('supplemental-'+mode)
  self.fs=Path(os.environ['EVOX_EXTRACT'])/'fs';self.rd=Path(os.environ['EVOX_TMP'])/'evx_rd'
  self.tmp.mkdir(parents=True,exist_ok=False)
  self.ready=json.loads(Path(os.environ['EVOX_READY']).read_text())
  self.need('frozen controlled user/GMS target',self.ready.get('approved') is True and self.ready.get('target')=='lineage_klimt-cp2a-user' and self.ready.get('runtime_unvalidated') is True)
  ref=Path(__file__).with_name('references.json')
  if sha(ref)!=REF_SHA:raise ToolFailure('Reference fixture hash drift')
  self.ref=json.loads(ref.read_text())
  self.modules=parse_modules((S/'out/soong/Android-lineage_klimt.mk').read_text())
  self.install=(S/'out/soong/installs-lineage_klimt.mk').read_text()
  self.vars=json.loads((S/'out/soong/soong.lineage_klimt.variables').read_text())
  self.identify(S/'out/soong/Android-lineage_klimt.mk');self.identify(S/'out/soong/installs-lineage_klimt.mk');self.identify(S/'out/soong/soong.lineage_klimt.variables');self.identify(ref)
 def need(self,name,condition,details=None):
  self.rows.append({'name':name,'pass':bool(condition),'details':details});print(('PASS ' if condition else 'FAIL ')+name,flush=True)
  if not condition:raise Defect(name)
 def identify(self,p):
  self.identities[str(p)]={'sha256':sha(p),'bytes':p.stat().st_size};return self.identities[str(p)]['sha256']
 def tool(self,name):
  candidates=[S/'out/host/linux-x86/bin'/name,S/'prebuilts/build-tools/linux-x86/bin'/name]
  if name.startswith('llvm-'):candidates=list((S/'prebuilts/clang/host/linux-x86').glob('clang-r*/bin/'+name))
  if name=='javap':candidates=[S/'prebuilts/jdk/jdk21/linux-x86/bin/javap',Path('/usr/bin/javap')]
  candidates=[p for p in candidates if p.is_file()]
  if not candidates:
   found=shutil.which(name)
   if found:candidates=[Path(found)]
  if not candidates:raise ToolFailure('Tool unavailable: '+name)
  chosen=sorted(candidates)[-1];self.identify(chosen);return str(chosen)
 def run(self,argv,label,defect_exit=False):
  self.counter+=1;log=self.report/f'raw-supplemental-{self.mode}-{self.counter:03d}-{re.sub("[^a-zA-Z0-9_-]","_",label)}.txt'
  # A full-build combined.ninja load measured 54.5 s / 16 GB RSS (attempt01); 45 s timed out.
  try:r=subprocess.run(argv,cwd=S,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=900)
  except (OSError,subprocess.TimeoutExpired) as e:raise ToolFailure(str(e)) from e
  log.write_text(r.stdout);self.raw.append({'argv':argv,'exit':r.returncode,'log':str(log)})
  if r.returncode:raise (Defect if defect_exit else ToolFailure)(label+' failed: '+str(log))
  return r.stdout
 def image(self,relative):
  parts=Path(relative).parts
  if parts[0]=='recovery':
   suffix=Path(*parts[2:]);matches=[p for p in self.rd.rglob(suffix.name) if p.is_file() and str(p).endswith(str(suffix))]
  elif parts[0]=='system':matches=[p for p in [self.fs/'system/system'/Path(*parts[1:]),self.fs/relative] if p.is_file()]
  else:matches=[self.fs/relative] if (self.fs/relative).is_file() else []
  if len(matches)!=1:raise Defect('Packaged artifact absent/ambiguous: '+relative)
  return matches[0]
 def selected(self):
  obj=self.vars.get('VendorVars',{}).get('ProductPackagesSet',{})
  # ProductPackagesSet is namespaced in this graph. Search by structured key.
  def find(node):
   if isinstance(node,dict):
    if isinstance(node.get('ProductPackages'),list):return node['ProductPackages']
    for v in node.values():
     got=find(v)
     if got is not None:return got
   return None
  got=find(self.vars)
  if not got:raise ToolFailure('Current Soong ProductPackages inventory unavailable')
  return set(got)
 def query(self,p):
  key=str(p);self.queries([key])
  return self.query_cache[key]
 def queries(self,nodes):
  missing=[str(n) for n in nodes if str(n) not in self.query_cache]
  if not missing:return
  text=self.run([self.tool('ninja'),'-f','out/combined-lineage_klimt.ninja','-t','query']+missing,'query-batch')
  sections=re.split(r'(?=^\S[^\n]*:\n)',text,flags=re.M)
  for section in sections:
   key=section.splitlines()[0].removesuffix(':') if section.splitlines() else ''
   if key in missing:self.query_cache[key]=parse_query(section)
  if any(n not in self.query_cache for n in missing):raise ToolFailure('Ninja query omitted requested node')
 def module(self,name,relative,path):
  target='out/target/product/klimt/'+relative
  found=[f for f in self.modules if f.get('LOCAL_MODULE')==name and f.get('LOCAL_SOONG_INSTALLED_MODULE')==target]
  self.need('unique actual module producer '+name,len(found)==1)
  f=found[0];self.need('expected source ownership '+name,f.get('LOCAL_PATH')==path,f.get('LOCAL_PATH'))
  producer=f.get('LOCAL_PREBUILT_MODULE_FILE','');rules=re.findall(r'^'+re.escape(target)+r': ([^\n]+)$',self.install,re.M)
  self.need('actual install rule binds producer '+name,len(rules)==1 and rules[0].split()[0]==producer)
  self.need('ninja target binds installed producer '+name,producer in self.query(target))
  self.need('producer/install/image bytes agree '+name,self.identify(S/producer)==self.identify(P/relative)==self.identify(self.image(relative)))
  f=dict(f);f['_relative']=relative;f['_producer']=producer;return f
 def installed_target(self,target):
  rel=target.removeprefix('out/target/product/klimt/')
  if rel==target:raise ToolFailure('Expected product installed target: '+target)
  deps=self.query(target)
  if not deps:raise ToolFailure('Installed target lacks actual producer '+target)
  producer=deps[0]
  csha=self.identify(S/producer)
  self.need('current install/image producer equality '+rel,csha==self.identify(P/rel)==self.identify(self.image(rel)))
  return rel,producer
 def make_apk(self,name,source):
  deps=self.query('device_'+name+'_all_targets')
  installed=[d for d in deps if d.startswith('out/target/product/klimt/') and '/obj/' not in d and d.endswith('.apk')]
  if len(installed)!=1:raise ToolFailure('Selected Make APK installation ambiguous '+name)
  rel,producer=self.installed_target(installed[0]);pending=[producer];seen=set();found=False
  while pending and len(seen)<100:
   batch=[n for n in pending if n not in seen];pending=[];self.queries(batch)
   for node in batch:
    seen.add(node);inputs=self.query_cache[node]
    if str(source.relative_to(S)) in inputs:found=True;break
    pending.extend(d for d in inputs if d.startswith('out/target/product/klimt/obj/APPS/'+name+'_intermediates/'))
   if found:break
  self.need('current Make APK graph consumes '+name,found)
  self.identify(source);self.need('selected GMS compiled payload equals source '+name,same_zip_payload(source,self.image(rel)))
  return rel
 def reaches_source(self,f,source):
  root='out/soong/.intermediates/'+f['LOCAL_PATH']+'/'+f['LOCAL_MODULE'].split('.')[0]+'/'
  # Module names contain dots. Derive prefix directly from selected producer.
  producer=f['_producer'];m=re.match(r'(out/soong/\.intermediates/.+?/'+re.escape(f['LOCAL_MODULE'].removesuffix('.vendor'))+r'/)',producer)
  if m:root=m[1]
  pending=[producer];seen=set();found=False
  while pending and len(seen)<350:
   batch=[n for n in pending if n not in seen];pending=[];self.queries(batch)
   for node in batch:
    seen.add(node);deps=self.query_cache[node]
    if source in deps:found=True;break
    pending.extend(d for d in deps if d.startswith(root))
   if found:break
  self.need('current ninja producer consumes '+source,found,{'producer':producer,'nodes':len(seen)})
  self.identify(S/source)
 def elf(self,p):
  text=self.run([self.tool('readelf'),'-h','-d','-n','-Ws',str(p)],'elf-'+p.name)
  self.need('actual AArch64 ELF '+p.name,'AArch64' in text and p.read_bytes()[:4]==b'\x7fELF')
  return text
 def disassemble(self,f,symbol):
  p=S/f['LOCAL_SOONG_UNSTRIPPED_BINARY'];self.identify(p)
  # Match .text bytes, not Build ID alone: a stale unstripped file is rejected.
  built=S/f['_producer'];objcopy=self.tool('llvm-objcopy')
  a=self.tmp/(p.name+'.producer.text');b=self.tmp/(p.name+'.unstripped.text')
  self.run([objcopy,'--dump-section','.text='+str(a),str(built)],'producer-text')
  self.run([objcopy,'--dump-section','.text='+str(b),str(p)],'unstripped-text')
  self.need('unstripped/installed executable .text equality '+p.name,self.identify(a)==self.identify(b))
  text=self.run([self.tool('llvm-objdump'),'-d','--disassemble-symbols='+symbol,str(p)],'disassembly-'+symbol)
  if 'failed to disassemble' in text or not parse_instructions(text):raise ToolFailure('Expected producer function missing '+symbol)
  return text
 def finish(self,status,error=None):
  out={'coverage':self.mode,'status':status,'error':error,'checks':self.rows,'inputs':self.identities,'raw':self.raw,'time':time.time(),'runtime_unvalidated':True,'limitations':['Static producer/image validation cannot prove device runtime behavior.','Unsupported compiler code generation is a tooling failure requiring reviewed adaptation.']}
  (self.report/('supplemental-'+self.mode+'.json')).write_text(json.dumps(out,indent=2)+'\n')

def policy(c):
 # Klimt ships split CIL, not vendor/precompiled_sepolicy. Reconstruct the exact
 # binary producer from its *packaged* CIL inputs using current Ninja arguments.
 target='out/soong/.intermediates/system/sepolicy/precompiled_sepolicy/android_common/klimt/precompiled_sepolicy'
 commands=c.run([c.tool('ninja'),'-f','out/combined-lineage_klimt.ninja','-t','commands',target],'current-policy-producer-commands')
 matches=[l for l in commands.splitlines() if l.startswith('out/host/linux-x86/bin/secilc ') and '-o '+target+'_policy' in l]
 if len(matches)!=1:raise ToolFailure('Exact normal policy producer command unavailable')
 command=matches[0].split(' && ',1)[0];argv=shlex.split(command);argv[0]=c.tool('secilc')
 installed=[]
 for i,arg in enumerate(argv):
  if arg.endswith('.cil'):
   targets=re.findall(r'^([^:\n]+): '+re.escape(arg)+r'(?:\s|$)',c.install,re.M)
   targets=[t for t in targets if t.startswith('out/target/product/klimt/')]
   if len(targets)!=1:raise ToolFailure('CIL producer install mapping missing/ambiguous: '+arg)
   rel=targets[0].removeprefix('out/target/product/klimt/');packaged=c.image(rel)
   c.need('installed CIL equals current producer '+rel,c.identify(packaged)==c.identify(S/arg)==c.identify(S/targets[0]))
   argv[i]=str(packaged);installed.append(rel)
 c.need('normal policy reconstruction complete',len(installed)>=8,installed)
 normal=c.tmp/'packaged-normal-sepolicy';argv[argv.index('-o')+1]=str(normal)
 c.run(argv,'recompile-packaged-normal-policy',True)
 c.need('packaged CIL yields actual compiled normal policy',c.identify(normal)==c.identify(S/target))
 c.need('normal producer invokes retained root analyzer','out/host/linux-x86/bin/sepolicy-analyze '+target+'_policy permissive' in matches[0])
 recovery=c.image('recovery/root/sepolicy')
 c.need('recovery compiled policy equals current install',c.identify(recovery)==c.identify(P/'recovery/root/sepolicy'))
 expected_policy={p['name']:set(p['permissive_domains']) for p in c.ref['policy_reference']}
 for label,p,allowed in [('normal',normal,expected_policy['normal']),('recovery',recovery,expected_policy['recovery'])]:
  names=set(c.run([c.tool('sepolicy-analyze'),str(p),'permissive'],'permissive-'+label).split())
  c.need('exact '+label+' permissive inventory',names==allowed,sorted(names))
  conf=c.tmp/(label+'.policy.conf')
  c.run([c.tool('checkpolicy'),'-b','-F','-M','-o',str(conf),str(p)],'binary-policy-conf-'+label)
  c.identify(conf);text=conf.read_text()
  # Evolution X 12.3 declares `permissive su;` outside userdebug_or_eng (evox16 reverted that
  # locally; evox17 keeps upstream). The exact inventory above binds it; this binds the text.
  c.need('su permissiveness follows upstream '+label,('permissive su;' in text)==('su' in allowed))
  if label=='normal':
   for ty in ('xiaomi_touch_device','displayfeature_device'):
    rules=re.findall(r'^allow hal_fingerprint_default '+re.escape(ty)+r'\s*:\s*chr_file\s+([^;]+);',text,re.M)
    perms=set(re.findall(r'\b\w+\b',' '.join(rules)))
    c.need('compiled fingerprint '+ty+' access',{'ioctl','open','read','write'}<=perms,sorted(perms))
   c.need('compiled sensor touch read access',bool(re.search(r'^allow hal_sensors_default sysfs_touch\s*:\s*file\s+[^;]*\bread\b',text,re.M)))
 for rel in ['vendor/etc/selinux/vendor_file_contexts','system/etc/selinux/plat_property_contexts','vendor/etc/selinux/vendor_service_contexts','vendor/etc/selinux/vendor_hwservice_contexts']:
  p=c.image(rel);c.need('packaged compiled context matches installed '+rel,c.identify(p)==c.identify(P/rel))
 contexts=c.image('vendor/etc/selinux/vendor_file_contexts').read_text()
 for path,label in [('/dev/xiaomi-touch','xiaomi_touch_device'),('/dev/mi_display/disp_feature','displayfeature_device'),('/vendor/bin/hw/android.hardware.biometrics.fingerprint-service.xiaomi','hal_fingerprint_default_exec')]:
  matches=[]
  for l in contexts.splitlines():
   if l.startswith('#') or not l.strip():continue
   fields=l.split()
   if len(fields)>=2:
    try:matched=re.fullmatch(fields[0],path)
    except re.error as e:raise ToolFailure('Invalid generated file_context regex') from e
    if matched:matches.append(fields[-1])
  c.need('compiled specific device context '+path,'u:object_r:'+label+':s0' in matches,matches)
 prop=c.image('system/etc/selinux/plat_property_contexts').read_text()
 # The shipped (and every historical) entry is the prefix `persist.sys.tap_gesture`
 # without a trailing dot; resolve the bridge's actual properties by longest prefix.
 entries=[]
 for rel in ['system/etc/selinux/plat_property_contexts','system_ext/etc/selinux/system_ext_property_contexts','product/etc/selinux/product_property_contexts','vendor/etc/selinux/vendor_property_contexts','odm/etc/selinux/odm_property_contexts']:
  p=c.fs/rel if not rel.startswith('system/') else c.fs/'system'/rel
  if p.is_file():
   for l in p.read_text().splitlines():
    f=l.split()
    if len(f)>=2 and not f[0].startswith('#'):entries.append((f[0],f[1],'exact' in f[2:]))
 def prop_label(name):
  hits=[(len(n),label) for n,label,exact in entries if (name==n if exact else name.startswith(n))]
  return max(hits)[1] if hits else None
 labels={n:prop_label(n) for n in ['persist.sys.tap_gesture.dt2w','persist.sys.tap_gesture.fod_screen_off']}
 c.need('compiled touch gesture property label',bool(prop) and all(v=='u:object_r:gesture_prop:s0' for v in labels.values()),labels)
 # evox17 carries no system/sepolicy change: the policy source is the reviewed upstream commit.
 analyzer=S/'out/host/linux-x86/bin/sepolicy-analyze';c.identify(analyzer)
 upstream_head(c,'system/sepolicy')

def upstream_head(c,project):
 """The project HEAD is the frozen pin and that pin is the reviewed upstream commit (no local change)."""
 head=c.run(['git','-C',str(S/project),'rev-parse','HEAD'],project.replace('/','-')+'-head').strip()
 status=c.run(['git','-C',str(S/project),'status','--porcelain','--untracked-files=normal'],project.replace('/','-')+'-status')
 c.need(project+' is the reviewed upstream commit',head==c.ready['reviewed_project_heads'].get(project)==c.ref['upstream_heads'][project] and not status.strip(),head)

def patch_packaging(c):
 f=c.module('miui-framework-stub','system/framework/miui-framework-stub.jar','device/xiaomi/klimt/miui-stub')
 boot=c.vars.get('BootJars',[]);c.need('MIUI actual bootclasspath membership','platform:miui-framework-stub' in boot)
 dexdump=c.tool('dexdump');jar=c.image(f['_relative'])
 xml=c.run([dexdump,'-l','xml',str(jar)],'miui-bootjar-dex')
 root=ET.fromstring(xml);packages=[p.get('name') for p in root.iter('package')]
 c.need('MIUI installed DEX package exists',any(p=='miui' or p.startswith('miui.') for p in packages if p),packages)
 allow=S/'build/soong/scripts/check_boot_jars/package_allowed_list.txt';c.identify(allow)
 patterns=[l.strip() for l in allow.read_text().splitlines() if l.strip() and not l.startswith('#')]
 allowed=re.compile('^(?:'+'|'.join(patterns)+')$')
 c.need('actual packaged MIUI jars satisfy current boot allowlist',bool(packages) and all(p and allowed.fullmatch(p) for p in packages))
 native=c.module('libui','system/lib64/libui.so','frameworks/native/libs/ui');c.elf(c.image(native['_relative']))
 c.reaches_source(native,'frameworks/native/libs/ui/Gralloc5.cpp')
 # Resolve exact compiled symbol from the current unstripped ELF symbol table.
 text=c.run([c.tool('readelf'),'-Ws',str(S/native['LOCAL_SOONG_UNSTRIPPED_BINARY'])],'libui-symbols')
 syms=sorted({l.split()[-1] for l in text.splitlines() if 'Gralloc5' in l and 'getSmpte2094_50' in l and ' FUNC ' in l})
 if len(syms)!=1:raise ToolFailure('Gralloc5 getter symbol missing/ambiguous')
 dis=c.disassemble(native,syms[0])
 ins=parse_instructions(dis)
 c.need('actual Gralloc getter initializes static capability guard','kGettable' in dis and '__cxa_guard_acquire' in dis and '__cxa_guard_release' in dis)
 # Mapper v5 table slots are getStandardMetadata=0x48, listSupportedMetadataTypes=0x60.
 c.need('actual Gralloc guard queries supported metadata list',bool(re.search(r'\bldr\s+x\d+,\s*\[x\d+, #0x60\]',dis)))
 gate=next((i for i,x in enumerate(ins) if x[1]=='b.ne' and i>0 and ins[i-1][1]=='cmp' and '#0x1' in ins[i-1][2]),None)
 getter=next((i for i,x in enumerate(ins) if x[1]=='ldr' and '#0x48]' in x[2]),None)
 c.need('actual Gralloc guard precedes metadata getter',gate is not None and getter is not None and gate<getter)
 if gate is not None:
  target=int(ins[gate][2].split()[0],16);branch=[x for x in ins if x[0]==target]
  c.need('unsupported metadata gate returns UNKNOWN_TRANSACTION',len(branch)==1 and branch[0][1]=='mov' and bool(re.search(r'w0,\s*#-0x4a\b',branch[0][2])))
 c.need('actual Gralloc guard checks SMPTE2094_50 type24',bool(re.search(r'\bcmp\s+x\d+,\s*#0x18\b',dis)))
 # Preserve lights' AIDL-only consumer route and exact current install producer.
 c.module('android.hardware.lights-service.mediatek','odm/bin/hw/android.hardware.lights-service.mediatek','vendor/xiaomi/klimt')
 light=c.image('odm/bin/hw/android.hardware.lights-service.mediatek');elf=c.elf(light)
 c.need('stock light actual AIDL dependency','libbinder_ndk.so' in elf)
 c.need('generic light alternatives absent',not any(p.is_file() for p in c.fs.rglob('android.hardware.lights-service.example')) and not any(p.is_file() for p in c.fs.rglob('android.hardware.light-service.lineage')))
 for rel in ['odm/etc/init/lights-mtk-default.rc','odm/etc/vintf/manifest/lights-mtk-default.xml']:
  p=c.image(rel);c.need('lights packaged metadata current '+rel,c.identify(p)==c.identify(P/rel))
 # evox16 re-added the 12.2 root-hiding UnixFileSystem change on top of AOSP libcore; evox17
 # follows Evolution X 12.3, which moved libcore to plain AOSP.
 upstream_head(c,'libcore')

def private_compatibility(c):
 for f in c.ref['private_route']:
  rel=f['path'].split('/proprietary/',1)[1];p=c.image(rel)
  c.need('private artifact baseline preserved '+rel,c.identify(S/f['path'])==c.identify(P/rel)==c.identify(p)==f['sha256'])
 for f in c.ref['private_elf']:
  rel=f['path'].split('/proprietary/',1)[1];text=c.elf(c.image(rel))
  needed=set(re.findall(r'\(NEEDED\).*?\[(.*?)\]',text))
  c.need('private ELF ABI dependencies '+rel,needed==set(f['needed']),sorted(needed))
  c.need('private ELF Build ID '+rel,set(re.findall(r'Build ID: (\w+)',text))==set(f['buildid']))
 # evox17 uses LineageOS's default ION-free libdmabufheap (evox16's legacy selector was reverted).
 # Upstream keeps the old BufferAllocator entry points for binary compatibility; bind the exact
 # symbols the proprietary users can only resolve from libdmabufheap.so, on the packaged vendor lib.
 upstream_head(c,'system/memory/libdmabufheap')
 vv=c.vars.get('VendorVars',{})
 c.need('allocator uses the upstream default implementation',vv.get('libdmabufheap',{}).get('legacy_impl') in (None,'false') and vv.get('libion',{}).get('legacy_impl') in (None,'false'),{'libdmabufheap':vv.get('libdmabufheap'),'libion':vv.get('libion')})
 f=c.module('libdmabufheap','system/lib64/libdmabufheap.so','system/memory/libdmabufheap');c.elf(c.image('system/lib64/libdmabufheap.so'));c.reaches_source(f,'system/memory/libdmabufheap/BufferAllocator.cpp')
 vendor=c.image('vendor/lib64/libdmabufheap.so');c.elf(vendor)
 exported={l.split()[-1] for l in c.run([c.tool('llvm-nm'),'-D','--defined-only',str(vendor)],'vendor-libdmabufheap-exports').splitlines() if l.strip()}
 required=set(c.ref['allocator_vendor_abi'])
 c.need('vendor libdmabufheap exports every symbol the blobs resolve from it',required<=exported,sorted(required-exported))
 f=c.module('libion','system/lib64/libion.so','system/memory/libion');c.elf(c.image('system/lib64/libion.so'));c.reaches_source(f,'system/memory/libion/ion.c')
 text=c.disassemble(f,'ion_open');instructions=parse_instructions(text)
 c.need('actual libion ion_open keeps stub backend',len(instructions)==2 and instructions[0][1]=='mov' and re.search(r'w0,\s*#-0x1\b',instructions[0][2]) is not None and instructions[1][1]=='ret')
 wifi=c.module('libwifi-hal-mtk-shim','vendor/lib64/libwifi-hal-mtk-shim.so','device/xiaomi/klimt/wifi');text=c.elf(c.image(wifi['_relative']))
 c.need('Wi-Fi shim exports actual entry point',bool(re.search(r'GLOBAL\s+DEFAULT\s+\d+\s+init_wifi_vendor_hal_func_table\b',text)))
 c.reaches_source(wifi,'device/xiaomi/klimt/wifi/wifi_hal_shim.cpp')
 c.need('Wi-Fi shim packaged stock library target',b'/vendor/lib64/libwifi-hal-mtk.so\0' in c.image(wifi['_relative']).read_bytes())

def health_semantics(c):
 for path,digest in c.ref['health_sources'].items():c.need('reviewed Health semantic source '+path,c.identify(S/path)==digest)
 for name,rel in [('android.hardware.health-service.klimt','vendor/bin/hw/android.hardware.health-service.klimt'),('android.hardware.health-service.klimt_recovery','recovery/root/system/bin/hw/android.hardware.health-service.klimt_recovery')]:
  f=c.module(name,rel,'device/xiaomi/klimt/health');c.elf(c.image(rel));c.reaches_source(f,'device/xiaomi/klimt/health/main.cpp')
  update=c.disassemble(f,'_ZN11KlimtHealth16UpdateHealthInfoEPN4aidl7android8hardware6health10HealthInfoE')
  cases=[0,1,-1,500000,-500000,2147483647,-2147483647,-2147483648]
  outcomes=[]
  for raw in cases:
   mem=health_update_eval(update,raw);expected=(0 if raw==-2147483648 else -raw)&0xffffffff
   c.need('compiled '+name+' HealthInfo case '+str(raw),mem[0x24]==expected and mem[0x50]==0 and mem[0x90]==0xffffffffffffffff,mem)
   outcomes.append({'raw':raw,'now':mem[0x24],'average':mem[0x50],'ttf':mem[0x90]})
  now=c.disassemble(f,'_ZN11KlimtHealth22getCurrentNowMicroampsEPi');avg=c.disassemble(f,'_ZN11KlimtHealth26getCurrentAverageMicroampsEPi')
  c.need('compiled '+name+' direct getter current normalization',bool(re.search(r'\bneg\s+w\d+,\s*w\d+',now)) and '#-0x80000000' in now and 'AStatus_fromExceptionCode' in now and '#-0x7' in now)
  c.need('compiled '+name+' direct average unsupported',bool(re.search(r'\bstr\s+wzr,\s*\[x1\]',avg)) and '#-0x7' in avg and 'AStatus_fromExceptionCode' in avg)
  c.need('compiled '+name+' real current sysfs path',b'/sys/class/power_supply/battery/current_now\0' in c.image(rel).read_bytes())

def gms_themes_apps(c):
 # Record actual packaged APKs before any old-artifact failure. Duplicate package
 # identities are evidence for review; their presence alone is not an invented
 # new gate because a reviewed preinstalled split/stub layout may be legitimate.
 inventory=[];badging_cache={}
 for apk in sorted(c.fs.rglob('*.apk')):
  relative=str(apk.relative_to(c.fs));record={'relative':relative,'path':str(apk)}
  if apk.is_symlink():record.update(kind='symlink',target=os.readlink(apk),package=None)
  elif apk.is_file():
   digest=c.identify(apk);record.update(kind='file',sha256=digest,bytes=apk.stat().st_size)
   if digest not in badging_cache:
    text=c.run([c.tool('aapt2'),'dump','badging',str(apk)],'image-apk-badging-'+apk.stem)
    package=re.search(r"^package: name='([^']+)'",text,re.M)
    if not package:raise ToolFailure('Image APK package identity unavailable: '+relative)
    badging_cache[digest]={'package':package[1],'package_line':next(l for l in text.splitlines() if l.startswith('package:'))}
   record.update(badging_cache[digest])
  else:continue
  inventory.append(record)
  (c.report/'image-apk-inventory.json').write_text(json.dumps(inventory,indent=2)+'\n')
 (c.report/'image-apk-duplicate-packages.json').write_text(json.dumps(duplicate_apk_packages(inventory),indent=2)+'\n')
 old=c.ref.get('obsolete_installed_artifacts',[])
 if len(old)!=7 or len({p['relative'] for p in old})!=7:raise ToolFailure('Reviewed seven-artifact GMS absence fixture missing/ambiguous')
 presence=obsolete_artifacts_present(c.fs,old)
 (c.report/'obsolete-installed-artifacts.json').write_text(json.dumps({'baseline':old,'present':presence},indent=2)+'\n')
 c.need('reviewed obsolete GMS installed artifact paths absent',not presence,[p['relative'] for p in presence])
 selected=c.selected();c.need('removed GMS module names unselected',not (set(c.ref['removed_gms_modules'])&selected),sorted(set(c.ref['removed_gms_modules'])&selected))
 c.need('actual GMS core selection',{'Phonesky','GoogleServicesFramework'}<=selected and any('GmsCore' in x for x in selected))
 c.need('Canvas excluded in GMS graph','Canvas' not in selected and not list(c.fs.rglob('Canvas.apk')))
 obsolete=[n for n in selected if re.search(r'ThemeIcons|IconPack(Acherus|Gradicon|Lorn|PUI)',n)]
 c.need('obsolete ThemeIcons module consumers absent',not obsolete,obsolete)
 # Every selected GMS APK has a real current source object and installed producer.
 # This also records renamed package modules and permits intentional downgrades.
 gms=[f for f in c.modules if f.get('LOCAL_PATH','').startswith('vendor/gms') and f.get('LOCAL_MODULE') in selected and f.get('LOCAL_SOONG_INSTALLED_MODULE','').endswith('.apk')]
 make=[]
 for mk in (S/'vendor/gms').rglob('Android.mk'):
  for block in mk.read_text().split('include $(CLEAR_VARS)'):
   fields=dict(re.findall(r'^(LOCAL_[A-Z0-9_]+)\s*:?=\s*(.*)$',block,re.M))
   if fields.get('LOCAL_MODULE') in selected and fields.get('LOCAL_MODULE_CLASS')=='APPS':
    # PrebuiltGmsCore companions use LOCAL_SRC_FILES := .../$(LOCAL_MODULE).apk;
    # expand only that variable and still reject any other Make expression.
    src=fields.get('LOCAL_SRC_FILES','').replace('$(LOCAL_MODULE)',fields['LOCAL_MODULE'])
    if '$' in src or not src.endswith('.apk'):raise ToolFailure('Unsupported GMS Make source '+str(mk))
    make.append((fields['LOCAL_MODULE'],mk.parent/src))
 c.need('actual selected GMS APK graph nonempty',len(gms)+len(make)>=20,{'soong':len(gms),'make':len(make)})
 c.queries(['device_'+name+'_all_targets' for name,_ in make])
 make_targets=[d for name,_ in make for d in c.query_cache['device_'+name+'_all_targets'] if d.startswith('out/target/product/klimt/') and '/obj/' not in d and d.endswith('.apk')]
 c.queries(make_targets+[f['LOCAL_SOONG_INSTALLED_MODULE'] for f in gms])
 c.queries([c.query_cache[t][0] for t in make_targets if c.query_cache[t]])
 installed_gms=[]
 for f in gms:
  rel=f['LOCAL_SOONG_INSTALLED_MODULE'].removeprefix('out/target/product/klimt/');p=c.image(rel)
  c.module(f['LOCAL_MODULE'],rel,f['LOCAL_PATH'])
  installed_gms.append(rel)
  with zipfile.ZipFile(p) as z:c.need('packaged GMS APK resources '+f['LOCAL_MODULE'],'AndroidManifest.xml' in z.namelist() and z.testzip() is None)
 for name,source in make:installed_gms.append(c.make_apk(name,source))
 # Permission XMLs are concrete output files. Preserve every installed source
 # GMS grant via producer hash and parse its packaged permission declarations.
 permissions=[p for partition in ['system','system_ext','product'] for p in (P/partition/'etc/permissions').glob('*.xml')]
 google_permissions=[]
 permissions=[p for p in permissions if 'com.google.' in p.read_text() or 'com.android.vending' in p.read_text()]
 c.queries([str(p.relative_to(S)) for p in permissions])
 for p in permissions:
  text=p.read_text()
  if 'com.google.' not in text and 'com.android.vending' not in text:continue
  rel=str(p.relative_to(P));c.installed_target(str(p.relative_to(S)));root=ET.parse(c.image(rel)).getroot()
  c.need('installed Google permissions valid '+rel,root.tag=='permissions');google_permissions.append(rel)
 c.need('actual GMS permission files present',len(google_permissions)>=5,len(google_permissions))
 for p in sorted((S/'vendor/gms').rglob('*.apk')):
  c.need('GMS source real binary '+str(p.relative_to(S)),p.read_bytes()[:4]==b'PK\x03\x04')
  c.identify(p)
  with zipfile.ZipFile(p) as z:c.need('GMS source binary manifest '+p.name,'AndroidManifest.xml' in z.namelist())
 theme=c.module('AxThemeStore','system_ext/priv-app/AxThemeStore/AxThemeStore.apk','packages/apps/ThemeStore')
 manifest=c.run([c.tool('aapt2'),'dump','xmltree',str(c.image(theme['_relative'])),'--file','AndroidManifest.xml'],'ThemeStore-manifest')
 c.need('ThemeStore packaged identity','com.android.axion.axthemestore' in manifest and 'android.uid.system' in manifest)
 c.need('ThemeStore compiled explicit activity exists','MainActivity' in manifest and 'exported' in manifest)
 c.need('ThemeStore resolved private provider','${applicationId}' not in manifest and 'com.android.axion.axthemestore.fileprovider' in manifest)
 permissions=c.module('privapp-permissions-axthemestore','system_ext/etc/permissions/privapp-permissions-axthemestore.xml','packages/apps/ThemeStore')
 root=ET.parse(c.image(permissions['_relative'])).getroot();grants=root.findall("privapp-permissions[@package='com.android.axion.axthemestore']/permission")
 c.need('ThemeStore actual install grants',{'android.permission.INSTALL_PACKAGES','android.permission.DELETE_PACKAGES','android.permission.QUERY_ALL_PACKAGES'}<={p.get('name') for p in grants})
 # Evolver is merged into Settings-core; GMS selects SettingsGoogle as its app.
 f=c.module('SettingsGoogle','system_ext/priv-app/SettingsGoogle/SettingsGoogle.apk','vendor/unbundled_google/packages/SettingsGoogle');rel=f['_relative']
 route=c.run([c.tool('aapt2'),'dump','xmltree',str(c.image(rel)),'--file','res/xml/evolution_settings_themes.xml'],'Evolver-theme-component-route')
 c.need('compiled Evolver ThemeStore component closure','com.android.axion.axthemestore' in route and 'com.android.axion.axthemestore.MainActivity' in route)
 # vendor/themes is a catalog and binary asset repository, not an installed Soong module.
 # Validate its protected complete catalog/assets without inventing a namespace.
 for catalog in ['themes.json','themes_v2.json']:
  p=S/'vendor/themes'/catalog;c.identify(p);data=json.loads(p.read_text());c.need('theme catalog parses '+catalog,isinstance(data,dict) and bool(data.get('themes')))
 apks=list((S/'vendor/themes/apks').glob('*.apk'));c.need('theme catalog binary assets exist',bool(apks))
 for p in apks:
  c.identify(p)
  with zipfile.ZipFile(p) as z:c.need('theme source APK real resources '+p.name,'AndroidManifest.xml' in z.namelist() and 'resources.arsc' in z.namelist())

def doze_packaging(c):
 f=c.module('KlimtTouchBridge','system_ext/priv-app/KlimtTouchBridge/KlimtTouchBridge.apk','device/xiaomi/klimt/apps/TouchBridge')
 c.reaches_source(f,'device/xiaomi/klimt/apps/TouchBridge/src/org/lineageos/klimt/touchbridge/TouchBridgeApp.java')
 manifest=c.run([c.tool('aapt2'),'dump','xmltree',str(c.image(f['_relative'])),'--file','AndroidManifest.xml'],'TouchBridge-manifest')
 for value in ['org.lineageos.klimt.touchbridge','android.uid.system','TouchBridgeApp']:
  c.need('TouchBridge compiled manifest '+value,value in manifest)
 for value in ['persistent','directBootAware','defaultToDeviceProtectedStorage']:c.need('TouchBridge actual manifest enabled '+value,manifest_true(manifest,value))
 jar=S/f['LOCAL_SOONG_CLASSES_JAR'];c.identify(jar)
 code=c.run([c.tool('javap'),'-c','-p','-classpath',str(jar),'org.lineageos.klimt.touchbridge.TouchBridgeApp'],'TouchBridge-javap')
 update=code.split('private void update();',1)[-1]
 # evox17 restores the evox15 bridge: the panel gesture follows secure double_tap_to_wake only
 # (evox16's extra doze_trigger_doubletap observer was reverted as not needed).
 c.need('compiled bridge reads the wake setting','Settings$Secure.getIntForUser' in update and 'String double_tap_to_wake' in update)
 c.need('compiled bridge has no doze double-tap observer','doze_trigger_doubletap' not in code and 'Settings$System.getUriFor' not in code)
 c.need('compiled bridge active user/FOD independence',len(re.findall(r'\bbipush\s+-2\b',update))>=2 and 'String screen_off_udfps_enabled' in update and 'String persist.sys.tap_gesture.fod_screen_off' in update)
 c.need('compiled observer tracks wake and FOD settings','String android.intent.action.USER_SWITCHED' in code and code.count('registerContentObserver')==2)
 dex=c.run([c.tool('dexdump'),'-d',str(c.image(f['_relative']))],'TouchBridge-dex')
 c.need('packaged bridge DEX is the evox15 bridge','doze_trigger_doubletap' not in dex and 'TouchBridgeApp' in dex and 'persist.sys.tap_gesture.dt2w' in dex)
 handler=c.module('libudfpshandler','vendor/lib64/libudfpshandler.so','device/xiaomi/klimt/udfps');c.elf(c.image(handler['_relative']));c.reaches_source(handler,'device/xiaomi/klimt/udfps/UdfpsHandler.cpp')
 sensor=c.module('sensors.xiaomi.v2','vendor/lib64/sensors.xiaomi.v2.so','hardware/xiaomi/sensors/v2');c.elf(c.image(sensor['_relative']));c.reaches_source(sensor,'hardware/xiaomi/sensors/v2/Sensor.cpp')
 c.need('actual custom wake sensor identity',b'org.lineageos.sensor.udfps\0' in c.image(sensor['_relative']).read_bytes())
 c.module('android.hardware.biometrics.fingerprint-service.xiaomi','vendor/bin/hw/android.hardware.biometrics.fingerprint-service.xiaomi','hardware/xiaomi/aidl/fingerprint')
 hals=c.image('vendor/etc/sensors/hals.conf');c.need('packaged sensor service route',c.identify(hals)==c.identify(S/'device/xiaomi/klimt/configs/sensors/hals.conf') and 'sensors.xiaomi.v2.so' in hals.read_text())
 framework=c.module('framework-res','system/framework/framework-res.apk','frameworks/base/core/res')
 res=c.run([c.tool('aapt2'),'dump','resources',str(c.image(framework['_relative']))],'framework-resources')
 expected={'config_dozeAlwaysOnDisplayAvailable':'true','config_dozeAlwaysOnEnabled':'false','config_dozeSupportsAodWallpaper':'false','config_screen_off_udfps_enabled':'true','config_screen_off_udfps_default_on':'true','config_supportDoubleTapWake':'true','config_dozeComponent':'com.android.systemui/com.android.systemui.doze.DozeService','config_dozeUdfpsLongPressSensorType':'org.lineageos.sensor.udfps'}
 # Mirror current OverlayConfig partition/config/static-priority ordering. Actual
 # packaged RRO values override earlier values; source XML conflict is not a defect.
 effective={name:resource_values(res,name) for name in expected};owners={name:'framework-res' for name in expected}
 order=['system','vendor','odm','oem','product','system_ext'];orderfile=c.fs/'product/overlay/partition_order.xml'
 if orderfile.is_file():
  c.installed_target('out/target/product/klimt/product/overlay/partition_order.xml');root=ET.parse(orderfile).getroot()
  custom=[p.get('name') for p in root.iter('partition')]
  if root.tag=='partition-order' and len(custom)==6 and set(custom)==set(order):order=custom
  else:c.rows.append({'name':'invalid partition order falls back to platform order','pass':True,'details':custom})
 resolution=[]
 for source in ['frameworks/base/core/java/android/content/pm/PackagePartitions.java','frameworks/base/core/java/com/android/internal/content/om/OverlayConfig.java','frameworks/base/core/java/com/android/internal/content/om/OverlayConfigParser.java']:c.identify(S/source)
 for partition in order:
  directory=c.fs/partition/('system/overlay' if partition=='system' else 'overlay')
  overlays=[]
  for apk in sorted(directory.rglob('*.apk')) if directory.is_dir() else []:
   manifest=c.run([c.tool('aapt2'),'dump','xmltree',str(apk),'--file','AndroidManifest.xml'],'overlay-'+apk.stem)
   if manifest_attr(manifest,'targetPackage')!='android':continue
   resources=c.run([c.tool('aapt2'),'dump','resources',str(apk)],'overlay-resources-'+apk.stem)
   if not any(re.search(r'\b(?:bool|string)/'+re.escape(name)+r'\b',resources) for name in expected):continue
   rel=partition+'/overlay/'+str(apk.relative_to(directory));c.installed_target('out/target/product/klimt/'+rel)
   priority=manifest_attr(manifest,'priority','0')
   overlays.append({'package':manifest_attr(manifest,'package'),'static':manifest_true(manifest,'isStatic'),'priority':int(priority,0),'path':str(apk),'resources':resources})
  cfg=directory/'config/config.xml';configured=None
  if cfg.is_file():
   configured,files=overlay_order_config(cfg)
   for p in files:c.installed_target('out/target/product/klimt/'+partition+'/overlay/'+str(p.relative_to(directory)))
  enabled=order_overlays(overlays,configured)
  for overlay in enabled:
   values={name:resource_values(overlay['resources'],name) for name in expected if re.search(r'\b(?:bool|string)/'+re.escape(name)+r'\b',overlay['resources'])}
   effective.update(values);owners.update({name:overlay['path'] for name in values});resolution.append({'partition':partition,'package':overlay['package'],'priority':overlay['priority'],'path':overlay['path'],'config':str(cfg) if configured is not None else None,'values':values})
 (c.report/'doze-overlay-resolution.json').write_text(json.dumps({'partition_order':order,'enabled_relevant_overlays':resolution,'effective':effective,'owners':owners},indent=2)+'\n')
 for name,value in expected.items():c.need('compiled effective Doze resource '+name,effective[name]==value,{'value':effective[name],'owner':owners[name]})
 props=prop_map(c.image('system/build.prop').read_text());vendor=prop_map(c.image('vendor/build.prop').read_text())
 c.need('actual panel low-power Doze property',props.get('doze.display.supported')=='true')
 c.need('actual sensor UDFPS property',vendor.get('ro.vendor.sensors.xiaomi.udfps')=='true' and vendor.get('persist.vendor.fingerprint.type')=='udfps_optical')
 ui=c.module('SystemUIGoogle','system_ext/priv-app/SystemUIGoogle/SystemUIGoogle.apk','vendor/unbundled_google/packages/SystemUIGoogle')
 uim=c.run([c.tool('aapt2'),'dump','xmltree',str(c.image(ui['_relative'])),'--file','AndroidManifest.xml'],'SystemUI-manifest')
 c.need('packaged SystemUI DozeService exists','com.android.systemui.doze.DozeService' in uim or '".doze.DozeService"' in uim)

def install_integrity(c):
 # evox16 boot-looped on the phone: the focused precheck's `m Telecom` had installed the legacy
 # Telecom app into the staging directory, the image was packed from that directory, and
 # PackageManager kept it over TelecomShim ("Skipping duplicate"). The verifier had recorded the
 # duplicate without failing. These gates make that class of defect fatal.
 owner=next((p/'owner.json' for p in Path(os.environ['EVOX_READY']).resolve().parents if (p/'owner.json').is_file()),None)
 if not owner:raise ToolFailure('Attempt owner record unavailable')
 started=json.loads(owner.read_text())['started_ns']
 listing=P/'.installable_files';c.identify(listing)
 c.need('install list written by this attempt',listing.stat().st_mtime_ns>=started)
 installable={x.removeprefix('out/target/product/klimt/') for x in listing.read_text().split()}
 staged=[str(p.relative_to(P)) for part in ['system','system_ext','product','vendor','odm','vendor_dlkm','system_dlkm','odm_dlkm'] if (P/part).is_dir() for p in (P/part).rglob('*') if p.is_file() or p.is_symlink()]
 other,kernel=stray_staged(staged,installable)
 (c.report/'staged-not-installed.json').write_text(json.dumps({'other':other,'kernel_module_files':kernel},indent=2)+'\n')
 c.need('every staged file is a product install (kernel module trees excepted)',not other,other)
 c.need('kernel module trees present',len([k for k in kernel if k.endswith('.ko')])>=600,len(kernel))
 # The image must hold exactly the staged APKs, and no package identity twice.
 image_apks=set();inventory=[];badging={}
 for apk in sorted(c.fs.rglob('*.apk')):
  if not (apk.is_file() or apk.is_symlink()):continue
  rel=image_relative(str(apk.relative_to(c.fs)));image_apks.add(rel)
  if apk.is_symlink():continue
  digest=c.identify(apk)
  if digest not in badging:
   text=c.run([c.tool('aapt2'),'dump','badging',str(apk)],'install-badging-'+apk.stem)
   m=re.search(r"^package: name='([^']+)'",text,re.M)
   if not m:raise ToolFailure('Image APK package identity unavailable: '+rel)
   badging[digest]=m[1]
  inventory.append({'relative':rel,'sha256':digest,'package':badging[digest]})
 staged_apks={s for s in staged if s.endswith('.apk')}
 c.need('image APK set equals staged product installs',image_apks==staged_apks,{'image_only':sorted(image_apks-staged_apks),'staged_only':sorted(staged_apks-image_apks)})
 c.need('every image APK is a product install',image_apks<=installable,sorted(image_apks-installable))
 duplicates=duplicate_apk_packages(inventory);extra=unexpected_duplicates(duplicates,c.ref['allowed_duplicate_packages'])
 (c.report/'install-duplicate-packages.json').write_text(json.dumps({'duplicates':{k:[r['relative'] for r in v] for k,v in duplicates.items()},'unexpected':extra},indent=2)+'\n')
 c.need('no package identity is installed twice (reviewed evox15 overlay pairs excepted)',not extra,extra)
 # Android 17 ships two Telecom app variants; the framework loader and the app must agree.
 mainline=c.vars.get('VendorVars',{}).get('ANDROID',{}).get('release_telecom_mainline_module')
 if mainline not in ('true','false'):raise ToolFailure('RELEASE_TELECOM_MAINLINE_MODULE unavailable')
 telecom=sorted(r['relative'] for r in inventory if r['package']=='com.android.server.telecom')
 want='system/priv-app/TelecomShim/TelecomShim.apk' if mainline=='true' else 'system/priv-app/Telecom/Telecom.apk'
 c.need('Telecom app variant matches the framework loader (mainline='+mainline+')',telecom==[want],telecom)
 selected=c.selected()
 c.need('product selects the matching Telecom app',('TelecomShim' in selected)==(mainline=='true') and ('Telecom' in selected)==(mainline!='true'),sorted(x for x in selected if x.startswith('Telecom')))

def main():
 parser=argparse.ArgumentParser();parser.add_argument('mode',choices=sorted(MODES));args=parser.parse_args();c=None;exit_code=0
 try:
  c=Check.__new__(Check);c.__init__(args.mode);globals()[args.mode](c);c.finish('passed');print('Static image coverage passed:',args.mode)
 except Defect as e:
  exit_code=1
  if c:c.finish('invariant-defect',str(e))
  print('INVARIANT DEFECT:',e,file=sys.stderr)
 except (ToolFailure,KeyError,OSError,ET.ParseError,zipfile.BadZipFile,json.JSONDecodeError) as e:
  exit_code=2
  if c:c.finish('tooling-failure',str(e))
  print('TOOLING/EVIDENCE FAILURE:',e,file=sys.stderr)
 except Exception as e:
  exit_code=3
  if c:c.finish('checker-error',str(e))
  traceback.print_exc()
 raise SystemExit(exit_code)
if __name__=='__main__':main()
