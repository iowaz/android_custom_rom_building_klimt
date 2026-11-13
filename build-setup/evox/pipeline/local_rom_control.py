"""Bind reviewed local ROM patches to an exact control and its unchanged audited kernel."""
from pathlib import Path
import candidate_gates
import kernel_carry
import kernel_contract

MODE = 'local-rom-patches-audited-kernel'
ROM = {'frameworks/base', 'packages/apps/Evolver'}
DEVICE = kernel_contract.DEVICE


def check_delta(control, current, old_bundle, new_bundle, reviewed_heads):
    if set(control) != set(current) or set(reviewed_heads) != ROM:
        raise ValueError('Local ROM control project set/review allowlist differs')
    changed = {p for p in control if control[p] != current[p]}
    if changed != ROM | {DEVICE}:
        raise ValueError('Local ROM changes must be exactly the two reviewed ROM projects and device bundle/label')
    if any(current[p] != reviewed_heads[p] for p in ROM):
        raise ValueError('Local ROM heads differ from reviewed implementation')
    if set(new_bundle) - set(old_bundle) != {'packages/apps/Evolver'}:
        raise ValueError('Only the Evolver patch project may be added')
    if set(old_bundle) - set(new_bundle):
        raise ValueError('An existing patch project was removed')
    for project, old in old_bundle.items():
        new = new_bundle[project]
        if project != 'frameworks/base':
            if new != old:
                raise ValueError('An unrelated patch record changed: ' + project)
            continue
        stable = set(old) - {'purpose', 'final_head', 'final_tree', 'patches'}
        if any(old[k] != new.get(k) for k in stable):
            raise ValueError('Framework base or classification changed')
        if new['patches'][:len(old['patches'])] != old['patches'] or len(new['patches']) != len(old['patches']) + 1:
            raise ValueError('Existing framework patches must be preserved with exactly one addition')
        if new['patches'][-1].get('class') != 'personal':
            raise ValueError('The owner-requested framework patch must be personal')
    evo = new_bundle['packages/apps/Evolver']
    if evo.get('class') != 'personal' or len(evo.get('patches', [])) != 1:
        raise ValueError('The Evolver addition must be one personal patch')
    for project in ROM:
        if new_bundle[project]['final_head'] != current[project]:
            raise ValueError('Reviewed ROM patch is not at final_head')


def validate(record, frozen, snapshot_sha, tooling):
    import controller
    import paths
    if record.get('schema') != 1 or record.get('mode') != MODE:
        raise ValueError('Not a local ROM patch control')
    if record.get('tooling_sha256') != tooling or record.get('frozen_sha256') != snapshot_sha:
        raise ValueError('Local ROM tooling/snapshot drift')
    baseline_path = Path(record['baseline'])
    if controller.sha(baseline_path) != record['baseline_sha256']:
        raise ValueError('Local ROM control manifest drift')
    old_frozen = controller.manifest_heads(baseline_path.read_bytes())
    old_bundle = controller.patch_bundle(old_frozen)
    new_bundle = controller.patch_bundle(frozen)
    old = controller.effective_heads(old_frozen, old_bundle)
    current = controller.effective_heads(frozen, new_bundle)
    kernel_carry.unchanged_contract(old, current)
    if record.get('heads') != {p: frozen[p] for p in (DEVICE, kernel_contract.KERNEL)}:
        raise ValueError('Local ROM device/kernel drift')
    review = candidate_gates.revalidate(record['implementation_review'])
    proof = candidate_gates.revalidate(record['preparation_review'])
    check_delta(old, current, old_bundle, new_bundle, review['source_heads'])
    if (proof.get('mode') != MODE or proof.get('build') != record['build']
            or proof.get('effective_control_heads') != old
            or proof.get('effective_candidate_heads') != current
            or proof.get('patch_check_exit') != 0
            or proof.get('prior_patches_preserved') is not True
            or proof.get('implementation_review') != record['implementation_review']
            or not proof.get('patch_check_output')
            or not all(line.startswith('FINAL ') for line in proof['patch_check_output'])):
        raise ValueError('Local ROM preparation proof differs from the reviewed graph')
    script = proof['preparation_script']
    if controller.sha(Path(script['path'])) != script['sha256']:
        raise ValueError('Local ROM preparation script drift')
    import subprocess
    if subprocess.run(['git', '-C', str(paths.SRC/DEVICE), 'merge-base', '--is-ancestor',
                       old[DEVICE], current[DEVICE]], capture_output=True).returncode:
        raise ValueError('Local device changes must descend from the control')
    changed = subprocess.check_output(['git', '-C', str(paths.SRC/DEVICE), 'diff', '--name-only',
                                      old[DEVICE], current[DEVICE]], text=True).splitlines()
    if any(not p.startswith('patches/') and p != 'configs/kernel/metadata.config' for p in changed):
        raise ValueError('Device changes exceed the patch bundle and build label')
    import prepare
    old_meta = subprocess.check_output(['git', '-C', str(paths.SRC/DEVICE), 'show',
            old[DEVICE]+':configs/kernel/metadata.config'], text=True)
    new_meta = subprocess.check_output(['git', '-C', str(paths.SRC/DEVICE), 'show',
            current[DEVICE]+':configs/kernel/metadata.config'], text=True)
    if prepare.relabel(old_meta, record['control_build'], record['build']) != new_meta:
        raise ValueError('Local ROM build changed kernel metadata beyond its label')
    for rel, digest in review['source_sha256'].items():
        p = Path(rel)
        if p.is_absolute() or '..' in p.parts or not any(rel.startswith(r+'/') for r in ROM):
            raise ValueError('Invalid reviewed source path')
        if controller.sha(paths.SRC/p) != digest:
            raise ValueError('Reviewed implementation source drift: '+rel)
    return record
