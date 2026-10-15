#!/bin/bash
: "${EVOX_EXTRACT:?attempt extraction path required}"
: "${EVOX_TMP:?attempt temporary path required}"
# evox11 checks: everything from evox10 (fixcheck10) plus the XiaomiParts thermal profiles, the mpbe ioctl and the
# batterysecret charging fix. Runs on the unpacked img zip in ${EVOX_EXTRACT} (cmp-extract-evox.sh).
F=${EVOX_EXTRACT}/fs; W=/mnt/wsl/evox/src
A=/mnt/wsl/build/evox-out/host/linux-x86/bin/aapt2; K=$W/vendor/evolution-priv/keys
APKSIGNER="java -jar $W/prebuilts/sdk/tools/linux/lib/apksigner.jar"
CIL=$F/vendor/etc/selinux/vendor_sepolicy.cil
ok(){ if eval "$2" >/dev/null 2>&1; then echo "OK   $1"; else echo "FAIL $1"; fi; }
certsha(){ openssl x509 -in "$1" -noout -fingerprint -sha256 | cut -d= -f2 | tr -d : | tr A-F a-f; }

echo "== evox10 checks (still present)"
bash /mnt/c/XiaomiBuilds/build-setup/evox/evox16/legacy/fixcheck10.sh 2>&1 | grep -E "^(OK|FAIL)"

echo "== XiaomiParts thermal profiles (device 3665c5c)"
P=$(ls $F/system_ext/priv-app/XiaomiParts/XiaomiParts.apk 2>/dev/null); echo "     ${P#$F/}"
ok "XiaomiParts.apk in system_ext/priv-app" "[ -n '$P' ]"
X=${EVOX_TMP}/xiaomiparts-manifest.txt; $A dump xmltree "$P" --file AndroidManifest.xml > $X 2>/dev/null
ok "package org.lineageos.settings" "grep -q 'package=\"org.lineageos.settings\"' $X"
ok "sharedUserId android.uid.system" "grep -q 'sharedUserId.*=\"android.uid.system\"' $X"
ok "persistent and directBootAware" "grep -q 'persistent.*=true' $X && grep -q 'directBootAware.*=true' $X"
ok "ThermalService, ThermalTileService, BootCompletedReceiver, ThermalActivity declared" \
   "grep -q 'thermal.ThermalService\"' $X && grep -q 'thermal.ThermalTileService\"' $X && grep -q 'BootCompletedReceiver\"' $X && grep -q 'thermal.ThermalActivity\"' $X"
ok "Settings > Battery injection (ia.battery)" "grep -q 'com.android.settings.category.ia.battery' $X"
ok "QS tile (BIND_QUICK_SETTINGS_TILE)" "grep -q 'android.permission.BIND_QUICK_SETTINGS_TILE' $X"
ok "no singleUser anywhere (persistent app)" "! grep -q singleUser $X"
pk=$(certsha $K/platform.x509.pem)
xp=$($APKSIGNER verify --print-certs "$P" 2>/dev/null | grep -m1 'SHA-256 digest' | awk '{print $NF}')
ok "signed with the platform key" "[ -n '$xp' ] && [ '$xp' = '$pk' ]"
ok "dex writes /sys/class/thermal/thermal_message/sconfig" "unzip -p '$P' 'classes*.dex' | grep -aq '/sys/class/thermal/thermal_message/sconfig'"
ok "pt-BR resources" "$A dump configurations '$P' | grep -q 'pt-rBR'"
rm -f $X

echo "== sepolicy (vendor_sepolicy.cil)"
grep -hE "^\((allow|allowx) (system_app[_0-9]* sysfs_therm|mpbe proc_mpbe|batterysecret sysfs_[0-9]+ )" $CIL | sed 's/^/     /'
ok "system_app may write sysfs_therm (sconfig)" "grep -qE '^\(allow system_app(_[0-9]+)? sysfs_therm \(file \([^)]*write' $CIL"
ok "mpbe ioctl 0x6703 allowed" "grep -E '^\(allowx mpbe proc_mpbe \(ioctl file' $CIL | grep -qE '0x6703|range 0x670[0-3] 0x670[3-9a-f]'"
ok "batterysecret may read/write plain sysfs files" "grep -qE '^\(allow batterysecret sysfs_[0-9]+ \(file \([^)]*open[^)]*write|^\(allow batterysecret sysfs_[0-9]+ \(file \([^)]*write[^)]*open' $CIL"
ok "batterysecret may read plain sysfs dirs" "grep -qE '^\(allow batterysecret sysfs_[0-9]+ \(dir \([^)]*read' $CIL"
