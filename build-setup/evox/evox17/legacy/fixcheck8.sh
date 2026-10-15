#!/bin/bash
: "${EVOX_EXTRACT:?attempt extraction path required}"
: "${EVOX_TMP:?attempt temporary path required}"
# evox8 checks: everything from evox7 (fixcheck7) plus the libui camera fix, charging control, reverse wireless
# charging, AOD and Dolby. Runs on the unpacked img zip in ${EVOX_EXTRACT} (cmp-extract-evox.sh).
F=${EVOX_EXTRACT}/fs; W=/mnt/wsl/evox/src; O=$W/out/target/product/klimt
A=/mnt/wsl/build/evox-out/host/linux-x86/bin/aapt2; K=$W/vendor/evolution-priv/keys
RE=$W/prebuilts/clang/host/linux-x86/clang-r596125/bin/llvm-readelf
APKSIGNER="java -jar $W/prebuilts/sdk/tools/linux/lib/apksigner.jar"
CIL=$F/vendor/etc/selinux/vendor_sepolicy.cil
ok(){ if eval "$2" >/dev/null 2>&1; then echo "OK   $1"; else echo "FAIL $1"; fi; }
certsha(){ openssl x509 -in "$1" -noout -fingerprint -sha256 | cut -d= -f2 | tr -d : | tr A-F a-f; }

echo "== evox7 checks (still present)"
bash /mnt/c/XiaomiBuilds/build-setup/evox/evox17/legacy/fixcheck7.sh 2>&1 | grep -E "^(OK|FAIL)"

echo "== camera: libui_vendor"
ok "vendor/lib64/libui_vendor.so present" "ls $F/vendor/lib64/libui_vendor.so"
ok "libui_vendor SONAME" "$RE -d $F/vendor/lib64/libui_vendor.so | grep -q 'SONAME.*libui_vendor.so'"
ok "libui_vendor links graphics.common-V7" "$RE -d $F/vendor/lib64/libui_vendor.so | grep -q 'NEEDED.*graphics.common-V7-ndk.so'"
ok "libmicamera_hal_core links libui_vendor" "$RE -d $F/vendor/lib64/libmicamera_hal_core.so | grep -q 'NEEDED.*\[libui_vendor.so\]'"
ok "libcom.xiaomi.grallocutils links libui_vendor" "$RE -d $F/vendor/lib64/libcom.xiaomi.grallocutils.so | grep -q 'NEEDED.*\[libui_vendor.so\]'"
still=$(for f in $(find $F/vendor $F/odm -type f \( -name '*.so' -o -path '*/bin/*' \)); do $RE -d $f 2>/dev/null | grep -q 'NEEDED.*\[libui.so\]' && echo ${f#$F/}; done)
echo "     still NEED libui.so (expected: source-built codec2 libs only): $(echo $still | tr ' ' ',')"
ok "only source-built libs still need libui.so" "[ -z \"\$(echo '$still' | tr ' ' '\n' | grep -vE 'libcodec2_(vndk|aidl|hidl@1\.[0-2])\.so|libgui_vendor' | grep .)\" ]"

echo "== charging control (vendor.lineage.health)"
H=$F/vendor/bin/hw/vendor.lineage.health-service.default
ok "health service binary" "ls $H"
ok "health service uses battery/input_suspend" "strings $H | grep -q '/sys/class/power_supply/battery/input_suspend'"
ok "health VINTF fragment" "grep -rlq 'vendor.lineage.health' $F/vendor/etc/vintf"
ok "health init rc" "ls $F/vendor/etc/init/vendor.lineage.health-service.default.rc"
ok "sepolicy: health writes sysfs_batteryinfo" "grep -E 'allow hal_lineage_health_default sysfs_batteryinfo[_0-9]* .file .*write' $CIL"
ok "rc: input_suspend chown at boot" "grep -q 'chown system system /sys/class/power_supply/battery/input_suspend' $F/vendor/etc/init/hw/init.mt6991.rc"
ok "LineageParts present (Charging control UI)" "ls -d $F/system_ext/priv-app/LineageParts $F/system/system/priv-app/LineageParts 2>/dev/null | grep -q ."

echo "== reverse wireless charging (vendor.lineage.powershare)"
P=$F/vendor/bin/hw/vendor.lineage.powershare-service.default
ok "powershare service binary" "ls $P"
ok "powershare uses wireless/reverse_chg_mode" "strings $P | grep -q '/sys/class/power_supply/wireless/reverse_chg_mode'"
ok "powershare VINTF fragment" "grep -rlq 'vendor.lineage.powershare' $F/vendor/etc/vintf"
ok "sepolicy: powershare writes sysfs_batteryinfo" "grep -E 'allow hal_lineage_powershare_default sysfs_batteryinfo[_0-9]* .file .*write' $CIL"
ok "rc: reverse_chg_mode chown at boot" "grep -q 'chown system system /sys/class/power_supply/wireless/reverse_chg_mode' $F/vendor/etc/init/hw/init.mt6991.rc"

echo "== always-on display"
R=$(ls $F/vendor/overlay/framework-res__*klimt*_rro_vendor.apk | head -1)
$A dump resources $R 2>/dev/null | grep -A1 -E "config_dozeAlwaysOn|config_dozeSupportsAodWallpaper" | grep -vE "^--" | tr -s ' ' | sed 's/^/     /'
ok "RRO config_dozeAlwaysOnDisplayAvailable=true" "$A dump resources $R | grep -A1 config_dozeAlwaysOnDisplayAvailable | grep -q true"
ok "RRO config_dozeAlwaysOnEnabled=false" "$A dump resources $R | grep -A1 config_dozeAlwaysOnEnabled | grep -q false"
ok "RRO config_dozeSupportsAodWallpaper=false" "$A dump resources $R | grep -A1 config_dozeSupportsAodWallpaper | grep -q false"
ok "doze.display.supported=true" "grep -rq '^doze.display.supported=true' $F/system/system/build.prop $F/product/etc/build.prop $F/vendor/build.prop"

echo "== Dolby Atmos"
D=$(ls $F/system_ext/priv-app/DolbyAtmos/DolbyAtmos.apk 2>/dev/null)
ok "DolbyAtmos.apk in system_ext/priv-app" "[ -n '$D' ]"
dc=$($APKSIGNER verify --print-certs $D 2>/dev/null | grep -m1 'SHA-256 digest' | awk '{print $NF}')
ok "DolbyAtmos signed with OUR platform key (${dc:0:16})" "[ '$dc' = '$(certsha $K/platform.x509.pem)' ]"
ok "MusicFX/AudioFX overridden (absent)" "! ls -d $F/system*/priv-app/MusicFX $F/system*/priv-app/AudioFX $F/system/system/priv-app/MusicFX $F/system_ext/priv-app/AudioFX 2>/dev/null | grep -q ."
ok "Dolby DAP effect still declared" "grep -q 'uuid=\"9d4921da-8225-4f29-aefa-39537a04bcaa\"' $F/vendor/etc/audio_effects_config.xml"
