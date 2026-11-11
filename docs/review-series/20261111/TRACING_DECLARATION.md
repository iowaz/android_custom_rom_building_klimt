# Tracing declaration disposition

The tracing change is deferred and incomplete. The vendor property is retained pending attribution of its
actual runtime reset writer and investigation of any boot dependency. No dependency has been established,
so retention is not described as completing the plan's conditional dependency-based disposition. No tracing
performance benefit is claimed. The phone was absent from ADB during implementation, and the earlier capture
did not retain the boottrace selector properties needed to attribute the exact reset writer.

The frozen system/core PropertyLoadBootDefaults loads system, system_ext, vendor, odm and product defaults
in that order, with later values overriding earlier map entries. The emitted system property is 0 and vendor
property is 0x4040e. Load order alone therefore does not explain the previously measured final zero.

The frozen frameworks/native atrace tool sets the tag property during trace setup and clears it on cleanup.
Perfetto's FtraceConfigMuxer calls `atrace --async_stop` when the last atrace categories/apps are removed.
The emitted system perfetto.rc also clears the property after boot when ro.boot.fastboot.boottrace is enabled
and the corresponding boot trace service is absent. The emitted vendor bootperf.rc independently enables
0x1fffffe for its ro.boot.boot_trace or persist.vendor.boot_trace selectors and disables tracing_on after boot.
Those conditional writers must not be collapsed into an invented unconditional boot reset.

No unconditional writer in the inspected device init files was found. To admit changing the vendor default
to zero, observe an early owner-started boot and relevant selector/service state, or establish the responsible
writer from a bounded private bugreport. If an actual dependency on the nonzero boot default is found, retain
it. No GED/FPSGO hook, trace support, property on the phone or init trigger was changed in this series.
