#!/bin/bash
# evox7 checks (round 3): screen-off FOD, private keys, user variant, FP override, MIUI Camera.
# Runs on the unpacked img zip in /mnt/wsl/build/compare/evox (cmp-extract-evox.sh) plus the build out dir.
F=/mnt/wsl/build/compare/evox/fs; W=/mnt/wsl/evox/src; O=$W/out/target/product/klimt
A=/mnt/wsl/build/evox-out/host/linux-x86/bin/aapt2; K=$W/vendor/evolution-priv/keys
APKSIGNER="java -jar $W/prebuilts/sdk/tools/linux/lib/apksigner.jar"
ok(){ if eval "$2" >/dev/null 2>&1; then echo "OK   $1"; else echo "FAIL $1"; fi; }
certsha(){ openssl x509 -in "$1" -noout -fingerprint -sha256 | cut -d= -f2 | tr -d : | tr A-F a-f; }
echo "== round 2 fixes (still present)"
bash /mnt/c/XiaomiBuilds/build-setup/evox/cmp/fixcheck.sh 2>&1 | grep -E "^(OK|FAIL)"

echo "== screen-off FOD"
ok "vendor hals.conf = stock 3 + sensors.xiaomi.v2.so" "[ \"\$(cat $F/vendor/etc/sensors/hals.conf)\" = \"\$(printf 'android.hardware.sensors@2.X-subhal-mediatek.so\nsensors.dynamic_sensor_hal.so\nsensors.touch.detect.so\nsensors.xiaomi.v2.so')\" ]"
ok "sensors.xiaomi.v2.so in vendor/lib64" "ls $F/vendor/lib64/sensors.xiaomi.v2.so"
ok "sensors.xiaomi.v2 exports sensorsHalGetSubHal_2_1" "nm -D $F/vendor/lib64/sensors.xiaomi.v2.so | grep -q sensorsHalGetSubHal_2_1"
ok "ro.vendor.sensors.xiaomi.udfps=true" "grep -q '^ro.vendor.sensors.xiaomi.udfps=true' $F/vendor/build.prop"
R=$(ls $F/vendor/overlay/framework-res__*klimt*_rro_vendor.apk | head -1)
$A dump resources $R 2>/dev/null | grep -A1 -E "config_dozeComponent|config_dozeUdfpsLongPressSensorType" | grep -vE "^--" | tr -s ' ' | sed 's/^/     /'
ok "RRO dozeComponent = DozeService" "$A dump resources $R | grep -A1 config_dozeComponent | grep -q 'com.android.systemui/com.android.systemui.doze.DozeService'"
ok "RRO UDFPS sensor = org.lineageos.sensor.udfps" "$A dump resources $R | grep -A1 config_dozeUdfpsLongPressSensorType | grep -q 'org.lineageos.sensor.udfps'"

echo "== Bluetooth audio"
ok "persist.bluetooth.a2dp_offload.disabled=true (vendor build.prop)" "grep -q '^persist.bluetooth.a2dp_offload.disabled=true' $F/vendor/build.prop"
ok "a2dp_offload_disabled audio policy present" "ls $F/vendor/etc/audio_policy_configuration_a2dp_offload_disabled.xml"

echo "== user variant / FP override"
grep -hE '^ro\.(build|system|system_ext|product|vendor|odm|vendor_dlkm|odm_dlkm|system_dlkm)\.build\.(fingerprint|type|tags)=|^ro\.build\.(fingerprint|type|tags|description)=|^ro\.debuggable=|^ro\.adb\.secure=' \
  $F/system/system/build.prop $F/system_ext/etc/build.prop $F/product/etc/build.prop $F/vendor/build.prop $F/odm/etc/build.prop \
  $F/vendor_dlkm/etc/build.prop $F/odm_dlkm/etc/build.prop $F/system_dlkm/etc/build.prop 2>/dev/null | sort | uniq -c | sed 's/^/     /'
