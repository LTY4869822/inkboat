import base64
import copy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import workflow as w
import motion
import studio_state as s
import studio
import draft_bridge as d

PIXEL=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aNX8AAAAASUVORK5CYII=')
class SavedStudioTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.run=Path(self.temp.name)
        self.md='# 标题\n\n## 实际问题\n\n完整正文。'
        (self.run/'article.md').write_text(self.md,encoding='utf8');(self.run/'body.md').write_text(self.md.split('\n\n',1)[1],encoding='utf8')
        w.save(self.run/'brief.json',{'schema_version':1,'font':'theme','theme':'green-white-clean'})
        self.snapshot={'schema_version':2,'baseThemeId':'green-white-clean','accent':'#12704f','font':'system','typeOverrides':{'body':{'size':18}},'styleSelections':{},'spacingOverrides':{},'motion':{'enabled':True,'items':[{'id':'opening','kind':'chapter','anchor':{'type':'h2','index':0},'content':{'title':'实际问题'},'reason':'引导读者理解正文的实际问题'}]}}
        uri='data:image/png;base64,'+base64.b64encode(PIXEL).decode()
        self.svg='<section aria-hidden="true"><svg id="opening" viewBox="0 0 720 200"><defs><clipPath id="clip"><rect width="720" height="200"></rect></clipPath></defs><image xlink:href="'+uri+'" clip-path="url(#clip)" width="720" height="200"></image><text style="opacity:1">实际问题<animate attributeName="opacity" values="0;1" dur="1s" fill="freeze"></animate></text></svg></section>'
        self.html='<article style="color:#12704f"><h1>标题</h1><h2>实际问题</h2>'+self.svg+'<p style="font-size:18px">完整正文。</p></article>'
    def tearDown(self):self.temp.cleanup()
    def save(self,**kw):
        p={'base_revision':s.latest(self.run).get('revision',0),'source_hash':w.file_hash(self.run/'article.md'),'markdown':self.md,'html':self.html,'snapshot':copy.deepcopy(self.snapshot)};p.update(kw);return s.save_version(self.run,p)
    def test_adopt_preserves_saved_html_and_layout_cannot_reset_size(self):
        self.save();s.adopt(self.run,1,'TEST FIXTURE ONLY: confirm saved revision')
        self.assertEqual((self.run/'article.html').read_text(encoding='utf8'),self.html)
        self.assertEqual(s.selection_current(self.run)['studio_revision'],1)
        self.assertTrue(w.layout(self.run)['preserved'])
        self.assertIn('font-size:18px',(self.run/'article.html').read_text(encoding='utf8'))
    def test_dirty_and_new_revision_invalidate_transfer(self):
        self.save();s.adopt(self.run,1,'TEST FIXTURE ONLY');w.save(self.run/'studio/dirty.json',{'dirty':True})
        with self.assertRaisesRegex(ValueError,'未保存'):s.selection_current(self.run)
        w.save(self.run/'studio/dirty.json',{'dirty':False});self.save()
        with self.assertRaisesRegex(ValueError,'更新'):s.selection_current(self.run)
    def test_conflicting_save_cannot_overwrite_revision(self):
        self.save()
        with self.assertRaisesRegex(ValueError,'窗口'):self.save(base_revision=0)
        self.assertEqual(s.latest(self.run)['revision'],1)
        self.assertEqual((s.paths(self.run,1)/'article.html').read_text(encoding='utf8'),self.html)
    def test_saved_preview_is_not_human_approval(self):
        self.save();w.save(self.run/'layout-selection.json',{'decision_origin':'user','user_decision':'old legacy theme choice','no_pending_edits':True})
        self.assertEqual(w.status(self.run)['next'],'studio-save-and-user-confirmation')
        with self.assertRaisesRegex(ValueError,'确认'):s.selection_current(self.run)
    def test_content_edit_requires_agent_fact_update(self):
        edited=self.md.replace('完整正文。','读者修改正文。');self.save(markdown=edited,html=self.html.replace('完整正文。','读者修改正文。'))
        with self.assertRaisesRegex(ValueError,'Agent需'):s.adopt(self.run,1,'TEST FIXTURE ONLY')
    def test_missing_svg_reference_and_static_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError,'references'):self.save(html=self.html.replace('id="clip"','id="different"'))
        static=copy.deepcopy(self.snapshot);static['motion']['enabled']=False
        with self.assertRaisesRegex(ValueError,'静态'):self.save(snapshot=static)
        self.assertFalse((self.run/'studio/revisions/r0001').exists())
    def test_bad_background_does_not_leave_half_revision(self):
        with self.assertRaisesRegex(ValueError,'本地原图'):self.save(html=self.html.replace('data:image/png;base64,'+base64.b64encode(PIXEL).decode(),'https://mmbiz.qpic.cn/mmbiz_png/fixture/0'))
        self.assertFalse((self.run/'studio/revisions/r0001').exists());self.save();self.assertEqual(s.latest(self.run)['revision'],1)
    def test_image_href_transfer_and_dropped_animation_detection(self):
        self.save();s.adopt(self.run,1,'TEST FIXTURE ONLY');record=s.latest(self.run)
        self.assertEqual(len(record['motion_assets']),1)
        w.save(self.run/'draft-transfer.json',{'authorization':'TEST FIXTURE ONLY','fingerprint':'fixture','html_sha256':w.file_hash(self.run/'article.html'),'images':record['motion_assets'],'image_occurrences':1})
        url='https://mmbiz.qpic.cn/mmbiz_png/fixture/0'
        with patch.object(d,'current',return_value='fixture'):d.transfer(self.run,[{'sha256':record['motion_assets'][0]['sha256'],'url':url}])
        transferred=(self.run/'wechat-transfer.html').read_text(encoding='utf8')
        self.assertIn('xlink:href="'+url+'"',transferred)
        self.assertTrue(all(v for k,v in d.compare(transferred,transferred).items() if k not in ('image_count','styled_nodes')))
        without=transferred.replace('<animate attributeName="opacity" values="0;1" dur="1s" fill="freeze"></animate>','')
        self.assertFalse(d.compare(transferred,without)['motion_structure'])
    def test_tampered_snapshot_and_background_rejected(self):
        self.save();last=s.latest(self.run);last['snapshot']['accent']='#ff0000';w.save(self.run/'studio/latest.json',last)
        with self.assertRaisesRegex(ValueError,'快照'):s.validate_saved(self.run)
    def test_short_article_gets_content_bound_motion_and_stale_rejected(self):
        plan=motion.plan(self.run);self.assertTrue(plan['enabled']);self.assertEqual(plan['items'][0]['content']['title'],'实际问题')
        (self.run/'article.md').write_text(self.md+'\n\n新事实。',encoding='utf8')
        with self.assertRaisesRegex(ValueError,'stale'):motion.plan(self.run)
    def test_agent_motion_plan_survives_workshop_generation(self):
        plan=motion.plan(self.run);plan['items'][0]['kind']='comparison';plan['items'][0]['content']['before']='原来';plan['items'][0]['content']['after']='现在';w.save(self.run/'motion-plan.json',plan)
        with patch.object(w,'build_layout',return_value={}),patch.object(w,'effective_theme',return_value='green-white-clean'):
            studio.build_working(self.run,self.md)
        actual=w.read(self.run/'studio/work/motion-plan.json');self.assertEqual(actual['items'][0]['kind'],'comparison');self.assertEqual(actual['items'][0]['content']['after'],'现在')
    def test_workshop_image_cannot_point_outside_run(self):
        with self.assertRaises(ValueError):studio.build_working(self.run,self.md+'\n\n![图](../../unrelated.png)')

if __name__=='__main__':unittest.main()
