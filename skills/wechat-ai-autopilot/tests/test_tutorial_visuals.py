import copy
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import workflow as w
from tutorial_visuals import tutorial_errors, content_fit_errors


class TutorialCoverageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.run = Path(self.temp.name)
        self.body = '打开注册入口并核对账号信息。\n\n![字段](assets/fields.png)\n\n完成验证后检查账号可用状态。\n\n![结果](assets/success.png)'
        (self.run/'body.md').write_text(self.body, encoding='utf-8')
        self.brief = {'tutorial_policy':'step-screenshots-v1'}
        self.refs = ['assets/fields.png','assets/success.png']
        self.images = [{'path':p,'role':'body','backend':'screenshot'} for p in self.refs]
        self.steps = [{'id':f'T{i+1}','title':'字段填写' if i==0 else '确认成功',
                       'before':'已打开当前流程的对应页面。','action':'按本步说明逐项核对并执行操作。',
                       'input_hint':'只填写自己的资料，没有输入则保持空白。',
                       'expected_result':'页面应显示与本步骤相应的完成状态。',
                       'attention':'出现验证障碍时保留状态，由本人协助处理。',
                       'body_quote':q,'image_paths':[p],'status':'ready'}
                      for i,(q,p) in enumerate(zip(['打开注册入口并核对账号信息。','完成验证后检查账号可用状态。'],self.refs))]
        self.plan = {'body_sha256':w.file_hash(self.run/'body.md'),'task_context':'当前官方流程、桌面中文入口已核验。',
                     'starting_point':'第一次操作，尚未拥有可用账号。','success_definition':'完成必需验证并看到账号可用的状态。','steps':self.steps}
        w.save(self.run/'reader-intent.json',{'article_type':'tutorial'})

    def check(self, plan=None, images=None, refs=None):
        if plan is not False: w.save(self.run/'tutorial-plan.json', self.plan if plan is None else plan)
        return tutorial_errors(self.run,self.brief,self.body,self.images if images is None else images,self.refs if refs is None else refs)

    def test_each_step_has_real_image_and_success_explanation(self):
        self.assertEqual(self.check(),[])

    def test_tutorial_declaration_cannot_skip_ledger(self):
        self.assertTrue(self.check(False))

    def test_missing_step_image_and_ai_substitution_rejected(self):
        bad=copy.deepcopy(self.plan); bad['steps'][1]['image_paths']=[]
        self.assertTrue(self.check(bad))
        images=copy.deepcopy(self.images);images[1]['backend']='native'
        self.assertTrue(self.check(images=images))
        self.assertTrue(self.check(refs=self.refs[:1]))

    def test_manual_gap_names_required_picture_and_never_passes(self):
        bad=copy.deepcopy(self.plan);bad['steps'][1]['status']='manual_needed'
        bad['missing_images']=[{'step_id':'T2','need':'完成本人邮箱验证后的账号可用界面。','reason':'关键验证只能本人完成，未取得有效外部图。','tried':['原产品验证页','原作者公开教程'],'help_action':'请本人完成验证，并提供可证明账号可用的截图。'}]
        errors=self.check(bad)
        self.assertTrue(any('完成本人邮箱验证' in e for e in errors))
        self.assertTrue(any('unresolved' in e for e in errors))

    def test_stale_instructions_and_missing_precautions_rejected(self):
        for mutation in ['stale','precautions','wrong_anchor','duplicate']:
            bad=copy.deepcopy(self.plan)
            if mutation=='stale':bad['body_sha256']='old'
            elif mutation=='precautions':bad['steps'][0]['attention']=''
            elif mutation=='wrong_anchor':bad['steps'][0]['body_quote']='文章没有这一句，不能假装它已写入。'
            else:bad['steps'][1]['id']='T1'
            self.assertTrue(self.check(bad))

    def test_mixed_article_tutorial_section_is_also_checked(self):
        w.save(self.run/'reader-intent.json',{'article_type':'news','tutorial_sections':['注册步骤']})
        self.assertTrue(self.check(False))

    def test_non_tutorial_and_legacy_do_not_require_step_ledger(self):
        w.save(self.run/'reader-intent.json',{'article_type':'opinion'})
        self.assertEqual(self.check(False),[])
        self.assertEqual(tutorial_errors(self.run,{},self.body,self.images,self.refs),[])


