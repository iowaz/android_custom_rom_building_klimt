"""Preserve every dereferenced audit proof in content-addressed release diagnostics."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

import candidate_gates
import paths
import rollback_security


def preserve(audit_path, output):
    audit_path, output = Path(audit_path).resolve(), Path(output).resolve()
    if not output.is_relative_to(paths.DIAGNOSTICS.resolve()):
        raise ValueError('Release audit preservation must be inside diagnostics/builds')
    output.mkdir(parents=True, exist_ok=False)
    audit = json.loads(audit_path.read_text())
    records = {Path(r['path']).resolve():r['sha256'] for c in audit['checks'].values() for r in c['files']}
    saved, visiting = {}, set()

    def path_of(value):
        if isinstance(value, str) and value.startswith('/'):
            path = Path(value).resolve()
            if path in records:
                return path
        return None

    def rewrite(value):
        if isinstance(value, dict):
            if set(value) >= {'path', 'sha256'}:
                # Earlier input records can retain their executed build path after an identical
                # ELF was copied elsewhere. Resolve that preserved content, never the overwritten path.
                matches = [p for p,s in records.items() if s == value['sha256'] and p.name == Path(value['path']).name]
                if matches:
                    return dict(value, **save(sorted(matches)[0]))
            return {k:(v if k == 'argv' else rewrite(v)) for k,v in value.items()}
        if isinstance(value, list):
            return [rewrite(v) for v in value]
        path = path_of(value)
        return save(path)['path'] if path else value

    def save(path):
        if path in saved:
            return saved[path]
        if path in visiting:
            raise ValueError('Cyclic audit proof dependency')
        visiting.add(path)
        if rollback_security.digest(path) != records[path]:
            raise ValueError('Source proof changed during preservation: '+str(path))
        payload = None
        if path.suffix == '.json':
            payload = json.dumps(rewrite(json.loads(path.read_text())), indent=2).encode()
            digest = hashlib.sha256(payload).hexdigest()
        else:
            digest = records[path]
        destination = output/'proofs'/digest/path.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            if payload is None:
                shutil.copyfile(path, destination)
            else:
                destination.write_bytes(payload)
        if rollback_security.digest(destination) != digest:
            raise ValueError('Preserved proof hash mismatch')
        saved[path] = dict(path=str(destination), sha256=digest)
        visiting.remove(path)
        return saved[path]

    for check in audit['checks'].values():
        check['files'] = [save(Path(r['path']).resolve()) for r in check['files']]
    result = output/'kernel-audit.json'
    result.write_text(json.dumps(audit, indent=2))
    (output/'PRESERVATION.json').write_text(json.dumps(dict(
        original=candidate_gates.file_record(audit_path), preserved=candidate_gates.file_record(result),
        files=[dict(original_path=str(p), original_sha256=records[p], preserved=r) for p,r in saved.items()],
        note='Original command argv remain historical; dereferenced proof/input paths use preserved copies.'), indent=2))
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--audit', required=True, type=Path)
    ap.add_argument('--output', required=True, type=Path)
    ap.add_argument('--frozen-manifest', required=True, type=Path)
    args = ap.parse_args()
    from controller import manifest_heads
    path = preserve(args.audit, args.output)
    audit = json.loads(path.read_text())
    candidate_gates.validate_audit(audit, manifest_heads(args.frozen_manifest.read_bytes()), audit['baseline_manifest_sha256'])
    print(path)


if __name__ == '__main__':
    main()
