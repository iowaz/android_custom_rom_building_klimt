# Separate P5 focused compiler precheck

`precheck.py`, `start-precheck.sh` and `precheck-build.sh` extend the tools with a
separate compile-only approval path. The existing full build controller, build
wrapper, verifier and historical comparisons are unchanged.

Root supplies the exact reviewed module list after source integration and writes
`C:/XiaomiBuilds/debug/evox16/PRECHECK_READY.json`. It must have:

- `approved:true`, `approval_scope:"evox16-p5-module-precheck"`,
  `target:"lineage_klimt-cp2a-user"`, `runtime_unvalidated:true`;
- the same frozen `snapshot` path and exact file `sha256`, full
  `reviewed_project_heads` and final reviewed `excluded_heads` as the static source
  inventory;
- `static_checks`: nonempty, uniquely named `{name,pass:true,evidence}` records
  establishing root-reviewed static source, patch, ownership and tooling inputs;
- `modules`: one to 64 unique exact module names, selected explicitly by root;
- `pending_module_gates`: nonempty uniquely named `{name,status:"pending"}` list,
  which remains pending in the resulting compile evidence;
- the existing five `public_certificate_sha256` PEM file hashes and reviewed
  numeric `minimum_start_gib` for host/source/output. Emergency guards retain
  host >=10 GiB and default source/output >=2 GiB. No keys are generated.

The precheck rejects full `BUILD_READY`-style `checks`, `image_checks` and
`full_build_approved` fields. It rejects package/full-build/clean targets including
`updatepackage`, `otapackage`, `evolution`, `droid`, `dist`, `all`, `checkbuild`,
`clean`, `clobber`, `installclean`, image aggregates and target-files-package.
Names cannot be options, paths or shell expressions. There is no default module
list and no automatic full build, retry, archive copy/extraction or verification.

```bash
bash /mnt/c/XiaomiBuilds/build-setup/evox/evox16/start-precheck.sh \
  evox16-precheck01 /mnt/c/XiaomiBuilds/debug/evox16/PRECHECK_READY.json
python3 -B /mnt/c/XiaomiBuilds/build-setup/evox/evox16/precheck.py status evox16-precheck01
python3 -B /mnt/c/XiaomiBuilds/build-setup/evox/evox16/precheck.py stop evox16-precheck01
# Reconnect to the existing precheck after its original controller has gone:
setsid nohup python3 -B /mnt/c/XiaomiBuilds/build-setup/evox/evox16/precheck.py \
  resume evox16-precheck01 > /mnt/wsl/evox/logs/evox16/evox16-precheck01.resume.log 2>&1 < /dev/null &
```

The supervisor holds exactly the full build's `source.lock`, checks for competing
old jobs and launches one session-owned wrapper with the reviewed modules. The
wrapper uses the existing environment/out/ccache/signing route, lunches
`lineage_klimt-cp2a-user`, positively checks product/release/user/GMS and runs
`m -j12 <exact modules>`. A separate instance of the existing independent
PID/start/boot/session watchdog retains emergency host/ext4 protection. Only
owned processes can be stopped. Resource and cumulative process CPU observations
are recorded; log silence never automatically triggers a hang stop.

Each attempt is a new `/mnt/wsl/evox/logs/evox16/evox16-precheckNN` directory.
Logs and copied core evidence live in
`C:/XiaomiBuilds/debug/evox16/evox16-precheckNN`. Files include the distinct
PRECHECK_READY input, process ownership, watchdog terminal marker, resource
JSONL, `precheck.log`, producer/supervisor exit record, before/after pinned
manifests, tooling hashes, status and RESULTS.json. Both successful and failed
compiles retain before/after source identity evidence. Source or tooling drift
records a separate tool failure and cannot be called an accepted compile result.

RESULTS records only the selected group's exit and unchanged input identity.
`compile_group_exit_zero:true` means all requested targets returned zero;
`pending_module_gates` remain explicitly pending for root's evaluation of actual
module/test evidence. It records `image_verification_performed:false` and
`full_build_approval_issued:false`. No VERIFIED marker or image claim is created.
`resume` observes this precheck and finalizes its own exit evidence; it cannot
restart a compile or invoke the full-build controller's run/resume paths.

Run focused tests without an Android compile:

```bash
python3 -B /mnt/c/XiaomiBuilds/build-setup/evox/evox16/precheck-tests.py
```
