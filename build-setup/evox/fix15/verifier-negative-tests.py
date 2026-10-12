import ast,re,hashlib,tempfile,xml.etree.ElementTree as ET
from pathlib import Path
source=Path('/mnt/c/XiaomiBuilds/build-setup/evox/fix15/check-image.py').read_text()
tree=ast.parse(source)
funcs=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['sha','selected_device_module','manifest_identity']]
assert len(funcs)==3
S=Path('/mnt/wsl/evox/src');P=S/'out/target/product/klimt'
mk=(S/'out/soong/Android-lineage_klimt.mk').read_text();imk=(S/'out/soong/installs-lineage_klimt.mk').read_text()
ns={'Path':Path,'re':re,'hashlib':hashlib,'ET':ET,'S':S,'P':P,'android_mk':mk,'install_mk':imk}
exec(compile(ast.Module(body=funcs,type_ignores=[]),'<checker functions>','exec'),ns)
count=0
for name,relative in [('android.hardware.health-service.klimt','vendor/bin/hw/android.hardware.health-service.klimt'),('android.hardware.health-service.klimt_recovery','recovery/root/system/bin/hw/android.hardware.health-service.klimt_recovery')]:
 fn=ns['selected_device_module'];assert fn(name,relative);count+=1
 block=next(b for b in mk.split('include $(CLEAR_VARS)') if re.search(r'^LOCAL_MODULE := '+re.escape(name)+r'$',b,re.M))
 rule=next(l for l in imk.splitlines() if l.startswith('out/target/product/klimt/'+relative+': '))
 mutations=[('wrong source',mk.replace('LOCAL_PATH := device/xiaomi/klimt/health','LOCAL_PATH := hardware/interfaces/health/aidl/default'),imk),
  ('wrong installed target',mk.replace('LOCAL_SOONG_INSTALLED_MODULE := out/target/product/klimt/'+relative,'LOCAL_SOONG_INSTALLED_MODULE := out/target/product/klimt/INVALID'),imk),
  ('wrong producer path',mk.replace('out/soong/.intermediates/device/xiaomi/klimt/health/'+name+'/','out/soong/.intermediates/WRONG/'+name+'/'),imk),
  ('duplicate module',mk+'\ninclude $(CLEAR_VARS)'+block,imk),
  ('duplicate install',mk,imk+'\n'+rule+'\n'),
  ('missing module',mk.replace(block,''),imk)]
 for label,altered_mk,altered_imk in mutations:
  ns.update(android_mk=altered_mk,install_mk=altered_imk)
  assert not fn(name,relative),(name,label)
  count+=1
 ns.update(android_mk=mk,install_mk=imk)
print(f'{count} module provenance positive/negative checks passed')
identity=ns['manifest_identity'];s=S/'device/xiaomi/klimt/health/android.hardware.health-service.klimt.xml'
base=s.read_text();wanted=identity(s);assert wanted is not None
assert identity(P/'vendor/etc/vintf/manifest/android.hardware.health-service.klimt.xml')==wanted
assert identity(P/'recovery/root/system/etc/vintf/manifest/android.hardware.health-service.klimt.xml')==wanted
changes=[('wrong HAL version',base.replace('<version>5</version>','<version>4</version>')),
 ('wrong HAL name',base.replace('android.hardware.health','android.hardware.wrong')),
 ('wrong instance',base.replace('IHealth/default','IHealth/other')),
 ('wrong root type',base.replace('type="device"','type="framework"')),
 ('extra HAL',base.replace('</manifest>','<hal format="aidl"><name>extra</name></hal></manifest>')),
 ('extra attribute',base.replace('<hal format="aidl">','<hal format="aidl" optional="true">')),
 ('invalid schema version',base.replace('version="1.0"','version="bad"')),
 ('processing instruction',base.replace('<hal format="aidl">','<?unexpected data?><hal format="aidl">')),
 ('processing instruction outside root','<?unexpected data?>'+base)]
with tempfile.TemporaryDirectory(prefix='evox15-verifier-test-') as temp:
 p=Path(temp)/'test.xml'
 p.write_text('<!-- allowed build comment -->'+base.replace('version="1.0"','version="9.0"'))
 assert identity(p)==wanted
 for label,text in changes:
  p.write_text(text);assert identity(p)!=wanted,label
print('VINTF source/build identity, comment/schema normalization and 9 negative changes checked')
report=Path('/mnt/c/XiaomiBuilds/debug/review15/verifier-fix/NEGATIVE_TESTS_PASSED.txt')
report.parent.mkdir(parents=True,exist_ok=True)
report.write_text('14 module provenance checks passed; VINTF identity and 9 negative mutations rejected.\nNo actual source/build/image files modified.\n')
