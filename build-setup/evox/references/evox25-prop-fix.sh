#!/system/bin/sh
# evox25 runtime identity fix — makes the build family coherent-Xiaomi (klimt_global HyperOS 3.0.335.0.XOSMIXM)
# Volatile: reverts on reboot. Run as root: su -c 'sh /data/local/tmp/evox25-prop-fix.sh'
FP="Xiaomi/klimt_global/klimt:17/OS3.3.260806.171839609/OS3.0.335.0.XOSMIXM:user/release-keys"
BID="OS3.3.260806.171839609"
INC="OS3.0.335.0.XOSMIXM"
for p in ro.build.fingerprint ro.system.build.fingerprint ro.product.build.fingerprint ro.odm.build.fingerprint ro.odm_dlkm.build.fingerprint ro.system_dlkm.build.fingerprint ro.system_ext.build.fingerprint ro.vendor.build.fingerprint ro.vendor_dlkm.build.fingerprint ro.bootimage.fingerprint; do
  resetprop $p "$FP"
done
resetprop ro.build.id "$BID"; resetprop ro.build.display.id "$BID"
for p in ro.system.build.id ro.product.build.id ro.odm.build.id ro.odm_dlkm.build.id ro.system_dlkm.build.id ro.system_ext.build.id ro.vendor.build.id ro.vendor_dlkm.build.id; do
  resetprop $p "$BID"
done
resetprop ro.build.version.incremental "$INC"
for p in ro.system.build.version.incremental ro.product.build.version.incremental ro.odm.build.version.incremental ro.odm_dlkm.build.version.incremental ro.system_dlkm.build.version.incremental ro.system_ext.build.version.incremental ro.vendor_dlkm.build.version.incremental; do
  resetprop $p "$INC"
done
resetprop ro.build.flavor klimt_global-user
resetprop ro.build.description "klimt_global-user 17 $BID $INC release-keys"
resetprop ro.build.host pangu-build-component-system-247-r6kfm
resetprop ro.build.user builder
resetprop ro.build.version.known_codenames "Base,Base11,Cupcake,Donut,Eclair,Eclair01,EclairMr1,Froyo,Gingerbread,GingerbreadMr1,Honeycomb,HoneycombMr2,IceCreamSandwich,IceCreamSandwichMr1,JellyBean,JellyBeanMr1,JellyBeanMr2,Kitkat,KitkatWatch,Lollipop,LollipopMr1,M,N,NMr1,O,OMr1,P,Q,R,S,Sv2,Tiramisu,UpsideDownCake,VanillaIceCream,Baklava,CinnamonBun"
resetprop --delete ro.modversion
resetprop --delete ro.rom.zone
resetprop --delete debug.photos.force_pixel_eol
resetprop --delete setupwizard.feature.show_pixel_tos
resetprop ro.vendor.build.security_patch 2026-10-05
resetprop ro.build.date.utc 1785974400
resetprop ro.system.build.date.utc 1785974400
resetprop ro.vendor.build.date.utc 1785974400
resetprop ro.build.date "Thu Aug  6 00:00:00 UTC 2026"
resetprop ro.system.build.date "Thu Aug  6 00:00:00 UTC 2026"
resetprop ro.vendor.build.date "Thu Aug  6 00:00:00 UTC 2026"
echo "done - identity is coherent-Xiaomi until reboot"
