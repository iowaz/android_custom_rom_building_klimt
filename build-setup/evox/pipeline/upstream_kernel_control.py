"""Bind a completed ordinary upstream refresh to an unchanged, previously audited kernel."""
import argparse
import json
from pathlib import Path

import candidate_gates
import kernel_carry
import kernel_contract
import paths

STEPS = {'UPSTREAM.json': 'upstream', 'MOVED_PROJECTS.json': 'move-renamed', 'SYNC.json': 'sync',
         'PATCH.json': 'patch', 'LABEL.json': 'label', 'FREEZE.json': 'freeze'}
MODE = 'upstream-refresh-audited-kernel'


def validate(record, frozen, snapshot_sha, tooling, load=candidate_gates.revalidate,
             heads=None, digest=None):
    if heads is None:
        from controller import expected_heads, manifest_heads
        heads = lambda raw: expected_heads(manifest_heads(raw))
    digest = digest or kernel_carry.rollback_security.digest
    if record.get('schema') != 1 or record.get('mode') != MODE:
        raise ValueError('Not an ordinary upstream refresh control')
    if record.get('tooling_sha256') != tooling or record.get('frozen_sha256') != snapshot_sha:
        raise ValueError('Upstream refresh tooling or frozen snapshot changed')
    if record.get('heads') != {p: frozen[p] for p in (kernel_contract.KERNEL, kernel_contract.DEVICE)}:
        raise ValueError('Upstream refresh device/kernel drift')
    control = record['baseline']
    if digest(control) != record['baseline_sha256']:
        raise ValueError('Upstream refresh kernel control manifest changed')
    kernel_carry.unchanged_contract(heads(Path(control).read_bytes()), frozen)
    evidence = record.get('source_preparation', {})
    if set(evidence) != set(STEPS):
        raise ValueError('All ordinary source preparation steps are required')
    values = {}
    for name, step in STEPS.items():
        value = load(evidence[name])
        if value.get('ok') is not True or value.get('step') != step or value.get('build') != record['build']:
            raise ValueError('Upstream source preparation missing, failed or from another build: ' + name)
        values[step] = value
    if values['sync'].get('exit') != 0 or values['patch'].get('check_exit') != 0:
        raise ValueError('Sync and patch checks must pass')
    output = values['patch'].get('check_output', [])
    if not output or not all(line.startswith('FINAL ') for line in output):
        raise ValueError('Every retained patch project must be FINAL')
    if values['freeze'].get('sha256') != snapshot_sha or values['freeze'].get('device_head') != frozen[kernel_contract.DEVICE]:
        raise ValueError('Upstream preparation does not bind the frozen device/snapshot')
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('build')
    parser.add_argument('--control', required=True, help='Previously fully verified build with the same kernel contract')
    args = parser.parse_args()
    if not paths.is_build(args.build) or not paths.is_build(args.control):
        parser.error('Invalid build/control')
    import controller
    current = paths.for_build(args.build)
    control = paths.for_build(args.control)
    snapshot = paths.SNAPSHOTS / (args.build + '.xml')
    baseline = paths.SNAPSHOTS / (args.control + '.xml')
    frozen = controller.expected_heads(controller.manifest_heads(snapshot.read_bytes()))
    controller.live_heads(frozen)
    if controller.foreign_processes():
        raise RuntimeError('Build/extraction active')
    anchor = json.loads((control['preparation'] / 'CANDIDATE.json').read_text())
    candidate_gates.freeze_deadline(anchor)
    record = dict(schema=1, mode=MODE, build=args.build, control_build=args.control,
                  baseline=str(baseline), baseline_sha256=candidate_gates.file_record(baseline)['sha256'],
                  frozen_sha256=candidate_gates.file_record(snapshot)['sha256'],
                  heads={p: frozen[p] for p in (kernel_contract.KERNEL, kernel_contract.DEVICE)},
                  control_freeze_utc=anchor['control_freeze_utc'], tooling_sha256=controller.tooling_hashes(),
                  source_preparation={name: candidate_gates.file_record(current['preparation'] / name) for name in STEPS})
    validate(record, frozen, record['frozen_sha256'], record['tooling_sha256'])
    destination = current['preparation'] / 'CANDIDATE.json'
    with destination.open('x') as stream:
        json.dump(record, stream, indent=2)
    print(destination)


if __name__ == '__main__':
    main()
