#!/bin/bash
: "${EVOX_EXTRACT:?attempt extraction path required}"
: "${EVOX_TMP:?attempt temporary path required}"
# evox10 checks: everything from evox9 (fixcheck9) plus the SystemUI pixel_pitch RRO and the centred UDFPS icon.
# Runs on the unpacked img zip in ${EVOX_EXTRACT} (cmp-extract-evox.sh).
F=${EVOX_EXTRACT}/fs; A=/mnt/wsl/build/evox-out/host/linux-x86/bin/aapt2
ok(){ if eval "$2" >/dev/null 2>&1; then echo "OK   $1"; else echo "FAIL $1"; fi; }

echo "== evox9 checks (still present)"
bash /mnt/c/XiaomiBuilds/build-setup/evox/evox16/legacy/fixcheck9.sh 2>&1 | grep -E "^(OK|FAIL)"

echo "== SystemUI pixel_pitch RRO (device 688efda)"
R=$(find $F/odm $F/vendor $F/product -name 'SystemUIResKlimt.apk' 2>/dev/null | head -1); echo "     ${R#$F/}"
ok "SystemUIResKlimt.apk present" "[ -n '$R' ]"
ok "RRO targets com.android.systemui (static)" "$A dump xmltree $R --file AndroidManifest.xml | grep -A3 'E: overlay' | grep -q 'com.android.systemui'"
ok "RRO pixel_pitch = 56.82" "$A dump resources $R | grep -A1 'dimen/pixel_pitch' | grep -q '56.82'"

echo "== UDFPS centre (device 894ab73)"
grep -h 'fingerprint.sensor_location=\|fp.fod.location.X_Y=\|fp.fod.size' $F/vendor/build.prop | sed 's/^/     /'
ok "sensor_location = 640|2518|105" "grep -q '^persist.vendor.fingerprint.sensor_location=640|2518|105$' $F/vendor/build.prop"
