#!/usr/bin/env python3
"""Extract a security/rollback control only from a verified, matching artifact inventory."""
import argparse
import json
from pathlib import Path
import rollback_security as security
import candidate_gates
import paths


def main():
    ap = argparse.ArgumentParser()
    for name in ('snapshot', 'extract', 'archive', 'report', 'output'):
        ap.add_argument('--'+name, required=True, type=Path)
    args = ap.parse_args()
    from controller import manifest_heads
    from ready import security_patch_level
    results = json.loads((args.report/'RESULTS.json').read_text())
    archive = candidate_gates.file_record(args.archive)
    if archive['sha256'] != results['archive_sha256'] or results['historical']['musthold'] != 'pass':
        raise ValueError('Control archive is not the previously verified artifact')
    source = manifest_heads(args.snapshot.read_bytes())
    from controller import expected_heads
    if expected_heads(source) != results['source_heads']:
        raise ValueError('Control manifest differs from verified artifact source')
    for filename, directory, required in (
            ('image-files.json', 'img', {n+'.img' for n in security.IMAGES}),
            ('filesystem-files.json', 'fs', set(security.PROPS.values()))):
        inventory = {r['path']:r for r in json.loads((args.report/filename).read_text())}
        for name in required:
            if security.digest(args.extract/directory/name) != inventory[name]['sha256']:
                raise ValueError('Control extraction differs from verified inventory: '+name)
    spl = security_patch_level(source)['platform_security_patch']
    record = dict(schema=1, baseline_manifest_sha256=security.digest(args.snapshot), archive=archive,
                  verified_results=candidate_gates.file_record(args.report/'RESULTS.json'),
                  image_inventory=candidate_gates.file_record(args.report/'image-files.json'),
                  security=security.collect(args.extract, paths.SRC/'external/avb/avbtool.py', spl))
    with args.output.open('x') as f:
        json.dump(record, f, indent=2)
    print(args.output)


if __name__ == '__main__':
    main()
