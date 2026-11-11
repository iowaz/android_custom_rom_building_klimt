# 20261111 review series

The built K candidate is kernel 08c56166 and device 1b1b1cc7. Its source manifest and build result are in
[20261111.md](../../20261111.md). It is experimental and image-checked only; the owner has not admitted a flash.

The three patches here publish all queued device changes for review while preserving the kernel-only
default cnb head used by the ZIP. They are not applied to that build. Their combined diff passes a read-only
git apply --check against device 1b1b1cc7; no source worktree or branch was changed by exporting them.

After K passes its runtime gates, renderer/documentation cleanup can be built and validated as K+D.
The six numeric 120 Hz keys are a later unpromoted experiment using validated K+D as its control. They
must not ship without the plan's objective benefit and non-regression evidence. Existing 60/90/144 Hz
values, vendor-named keys and tracing behavior remain unchanged. No per-build branch was created.

The archived PLAN describes the runtime sequence. Review reports and their final disposition are added
alongside this series after the independent code reviews complete. Raw phone captures, proprietary
blobs, signing keys, debug ELFs and large local proof stores are deliberately absent from Git.
