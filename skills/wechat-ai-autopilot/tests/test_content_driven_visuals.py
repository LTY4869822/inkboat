import copy
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import workflow as w


class ContentDrivenVisualTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.run = Path(self.temp.name)
        self.body = '## 工作方式的变化\n\n公司发布了新的工作流能力。\n\n![数据](assets/data.png)\n\n## 读者可以怎样使用\n\n使用时先确定任务边界。'
        (self.run/'body.md').write_text(self.body, encoding='utf-8')
        self.brief = {'body_images': 'auto', 'visual_policy': {'mode':'mixed','min_screenshots':1,'selection':'content-driven-v1'}}
        self.plan = {'body_sha256':w.file_hash(self.run/'body.md'),
                     'coverage':[{'section':'工作方式的变化','anchor':'公司发布了新的工作流能力。','need':'screenshot','reason':'原始对照数据能解释本次能力变化。','asset_paths':['assets/data.png']},
                                 {'section':'读者可以怎样使用','anchor':'使用时先确定任务边界。','need':'text-only','reason':'本节输入指令已能说明操作，无需另配图。','asset_paths':[]}],
                     'assets':[{'path':'assets/data.png','role':'body','backend':'screenshot','value_check':{
                         'question':'新能力究竟带来了什么变化？','reader_gain':'读者可以对照原始数据理解变化。','why_this_medium':'真实结果图保留了数据与测试条件。','removal_cost':'删掉会失去这一判断的可视证据。','evidence_kind':'data'}}]}

    def check(self, plan=None):
        w.save(self.run/'images-plan.json', plan or self.plan)
        return w.image_plan_errors(self.run,self.brief,self.body,['assets/data.png'])

    def test_auto_has_no_fixed_minimum_or_upper_quota(self):
        self.assertEqual(w.explicit_image_minimum(self.brief),0)
        self.assertEqual(w.explicit_image_minimum({'body_images':7}),7)
        self.assertEqual(self.check(),[])

    def test_identity_only_and_empty_value_rejected(self):
        for key,value in [('evidence_kind','identity-only'),('reader_gain','')]:
            bad=copy.deepcopy(self.plan)
            bad['assets'][0]['value_check'][key]=value
            self.assertTrue(self.check(bad))

    def test_full_article_must_be_considered(self):
        bad=copy.deepcopy(self.plan); bad['coverage'].pop()
        self.assertTrue(self.check(bad))

    def test_stale_body_or_unplanned_image_rejected(self):
        bad=copy.deepcopy(self.plan); bad['body_sha256']='old'
        self.assertTrue(self.check(bad))
        bad=copy.deepcopy(self.plan); bad['assets']=[]
        self.assertTrue(self.check(bad))

    def test_text_only_cannot_include_decorative_image(self):
        bad=copy.deepcopy(self.plan);bad['coverage'][1]['asset_paths']=['assets/data.png']
        self.assertTrue(self.check(bad))

    def test_decided_medium_must_match_actual_asset(self):
        bad=copy.deepcopy(self.plan);bad['assets'][0]['backend']='native'
        self.assertTrue(self.check(bad))

    def test_legacy_runs_keep_their_prior_contract(self):
        self.assertEqual(w.image_plan_errors(self.run,{},self.body,[]),[])
        self.assertTrue(w.mixed_image_errors(self.run,{'visual_policy':'invalid'},[],[],[],self.body))


class PDFProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.run=Path(self.temp.name)
        # Only a byte-provenance fixture; semantic PDF and pixel review are host responsibilities.
        (self.run/'original.pdf').write_bytes(b'%PDF-1.4\nunit-test-original\n%%EOF')
        self.sources=[{'id':'S1','kind':'primary','verified':True,'url':'https://vendor.example/card.pdf'}]
        self.record={'kind':'announcement','source_ids':['S1'],'page_url':self.sources[0]['url'],
                     'page_title':'System card','captured_at':'2026-10-04T00:40:00+08:00',
                     'capture_method':'pdf-render-crop','capture_sha256':'pixels',
                     'pdf_file':'original.pdf','pdf_sha256':w.file_hash(self.run/'original.pdf'),
                     'page_number':111,'page_size_points':{'width':612,'height':792},'render_scale':3,
                     'viewport':{'width':1836,'height':2376},'clip':{'x':204,'y':663,'width':1416,'height':1062},
                     'observed_text':'Score and average output tokens','insert_after':'原始测试展示不同档位的关系。',
                     'review_note':'Original plot, axes and legend retained; conditions discussed alongside.'}
    def check(self, changes=None):
        record={**self.record,**(changes or {})}
        return w.screenshot_errors(self.run,{'path':'assets/chart.png','sha256':'pixels','provenance':record},self.sources)
    def test_original_pdf_crop_is_supported(self): self.assertEqual(self.check(),[])
    def test_changed_pdf_wrong_page_or_render_scale_rejected(self):
        for changes in [{'pdf_sha256':'changed'},{'page_number':0},{'render_scale':2},{'pdf_file':'missing.pdf'},
                        {'pdf_file':'../outside.pdf'},{'capture_method':'imagegen'}]:
            self.assertTrue(self.check(changes))


if __name__=='__main__': unittest.main()
