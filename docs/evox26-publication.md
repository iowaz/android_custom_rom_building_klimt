# Evox26 source publication

Review branches are named `evox26`. Source HEADs are the exact revisions of the running attempt; publication does not amend them or modify the active pipeline. The kernel, native, interfaces and earlier framework changes are included to make the complete custom source state easy to inspect.

| Source project | Review branch | Exact commit |
|---|---|---|
| `device/xiaomi/klimt` | [android_device_xiaomi_klimt](https://github.com/iowaz/android_device_xiaomi_klimt/tree/evox26) | [12a38ffebe1e](https://github.com/iowaz/android_device_xiaomi_klimt/commit/12a38ffebe1e021897ebb367826c4b803b31cdad) |
| `build/make` | [build](https://github.com/iowaz/build/tree/evox26) | [4923147cc6c6](https://github.com/iowaz/build/commit/4923147cc6c6fede608eba7807350d32007246e7) |
| `build/soong` | [build_soong](https://github.com/iowaz/build_soong/tree/evox26) | [f1cbddf5c935](https://github.com/iowaz/build_soong/commit/f1cbddf5c93541039f63180cd19aadb48bb34a63) |
| `frameworks/base` | [frameworks_base](https://github.com/iowaz/frameworks_base/tree/evox26) | [829dab06450f](https://github.com/iowaz/frameworks_base/commit/829dab06450fd192e7fb0115b639b8066052be89) |
| `device/lineage/sepolicy` | [device_evolution_sepolicy](https://github.com/iowaz/device_evolution_sepolicy/tree/evox26) | [9112cdacfea9](https://github.com/iowaz/device_evolution_sepolicy/commit/9112cdacfea9cdb48a5ee145dfc53c471669ae3d) |
| `kernel/xiaomi/klimt` | [android_kernel_xiaomi_klimt](https://github.com/iowaz/android_kernel_xiaomi_klimt/tree/evox26) | [f6a5b29f9fe5](https://github.com/iowaz/android_kernel_xiaomi_klimt/commit/f6a5b29f9fe59e4849680d50232f8b5758aa8c11) |
| `frameworks/native` | [frameworks_native](https://github.com/iowaz/frameworks_native/tree/evox26) | [2341752da7cc](https://github.com/iowaz/frameworks_native/commit/2341752da7cc47dfb8ca54af82e8ae825bc53d5e) |
| `hardware/interfaces` | [hardware_interfaces](https://github.com/iowaz/hardware_interfaces/tree/evox26) | [11087c5b9457](https://github.com/iowaz/hardware_interfaces/commit/11087c5b9457e65346d0324f5452c647fc080a7c) |

The existing private `vendor/lineage` and `vendor/xiaomi/klimt` forks remain private, receive `evox26` review branches, and are intentionally omitted from the public link table. No signing keys, keyboxes, account data, raw phone captures or CLI review packets are part of this public repository.

[Original attempt manifest](../manifests/snapshots/evox26.xml) is preserved byte-for-byte. [Published transport manifest](../manifests/snapshots/evox26-published.xml) has the same 1,263 path/revision pairs. Revisions remain fixed SHA pins; remapped projects fetch from owner forks with `upstream="evox26"` and `dest-branch="evox26"`. Those SHAs are the published branch tips. The private frozen-manifest repository also receives an `evox26` branch containing that transport manifest as `default.xml`. Private blob access and separate signing keys are still required.

The [build notes](evox26.md) and [independent-review disposition](evox26-review.md) state the implemented metadata and remaining flash/rollback limits. The runtime comparison input is retained in [references](../build-setup/evox/references/evox25-prop-fix.sh); it was not executed for this build. [Focused validation scripts](../build-setup/evox/validation/evox26/README.md) show the pre-build generator and negative-case checks without installing modules or issuing phone commands.

Build compilation and automatic static image verification are separate from this publication. No build-completion, boot-test or flash claim is made by a source push. The evolving private attempt logs remain the authority for build progress.
