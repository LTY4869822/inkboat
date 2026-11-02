import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import draft_bridge as d


class DraftChecks(unittest.TestCase):
    def test_roundtrip_and_rendition(self):
        a = '<article style="color: green; line-height: 29px"><p>全文</p><img src="https://mmbiz.qpic.cn/mmbiz_png/abc/0?wx_fmt=png"></article>'
        b = '<section style="color:green;line-height:29px"><p>全 文</p><img src="https://mmbiz.qpic.cn/mmbiz_png/abc/640?wx_fmt=png"></section>'
        self.assertTrue(all(d.compare(a, b).values()))

    def test_changed_text_rejected(self):
        self.assertFalse(d.compare('<p style="color:green">AB</p>', '<p style="color:green">BA</p>')['text_sequence'])

    def test_dropped_css_rejected(self):
        self.assertFalse(d.compare('<p style="color:green">AB</p>', '<p>AB</p>')['inline_styles'])

    def test_wrong_image_rejected(self):
        a = '<p style="color:green">图</p><img src="https://mmbiz.qpic.cn/mmbiz_png/abc/0">'
        self.assertFalse(d.compare(a, a.replace('/abc/', '/def/'))['image_order'])

    def test_code_indentation_rejected(self):
        a = '<pre style="color:green">if x:\n    run()</pre>'
        b = '<pre style="color:green">if x:\nrun()</pre>'
        self.assertFalse(d.compare(a, b)['code_blocks'])

    def test_editor_code_br_preserves_newline(self):
        a = '<pre style="color:green"><code>if x:\n    run()</code></pre>'
        b = '<pre style="color:green"><code><span>if x:</span><span><br class="ProseMirror-trailingBreak"></span><span>    run()</span></code></pre>'
        self.assertTrue(d.compare(a, b)['code_blocks'])
        self.assertFalse(d.compare(a, b.replace('<br class="ProseMirror-trailingBreak">', ''))['code_blocks'])
        self.assertFalse(d.compare(a, b.replace('    run()', 'run()'))['code_blocks'])

    def test_secret_url_rejected(self):
        with self.assertRaises(ValueError):
            d.image_url('https://mmbiz.qpic.cn/a/0?access_token=private')
        with self.assertRaises(ValueError):
            d.image_url('https://example.com/a.png')

    def test_stale_gate_rejected(self):
        with patch.object(d.w, 'read', return_value={'passed': True, 'fingerprint': 'old'}), patch.object(d.w, 'fingerprint', return_value={'fingerprint': 'new'}):
            with self.assertRaises(ValueError):
                d.current(Path('.'))


if __name__ == '__main__':
    unittest.main()
