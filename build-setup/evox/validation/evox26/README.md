# Evox26 focused validation

These are the source scripts used for the pre-build generator and negative-case checks, retained outside pipeline/ so publication cannot change the running attempt tooling snapshot. They assume the documented WSL workspace and an existing prior build output; they run generators into diagnostics/builds/evox26/preparation/generator-checks and temporary scratch, never install modules into packaged staging, and issue no phone commands.

Run test-generators.py first, then test-metadata.py. The first runs the real Soong property generator and Make vendor macro, including duplicate-property postprocessing and a no-override fallback regression. The second consumes those outputs and checks rejection of missing/stale properties, vendor SPL, inconsistent dates, conflicting duplicates and kernel metadata.

The reference script in ../../references/evox25-prop-fix.sh is the owner's runtime comparison input. It was not executed during this build task. Its optional feature-property deletions and fixed platform dates were not carried into Evox26; see the review disposition. Running that reference script on a phone would be a separate operation.
