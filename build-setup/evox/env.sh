# Sourced by the Evo build scripts
cd /mnt/wsl/evox/src || exit 1
# out -> /mnt/wsl/build/evox-out (symlink). An absolute OUT_DIR outside the tree breaks test_package paths in soong.
unset OUT_DIR
mkdir -p /mnt/wsl/build/evox-out
[ -L out ] || ln -s /mnt/wsl/build/evox-out out
export SOONG_NINJA=ninja
export USE_CCACHE=1 CCACHE_EXEC=/usr/bin/ccache CCACHE_DIR=/mnt/wsl/build/ccache
# 20G cap (was 50G): D: has little free space, so ccache evicts old entries instead of growing build.vhdx.
mkdir -p "$CCACHE_DIR"; ccache -M 20G >/dev/null
source build/envsetup.sh >/dev/null
source vendor/lineage/vars/aosp_target_release
# user (was userdebug since evox1): decided 2026-10-09 for Play Integrity; no adb root.
LUNCH_TARGET="lineage_klimt-${aosp_target_release}-user"
