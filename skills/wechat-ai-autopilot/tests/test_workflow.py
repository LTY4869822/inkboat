import base64
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import workflow as w
from validate_decision import validate


class Response:
    def __init__(self, value, etag="fixture"):
        self.data = json.dumps(value).encode()
        self.headers = {"ETag": etag}
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self, size): return self.data[:size]


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.run = Path(self.temp.name)
    def tearDown(self): self.temp.cleanup()

    def test_paths_cannot_escape_run(self):
        with self.assertRaises(ValueError): w.within(self.run, "../credentials.json")

    def test_public_article_is_clean_but_internal_evidence_is_retained(self):
        new = Path(w.init(self.run, "news", "AI")["run"])
        import intake
        intake.apply(new, {'topic_mode':'own','topic':'AI','length_preset':'standard','font':'system',
                          'writing_style':'khazix','answer_origin':'user','user_instruction':'测试输入：AI选题，标准篇幅、系统字体、卡兹克文风'})
        policy = w.read(new / "brief.json")["presentation"]
        self.assertEqual(policy, {"citations": "internal", "image_captions": "none"})
        body = "这是需要核对的具体发布。\n\n![产品角色](assets/a.png)"
        (new/'body.md').write_text(body, encoding='utf-8')
        w.save(new/'topic.json', {"working_title":"产品变化"})
        w.save(new/'sources.json', [{"id":"S1","title":"内部资料","url":"https://example.org"}])
        claims=[{"source_ids":["S1"],"locator":"开头","body_quote":"这是需要核对的具体发布。"}]
        w.save(new/'claims.json', claims)
        before=w.file_hash(new/'sources.json')
        w.assemble(new)
        public=(new/'article.md').read_text(encoding='utf-8')
        self.assertEqual(public, "# 产品变化\n\n"+body+"\n")
        self.assertEqual(w.file_hash(new/'sources.json'), before)
        self.assertEqual(w.evidence_ids(body, claims, policy), {"S1"})
        w.save(new/'claims.json', [{"source_ids":["S99"],"locator":"开头","body_quote":"已删除的旧段落。"}])
        errors=w.audit(new)['errors']
        self.assertIn('missing/unknown evidence references',errors)
        self.assertIn('internal claims need current body passages and locators',errors)

    def test_presentation_rejects_leaks_and_can_explicitly_opt_into_inline(self):
        body="发布事实。[S1]\n\n![图](assets/a.png)\n\n*图注：AI生成示意*"
        (self.run/'body.md').write_text(body,encoding='utf-8')
        w.save(self.run/'brief.json',{'presentation':{'citations':'internal','image_captions':'none'},'type':'news'})
        w.save(self.run/'topic.json',{'working_title':'标题'})
        with self.assertRaisesRegex(ValueError,'public article'): w.assemble(self.run)
        w.configure(self.run,citations='inline',image_captions='labeled')
        w.save(self.run/'sources.json',[{'id':'S1','title':'来源','url':'https://example.org'}])
        w.assemble(self.run)
        self.assertIn('https://example.org',(self.run/'article.md').read_text(encoding='utf-8'))

    def test_new_run_defaults_longer_but_respects_explicit_ranges(self):
        new = Path(w.init(self.run, "news", "AI")["run"])
        brief = w.read(new / "brief.json")
        self.assertEqual((brief["min_chars"], brief["max_chars"]), (3000, 4500))
        self.assertEqual(brief["theme"], "auto")
        w.configure(new, preset="deep", theme="sand-gold-journal")
        self.assertEqual(w.read(new / "brief.json")["min_chars"], 5000)
        w.configure(new, chars=[3600, 4400])
        self.assertEqual(w.read(new / "brief.json")["length_preset"], "custom")
        with self.assertRaises(ValueError): w.configure(new, chars=[4400, 3600])
        with self.assertRaises(ValueError): w.configure(new, theme="made-up")
        self.assertEqual(w.read(new / "brief.json")["theme"], "sand-gold-journal")

    def test_user_theme_overrides_recommendation_and_body_changes_make_it_stale(self):
        w.save(self.run / "brief.json", {"schema_version": 2, "theme": "sand-gold-journal", "visual_style": "editorial"})
        (self.run / "body.md").write_text("这是一篇新闻分析。", encoding="utf-8")
        result = w.recommend_layout(self.run, "ink-blue-editorial", "本稿连续分析较多，墨蓝刊读适合衬线长文阅读。")
        self.assertTrue(result["user_override"])
        self.assertEqual(w.effective_theme(self.run, w.read(self.run / "brief.json")), "sand-gold-journal")
        w.configure(self.run, theme="auto")
        self.assertEqual(w.effective_theme(self.run, w.read(self.run / "brief.json")), "ink-blue-editorial")
        (self.run / "body.md").write_text("换成有代码的操作教程。", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "stale"): w.effective_theme(self.run, w.read(self.run / "brief.json"))

    def test_length_is_prose_not_code_images_or_captions(self):
        body = "正文四字。[S1]\n\n*独立强调*\n\n```python\n# 代码里的中文不计\n```\n\n![很长的配图描述](assets/a.png)\n\n*图注：很长的图注不计*\n\n最后两字。"
        self.assertEqual(w.prose_cjk(body), 12)
        self.assertEqual(w.prose_cjk("正文\n\n~~~python\n代码中文\n~~~\n\n结尾"), 4)
        self.assertEqual(w.prose_cjk("正文\n\n![图](assets/a.png)\n\nAI生成示意"), 2)
        self.assertEqual(w.prose_cjk("正文\n\n![图](assets/a.png)\n\n图注：解释图"), 2)
        self.assertEqual(w.prose_cjk("正文\n\n![图](assets/a.png)\n\n正常段落继续正文。"), 10)
        self.assertEqual(w.prose_cjk("正文\n\n![图](assets/a.png)\n\n*这段正文继续解释人工复核的必要性。*"), 18)
        self.assertEqual(w.prose_cjk("正文\n\n![图](assets/a.png)\n\nAI生成的结果仍需人工复核。"), 13)

    def test_legacy_brief_theme_does_not_require_new_recommendation(self):
        self.assertEqual(w.effective_theme(self.run, {"schema_version": 1, "theme": "green-white-clean"}), "green-white-clean")

    def test_etag_304_reuses_same_response(self):
        url = "https://aihot.virxact.com/api/v1/hot-topics"
        original = {"items": [{"rank": 1}, {"rank": 2}]}
        w.fetch(url, self.run, opener=lambda *a, **k: Response(original))
        def not_modified(request, **kwargs):
            self.assertEqual(request.get_header("If-none-match"), "fixture")
            raise urllib.error.HTTPError(url, 304, "", {}, io.BytesIO())
        self.assertEqual(w.fetch(url, self.run, opener=not_modified), original)

    def test_keyword_empty_selected_falls_back_once_preserving_query(self):
        w.save(self.run / "brief.json", {"topic": "Clef"})
        urls = []
        def request(req, **kwargs):
            urls.append(req.full_url)
            return Response({"items": []})
        result = w.discover(self.run, opener=request)
        self.assertEqual(result["counts"], [0, 0, 0])
        self.assertIn("mode=all", urls[-1])
        self.assertIn("q=Clef", urls[-1])
        self.assertEqual(len(urls), 3)

    def test_discover_wide_query_does_not_expand_empty_pool(self):
        w.save(self.run / "brief.json", {"topic": "AI"})
        calls = []
        def request(req, **kwargs):
            calls.append(req.full_url)
            return Response({"items": []})
        w.discover(self.run, opener=request)
        self.assertEqual(len(calls), 2)

    def test_title_change_requires_regeneration(self):
        (self.run / "body.md").write_text("正文。[S1]", encoding="utf-8")
        w.save(self.run / "topic.json", {"working_title": "工作标题"})
        w.save(self.run / "sources.json", [{"id": "S1", "title": "来源", "url": "https://example.org"}])
        w.save(self.run / "titles.json", {"body_sha256": w.file_hash(self.run / "body.md"), "selected": "T1",
               "candidates": [{"id": "T1", "title": "定稿标题", "risk": "low"}]})
        w.assemble(self.run)
        (self.run / "body.md").write_text("新的正文。[S1]", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "stale"): w.assemble(self.run)

    def test_export_rejects_dropped_text_and_scripts(self):
        (self.run / "article.md").write_text("# 标题\n\n重要正文。", encoding="utf-8")
        self.assertTrue(w.html_check(self.run, '<section style="color:black"><h1>标题</h1><script>alert(1)</script></section>'))
        self.assertEqual(w.html_check(self.run, '<section style="color:black"><span aria-hidden="true">DECOR</span><h1>标题</h1><p>重要正文。</p></section>'), [])

    def test_code_fence_language_is_not_article_text(self):
        (self.run / "article.md").write_text('# 标题\n\n```python\nprint("hello")\n```', encoding="utf-8")
        content = '<section style="color:black"><h1>标题</h1><pre><code>print("hello")</code></pre></section>'
        self.assertEqual(w.html_check(self.run, content), [])

    def test_italic_caption_survives_export_without_its_markers(self):
        (self.run / "article.md").write_text('# 标题\n\n*AI 生成的概念示意。*', encoding='utf-8')
        self.assertEqual(w.html_check(self.run, '<section style="color:black"><h1>标题</h1><p><em>AI 生成的概念示意。</em></p></section>'), [])
        self.assertIn('x*y', w.plain_md('```python\nx*y\n```'))

    def test_export_rejects_added_claims_and_reordered_paragraphs(self):
        (self.run / 'article.md').write_text('# 标题\n\n第一段。\n\n第二段。', encoding='utf-8')
        base='<article style="color:black"><h1>标题</h1><p>第一段。</p><p>第二段。</p></article>'
        self.assertEqual(w.html_check(self.run,base),[])
        self.assertTrue(w.html_check(self.run,base+'<p>新增未核验断言。</p>'))
        self.assertTrue(w.html_check(self.run,base.replace('<p>第一段。</p><p>第二段。</p>','<p>第二段。</p><p>第一段。</p>')))

    def test_export_rejects_changed_image(self):
        (self.run / "assets").mkdir()
        (self.run / "assets" / "a.png").write_bytes(b"original")
        (self.run / "article.md").write_text("# 标题\n\n![示意](assets/a.png)", encoding="utf-8")
        content = '<section style="color:black"><h1>标题</h1><img src="data:image/png;base64,' + base64.b64encode(b"changed").decode() + '"></section>'
        self.assertTrue(any("differs" in x for x in w.html_check(self.run, content)))

    def test_missing_artifacts_and_review_cannot_pass(self):
        w.save(self.run / "brief.json", {"type": "practical", "min_chars": 0, "max_chars": 100})
        report = w.audit(self.run)
        self.assertFalse(report["passed"])
        self.assertIn("semantic/visual review missing or stale", report["errors"])
        self.assertIn("HTML export missing or stale", report["errors"])

    def test_changed_image_invalidates_completed_state(self):
        (self.run / "a.png").write_bytes(b"a")
        w.save(self.run / "images.json", [{"path": "a.png"}])
        fingerprint = w.fingerprint(self.run)["fingerprint"]
        w.save(self.run / "quality.json", {"passed": True, "fingerprint": fingerprint})
        self.assertFalse(w.status(self.run)["stale_audit"])
        (self.run / "a.png").write_bytes(b"b")
        self.assertTrue(w.status(self.run)["stale_audit"])

    def test_decision_fails_closed_on_malformed_types(self):
        for value in ([], {"action": []}, {"action": [], "reason": "test"},
                      {"action": "publish", "reason": "test"}, {"action": "verify", "reason": 1}):
            self.assertFalse(validate(value)["accepted"])
        self.assertTrue(validate({"action": "verify", "reason": "check source"})["accepted"])


if __name__ == "__main__": unittest.main()