class AdaptiveStyleTests(unittest.TestCase):
    def setUp(self):
        self.body='先区分事实约束与假设，再选择解释方式。'
        self.plan={'assets':[{'path':'assets/concept.png','role':'body','backend':'native',
                            'style_decision':{'style':'中文关系信息插画，强调不同条件。','reason':'此段需要区分三类前提，标签与关系优先于场景氛围。'}}],
                   'density_review':{'status':'pass','body_quote':self.body,'excess_check':'本段只有一张分类图，没有同义装饰或连占屏幕。','gap_check':'分类在图与邻文共同解释，其他具体操作由真实截图说明。'}}

    def test_styles_and_counts_are_not_fixed(self):
        styles=['信息插画','等距剖视','叙事摄影','漫画']
        for count in (1,3,7):
            plan=copy.deepcopy(self.plan);plan['assets']=[{**copy.deepcopy(plan['assets'][0]),'path':f'assets/c{i}.png','style_decision':{'style':styles[i%len(styles)],'reason':'按本段具体关系选择视觉表达，不以封面风格或固定张数决定。'}} for i in range(count)]
            self.assertEqual(content_fit_errors({'illustration_policy':'content-fit-v1'},plan,self.body),[])

    def test_missing_style_reason_or_density_review_rejected(self):
        for what in ('reason','density','stale_quote'):
            plan=copy.deepcopy(self.plan)
            if what=='reason':plan['assets'][0]['style_decision']['reason']='高级'
            elif what=='density':plan.pop('density_review')
            else:plan['density_review']['body_quote']='这是不存在于当前正文的锚点。'
            self.assertTrue(content_fit_errors({'illustration_policy':'content-fit-v1'},plan,self.body))

    def test_cover_style_is_independent_and_legacy_preserved(self):
        plan=copy.deepcopy(self.plan);plan['assets'][0]['role']='cover';plan['assets'][0].pop('style_decision')
        self.assertEqual(content_fit_errors({'illustration_policy':'content-fit-v1'},plan,self.body),[])
        self.assertEqual(content_fit_errors({}, {}, self.body),[])

    def test_preflight_plan_does_not_claim_final_visual_review(self):
        plan=copy.deepcopy(self.plan);plan['density_review']['status']='planned'
        brief={'illustration_policy':'content-fit-v1'}
        self.assertEqual(content_fit_errors(brief,plan,self.body,final_review=False),[])
        self.assertTrue(content_fit_errors(brief,plan,self.body))


class ImportedScreenshotTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.run=Path(self.temp.name)
        # Byte provenance fixture only, not a claim of a real screenshot or image decoding.
        (self.run/'original.png').write_bytes(b'original image fixture')
        self.sources=[{'id':'S1','kind':'primary','verified':True,'url':'https://author.example/tutorial'}]
        self.record={'kind':'tutorial-step','tutorial_origin':'external','source_ids':['S1'],
                     'page_url':'https://author.example/tutorial','page_title':'作者实际操作教程','platform':'公开网页',
                     'author':'原始作者','post_time':'原发日期未知，未冒充今天','evidence_scope':'本步填写字段及对应操作状态',
                     'captured_at':'2026-10-05T01:00:00+08:00','capture_method':'source-image-crop','capture_sha256':'pixels',
                     'viewport':{'width':400,'height':300},'clip':{'x':10,'y':10,'width':200,'height':100},
                     'original_image_file':'original.png','original_image_sha256':w.file_hash(self.run/'original.png'),
                     'output_pixel_size':{'width':200,'height':100},'pixel_operation':'crop_only',
                     'usage_basis':'原作者授权可用于操作教程，保留内部授权依据。',
                     'observed_text':'本步字段名称与操作控件，实际观察记录。','review_note':'只裁真实像素，未改写字段与结果。','insert_after':'打开注册入口并核对账号信息。'}

    def check(self, record=None, sources=None):
        return w.screenshot_errors(self.run,{'path':'assets/step.png','sha256':'pixels','provenance':record or self.record},sources or self.sources)

    def test_verified_external_original_is_supported(self): self.assertEqual(self.check(),[])

    def test_user_image_does_not_need_fabricated_url(self):
        record={**self.record,'tutorial_origin':'user','supplied_by':'user','page_url':''}
        sources=[{'id':'S1','kind':'primary','verified':True,'read_record':{'access':'human_supplied'}}]
        self.assertEqual(self.check(record,sources),[])
        self.assertTrue(self.check(record,self.sources))

    def test_wrong_hash_origin_permission_and_outside_path_rejected(self):
        for change in [{'original_image_sha256':'wrong'},{'original_image_file':'../outside.png'},
                       {'usage_basis':''},{'tutorial_origin':'generated'},{'author':''},
                       {'page_url':'https://unrelated.example/page'}]:
            self.assertTrue(self.check({**self.record,**change}))

    def test_full_source_image_requires_actual_partial_context(self):
        rec={**self.record,'clip':{'x':0,'y':0,'width':400,'height':300},'output_pixel_size':{'width':400,'height':300}}
        self.assertTrue(self.check(rec))
        rec.update(already_partial=True,partial_note='原作者提供的图片已仅含本步操作区域，未含整页导航和长文。')
        self.assertEqual(self.check(rec),[])


if __name__=='__main__': unittest.main()
