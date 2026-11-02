import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import zhouxing_adapter as adapter
import workflow as workflow


class ConfirmedThemeTests(unittest.TestCase):
    def test_user_host_styles_survive_id_and_order_collisions(self):
        own = json.loads((adapter.ROOT / 'assets/layout-themes/cinnabar-cultural.json').read_text(encoding='utf8'))
        own['css'] = 'outdated host copy'
        inherited = [
            {'id': 'green-white-clean', 'default': True, 'order': 1},
            {'id': 'my-personal-theme', 'default': False, 'order': 103, 'css': 'user CSS'},
            own,
        ]
        before = copy.deepcopy(inherited)
        merged = adapter.merge_themes(inherited, lambda *_args, **_kwargs: [])
        self.assertEqual(inherited, before)
        self.assertEqual(sum(t.get('default', False) for t in merged), 1)
        self.assertEqual(len({t['order'] for t in merged}), len(merged))
        self.assertEqual(len({t['id'] for t in merged}), len(merged))
        self.assertEqual(next(t['css'] for t in merged if t['id'] == 'my-personal-theme'), 'user CSS')
        self.assertNotEqual(next(t['css'] for t in merged if t['id'] == own['id']), 'outdated host copy')
        self.assertEqual([t['id'] for t in merged if t['id'] not in ('green-white-clean', 'my-personal-theme')],
                         ['moonwhite-literary', 'cinnabar-cultural', 'celadon-knowledge', 'pine-fieldnotes', 'rouge-daily'])

    def test_invalid_packaged_css_is_rejected_before_render(self):
        inherited = [{'id': 'green-white-clean', 'default': True, 'order': 1}]
        with self.assertRaisesRegex(ValueError, 'invalid confirmed theme'):
            adapter.merge_themes(inherited, lambda *_args, **_kwargs: ['unsupported CSS'])

    def test_missing_renderer_does_not_claim_theme_availability(self):
        from unittest.mock import patch
        with patch.object(workflow, 'skill_paths', return_value={'zhouxing-paiban-wx': None}):
            catalog = workflow.preferences()
        self.assertEqual(len(catalog['themes']), 10)
        self.assertFalse(any(catalog['theme_availability'].values()))


if __name__ == '__main__':
    unittest.main()
