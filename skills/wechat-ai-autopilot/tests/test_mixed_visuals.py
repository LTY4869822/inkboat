import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import workflow as w


class MixedVisualTests(unittest.TestCase):
    def setUp(self):
        self.sources = [{'id': 'S1', 'url': 'https://vendor.example/announcement',
                         'kind': 'primary', 'verified': True}]
        self.policy = {'visual_policy': {'mode': 'mixed', 'min_screenshots': 1}}
        self.anchor = '公司发布了新的工作流能力。'
        self.body = self.anchor + '\n\n![关键公告](assets/notice.jpg)'
        self.image = {'path': 'assets/notice.jpg', 'role': 'body', 'backend': 'screenshot', 'sha256': 'pixels',
                      'provenance': {'kind': 'announcement', 'source_ids': ['S1'],
                                     'page_url': self.sources[0]['url'], 'page_title': 'New workflow',
                                     'captured_at': '2026-10-03T23:00:00+08:00', 'capture_method': 'browser-clip',
                                     'capture_sha256': 'pixels', 'viewport': {'width': 1280, 'height': 720},
                                     'clip': {'x': 338, 'y': 432, 'width': 600, 'height': 215},
                                     'observed_text': 'New workflow features', 'insert_after': self.anchor,
                                     'review_note': 'Title and useful excerpt are complete and legible'}}

    def check(self, images=None, refs=None, body=None, sources=None, brief=None):
        return w.mixed_image_errors(Path('.'), brief if brief is not None else self.policy,
                                    images if images is not None else [self.image],
                                    refs if refs is not None else ['assets/notice.jpg'],
                                    sources if sources is not None else self.sources,
                                    body if body is not None else self.body)

    def test_traceable_inserted_crop_passes(self):
        self.assertEqual(self.check(), [])

    def test_all_ai_or_unused_screenshot_cannot_pass(self):
        generated = {**self.image, 'backend': 'native'}
        self.assertTrue(self.check(images=[generated]))
        self.assertTrue(self.check(refs=['assets/other.jpg']))
        self.assertTrue(self.check(body='![关键公告](assets/notice.jpg)\n' + self.anchor))

    def test_wrong_origin_or_unverified_source_rejected(self):
        for changes in ({'page_url': 'https://other.example/announcement'}, {'source_ids': ['unknown']},
                        {'page_url': 'https://vendor.example/announcement?token=private'}):
            bad = copy.deepcopy(self.image)
            bad['provenance'].update(changes)
            self.assertTrue(self.check(images=[bad]))
        self.assertTrue(self.check(sources=[{**self.sources[0], 'verified': False}]))

    def test_full_page_crop_or_changed_pixels_rejected(self):
        for changes in ({'clip': {'x': 0, 'y': 0, 'width': 1280, 'height': 720}},
                        {'clip': {'x': 1200, 'y': 432, 'width': 600, 'height': 215}},
                        {'capture_sha256': 'other pixels'}, {'capture_method': 'imagegen'}):
            bad = copy.deepcopy(self.image)
            bad['provenance'].update(changes)
            self.assertTrue(self.check(images=[bad]))

    def test_operation_requires_real_experiment_record(self):
        operation = copy.deepcopy(self.image)
        operation['provenance']['kind'] = 'operation'
        self.assertTrue(self.check(images=[operation]))
        experiment = {**self.sources[0], 'kind': 'experiment', 'url': 'operation-log.json'}
        self.assertEqual(self.check(images=[operation], sources=[experiment]), [])

    def test_previously_approved_runs_are_not_retroactively_changed(self):
        self.assertEqual(self.check(images=[], refs=[], brief={}), [])


if __name__ == '__main__':
    unittest.main()
