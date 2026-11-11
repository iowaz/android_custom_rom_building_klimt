"""Prepare a local, exact candidate without syncing or relaxing normal upstream checks."""
import contextlib
import json
import re
import subprocess
import time
from pathlib import Path

import paths
import kernel_contract

ALLOWED = {kernel_contract.KERNEL, kernel_contract.DEVICE}


def validate_spec(spec, baseline_sha, tooling):
    if spec.get('schema') != 1 or spec.get('baseline_sha256') != baseline_sha:
        raise ValueError('Candidate baseline digest missing/mismatched')
    changes = spec.get('heads', {})
    if set(changes) != ALLOWED or any(not re.fullmatch(r'[0-9a-f]{40}', str(h)) for h in changes.values()):
        raise ValueError('Candidate allowlist is exactly kernel and device, with immutable heads')
    if spec.get('tooling_sha256') != tooling:
        raise ValueError('Candidate tooling differs from reviewed tooling')
    audit = Path(spec.get('audit_repository', ''))
    if not audit.is_absolute() or not audit.is_dir():
        raise ValueError('An existing absolute audit repository is required')
    return changes, audit


def run(prep, spec_path):
    import controller
    from prepare import git, clean, sha256, KERNEL, DEVICE, M, S
    spec_path = Path(spec_path).resolve()
    spec = json.loads(spec_path.read_text())
    changes, audit = validate_spec(spec, sha256(prep.snapshot), controller.tooling_hashes())
    record = prep.out / 'CANDIDATE.json'
    if record.exists() or any(prep.out.glob('*.json')):
        raise RuntimeError('Candidate preparation record already exists')
    frozen = controller.manifest_heads(prep.snapshot.read_bytes())
    expected = controller.expected_heads(frozen)
    # Device commits may already contain the metadata adaptation, but no ROM patch-bundle change.
    expected[DEVICE] = changes[DEVICE]
    baseline_bundle = prep.bundle(frozen[DEVICE])
    if prep.bundle(changes[DEVICE]) != baseline_bundle:
        raise RuntimeError('Frozen candidate may not change the ROM patch bundle')
    def audit_git(*args):
        return subprocess.check_output(['git', '--git-dir='+str(audit), *args], text=True).strip()
    candidate = audit_git('rev-parse', changes[KERNEL]+'^{commit}')
    if candidate != changes[KERNEL]:
        raise RuntimeError('Audit candidate commit mismatch')
    subprocess.run(['git', '--git-dir='+str(audit), 'merge-base', '--is-ancestor', frozen[KERNEL], candidate], check=True)
    # The isolated default branch advances; the shallow build checkout consumes only a detached commit.
    if audit_git('rev-parse', 'refs/heads/17.0') != candidate:
        raise RuntimeError('Audit default 17.0 must identify the reviewed candidate')
    with contextlib.ExitStack() as stack:
        for directory in sorted(set(paths.LOGS.glob('*')) | {paths.for_build(prep.build)['logs']}):
            if paths.is_build(directory.name):
                stack.enter_context(controller.lock(directory/'source.lock'))
        if controller.foreign_processes():
            raise RuntimeError('A build/extraction is active')
        clean(M)
        controller.live_heads(expected)
        # Verify metadata and version from the local audit object before touching the build checkout.
        metadata = git(S/DEVICE, 'show', changes[DEVICE]+':configs/kernel/metadata.config')
        kernel_contract.derive(audit_git('show', candidate+':Makefile'),
                               audit_git('show', candidate+':build.config.common'), metadata,
                               candidate, prep.previous)
        apply = subprocess.run(['python3', '-B', str(S/DEVICE/'patches/apply.py'), str(S), '--check'], capture_output=True, text=True)
        import ready
        if not ready.bundle_final(apply.returncode, apply.stdout, baseline_bundle):
            raise RuntimeError('Existing patch bundle is not FINAL')
        if prep.dry:
            print('Candidate preflight passed; no checkout/label/freeze performed')
            return
        git(S/KERNEL, 'fetch', '--no-tags', str(audit), candidate)
        controller.live_heads(expected)
        git(S/KERNEL, 'checkout', '--detach', candidate)
        expected[KERNEL] = candidate
        controller.live_heads(expected)
        prep.out.mkdir(parents=True, exist_ok=True)
        anchor = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        previous_record = paths.for_build(prep.previous)['preparation']/'CANDIDATE.json'
        if previous_record.is_file():
            import candidate_gates
            previous_data = json.loads(previous_record.read_text())
            candidate_gates.freeze_deadline(previous_data)
            anchor = previous_data['control_freeze_utc']
        data = dict(schema=1, mode='frozen-candidate', build=prep.build, previous=prep.previous,
                    baseline=str(prep.snapshot), baseline_sha256=sha256(prep.snapshot),
                    heads=changes, effective_control_heads=controller.expected_heads(frozen),
                    audit_repository=str(audit), spec_path=str(spec_path), spec_sha256=sha256(spec_path),
                    tooling_sha256=controller.tooling_hashes(), control_freeze_utc=anchor,
                    published=False)
        with record.open('x') as f:
            json.dump(data, f, indent=2)
        print(record)


def check_record(prep):
    from prepare import sha256, git, S, KERNEL, DEVICE
    import controller
    record = json.loads((prep.out/'CANDIDATE.json').read_text())
    if record['build'] != prep.build or record['previous'] != prep.previous or record['baseline_sha256'] != sha256(prep.snapshot):
        raise RuntimeError('Candidate preparation baseline drift')
    if record['tooling_sha256'] != controller.tooling_hashes() or sha256(record['spec_path']) != record['spec_sha256']:
        raise RuntimeError('Candidate preparation tooling/spec drift')
    expected = dict(record['effective_control_heads'], **record['heads'])
    label = prep.out/'LABEL.json'
    if label.exists():
        expected[DEVICE] = json.loads(label.read_text())['device_after']
    controller.live_heads(expected)
    if git(S/KERNEL, 'branch', '--show-current'):
        raise RuntimeError('Candidate kernel must remain detached')
    return record
