from pathlib import Path
import os
import hashlib,re
import xml.etree.ElementTree as ET
S=Path('/mnt/wsl/evox/src');D=S/'device/xiaomi/klimt';P=S/'out/target/product/klimt'
F=Path(os.environ['EVOX_EXTRACT'])/'fs';RD=Path(os.environ['EVOX_TMP'])/'evx_rd'
checks=[]
def ok(name,cond):
    checks.append(bool(cond));print(('OK   ' if cond else 'FAIL ')+name)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
his=F/'odm/lib64/camera/plugins/streaming/com.xiaomi.plugin.mihisv2.so'
ok('retained HIS/Health HIS reviewed controlled candidate SHA',sha(his)=='4a4fe8a0b6ca0bcc57b5045da37ca6ad64e52f4ee889a2dcefde23d09836329a')
ok('retained HIS/Health HIS distinct deterministic BuildId',his.is_file() and his.read_bytes()[0x298:0x2a8].hex()=='30ee8f4f63103efcd6f66558e345682c')
# updatepackage does not regenerate the developer module-info.json cache.
# Follow current Soong module/install producers through to the built binaries.
android_mk=(S/'out/soong/Android-lineage_klimt.mk').read_text()
install_mk=(S/'out/soong/installs-lineage_klimt.mk').read_text()
def selected_device_module(name,relative):
    blocks=[b for b in android_mk.split('include $(CLEAR_VARS)') if re.search(r'^LOCAL_MODULE := '+re.escape(name)+r'$',b,re.M)]
    fields=dict(re.findall(r'^([A-Z0-9_]+) := (.*)$',blocks[0],re.M)) if len(blocks)==1 else {}
    target='out/target/product/klimt/'+relative
    producer=fields.get('LOCAL_PREBUILT_MODULE_FILE','')
    rules=re.findall(r'^'+re.escape(target)+r': ([^\n]+)$',install_mk,re.M)
    valid=(len(blocks)==1 and fields.get('LOCAL_PATH')=='device/xiaomi/klimt/health'
        and fields.get('LOCAL_MODULE_CLASS')=='EXECUTABLES' and fields.get('LOCAL_SOONG_MODULE_TYPE')=='cc_binary'
        and fields.get('LOCAL_SOONG_INSTALLED_MODULE')==target
        and fields.get('LOCAL_FULL_INIT_RC')=='device/xiaomi/klimt/health/'+name+'.rc'
        and fields.get('LOCAL_FULL_VINTF_FRAGMENTS')=='device/xiaomi/klimt/health/android.hardware.health-service.klimt.xml'
        and producer.startswith('out/soong/.intermediates/device/xiaomi/klimt/health/'+name+'/')
        and Path(producer).name==name and len(rules)==1 and rules[0].split()[0]==producer
        and sha(S/producer) is not None and sha(S/producer)==sha(P/relative))
    return valid

for name,relative in [('android.hardware.health-service.klimt','vendor/bin/hw/android.hardware.health-service.klimt'),('android.hardware.health-service.klimt_recovery','recovery/root/system/bin/hw/android.hardware.health-service.klimt_recovery')]:
    ok(f'retained HIS/Health selected {name} from device health source',selected_device_module(name,relative))
normal=F/'vendor/bin/hw/android.hardware.health-service.klimt';built=P/'vendor/bin/hw/android.hardware.health-service.klimt'
ok('retained HIS/Health packaged device health binary equals built output',sha(normal) is not None and sha(normal)==sha(built) and not (F/'vendor/bin/hw/android.hardware.health-service.example').exists())
# Generic Health binary from the verified evox14 image; no private debug artifact needed.
BASELINE_HEALTH_SHA='2f3f2d7a2a5eb290b5834a6d5c9098b7fbe03c2dfc4e6c8929cb94417a3a2c47'
ok('retained HIS/Health health binary replaced generic baseline',sha(normal) is not None and sha(normal)!=BASELINE_HEALTH_SHA)
rec=P/'recovery/root/system/bin/hw/android.hardware.health-service.klimt_recovery'
found=[x for x in RD.rglob('android.hardware.health-service.klimt_recovery') if x.is_file()]
ok('retained HIS/Health packaged recovery health equals built output',rec.is_file() and len(found)==1 and sha(found[0])==sha(rec) and not list(RD.rglob('android.hardware.health-service.example_recovery')))
ok('retained HIS/Health retained android.hardware.health-service.klimt.rc',sha(F/'vendor/etc/init/android.hardware.health-service.klimt.rc') is not None and sha(F/'vendor/etc/init/android.hardware.health-service.klimt.rc')==sha(D/'health/android.hardware.health-service.klimt.rc'))

def manifest_identity(path):
    try:
        if any(True for _ in ET.iterparse(path,events=('pi',))):
            return None
        root=ET.parse(path).getroot()
        if root.tag!='manifest' or not re.fullmatch(r'\d+\.\d+',root.get('version','')):
            return None
        # assemble_vintf serializes its current root schema version and an input
        # comment. Retain all HAL attributes, child values and meaningful text.
        root.attrib.pop('version')
        def canonical(node):
            return (node.tag,tuple(sorted(node.attrib.items())),(node.text or '').strip(),
                    tuple(canonical(child) for child in node),(node.tail or '').strip())
        return canonical(root)
    except (OSError,ET.ParseError):
        return None
xml_name='android.hardware.health-service.klimt.xml'
source_xml=D/'health'/xml_name
normal_xml=F/'vendor/etc/vintf/manifest'/xml_name
built_xml=P/'vendor/etc/vintf/manifest'/xml_name
recovery_xmls=[x for x in RD.rglob(xml_name) if x.is_file()]
built_recovery_xml=P/'recovery/root/system/etc/vintf/manifest'/xml_name
identity=manifest_identity(source_xml)
ok('retained HIS/Health retained android.hardware.health-service.klimt.xml',identity is not None
   and manifest_identity(normal_xml)==identity and sha(normal_xml) is not None and sha(normal_xml)==sha(built_xml)
   and len(recovery_xmls)==1 and manifest_identity(recovery_xmls[0])==identity
   and sha(recovery_xmls[0]) is not None and sha(recovery_xmls[0])==sha(built_recovery_xml))
rcs=[x for x in RD.rglob('android.hardware.health-service.klimt_recovery.rc') if x.is_file()]
ok('retained HIS/Health recovery health init retained',len(rcs)==1 and sha(rcs[0])==sha(D/'health/android.hardware.health-service.klimt_recovery.rc'))
if not all(checks):raise SystemExit(1)