ok "ro.build.fingerprint = bluejay canary" "grep -q '^ro.build.fingerprint=google/bluejay_beta/bluejay:CANARY/ZP11.260918.007/16484274:user/release-keys' $F/system/system/build.prop"
ok "no userdebug/test-keys in any build.prop" "! grep -rlE 'userdebug|test-keys' $F/system/system/build.prop $F/system_ext/etc/build.prop $F/product/etc/build.prop $F/vendor/build.prop $F/odm/etc/build.prop $F/vendor_dlkm/etc/build.prop $F/odm_dlkm/etc/build.prop $F/system_dlkm/etc/build.prop"
grep -lE 'userdebug|test-keys' $F/*/build.prop $F/*/etc/build.prop $F/system/system/build.prop 2>/dev/null | sed 's/^/     still has userdebug|test-keys: /'
ok "ro.debuggable=0" "grep -rq '^ro.debuggable=0' $F/system/system/build.prop $F/vendor/build.prop $O/vendor_ramdisk 2>/dev/null || ! grep -rq '^ro.debuggable=1' $F/system/system/build.prop $F/vendor/build.prop"
ok "no vendor_boot-debug in img zip" "! ls /mnt/wsl/build/compare/evox/img/vendor_boot-debug.img"

echo "== private keys"
for k in platform releasekey shared media networkstack; do
  ours=$(certsha $K/$k.x509.pem); aosp=$(certsha $W/build/make/target/product/security/${k/releasekey/testkey}.x509.pem)
  echo "     $k ours=${ours:0:16} aosp=${aosp:0:16}"
done
fr=$($APKSIGNER verify --print-certs $F/system/system/framework/framework-res.apk 2>/dev/null | grep -m1 'SHA-256 digest' | awk '{print $NF}')
ok "framework-res signed with OUR platform key (${fr:0:16})" "[ '$fr' = '$(certsha $K/platform.x509.pem)' ]"
su=$($APKSIGNER verify --print-certs $F/system_ext/priv-app/SystemUI*/SystemUI*.apk 2>/dev/null | grep -m1 'SHA-256 digest' | awk '{print $NF}')
echo "     SystemUI cert ${su:0:16}"
mc=$($APKSIGNER verify --print-certs $F/product/priv-app/MiuiCamera/MiuiCamera.apk 2>/dev/null | grep -m1 'SHA-256 digest' | awk '{print $NF}')
ok "MiuiCamera signed with OUR platform key (${mc:0:16})" "[ '$mc' = '$(certsha $K/platform.x509.pem)' ]"
rm -rf /tmp/ota7; mkdir -p /tmp/ota7; unzip -q -o $F/system/system/etc/security/otacerts.zip -d /tmp/ota7
for c in /tmp/ota7/*; do echo "     otacerts: $(basename $c) $(certsha $c | cut -c1-16)"; done
ok "otacerts = our releasekey (testkey symlink)" "[ \"\$(certsha /tmp/ota7/*)\" = '$(certsha $K/releasekey.x509.pem)' ]"
echo "     check_keys.py (apk/apex signed with an unknown key):"
(cd $K && python3 check_keys.py $O 2>/dev/null | sed 's/^/       /' | head -20)

echo "== MIUI Camera"
ok "MiuiCamera.apk in product/priv-app" "ls $F/product/priv-app/MiuiCamera/MiuiCamera.apk"
ok "MiuiCamera has classes8.dex (AudioParaManger stub)" "unzip -l $F/product/priv-app/MiuiCamera/MiuiCamera.apk | grep -q classes8.dex"
for l in libcamera_algoup_jni.xiaomi.so libcamera_ispinterface_jni.xiaomi.so libcamera_mianode_jni.xiaomi.so libmtkisp_metadata_sys.so vendor.mediatek.hardware.camera.isphal-V1-ndk.so vendor.mediatek.hardware.camera.isphal@1.0.so; do
  ok "system/lib64/$l" "ls $F/system/system/lib64/$l"
done
ok "public.libraries-xiaomi.txt" "ls $F/system/system/etc/public.libraries-xiaomi.txt"
ok "privapp/default permissions + hiddenapi allowlist" "ls $F/product/etc/permissions/privapp-permissions-miuicamera.xml $F/product/etc/default-permissions/default-permissions-miuicamera.xml $F/product/etc/sysconfig/miuicamera-hiddenapi-package-allowlist.xml"
ok "vendor.camera.aux.packagelist has com.android.camera" "grep -rq 'vendor.camera.aux.packagelist=com.android.camera' $F/system/system/build.prop $F/vendor/build.prop $F/product/etc/build.prop $F/system_ext/etc/build.prop"
ok "platform_app_36 camera rules in vendor sepolicy" "grep -qE 'allow platform_app_36(_[0-9]+)? xiaomi_bgservice_service' $F/vendor/etc/selinux/vendor_sepolicy.cil"
