from pathlib import Path
import importlib.util, tempfile, shutil, json, re, subprocess
B=Path('/mnt/d/android_rom_building/repositories/android_custom_rom_building_klimt/build-setup/evox/pipeline');D=Path('/mnt/d/android_rom_building/diagnostics/builds/evox26/preparation')
spec=importlib.util.spec_from_file_location('metadata26',B/'check-metadata26.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
checks=[]
with tempfile.TemporaryDirectory(prefix='metadata26-',dir='/mnt/wsl/build') as tmp:
 fs=Path(tmp)
 for part,rel in m.PARTS.items():
  dest=fs/rel;dest.parent.mkdir(parents=True,exist_ok=True)
  src=D/'generator-checks'/part/'build.prop' if part!='vendor' else D/'generator-checks/vendor.prop';shutil.copyfile(src,dest)
  if part=='vendor':subprocess.run(['/mnt/wsl/evox/src/out/host/linux-x86/bin/post_process_props','--sdk-version','37','--kernel-version-file-for-uffd-gc','',str(dest)],check=True)
  if part=='vendor':
   board=Path('/mnt/wsl/evox/src/device/xiaomi/klimt/BoardConfig.mk').read_text();spl=re.search(r'^VENDOR_SECURITY_PATCH := (.+)$',board,re.M).group(1)
   with dest.open('a') as out:out.write('ro.vendor.build.security_patch='+spl+'\n')
 kernel='Linux version 6.6.142-android15-8-gf6a5b29f9fe5-ab26 (builder@pangu-build-component-system-247-r6kfm) (compiler) #1 SMP PREEMPT Thu Aug 6 00:00:00 UTC 2026\n'
 checks.append({'case':'accept actual generator outputs','assertions':m.validate(fs,kernel),'pass':True})
 def reject(case,path=None,old=None,new=None,banner=kernel):
  if path:
   text=path.read_text();assert old in text;path.write_text(text.replace(old,new))
  try:
   m.validate(fs,banner)
  except ValueError as e:checks.append({'case':case,'pass':True,'rejection':str(e)})
  else:raise AssertionError('accepted '+case)
  finally:
   if path:path.write_text(text)
 reject('stale vendor incremental',fs/m.PARTS['vendor'],'ro.vendor.build.version.incremental='+m.INC,'ro.vendor.build.version.incremental=1792587938')
 reject('missing partition fingerprint',fs/m.PARTS['odm'],'ro.odm.build.fingerprint=','missing.odm.build.fingerprint=')
 reject('stale CANARY known codename',fs/m.PARTS['system'],'Baklava,CinnamonBun','Baklava,CANARY,CinnamonBun')
 reject('divergent partition date',fs/m.PARTS['system_ext'],(Path('/mnt/wsl/evox/src/out/build_date.txt')).read_text().strip(),'1')
 reject('wrong vendor SPL',fs/m.PARTS['vendor'],'ro.vendor.build.security_patch=2026-10-05','ro.vendor.build.security_patch=2026-02-01')
 reject('missing boot fingerprint alias',fs/m.PARTS['system'],'ro.bootimage.fingerprint=','missing.bootimage.fingerprint=')
 reject('conflicting duplicate property',fs/m.PARTS['vendor'],'ro.vendor.build.id='+m.BID,'ro.vendor.build.id='+m.BID+'\nro.vendor.build.id=wrong')
 reject('kernel missing localversion',banner=kernel.replace('-gf6a5b29f9fe5-ab26',''))
 reject('kernel wrong timestamp',banner=kernel.replace('Thu Aug 6 00:00:00 UTC 2026','Wed Oct 21 00:00:00 UTC 2026'))
(D/'METADATA_NEGATIVE_TESTS.json').write_text(json.dumps({'pass':True,'checks':checks},indent=2)+'\n');print('Metadata checker:',len(checks),'positive/negative cases passed')
