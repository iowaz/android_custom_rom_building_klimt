import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

os.environ.setdefault('KLIMT_BUILD', '20261111')
from controller import tooling_hashes
from verify import review_binding
import promotion_tooling as guard


class Promotion(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.root = Path(self.temp.name)
        self.attempt = self.root/'attempt';self.staged = self.root/'staged'
        self.attempt.mkdir();self.staged.mkdir()
        (self.attempt/'prebuild.xml').write_text('<manifest/>')
        self.review = dict(approved=True,attempt='20261111-attempt02',
            source_snapshot_sha256=self.sha(self.attempt/'prebuild.xml'),tooling_sha256=tooling_hashes(),
            evidence='Explicit verifier-only correction on the unchanged compiled source')
        self.write()

    def tearDown(self): self.temp.cleanup()
    def sha(self, p): return hashlib.sha256(p.read_bytes()).hexdigest()
    def write(self): (self.staged/'TOOL_REVIEW.json').write_text(json.dumps(self.review))

    def test_ordinary_promotion_keeps_original_exact_tooling_guard(self):
        calls=[]
        guard.validate('20261111-attempt02',None,self.staged,self.attempt,lambda p:calls.append(p),review_binding,self.sha)
        self.assertEqual(calls,[self.attempt])

    def test_explicit_recheck_uses_current_review_not_original_tooling(self):
        def wrong_path(p): raise AssertionError('Recheck must use its bound TOOL_REVIEW')
        guard.validate('20261111-attempt02','recheck01',self.staged,self.attempt,wrong_path,review_binding,self.sha)

    def test_recheck_rejects_changed_source_tooling_or_attempt(self):
        for changes in ({'source_snapshot_sha256':'0'*64},{'tooling_sha256':{}},{'attempt':'other'}):
            with self.subTest(changes=changes):
                original=dict(self.review);self.review.update(changes);self.write()
                with self.assertRaises(RuntimeError):
                    guard.validate('20261111-attempt02','recheck01',self.staged,self.attempt,lambda p:None,review_binding,self.sha)
                self.review=original


if __name__ == '__main__': unittest.main(verbosity=2)
