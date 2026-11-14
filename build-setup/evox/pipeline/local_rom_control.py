"""Bind reviewed local ROM patches to an exact control and its unchanged audited kernel."""
from pathlib import Path
import candidate_gates
import kernel_carry
import kernel_contract

MODE = 'local-rom-patches-audited-kernel'
ROM = {'frameworks/base', 'packages/apps/Evolver'}
DEVICE = kernel_contract.DEVICE


def check_delta(control, current, old_bundle, new_bundle, reviewed_heads, consolidated=False):
    if set(control) != set(current) or set(reviewed_heads) != ROM:
        raise ValueError('Local ROM control project set/review allowlist differs')
    changed = {p for p in control if control[p] != current[p]}
    if changed != ROM | {DEVICE}:
        raise ValueError('Local ROM changes must be exactly the two reviewed ROM projects and device bundle/label')
    if any(current[p] != reviewed_heads[p] for p in ROM):
        raise ValueError('Local ROM heads differ from reviewed implementation')
    added = set(new_bundle) - set(old_bundle)
    if added != ({'packages/apps/Evolver'} if 'packages/apps/Evolver' not in old_bundle else set()):
        raise ValueError('Only the initial Evolver patch project may be added')
    if set(old_bundle) - set(new_bundle):
        raise ValueError('An existing patch project was removed')
    for project, old in old_bundle.items():
        new = new_bundle[project]
        if project not in ROM:
            if new != old:
                raise ValueError('An unrelated patch record changed: ' + project)
            continue
        stable = set(old) - {'purpose', 'final_head', 'final_tree', 'patches'}
        if any(old[k] != new.get(k) for k in stable):
            raise ValueError('Reviewed ROM base or classification changed: ' + project)
        if consolidated:
            keep = 2 if project == 'frameworks/base' else 0
            if (len(old['patches']) != keep + 1 or len(new['patches']) != keep + 1
                    or old['patches'][:keep] != new['patches'][:keep]):
                raise ValueError('Consolidation must preserve unrelated patches and one feature patch: ' + project)
        elif new['patches'][:len(old['patches'])] != old['patches'] or len(new['patches']) != len(old['patches']) + 1:
            raise ValueError('Existing ROM patches must be preserved with exactly one addition: ' + project)
        if new['patches'][-1].get('class') != 'personal':
            raise ValueError('The owner-requested ROM patch must be personal: ' + project)
    evo = new_bundle['packages/apps/Evolver']
    previous_count = len(old_bundle.get('packages/apps/Evolver', {}).get('patches', []))
    expected_count = 1 if consolidated else previous_count + 1
    if evo.get('class') != 'personal' or len(evo.get('patches', [])) != expected_count:
        raise ValueError('The Evolver update must add exactly one personal patch')
    for project in ROM:
        if new_bundle[project]['final_head'] != current[project]:
            raise ValueError('Reviewed ROM patch is not at final_head')


def validate_consolidation(review, new_bundle):
    """Accept changed commit/patch identities only for the exact previously reviewed trees."""
    bridge = review.get('consolidation')
    if bridge is None:
        return False
    import controller
    import paths
    import subprocess
    original = candidate_gates.revalidate(bridge['original_review'])
    anchor = candidate_gates.revalidate(bridge['anchor_preparation'])
    receipt = candidate_gates.revalidate(bridge['receipt'])
    if (anchor.get('implementation_review') != bridge['original_review']
            or review.get('source_sha256') != original.get('source_sha256')
            or receipt.get('functional_changes') is not False
            or receipt.get('unchanged_unrelated_patches') != 15
            or set(receipt.get('projects', {})) != ROM):
        raise ValueError('Consolidation is not bound to the original reviewed implementation')
    for project in ROM:
        item = receipt['projects'][project]
        if (item.get('old_head') != original['source_heads'][project]
                or item.get('new_head') != review['source_heads'][project]
                or item.get('replays') != 2):
            raise ValueError('Consolidation source-head/replay binding differs')
        trees = [subprocess.check_output(['git', '-C', str(paths.SRC/project),
                  'rev-parse', item[key]+'^{tree}'], text=True).strip() for key in ('old_head','new_head')]
        if trees != [item['old_tree'], item['old_tree']] or item['new_tree'] != item['old_tree']:
            raise ValueError('Consolidation changed reviewed source contents')
    sealed = subprocess.check_output(['git', '-C', str(paths.SRC/DEVICE), 'show',
                     receipt['device_head']+':patches/PATCHES.json'], text=True)
    if controller.parse_patch_bundle(sealed) != new_bundle:
        raise ValueError('Consolidated patch bundle differs from the replayed receipt')
    return True


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
    check_delta(old, current, old_bundle, new_bundle, review['source_heads'],
                consolidated=validate_consolidation(review, new_bundle))
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
