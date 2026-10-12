from pathlib import Path
import hashlib,json
S=Path('/mnt/wsl/evox/src');D=S/'device/xiaomi/klimt';P=S/'out/target/product/klimt'
F=Path('/mnt/wsl/build/compare/evox/fs');RD=Path('/tmp/evx_rd')
checks=[]
def ok(name,cond):
    checks.append(bool(cond));print(('OK   ' if cond else 'FAIL ')+name)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
his=F/'odm/lib64/camera/plugins/streaming/com.xiaomi.plugin.mihisv2.so'
ok('evox15 HIS reviewed controlled candidate SHA',sha(his)=='4a4fe8a0b6ca0bcc57b5045da37ca6ad64e52f4ee889a2dcefde23d09836329a')
ok('evox15 HIS distinct deterministic BuildId',his.is_file() and his.read_bytes()[0x298:0x2a8].hex()=='30ee8f4f63103efcd6f66558e345682c')
mods=json.loads((P/'module-info.json').read_text())
for name in ['android.hardware.health-service.klimt','android.hardware.health-service.klimt_recovery']:
    mod=mods.get(name,{})
    ok(f'evox15 selected {name} from device health source','device/xiaomi/klimt/health' in mod.get('path',[]) and bool(mod.get('installed')))
normal=F/'vendor/bin/hw/android.hardware.health-service.klimt';built=P/'vendor/bin/hw/android.hardware.health-service.klimt'
ok('evox15 packaged device health binary equals built output',sha(normal) is not None and sha(normal)==sha(built) and not (F/'vendor/bin/hw/android.hardware.health-service.example').exists())
# Generic Health binary from the verified evox14 image; no private debug artifact needed.
BASELINE_HEALTH_SHA='2f3f2d7a2a5eb290b5834a6d5c9098b7fbe03c2dfc4e6c8929cb94417a3a2c47'
ok('evox15 health binary replaced generic baseline',sha(normal) is not None and sha(normal)!=BASELINE_HEALTH_SHA)
rec=P/'recovery/root/system/bin/hw/android.hardware.health-service.klimt_recovery'
found=[x for x in RD.rglob('android.hardware.health-service.klimt_recovery') if x.is_file()]
ok('evox15 packaged recovery health equals built output',rec.is_file() and len(found)==1 and sha(found[0])==sha(rec) and not list(RD.rglob('android.hardware.health-service.example_recovery')))
for relative,source in [('vendor/etc/init/android.hardware.health-service.klimt.rc','android.hardware.health-service.klimt.rc'),('vendor/etc/vintf/manifest/android.hardware.health-service.klimt.xml','android.hardware.health-service.klimt.xml')]:
    ok(f'evox15 retained {source}',sha(F/relative) is not None and sha(F/relative)==sha(D/'health'/source))
rcs=[x for x in RD.rglob('android.hardware.health-service.klimt_recovery.rc') if x.is_file()]
ok('evox15 recovery health init retained',len(rcs)==1 and sha(rcs[0])==sha(D/'health/android.hardware.health-service.klimt_recovery.rc'))
assert len(checks)==10
if not all(checks):raise SystemExit(1)
