#!/usr/bin/env python3
"""Move one verified delivery of a build to output-zips/<build> (the folder you flash from).

usage: KLIMT_BUILD=evox18 python3 -B promote.py <attempt> [<recheckNN>]

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
    assert (report / 'VERIFIED.txt').is_file() and results['runtime_unvalidated'] is True
    assert results['historical']['musthold'] == 'pass'
    historic = results['historical']['checks']
    assert len(historic) == 165 and all(v['pass'] is True for v in historic)
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
