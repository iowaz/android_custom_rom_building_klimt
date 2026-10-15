#!/bin/bash
: "${EVOX_EXTRACT:?attempt extraction path required}"
: "${EVOX_TMP:?attempt temporary path required}"
# evox13 checks: everything from evox12 (fixcheck12) plus the log-noise fixes: libui SMPTE 2094-50 check,
# citsensorservice, MiSys watermark dirs, camera/audio/GPS dontaudits, camera and TEE property labels,
# FeliCa provisioned check, USB product string. Runs on the unpacked img zip in ${EVOX_EXTRACT}.
F=${EVOX_EXTRACT}/fs
CIL=$F/vendor/etc/selinux/vendor_sepolicy.cil; VPC=$F/vendor/etc/selinux/vendor_property_contexts
VFC=$F/vendor/etc/selinux/vendor_file_contexts
RE=$(ls -d /mnt/wsl/evox/src/prebuilts/clang/host/linux-x86/clang-r*/bin/llvm-readelf | tail -1)
ok(){ if eval "$2" >/dev/null 2>&1; then echo "OK   $1"; else echo "FAIL $1"; fi; }

echo "== evox12 checks (still present)"
bash "$(dirname "$(realpath "$0")")/fixcheck12.sh" 2>&1 | grep -E "^(OK|FAIL)"

echo "== libui (SMPTE 2094-50 support check)"
old=$(awk '/system\/lib64\/libui.so/{print $1}' "$(dirname "$(realpath "$0")")/../evox12-libui.sha256")
new=$(sha256sum $F/system/system/lib64/libui.so | cut -d' ' -f1)   # system.img has /system inside
ok "system libui.so rebuilt (differs from evox12)" "[ -n '$new' ] && [ '$new' != '$old' ]"
ok "frameworks/native carries the patch" "python3 -B $(dirname "$(realpath "$0")")/../source-gate.py frameworks/native 'SMPTE 2094-50 capability guard'"

echo "== citsensorservice"
B=$F/odm/bin/hw/vendor.xiaomi.sensor.citsensorservice.aidl
ok "binary in /odm/bin/hw" "[ -x $B ]"
ok "binary NEEDs libui_vendor.so, not libui.so" "$RE -d $B | grep -q 'libui_vendor.so' && ! $RE -d $B | grep -q '\[libui.so\]'"
ok "init rc in /odm/etc/init" "grep -q '^service citsensorservice /odm/bin/hw/vendor.xiaomi.sensor.citsensorservice.aidl' $F/odm/etc/init/vendor.xiaomi.sensor.citsensorservice.aidl.rc || grep -q 'service citsensorservice' $F/odm/etc/init/vendor.xiaomi.sensor.citsensorservice.aidl.rc"
ok "VINTF fragment in /odm/etc/vintf/manifest" "grep -q 'vendor.xiaomi.sensor.citsensorservice' $F/odm/etc/vintf/manifest/vendor.xiaomi.sensor.citsensorservice.aidl.xml"
ok "binary NEEDs sensors-V3-ndk, not V2 (aidl_bump)" "$RE -d $B | grep -q 'android.hardware.sensors-V3-ndk.so' && ! $RE -d $B | grep -q 'sensors-V2-ndk'"
ok "android.hardware.sensors-V3-ndk.so in /vendor/lib64" "[ -f $F/vendor/lib64/android.hardware.sensors-V3-ndk.so ]"
ok "file_contexts labels it citsensorservice_exec" "grep -q 'citsensorservice\\\\.aidl.*citsensorservice_exec' $VFC"
ok "domain + init transition" "grep -qE '^\(typetransition init(_[0-9]+)? citsensorservice_exec process citsensorservice\)' $CIL"
ok "may add its service" "grep -qE '^\(allow citsensorservice citsensorservice_service \(service_manager \(add' $CIL"
ok "composer may call it" "grep -qE '^\(allow hal_graphics_composer_default citsensorservice \(binder \(call' $CIL"

echo "== MiSys watermark dirs"
ok "xiaomi_misys_common may create vendor_data_file dirs" "grep -qE '^\(allow xiaomi_misys_common vendor_data_file(_[0-9]+)? \(dir \([^)]*create' $CIL"

echo "== dontaudit unlabeled property reads"
for d in mtk_hal_camera hal_audio_default mnld; do
  ok "$d default_prop read dontaudited" "grep -qE '^\(dontaudit $d default_prop(_[0-9]+)? \(file \(read\)\)\)' $CIL"
done

echo "== property labels"
ok "vendor.camera.sensor.logsystem -> vendor_camera_skynet_prop" "grep -qE '^vendor\.camera\.sensor\.logsystem +u:object_r:vendor_camera_skynet_prop:s0' $VPC"
ok "persist.vendor.camera.st_repair. -> vendor_mtk_camera_prop" "grep -qE '^persist\.vendor\.camera\.st_repair\. +u:object_r:vendor_mtk_camera_prop:s0' $VPC"
ok "6 TEE status props -> vendor_payment_security_prop" "[ \$(grep -c 'vendor_payment_security_prop' $VPC) -eq 6 ]"
ok "mitee_mtdservice may set them" "grep -qE '^\(allow mitee_mtdservice vendor_payment_security_prop \(property_service \(set' $CIL"

echo "== FeliCa script, USB product string"
ok "klimt_felica may call system_server" "grep -qE '^\(allow klimt_felica system_server(_[0-9]+)? \(binder \(call transfer' $CIL"
ok "USB product written as Xiaomi 15T Pro" "grep -qF 'strings/0x409/product \"Xiaomi 15T Pro\"' $F/vendor/etc/init/hw/init.mt6991.usb.rc"
ok "no \${ro.product.marketname} left in vendor rc (comments aside)" "! grep -rh 'ro.product.marketname' $F/vendor/etc/init | grep -qv '^ *#'"
