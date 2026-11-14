import copy
import unittest
import local_rom_control as gate


class LocalRomControl(unittest.TestCase):
    def setUp(self):
        self.old = {p: 'old-'+p for p in gate.ROM | {gate.DEVICE, 'kernel/xiaomi/klimt', 'vendor/xiaomi/klimt'}}
        self.new = dict(self.old, **{p:'new-'+p for p in gate.ROM | {gate.DEVICE}})
        self.before = {'frameworks/base':dict(base='base',final_head='old-frameworks/base',
            final_tree='old-tree',purpose='old',patches=[{'file':'old.patch','class':'personal'}]),
            'unrelated':dict(base='unchanged',patches=[])}
        self.before['frameworks/base']['class']='personal'
        self.after=copy.deepcopy(self.before)
        self.after['frameworks/base'].update(final_head=self.new['frameworks/base'],final_tree='new-tree')
        self.after['frameworks/base']['patches'].append({'file':'new.patch','class':'personal'})
        self.after['packages/apps/Evolver']={'class':'personal','patches':[{'file':'evo.patch'}],
                                          'final_head':self.new['packages/apps/Evolver']}
        self.review={p:self.new[p] for p in gate.ROM}

    def check(self): gate.check_delta(self.old,self.new,self.before,self.after,self.review)

    def test_reviewed_delta_preserves_existing_patches(self): self.check()

    def test_unrelated_head_change_is_rejected(self):
        self.new['vendor/xiaomi/klimt']='changed'
        with self.assertRaises(ValueError): self.check()

    def test_project_removal_is_rejected(self):
        del self.new['vendor/xiaomi/klimt']
        with self.assertRaises(ValueError): self.check()

    def test_unreviewed_rom_head_is_rejected(self):
        self.review['frameworks/base']='unexpected'
        with self.assertRaises(ValueError): self.check()

    def test_existing_patch_or_base_change_is_rejected(self):
        for field,value in [('base','other'),('patches',[{'file':'replacement','class':'personal'}])]:
            with self.subTest(field=field):
                after=copy.deepcopy(self.after)
                self.after['frameworks/base'][field]=value
                with self.assertRaises(ValueError): self.check()
                self.after=after

    def test_unrelated_patch_record_change_is_rejected(self):
        self.after['unrelated']['base']='different'
        with self.assertRaises(ValueError): self.check()

    def test_nonpersonal_or_extra_evolver_patch_is_rejected(self):
        self.after['packages/apps/Evolver']['class']='klimt'
        with self.assertRaises(ValueError): self.check()
        self.after['packages/apps/Evolver']['class']='personal'
        self.after['packages/apps/Evolver']['patches'].append({'file':'unexpected'})
        with self.assertRaises(ValueError): self.check()

    def test_nonfinal_patch_head_is_rejected(self):
        self.after['frameworks/base']['final_head']='base'
        with self.assertRaises(ValueError): self.check()

    def existing_evolver(self):
        self.before['packages/apps/Evolver'] = dict(
            base='evo-base', final_tree='old-evo-tree', purpose='monitor',
            final_head=self.old['packages/apps/Evolver'],
            patches=[{'file':'existing-evo.patch','class':'personal'}])
        self.before['packages/apps/Evolver']['class']='personal'
        self.after['packages/apps/Evolver']=copy.deepcopy(self.before['packages/apps/Evolver'])
        self.after['packages/apps/Evolver'].update(
            final_head=self.new['packages/apps/Evolver'], final_tree='new-evo-tree')
        self.after['packages/apps/Evolver']['patches'].append({'file':'revision.patch','class':'personal'})

    def test_existing_evolver_can_add_one_reviewed_patch(self):
        self.existing_evolver()
        self.check()

    def test_existing_evolver_patch_cannot_be_rewritten(self):
        self.existing_evolver()
        self.after['packages/apps/Evolver']['patches'][0]['file']='rewritten.patch'
        with self.assertRaises(ValueError): self.check()

    def test_existing_evolver_base_cannot_change(self):
        self.existing_evolver()
        self.after['packages/apps/Evolver']['base']='different'
        with self.assertRaises(ValueError): self.check()


if __name__=='__main__': unittest.main()
