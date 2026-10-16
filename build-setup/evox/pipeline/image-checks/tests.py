#!/usr/bin/env python3
"""Negative fixtures exercise post-build checker parsing, without running a build."""
import contextlib,io,json,tempfile,unittest,zipfile,os
from unittest.mock import patch
from pathlib import Path
import check_image as m

HEALTH='''
100: b9402429 ldr w9, [x1, #0x24]
104: 52b00008 mov w8, #-0x80000000
108: b900503f str wzr, [x1, #0x50]
10c: 6b08013f cmp w9, w8
110: 5a8907e8 csneg w8, wzr, w9, eq
114: 92800009 mov x9, #-0x1
118: b9002428 str w8, [x1, #0x24]
11c: f9004829 str x9, [x1, #0x90]
120: d65f03c0 ret
'''
class Tests(unittest.TestCase):
 def test_health_real_instruction_semantics(self):
  for raw in [0,1,-1,500000,-500000,2147483647,-2147483647,-2147483648]:
   with self.subTest(raw=raw):
    out=m.health_update_eval(HEALTH,raw)
    self.assertEqual(out,{0x24:(0 if raw==-2147483648 else -raw)&0xffffffff,0x50:0,0x90:0xffffffffffffffff})
 def test_health_wrong_polarity_detected(self):
  out=m.health_update_eval(HEALTH.replace('csneg w8, wzr, w9, eq','csel w8, wzr, w9, eq'),100)
  self.assertNotEqual(out[0x24],(-100)&0xffffffff)
 def test_health_wrong_average_detected(self):
  out=m.health_update_eval(HEALTH.replace('str wzr, [x1, #0x50]','str w9, [x1, #0x50]'),100)
  self.assertNotEqual(out[0x50],0)
 def test_health_wrong_ttf_detected(self):
  out=m.health_update_eval(HEALTH.replace('mov x9, #-0x1','mov x9, #0x1'),100)
  self.assertNotEqual(out[0x90],0xffffffffffffffff)
 def test_health_unknown_codegen_is_tooling_failure(self):
  with self.assertRaises(m.ToolFailure):m.health_update_eval(HEALTH.replace('csneg','eor'),100)
 def test_health_changed_layout_is_tooling_failure(self):
  with self.assertRaises(m.ToolFailure):m.health_update_eval(HEALTH.replace('#0x24','#0x28'),100)
 def test_stray_staged_file_rejected(self):
  other,kernel=m.stray_staged(['system/priv-app/Telecom/Telecom.apk','system/priv-app/TelecomShim/TelecomShim.apk','vendor_dlkm/lib/modules/a.ko','vendor_dlkm/lib/modules/modules.load'],{'system/priv-app/TelecomShim/TelecomShim.apk'})
  self.assertEqual(other,['system/priv-app/Telecom/Telecom.apk']);self.assertEqual(len(kernel),2)
 def test_install_listing_follows_soong_rename(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'.installable_files.previous').write_text('a\n')
   self.assertEqual(m.install_listing(p),p/'.installable_files.previous')
   (p/'.installable_files').write_text('a\n')
   self.assertEqual(m.install_listing(p),p/'.installable_files')
 def test_stray_kernel_allowance_is_narrow(self):
  other,kernel=m.stray_staged(['vendor_dlkm/lib/modules/sub/a.ko','vendor_dlkm/etc/x.conf','system/bin/property_info_checker'],set())
  self.assertEqual(sorted(other),['system/bin/property_info_checker','vendor_dlkm/etc/x.conf','vendor_dlkm/lib/modules/sub/a.ko']);self.assertEqual(kernel,[])
 def test_image_relative_system_as_root(self):
  self.assertEqual(m.image_relative('system/system/priv-app/A/A.apk'),'system/priv-app/A/A.apk');self.assertEqual(m.image_relative('product/app/B/B.apk'),'product/app/B/B.apk')
 def test_duplicate_telecom_rejected(self):
  recs=[{'relative':'system/priv-app/Telecom/Telecom.apk','package':'com.android.server.telecom'},{'relative':'system/priv-app/TelecomShim/TelecomShim.apk','package':'com.android.server.telecom'}]
  self.assertIn('com.android.server.telecom',m.unexpected_duplicates(m.duplicate_apk_packages(recs),{}))
 def test_reviewed_duplicate_pair_allowed_exactly(self):
  recs=[{'relative':'product/overlay/A.apk','package':'p'},{'relative':'product/overlay/B.apk','package':'p'}]
  self.assertEqual(m.unexpected_duplicates(m.duplicate_apk_packages(recs),{'p':['product/overlay/B.apk','product/overlay/A.apk']}),{})
  self.assertIn('p',m.unexpected_duplicates(m.duplicate_apk_packages(recs+[{'relative':'system/app/C.apk','package':'p'}]),{'p':['product/overlay/A.apk','product/overlay/B.apk']}))
 def telecom_dex(self,service_body,extra=''):
  return ("Class #0            -\n  Class descriptor  : 'Lcom/android/server/telecom/components/TelecomService;'\n  Superclass        : 'Landroid/app/Service;'\n"+service_body+"\n"+extra)
 def legacy_class(self,name):
  return "Class #1            -\n  Class descriptor  : '"+name+"'\n  Superclass        : 'Lcom/android/internal/telecom/ITelecomLoader$Stub;'\n"
 def test_telecom_mainline_contract(self):
  self.assertEqual(m.telecom_service_contract(self.telecom_dex('invoke-static {}, Landroid/telecom/TelecomServiceInitializerRepository;.getInitializer:()')),'mainline')
 def test_telecom_legacy_contract(self):
  self.assertEqual(m.telecom_service_contract(self.telecom_dex('new-instance v0, Lcom/android/server/telecom/components/TelecomService$1;',self.legacy_class('Lcom/android/server/telecom/components/TelecomService$1;'))),'legacy')
 def test_telecom_legacy_payload_at_shim_path_rejected(self):
  # A legacy payload is legacy wherever it is installed; the gate compares the contract, not the path.
  self.assertNotEqual(m.telecom_service_contract(self.telecom_dex('nop',self.legacy_class('Lx$1;'))),'mainline')
 def test_telecom_missing_or_mixed_contract(self):
  self.assertIsNone(m.telecom_service_contract("Class #0            -\n  Class descriptor  : 'Lother;'\n"))
  self.assertEqual(m.telecom_service_contract(self.telecom_dex('Landroid/telecom/TelecomServiceInitializerRepository;',self.legacy_class('Lx$1;'))),'ambiguous')
 def test_query_implicit_dependencies(self):
  self.assertEqual(m.parse_query('out/a:\n  input: rule\n    one\n    | two\n    || three\n  outputs:\n    out/b\n'),['one','two','three'])
 def test_resource_default(self):
  self.assertEqual(m.resource_values('resource 0x1 bool/foo\n  () true\n  (land) false\n','foo'),'true')
 def test_resource_missing_default(self):
  with self.assertRaises(m.ToolFailure):m.resource_values('resource 0x1 bool/foo\n  (land) true\n','foo')
 def test_resource_duplicate_definition(self):
  with self.assertRaises(m.ToolFailure):m.resource_values('resource 0x1 bool/foo\n  () true\nresource 0x2 bool/foo\n  () true\n','foo')
 def overlay_fixture(self):
  return [{'package':'a','priority':2,'static':True,'path':'/vendor/overlay/z.apk'},{'package':'b','priority':1,'static':True,'path':'/vendor/overlay/b.apk'},{'package':'dynamic','priority':3,'static':False,'path':'/vendor/overlay/d.apk'}]
 def test_overlay_static_priority_order(self):self.assertEqual([x['package'] for x in m.order_overlays(self.overlay_fixture(),None)],['b','a'])
 def test_overlay_config_disabled_static(self):self.assertEqual(m.order_overlays(self.overlay_fixture(),[{'package':'a','enabled':False}]),[])
 def test_overlay_config_enabled_dynamic(self):self.assertEqual([x['package'] for x in m.order_overlays(self.overlay_fixture(),[{'package':'dynamic','enabled':True}])],['dynamic'])
 def test_overlay_config_omitted_static_disabled(self):self.assertEqual([x['package'] for x in m.order_overlays(self.overlay_fixture(),[{'package':'b','enabled':True}])],['b'])
 def test_overlay_config_merge_order(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'config.xml').write_text('<config><overlay package="a" enabled="true"/><merge path="other.xml"/></config>');(p/'other.xml').write_text('<config><overlay package="b"/></config>')
   config,files=m.overlay_order_config(p/'config.xml');self.assertEqual([x['package'] for x in config],['a','b']);self.assertEqual([x['enabled'] for x in config],[True,False]);self.assertEqual(len(files),2)
 def test_overlay_config_merge_cycle_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'config.xml';p.write_text('<config><merge path="config.xml"/></config>')
   with self.assertRaises(m.ToolFailure):m.overlay_order_config(p)
 def test_manifest_attribute_typed_integer(self):self.assertEqual(m.manifest_attr('A: android:priority(0x0101001c)=(type 0x10)0x1','priority'),'0x1')
 def test_property_conflicting_duplicate(self):
  with self.assertRaises(m.Defect):m.prop_map('doze.display.supported=true\ndoze.display.supported=false\n')
 def test_property_comment_not_value(self):self.assertEqual(m.prop_map('# doze.display.supported=true\n'),{})
 def test_manifest_true_not_attribute_name(self):
  self.assertTrue(m.manifest_true('A: android:persistent(0x1)=(type 0x12)0xffffffff','persistent'))
  self.assertFalse(m.manifest_true('A: android:persistent(0x1)=(type 0x12)0x0','persistent'))
 def test_apk_payload_and_signature_distinction(self):
  with tempfile.TemporaryDirectory() as t:
   a=Path(t)/'a.apk';b=Path(t)/'b.apk';wrong=Path(t)/'wrong.apk'
   for p,dex,sig in [(a,b'dex-a',b'sig-a'),(b,b'dex-a',b'sig-b'),(wrong,b'dex-b',b'sig-a')]:
    with zipfile.ZipFile(p,'w') as z:
     z.writestr('classes.dex',dex);z.writestr('AndroidManifest.xml',b'manifest');z.writestr('resources.arsc',b'resources');z.writestr('META-INF/CERT.RSA',sig)
   self.assertTrue(m.same_zip_payload(a,b));self.assertFalse(m.same_zip_payload(a,wrong))
 def test_known_obsolete_artifact_absent(self):
  with tempfile.TemporaryDirectory() as t:
   records=[{'relative':'product/priv-app/Old/Old.apk','module':'Old'}]
   self.assertEqual(m.obsolete_artifacts_present(Path(t),records),[])
 def test_injected_known_obsolete_apk_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);relative='product/priv-app/GoogleRestorePrebuilt-v1068888/GoogleRestorePrebuilt-v1068888.apk';p=root/relative;p.parent.mkdir(parents=True);p.write_bytes(b'injected-old-apk')
   records=[{'relative':relative,'module':'GoogleRestorePrebuilt-v1068888','baseline_sha256':'ignored-for-absence-any-bytes-fail'}]
   self.assertEqual(m.obsolete_artifacts_present(root,records),records)
 def test_each_bound_obsolete_path_detected(self):
  refs=json.loads(Path(m.__file__).with_name('references.json').read_text())
  records=refs.get('obsolete_installed_artifacts',[])
  self.assertEqual(len(records),7)
  for record in records:
   with self.subTest(relative=record['relative']),tempfile.TemporaryDirectory() as t:
    root=Path(t);p=root/record['relative'];p.parent.mkdir(parents=True);p.write_bytes(b'new-bytes-at-retired-path')
    self.assertEqual(m.obsolete_artifacts_present(root,records),[record])
 def test_obsolete_symlink_also_detected(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);record={'relative':'system_ext/etc/sysconfig/pixel-haptics-override.xml'};p=root/record['relative'];p.parent.mkdir(parents=True)
   try:p.symlink_to(root/'missing-target')
   except OSError as e:
    if getattr(e,'winerror',None)==1314:self.skipTest('Windows host lacks symlink privilege; real POSIX symlink fixture remains pending')
    raise
   self.assertEqual(m.obsolete_artifacts_present(root,[record]),[record])
 def test_broken_symlink_trait_is_not_treated_as_absence(self):
  record={'relative':'system_ext/etc/sysconfig/pixel-haptics-override.xml'}
  with patch.object(Path,'exists',return_value=False),patch.object(Path,'is_symlink',return_value=True):
   self.assertEqual(m.obsolete_artifacts_present(Path('/fixture'),[record]),[record])
 def test_reference_fixture_bound_exactly(self):self.assertEqual(m.sha(Path(m.__file__).with_name('references.json')),m.REF_SHA)
 def test_retained_pixelsystemservice_install_config_not_forbidden(self):
  refs=json.loads(Path(m.__file__).with_name('references.json').read_text())
  self.assertNotIn('system_ext/etc/sysconfig/preinstalled-packages-pixelsystemservice.xml',[p['relative'] for p in refs.get('obsolete_installed_artifacts',[])])
 def test_apk_duplicate_package_inventory(self):
  rows=[{'relative':'a.apk','package':'same'},{'relative':'b.apk','package':'same'},{'relative':'c.apk','package':'unique'},{'relative':'link.apk','package':None}]
  self.assertEqual(m.duplicate_apk_packages(rows),{'same':rows[:2]})
 def producer_fixture(self,mutation):
  with tempfile.TemporaryDirectory() as t:
   oldS,oldP=m.S,m.P;m.S=Path(t)/'source';m.P=m.S/'out/target/product/klimt'
   try:
    producer='out/soong/.intermediates/demo/X/android_common/X.apk';rel='system_ext/priv-app/X/X.apk';target='out/target/product/klimt/'+rel
    for p in [m.S/producer,m.P/rel,Path(t)/'fs'/rel]:p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'producer')
    c=m.Check.__new__(m.Check);c.mode='test';c.rows=[];c.identities={};c.fs=Path(t)/'fs';c.rd=Path(t)/'rd';c.query_cache={target:[producer]}
    c.modules=[{'LOCAL_MODULE':'X','LOCAL_PATH':'demo','LOCAL_PREBUILT_MODULE_FILE':producer,'LOCAL_SOONG_INSTALLED_MODULE':target}]
    c.install=target+': '+producer+'\n'
    mutation(c,m.S/producer,m.P/rel,Path(t)/'fs'/rel)
    with contextlib.redirect_stdout(io.StringIO()):return c.module('X',rel,'demo')
   finally:m.S,m.P=oldS,oldP
 def test_producer_fixture_pass(self):self.assertEqual(self.producer_fixture(lambda *a:None)['LOCAL_MODULE'],'X')
 def test_stale_installed_output_rejected(self):
  with self.assertRaises(m.Defect):self.producer_fixture(lambda c,prod,built,image:built.write_bytes(b'stale'))
 def test_image_output_mutation_rejected(self):
  with self.assertRaises(m.Defect):self.producer_fixture(lambda c,prod,built,image:image.write_bytes(b'old-image'))
 def test_wrong_producer_rule_rejected(self):
  with self.assertRaises(m.Defect):self.producer_fixture(lambda c,*p:setattr(c,'install',c.install.replace(': out/soong/',': wrong/')))
 def test_duplicate_module_rejected(self):
  with self.assertRaises(m.Defect):self.producer_fixture(lambda c,*p:c.modules.append(dict(c.modules[0])))
 def test_wrong_source_owner_rejected(self):
  with self.assertRaises(m.Defect):self.producer_fixture(lambda c,*p:c.modules[0].update(LOCAL_PATH='different'))
 def test_wrong_ninja_producer_rejected(self):
  with self.assertRaises(m.Defect):self.producer_fixture(lambda c,*p:c.query_cache.update({next(iter(c.query_cache)):['stale/producer.apk']}))

if __name__=='__main__':
 fixture_root=Path(__file__).parent/'fixture-temp'
 if not fixture_root.resolve().is_relative_to(Path(__file__).parent.resolve()):raise RuntimeError('Fixture temporary root escaped checker workspace')
 fixture_root.mkdir(exist_ok=True);tempfile.tempdir=str(fixture_root)
 suite=unittest.defaultTestLoader.loadTestsFromTestCase(Tests)
 result=unittest.TextTestRunner(verbosity=2).run(suite)
 record={'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),'skipped_details':[str(reason) for _,reason in result.skipped],'passed':result.wasSuccessful(),'host':os.name,'scope':'helper/negative fixture tests only; no actual EVOX17 image verification performed'}
 Path(__file__).with_name('TEST_RESULTS.json').write_text(json.dumps(record,indent=2)+'\n')
 raise SystemExit(0 if result.wasSuccessful() else 1)
