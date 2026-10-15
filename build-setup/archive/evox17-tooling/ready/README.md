# evox17 readiness scripts

Run in WSL, in this order, after the tree is synced to the frozen manifest:

1. `final_source17.py`: checks that every project HEAD equals `evox17-frozen.xml`, that every worktree is clean
   and that the five public certificates are unchanged; writes `FINAL_SOURCE.json`.
2. `semantic_checks.py`: proves the four historical security fixes and the SMPTE 2094-50 guard are present at the
   frozen heads (each original patch reverse-applies cleanly).
3. `make_build_ready17.py`: writes `BUILD_READY.json` only if every gate passes (frozen graph, upstream heads,
   two-patch device bundle already final, merged evox16 reviews, install_integrity rejects evox16, installclean in
   the wrapper, semantic checks, the seven registered and self-tested image checks, disk budget).

They read the work folder of the build PC (`C:\Users\diogo\Documents\Codex\2026-10-14\ru\work\evox17`); adjust
the paths elsewhere.
