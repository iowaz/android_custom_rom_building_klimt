#!/bin/bash
: "${EVOX_EXTRACT:?attempt extraction path required}"
: "${EVOX_TMP:?attempt temporary path required}"
# evox9 checks: everything from evox8 (fixcheck8) plus LM Studio's PIF/hide/SPL sync, its completion and the
# upstream picks (EVOX_PROGRESS.md "evox9"). Runs on the unpacked img zip in ${EVOX_EXTRACT}.
F=${EVOX_EXTRACT}/fs; W=/mnt/wsl/evox/src; I=$W/out/soong/.intermediates
RE=$W/prebuilts/clang/host/linux-x86/clang-r596125/bin/llvm-readelf
ok(){ if eval "$2" >/dev/null 2>&1; then echo "OK   $1"; else echo "FAIL $1"; fi; }
dexgrep(){ unzip -p "$1" 'classes*.dex' 2>/dev/null | grep -aq "$2"; }   # dexgrep <jar|apk> <string>

echo "== evox8 checks (still present)"
bash "$(dirname "$(realpath "$0")")/fixcheck8.sh" 2>&1 | grep -E "^(OK|FAIL)"

echo "== security patch level"
BP=$F/system/system/build.prop
grep -hE '^ro\.(build\.version|vendor\.build)\.security_patch=' $BP $F/vendor/build.prop | sed 's/^/     /'
ok "system SPL 2026-10-05" "grep -q '^ro.build.version.security_patch=2026-10-05$' $BP"
ok "vendor SPL unchanged 2026-02-01" "grep -q '^ro.vendor.build.security_patch=2026-02-01' $F/vendor/build.prop"

echo "== PIF default (frameworks/base 3a2e4dd70, Evolver 4433167)"
FW=$F/system/system/framework/framework.jar
ok "framework.jar has getDefaultPifCodename" "dexgrep $FW getDefaultPifCodename"
ok "framework.jar has PICKER_ORDER" "dexgrep $FW PICKER_ORDER"
ok "framework.jar has no getPreferredASeriesCodename" "! dexgrep $FW getPreferredASeriesCodename"
# Evolver is built into SettingsGoogle (no Evolver*.apk of its own).
EV=$(find $F/system_ext $F/system/system $F/product -name 'Evolver*.apk' -o -name 'SettingsGoogle.apk' 2>/dev/null | head -1); echo "     Evolver: ${EV#$F/}"
ok "Evolver uses getDefaultPifCodename" "dexgrep $EV getDefaultPifCodename"
ok "Evolver has no A_SERIES_ORDER" "! dexgrep $EV A_SERIES_ORDER"

echo "== PackageManager ROM-package hiding (frameworks/base 141fcb879)"
SV=$F/system/system/framework/services.jar
ok "services.jar has shouldHideFromUid" "dexgrep $SV shouldHideFromUid"
ok "services.jar hides org.evolution. packages" "dexgrep $SV 'org.evolution.'"

echo "== bionic custom_rom_hide (= upstream 3d41693)"
LIBC=$(ls $I/bionic/libc/libc/android_arm64_armv8-a_shared_apex*/libc.so 2>/dev/null | head -1); echo "     ${LIBC#$W/}"
ok "libc has the framework-dir artifact list" "strings $LIBC | grep -qx '/system_ext/framework'"
ok "libc has the new ROM artifact prefixes" "strings $LIBC | grep -qx 'org.libremobileos.'"
ok "runtime APEX rebuilt after the libc" "python3 -B $(dirname "$(realpath "$0")")/../producer-check.py runtime-apex"

echo "== custom ROM detection picks"
n=$(strings $F/system/system/bin/init | grep -c 'sys.oem_unlock_allowed'); echo "     init: 'sys.oem_unlock_allowed' strings: $n"
ok "init no longer spoofs sys.oem_unlock_allowed (ee96af1583)" "[ $n -eq 0 ]"
exp=$(for f in $F/system/system/lib64/libstagefright*.so; do $RE --dyn-syms -W $f 2>/dev/null | grep -E 'ANetworkSession(10threadLoop|9interrupt)Ev' | grep -v UND; done | wc -l)
ok "ANetworkSession threadLoop/interrupt not exported (7eaa22020c)" "[ $exp -eq 0 ]"

echo "== October security picks (sources are in the tree; the image is built from them)"
for p in "frameworks/base:Fix security vulnerabilities in PduParser.java" "frameworks/base:Fix potential OOM in PduParser by using stream skip" \
         "packages/modules/Bluetooth:Remove unused ext_attrs from playerapplicationsetting_cb" \
         "frameworks/opt/telephony:RESTRICT AUTOMERGE: Fix remote DoS in decodeWapPdu (b/517376969)"; do
  ok "${p%%:*}: ${p#*:}" "python3 -B $(dirname "$(realpath "$0")")/../source-gate.py \"${p%%:*}\" \"${p#*:}\""
done
