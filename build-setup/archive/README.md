# Archive

Scripts that earlier builds ran, kept so the build docs can point at exactly what ran. Nothing here is used by the
current pipeline ([`../evox/pipeline`](../evox/pipeline)).

| Folder | What it is |
|---|---|
| [`evox17-tooling`](evox17-tooling) | evox17's copy of the controller, verifier and image checks, with `evox17` baked into its paths (`/mnt/c/XiaomiBuilds/...`, `D:\WitAquaBuild\out-evox`). The pipeline is this, made generic. `ready/` has the readiness, recheck and promotion scripts and records of evox17. |
| [`evox16-tooling`](evox16-tooling) | evox16's copy, including the focused precheck whose `m <module>` installs caused the evox16 boot loop. |
| [`pre-evox16`](pre-evox16) | The evox1-15 flow: `build.sh`/`start-build.sh`/`progress.sh`/`dwatch.sh`, the per-build `build-evoxNN.sh` and `verify-evoxNN.sh`, the comparison scripts in `cmp/` (the originals of the pipeline's `legacy/` checks), `fix14/`, `fix15/` and the old flash helpers. |

Their absolute paths are the build PC's layout before the 2026-10-15 reorganization (`C:\XiaomiBuilds`,
`D:\WitAquaBuild`, `D:\EvoXBuild`).
