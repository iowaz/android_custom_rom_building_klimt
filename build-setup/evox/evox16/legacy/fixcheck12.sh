#!/bin/bash
: "${EVOX_EXTRACT:?attempt extraction path required}"
: "${EVOX_TMP:?attempt temporary path required}"
# evox12 checks: everything from evox11 (fixcheck11) plus the wakeup-source labels, the power HAL and camera HAL
# rules and video calling off. Runs on the unpacked img zip in ${EVOX_EXTRACT} (cmp-extract-evox.sh).
F=${EVOX_EXTRACT}/fs
CIL=$F/vendor/etc/selinux/vendor_sepolicy.cil; VP=$F/vendor/build.prop
ok(){ if eval "$2" >/dev/null 2>&1; then echo "OK   $1"; else echo "FAIL $1"; fi; }

echo "== evox11 checks (still present)"
bash /mnt/c/XiaomiBuilds/build-setup/evox/evox16/legacy/fixcheck11.sh 2>&1 | grep -E "^(OK|FAIL)"

echo "== wakeup-source labels"
n=$(grep -c '^(genfscon sysfs .*sysfs_wakeup' $CIL); echo "     sysfs_wakeup genfscon: $n (evox11: 94)"
ok "54 new sysfs_wakeup genfscon (94 -> 148)" "[ $n -eq 148 ]"
for p in /devices/platform/1c01a000.spmi/spmi-0/0-04/wakeup /devices/virtual/gpsmdl-agent/gpsmdl-agent/wakeup \
         /devices/platform/battery-manager/power_supply/battery/wakeup /devices/platform/soc/13ab0000.i2c/i2c-7/7-0033/wakeup \
         '/devices/platform/1c01a000.spmi/spmi-0/0-0e/1c01a000.spmi:mt6379@e:tcpc/tcpc/type_c_port0/wakeup'; do
  ok "genfscon ${p#/devices/}" "grep -qF '(genfscon sysfs \"$p\" (u object_r sysfs_wakeup' $CIL"
done

echo "== HAL rules"
ok "mtk_hal_power may search hal_fingerprint_default /proc" "grep -qE '^\(allow mtk_hal_power hal_fingerprint_default \(dir \([^)]*search' $CIL"
ok "mtk_hal_power may read hal_fingerprint_default /proc files" "grep -qE '^\(allow mtk_hal_power hal_fingerprint_default \(file \([^)]*read' $CIL"
ok "mtk_hal_camera may setattr vendor_data_file" "grep -qE '^\(allow mtk_hal_camera vendor_data_file(_[0-9]+)? \(file \([^)]*setattr' $CIL"

echo "== video calling off, VoLTE on"
grep -hE '^persist\.vendor\.(vilte|viwifi|volte)_support=' $VP | sed 's/^/     /'
ok "persist.vendor.vilte_support=0" "grep -qx 'persist.vendor.vilte_support=0' $VP"
ok "persist.vendor.viwifi_support=0" "grep -qx 'persist.vendor.viwifi_support=0' $VP"
ok "persist.vendor.volte_support=1" "grep -qx 'persist.vendor.volte_support=1' $VP"
