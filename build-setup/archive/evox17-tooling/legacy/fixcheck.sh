#!/bin/bash
: "${EVOX_EXTRACT:?attempt extraction path required}"
: "${EVOX_TMP:?attempt temporary path required}"
F=${EVOX_EXTRACT}/fs; T=/mnt/wsl/build/compare/tools; A=/mnt/wsl/build/evox-out/host/linux-x86/bin/aapt2
CIL=$F/vendor/etc/selinux/vendor_sepolicy.cil
ok(){ if eval "$2" >/dev/null 2>&1; then echo "OK   $1"; else echo "FAIL $1"; fi; }
ok "USB HALs labelled mtk_hal_usb_exec" "grep -F 'usb-aidl-service\\.mediatekv1\\.0' $F/vendor/etc/selinux/vendor_file_contexts | grep -q mtk_hal_usb_exec && grep -F 'usb\\.gadget-aidl-service\\.mediatekv1\\.0' $F/vendor/etc/selinux/vendor_file_contexts | grep -q mtk_hal_usb_exec"
grep -E "aidl-service" $F/vendor/etc/selinux/vendor_file_contexts | sed 's/^/     /'
ok "touchfeature props labelled" "grep -q 'persist.vendor.touchfeature.*vendor_touchfeature_prop' $F/vendor/etc/selinux/vendor_property_contexts && grep -q 'persist.vendor.hostprocess.*vendor_touch_hostprocess_prop' $F/vendor/etc/selinux/vendor_property_contexts"
ok "touchfeature may set its props" "grep -q 'allow hal_touchfeature vendor_touchfeature_prop (property_service (set))' $F/vendor/etc/selinux/vendor_sepolicy.cil"
ok "mtk_hal_usb extcon/usb sysfs rules" "grep -q 'allow mtk_hal_usb sysfs_usb' $F/vendor/etc/selinux/vendor_sepolicy.cil && grep -q 'allow mtk_hal_usb sysfs_extcon' $F/vendor/etc/selinux/vendor_sepolicy.cil"
ok "fingerprint HAL reads gesture_prop" "grep -qE 'allow hal_fingerprint_default gesture_prop(_[0-9]+)? \(file' $F/vendor/etc/selinux/vendor_sepolicy.cil"
ok "fingerprint HAL may use power HAL" "grep -E '^\(typeattributeset hal_power_client ' $CIL | grep -qw hal_fingerprint_default && grep -qE '^\(allow hal_power_client hal_power_(hwservice|service) \(.*find' $F/system/system/etc/selinux/plat_sepolicy.cil"
ok "UDFPS location 640|2518|105" "grep -q 'persist.vendor.fingerprint.sensor_location=640|2518|105' $F/vendor/build.prop"
ok "KlimtTouchBridge.apk installed" "ls $F/system_ext/priv-app/KlimtTouchBridge/KlimtTouchBridge.apk"
ok "libudfpshandler uses tap_gesture props" "grep -aq 'persist.sys.tap_gesture.dt2w' $F/vendor/lib64/libudfpshandler.so && grep -aq 'persist.sys.tap_gesture.fod_screen_off' $F/vendor/lib64/libudfpshandler.so"
ok "TouchBridge uses tap_gesture props" "unzip -p $F/system_ext/priv-app/KlimtTouchBridge/KlimtTouchBridge.apk classes.dex | grep -aq 'persist.sys.tap_gesture.dt2w'"
R=$(ls $F/vendor/overlay/framework-res__*klimt*_rro_vendor.apk | head -1)
echo "     framework RRO: $(basename $R)"
$A dump resources $R 2>/dev/null | grep -A1 -E "config_supportDoubleTapWake|config_screen_off_udfps_enabled|config_screen_off_udfps_default_on|config_dozeUdfpsLongPressSensorType" | grep -vE "^--" | tr -s ' ' | sed 's/^/     /'
C=$(ls $F/vendor/overlay/CarrierConfig__*klimt*_rro_vendor.apk | head -1)
ok "CarrierConfig RRO has VIVO cid 530 VoLTE" "$A dump xmltree --file res/xml/vendor.xml $C | grep -q '530'"
