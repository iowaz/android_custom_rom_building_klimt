from pathlib import Path
import subprocess,json,shlex,re,hashlib,os
os.environ['OUT_DIR']='out'
S=Path('/mnt/wsl/evox/src');D=Path('/mnt/d/android_rom_building/diagnostics/builds/evox26/preparation');W=D/'generator-checks';W.mkdir(exist_ok=True)
# Run the actual Make macro in scratch with the actual product config. No staging.
macro=(S/'build/make/core/sysprop.mk').read_text().split('define generate-common-build-props\n',1)[1].split('\nendef',1)[0]
harness='''SRC_TARGET_DIR := build/make/target
include device/xiaomi/klimt/lineage_klimt.mk
TARGET_DEVICE := klimt
TARGET_PRODUCT := lineage_klimt
TARGET_BUILD_VARIANT := user
BUILD_ID := CP2A.260605.016
BUILD_UUID_FROM_FILE := test-uuid
BUILD_NUMBER_FROM_FILE := eng.test
BUILD_FINGERPRINT_FROM_FILE := fallback/fingerprint
BUILD_VERSION_TAGS := release-keys
PLATFORM_VERSION_LAST_STABLE := 17
PLATFORM_VERSION := 17
PLATFORM_SDK_VERSION := 37
PLATFORM_SDK_VERSION_FULL := 37.0
DATE_FROM_FILE := date -ud @$(shell cat /mnt/wsl/evox/src/out/build_date.txt)
TARGET_CPU_ABI_LIST_64_BIT := arm64-v8a
ZYGOTE_FORCE_64 := true
'''
for key in ['PRODUCT_BUILD_PROP_OVERRIDES','PRODUCT_SYSTEM_PROPERTIES','PRODUCT_PRODUCT_PROPERTIES']:
 harness+=f'$(file >{W}/{key}.txt,$({key}))\n'
harness+='define generate-common-build-props\n'+macro+'\nendef\nall:\n\t$(call generate-common-build-props,vendor,'+str(W/'vendor.prop')+')\n'
(W/'Makefile').write_text(harness);(W/'vendor.prop').unlink(missing_ok=True)
subprocess.run(['make','--no-print-directory','-f',str(W/'Makefile')],cwd=S,check=True,stdout=subprocess.DEVNULL)
config=json.load(open(S/'out/soong/.intermediates/build/soong/product_config/product_config.json'))
for key in ['PRODUCT_BUILD_PROP_OVERRIDES','PRODUCT_SYSTEM_PROPERTIES','PRODUCT_PRODUCT_PROPERTIES']:
 values=shlex.split((W/(key+'.txt')).read_text())
 if key=='PRODUCT_BUILD_PROP_OVERRIDES':config[key]=values
 else:config[key]=[p for p in config.get(key,[]) if not p.startswith(('ro.build.display.id=','ro.bootimage.fingerprint='))]+values
config['VendorSecurityPatch']='2026-10-05';(W/'config.json').write_text(json.dumps(config))
FP='Xiaomi/klimt_global/klimt:17/OS3.3.260806.171839609/OS3.0.335.0.XOSMIXM:user/release-keys';BID='OS3.3.260806.171839609';INC='OS3.0.335.0.XOSMIXM'
checks=[]
def props(path):
 result={}
 for line in path.read_text().splitlines():
  if line.startswith('#') or '=' not in line:continue
  k,v=line.split('=',1);result[k.rstrip('?')]=v
 return result
for part in ['system','system_ext','product','odm','vendor_dlkm','odm_dlkm','system_dlkm']:
 output=W/part/'build.prop';output.parent.mkdir(exist_ok=True);args=['python3',str(S/'build/soong/scripts/gen_build_prop.py')]
 for flag,path in {'build-hostname-file':'out/soong/build_hostname.txt','build-number-file':'out/soong/build_number.txt','build-uuid-file':'out/soong/build_uuid-lineage_klimt.txt','build-fingerprint-file':'out/target/product/klimt/build_fingerprint-lineage_klimt.txt','build-system-fingerprint-file':'out/target/product/klimt/build_system_fingerprint-lineage_klimt.txt','date-file':'out/build_date.txt','platform-preview-sdk-fingerprint-file':'out/soong/api_fingerprint.txt'}.items():args+=['--'+flag,str(S/path)]
 args+=['--build-username','android-build','--product-config',str(W/'config.json'),'--partition',part,'--out',str(output)]
 prop=S/f'device/xiaomi/klimt/configs/props/{part}.prop'
 if prop.exists():args+=['--prop-files',str(prop)]
 subprocess.run(args,cwd=S,check=True)
 subprocess.run([str(S/'out/host/linux-x86/bin/post_process_props'),'--sdk-version','37','--kernel-version-file-for-uffd-gc','',str(output)],check=True)
 p=props(output)
 for key,want in {f'ro.{part}.build.fingerprint':FP,f'ro.{part}.build.id':BID,f'ro.{part}.build.version.incremental':INC,f'ro.{part}.build.date.utc':(S/'out/build_date.txt').read_text().strip(),f'ro.product.{part}.name':'klimt'}.items():assert p.get(key)==want,(part,key,p.get(key),want)
 if part in ['system','product']:
  for key,want in {'ro.build.display.id':BID,'ro.build.flavor':'klimt_global-user','ro.build.user':'builder','ro.build.host':'pangu-build-component-system-247-r6kfm','ro.build.description':f'klimt_global-user 17 {BID} {INC} release-keys'}.items():assert p.get(key)==want,(part,key,p.get(key),want)
  assert 'CANARY' not in p['ro.build.version.known_codenames']
 if part=='system':assert p['ro.bootimage.fingerprint']==FP
 checks.append(part+' actual Soong generator + duplicate-property postprocess')
p=props(W/'vendor.prop')
for key,want in {'ro.vendor.build.fingerprint':FP,'ro.vendor.build.id':BID,'ro.vendor.build.version.incremental':INC,'ro.vendor.build.date.utc':(S/'out/build_date.txt').read_text().strip(),'ro.product.vendor.name':'klimt_global'}.items():assert p.get(key)==want,(key,p.get(key),want)
checks.append('vendor actual Make macro with product overrides')
# Fallback behavior of the generic Make macro is unchanged for products without overrides.
harness=harness.replace('include device/xiaomi/klimt/lineage_klimt.mk','PRODUCT_BRAND := Example\nPRODUCT_MANUFACTURER := Example\nPRODUCT_MODEL := Example').replace(str(W/'vendor.prop'),str(W/'fallback.prop'))
(W/'fallback.Makefile').write_text(harness);(W/'fallback.prop').unlink(missing_ok=True)
subprocess.run(['make','--no-print-directory','-f',str(W/'fallback.Makefile')],cwd=S,check=True,stdout=subprocess.DEVNULL)
fallback=props(W/'fallback.prop');assert fallback['ro.vendor.build.id']=='CP2A.260605.016';assert fallback['ro.vendor.build.version.incremental']==(S/'out/build_date.txt').read_text().strip();checks.append('Make no-override fallback regression')
(D/'GENERATOR_CHECKS.json').write_text(json.dumps({'pass':True,'checks':checks},indent=2)+'\n');print('\n'.join(checks))
