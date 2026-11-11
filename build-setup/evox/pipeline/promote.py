#!/usr/bin/env python3
"""Move one verified delivery of a build to output-zips/<build> (the folder you flash from).

usage: KLIMT_BUILD=20261105 python3 -B promote.py <attempt> [<recheckNN>]

The delivery staged by verify.py (diagnostics/builds/<build>/delivery/<attempt>[/rechecks/<recheck>]) is
checked against its SHA256SUMS and RESULTS.json, then moved (a rename on the same disk, no copy) to
output-zips/<build>. Any other staged ZIP of the same build with the same SHA-256 is an exact duplicate and
is removed. Nothing else is deleted.
"""
import hashlib, json, os, sys
from pathlib import Path

import paths
from controller import BUILD, sha

MODES = {'policy', 'patch_packaging', 'private_compatibility', 'health_semantics', 'gms_themes_apps', 'doze_packaging', 'install_integrity'}

def main():
    attempt = sys.argv[1]
    recheck = sys.argv[2] if len(sys.argv) > 2 else None
    assert paths.build_of(attempt) == BUILD
    p = paths.for_build(BUILD)
    staged = p['staging'] / attempt / ('rechecks/' + recheck if recheck else '')
    report = p['reports'] / attempt / ('rechecks/' + recheck if recheck else '')
    dest = p['delivery']
    results = json.loads((report / 'RESULTS.json').read_text())
    import kernel_contract
    if results['source_heads'][kernel_contract.KERNEL] != kernel_contract.BASELINE and not results.get('candidate_evidence'):
        raise RuntimeError('Changed kernel cannot be promoted without candidate audit/rollback evidence')
    from controller import L, require_tooling_frozen
    if results.get('candidate_evidence'):
        import candidate_gates, rollback_security
        import promotion_tooling
        from verify import review_binding
        promotion_tooling.validate(attempt, recheck, staged, L/attempt, require_tooling_frozen, review_binding, sha)
        ready = json.loads((L/attempt/'BUILD_READY.json').read_text())
        if recheck:
            import reviewed_readiness
            review = json.loads((staged/'TOOL_REVIEW.json').read_text())
            ready = reviewed_readiness.apply(ready, review, candidate_gates.revalidate, candidate_gates.validate_ready)
        else:
            import release_audit
            ready = release_audit.effective_ready(L/attempt, ready)
        from controller import ready_heads
        if ready_heads(ready) != results['source_heads']:
            raise RuntimeError('Verified source heads disagree with candidate readiness')
        candidate_gates.validate_ready(ready, ready['reviewed_project_heads'])
        if ready['candidate_evidence'] != results['candidate_evidence']:
            raise RuntimeError('Candidate audit evidence differs from verified attempt')
        import kernel_artifact
        artifact_reports = results.get('kernel_artifact_evidence', {})
        if set(artifact_reports) != {'kernel-artifact-binding.json', 'image-files.json', 'filesystem-files.json'}:
            raise RuntimeError('Packaged kernel/ELF/config/module binding evidence required')
        for name, digest in artifact_reports.items():
            if sha(report/name) != digest or sha(staged/name) != digest:
                raise RuntimeError('Packaged kernel binding evidence changed after verification')
        kernel_artifact.validate_receipt(json.loads((report/'kernel-artifact-binding.json').read_text()),
                                         candidate_gates.revalidate(ready['candidate_evidence']['kernel_audit']),
                                         ready['reviewed_project_heads'], results['archive_sha256'],
                                         json.loads((report/'image-files.json').read_text()),
                                         json.loads((report/'filesystem-files.json').read_text()))
        for name, digest in results['rollback_security'].items():
            if sha(report/name) != digest or sha(staged/name) != digest:
                raise RuntimeError('Rollback/security report changed after verification')
        rollback_security.compare(candidate_gates.revalidate(ready['candidate_evidence']['rollback_baseline'])['security'],
                                  json.loads((report/'rollback-security-candidate.json').read_text()))
    assert (report / 'VERIFIED.txt').is_file() and results['runtime_unvalidated'] is True
    assert results['historical']['musthold'] == 'pass'
    historic = results['historical']['checks']
    expected = json.loads((Path(__file__).resolve().parent / 'expected-legacy-checks.json').read_text())
    assert sorted(v['name'] for v in historic) == sorted(expected) and all(v['pass'] is True for v in historic)
    assert {v['coverage'] for v in results['supplemental']} == MODES and all(v['exit'] == 0 for v in results['supplemental'])
    archive = staged / f'lineage_klimt-{BUILD}-img.zip'
    assert Path(results['archive']).resolve() == archive.resolve(), (results['archive'], archive)
    for line in (staged / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ', 1)
        assert sha(staged / name) == digest, (name, 'staged delivery hash mismatch')
    assert sha(archive) == results['archive_sha256']
    assert not dest.exists(), f'{dest} exists; a build is promoted once'
    dest.parent.mkdir(parents=True, exist_ok=True)
    os.rename(staged, dest)  # same NTFS volume
    removed = []
    for other in p['staging'].rglob(f'lineage_klimt-{BUILD}-img.zip'):
        if other.stat().st_size == results['archive_bytes'] and sha(other) == results['archive_sha256']:
            other.unlink(); removed.append(str(other))
    receipt = dict(build=BUILD, attempt=attempt, recheck=recheck, report=str(report), delivery=str(dest),
                   archive_sha256=results['archive_sha256'], removed_duplicate_zips=removed, runtime_unvalidated=True)
    (p['debug'] / 'PROMOTED.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('Promoted', dest, '| removed duplicates:', removed)

if __name__ == '__main__':
    main()
