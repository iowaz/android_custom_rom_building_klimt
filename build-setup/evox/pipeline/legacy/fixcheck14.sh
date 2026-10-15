#!/bin/bash
: "${EVOX_EXTRACT:?attempt extraction path required}"
: "${EVOX_TMP:?attempt temporary path required}"
# evox14 checks: evox13 coverage plus stock-parity camera, composer, MiSys and sensor startup fixes.
F=${EVOX_EXTRACT}/fs
CIL=$F/vendor/etc/selinux/vendor_sepolicy.cil
VPC=$F/vendor/etc/selinux/vendor_property_contexts
VFC=$F/vendor/etc/selinux/vendor_file_contexts
ok(){ if eval "$2" >/dev/null 2>&1; then echo "OK   $1"; else echo "FAIL $1"; fi; }
bash "$(dirname "$(realpath "$0")")/fixcheck13.sh"
echo '== evox14'
ok 'dio mapper has dedicated stock label' "grep -qE '^/dev/dio_dma_mapper_misc +u:object_r:dio_dma_mapper_device:s0' $VFC"
for p in read write open ioctl map; do
  ok "camera dio mapper $p" "grep -qE '^\(allow mtk_hal_camera dio_dma_mapper_device \(chr_file \([^)]*\\b$p\\b' $CIL"
done
ok 'camera vendor data append' "grep -qE '^\(allow mtk_hal_camera vendor_data_file(_[0-9]+)? \(file \([^)]*append' $CIL"
for pre in 'vendor.camera.' 'persist.vendor.camera.'; do
  ok "$pre uses stock vendor_mtkcam_prop" "grep -qF '$pre ' $VPC && grep -F '$pre ' $VPC | grep -q vendor_mtkcam_prop"
done
ok 'camera may set vendor_mtkcam_prop' "grep -qE '^\(allow mtk_hal_camera vendor_mtkcam_prop \(property_service \(set' $CIL"
ok 'kickidle has stock label' "grep -qE '^vendor\\.debug\\.sf\\.kickidle\\. +u:object_r:vendor_mtk_debug_sf_kickidle_prop:s0' $VPC"
ok 'composer may set kickidle' "grep -qE '^\(allow hal_graphics_composer_default vendor_mtk_debug_sf_kickidle_prop \(property_service \(set' $CIL"
ok 'blackbox has dedicated stock label' "grep -qE '^/dev/block/by-name/blackbox +u:object_r:blackbox_block_device:s0' $VFC"
ok 'MiSys may read blackbox' "grep -qE '^\(allow xiaomi_misys_common blackbox_block_device \(blk_file \([^)]*read' $CIL"
for type in dmabuf_system_heap_device dmabuf_system_secure_heap_device; do
  ok "citsensorservice may open/read $type" "grep -qE '^\(allow citsensorservice $type(_[0-9]+)? \(chr_file \([^)]*read' $CIL && grep -qE '^\(allow citsensorservice $type(_[0-9]+)? \(chr_file \([^)]*open' $CIL"
done
ok 'citsensor system_prop read has stock dontaudit' "grep -qE '^\(dontaudit citsensorservice system_prop(_[0-9]+)? \(file \(read\)\)\)' $CIL"
ok 'citsensor may set its framebuffer property' "grep -qE '^\(allow citsensorservice vendor_citsensor_framebuffer_prop \(property_service \(set' $CIL"
ok 'framebuffer property has an exact boolean label' "grep -qE '^persist\\.vendor\\.sensors\\.used\\.framebuffer +u:object_r:vendor_citsensor_framebuffer_prop:s0 +exact +bool' $VPC"
