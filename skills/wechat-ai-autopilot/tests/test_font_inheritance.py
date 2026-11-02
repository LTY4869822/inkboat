import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from workflow import ContentParser


class FontInheritanceTests(unittest.TestCase):
    def test_editor_deduplication_preserves_font(self):
        parser = ContentParser()
        parser.feed('<article style="font-family: &quot;Microsoft YaHei&quot;,sans-serif"><h1>标题</h1><p>段落<img src="data:image/png;base64,AA=="></p><section><p style="font-family:inherit">另段</p></section></article>')
        self.assertEqual(parser.fonts, ['"Microsoft YaHei",sans-serif'] * 3)

    def test_wrong_override_and_unstyled_sibling_are_not_hidden(self):
        parser = ContentParser()
        parser.feed('<article style="font-family:Microsoft YaHei"><section style="font-family:serif"><p>错误字体</p></section><p>恢复继承</p></article><p>未设字体</p>')
        self.assertEqual(parser.fonts, ['serif', 'Microsoft YaHei', ''])


if __name__ == '__main__':
    unittest.main()
