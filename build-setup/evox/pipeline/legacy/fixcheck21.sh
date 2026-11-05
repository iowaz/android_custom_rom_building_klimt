#!/bin/bash
: "${EVOX_EXTRACT:?attempt extraction path required}"
: "${EVOX_TMP:?attempt temporary path required}"
# evox21 checks: evox20 coverage plus the scan-driven follow-up (evolution_x_klimt_build_tasks_20261020.md):
# bionic at Evolution X f8b37b8 and the adb root policy kept out of user builds (device/lineage/sepolicy; that
# patch and its two policy checks were dropped on 2026-11-04 with the forks, see below).
F=${EVOX_EXTRACT}/fs; W=/mnt/wsl/evox/src; I=$W/out/soong/.intermediates
OD=$W/prebuilts/clang/host/linux-x86/clang-r596125/bin/llvm-objdump
ok(){ if eval "$2" >/dev/null 2>&1; then echo "OK   $1"; else echo "FAIL $1"; fi; }
bash "$(dirname "$(realpath "$0")")/fixcheck20.sh"

echo '== evox21 bionic custom_rom_hide (= upstream f8b37b8)'
# The APEX libc fixcheck9 reads; its "runtime APEX rebuilt after the libc" check ties it to the image.
LIBC=$(ls $I/bionic/libc/libc/android_arm64_armv8-a_shared_apex*/libc.so 2>/dev/null | head -1); echo "     ${LIBC#$W/}"
ULIBC=$(dirname "$LIBC")/unstripped/libc.so
# 33095e6/fff9253: kOverlayDirs, the */overlay dirs whose ROM-named APKs are left out of listings and maps.
overlay_dirs(){ local s d; s=$(strings "$LIBC") || return 1
  for d in system system_ext product vendor odm; do grep -qx "/$d/overlay" <<<"$s" || return 1; done; }
# f8b37b8: custom_rom_hide_spoof_stat no longer gives /data/local/tmp the fixed inode 4223 (0x107f).
no_tmp_inode(){ local t; t=$($OD -d --no-show-raw-insn --disassemble-symbols=custom_rom_hide_spoof_stat "$ULIBC") || return 1
  grep -q '<custom_rom_hide_spoof_stat>:$' <<<"$t" && [ "$(grep -cE '^ +[0-9a-f]+:' <<<"$t")" -ge 8 ] || return 1
  ! grep -qE '#0x107f\b' <<<"$t"; }
ok "libc filters the five */overlay dirs" "overlay_dirs"
ok "libc no longer fakes the /data/local/tmp inode" "no_tmp_inode"

echo '== evox21 no adb root in user builds'
# Retired 2026-11-04: "no packaged policy rule names an adbroot type" and "adbroot types stay declared for the
# contexts" tested the device/lineage/sepolicy patch "sepolicy: Keep the adb root policy to debuggable builds".
# It was dropped with the forks, by the owner's decision (generic hardening, not a klimt need), so a user build
# carries upstream's adbroot rules again. The binary check stays: vendor/lineage installs adb_root only with
# WITH_SU, which a user build does not set.
ok "no adb_root binary or init service" "[ ! -e $F/system_ext/bin/adb_root ] && [ ! -e $F/system/system/bin/adb_root ] && [ -d $F/system_ext/etc/init ] && ! grep -rqs adb_root $F/system/system/etc/init $F/system_ext/etc/init"

echo '== evox21 USB configuration left to the runtime'
props(){ find $F -maxdepth 4 -name '*.prop' -type f; }
ok "no prop file sets persist.sys.usb.config" "[ -f $F/system/system/build.prop ] && ! grep -qE '^persist\.sys\.usb\.config=' \$(props)"

echo '== 20261105 log review (2026-11-04 runtime logs)'
CIL=$F/vendor/etc/selinux/vendor_sepolicy.cil; SUI=$W/frameworks/base/packages/SystemUI/src/com/android/systemui/charging
# Stock does not let hypsys_vendor read vendor_mtkcam_prop either: denied, not logged, and not allowed.
ok "hypsys_vendor camera property reads dontaudited, not allowed" "grep -qE '^\(dontaudit xiaomi_misys_common vendor_mtkcam_prop(_[0-9]+)? \(file \([^)]*read' $CIL && { grep -qE '^\(allow xiaomi_misys_common vendor_mtkcam_prop' $CIL; [ \$? -eq 1 ]; }"
ok "mpbe f2fs gc_urgent writes dontaudited" "grep -qE '^\(dontaudit mpbe sysfs_fs_f2fs(_[0-9]+)? \(file \(write\)\)\)' $CIL"
ok "vendor ambient-light debug log tags quieted" "grep -qxF 'log.tag.libsensor-displayalgo=W' $F/system/system/build.prop && grep -qxF 'log.tag.libsensor-parseRGB=W' $F/system/system/build.prop && grep -qxF 'log.tag.libcomposer_ext=I' $F/system/system/build.prop"
# Source-level coverage (the frozen frameworks/base HEAD the controller and verifier already pin): hidden while
# dozing; the doze change, which ScrimUtils sends from a background executor, handled on the main thread; the
# initial doze state read; the view's dozing setter stops the running animators and startAnimations() refuses.
charging_off_aod(){ local c v; c=$(tr -d '\r' < $SUI/ChargingAnimationViewController.kt) && v=$(tr -d '\r' < $SUI/ChargingAnimationView.kt) || return 1
  grep -qxF '            isDozing -> false' <<<"$c" && ! grep -qF 'isDozing -> currentSettings.showOnAod' <<<"$c" || return 1
  grep -A2 -F 'override fun onDozingChanged(dozing: Boolean) {' <<<"$c" | grep -qF 'mainHandler.post {' || return 1
  grep -qF 'isDozing = it.isDozing()' <<<"$c" && grep -qF 'chargingView.dozing = isDozing' <<<"$c" || return 1
  grep -A6 -F 'var dozing: Boolean = false' <<<"$v" | grep -qF 'stopAllAnimations()' || return 1
  grep -qF 'if (!visible || dozing) return' <<<"$v"; }
ok "charging animation kept off the always-on display (source)" "charging_off_aod"
