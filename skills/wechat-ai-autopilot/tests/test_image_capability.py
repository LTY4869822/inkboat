import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from visual_policy import generation_errors
import workflow as w


class ImageCapabilityTests(unittest.TestCase):
    def setUp(self):
        self.policy = {'selection':'content-driven-v2', 'body_ai':'when_available'}
        self.plan = {'generation':{'builtin_available':True, 'mode':'builtin',
                     'tool':'image_gen__imagegen', 'capability_evidence':'Host exposes its built-in image generation tool'},
                     'coverage':[{'anchor':'文档问答与汇报交付有不同验收方式。','need':'generated'}]}
        self.image = {'path':'assets/concept.png','role':'body','backend':'native','sha256':'pixels',
                      'generation_record':{'status':'success','tool':'image_gen__imagegen',
                          'output_sha256':'pixels','generated_at':'2026-10-04T19:00:00+08:00'}}

    def check(self, plan=None, images=None):
        return generation_errors(self.policy, plan or self.plan,
                                 [self.image] if images is None else images, ['assets/concept.png'])

    def test_successful_builtin_body_image(self):
        self.assertEqual(self.check(), [])

    def test_cover_only_or_uninserted_body_does_not_count(self):
        cover={**self.image,'role':'cover'}
        self.assertTrue(self.check(images=[cover]))
        image={**self.image,'path':'assets/not-in-body.png'}
        self.assertTrue(self.check(images=[image]))

    def test_no_tool_call_or_changed_output_rejected(self):
        for record in [{}, {**self.image['generation_record'],'output_sha256':'other'},
                       {**self.image['generation_record'],'status':'failed'}]:
            self.assertTrue(self.check(images=[{**self.image,'generation_record':record}]))

    def test_no_builtin_requires_answer_and_working_selected_model(self):
        plan=copy.deepcopy(self.plan)
        plan['generation'].update(builtin_available=False,mode='pending')
        self.assertTrue(self.check(plan, []))
        plan['generation'].update(mode='configured',provider='Example',model='chosen-image',
                                  tool='official-provider-api',user_decision='配置 Example chosen-image',setup_status='verified')
        image=copy.deepcopy(self.image)
        image.update(backend='configured',actual_model='chosen-image')
        image['generation_record'].update(tool='official-provider-api',provider='Example',model='chosen-image')
        self.assertEqual(self.check(plan,[image]),[])
        plan['generation']['setup_status']='unverified'
        self.assertTrue(self.check(plan,[image]))

    def test_decline_allows_screenshots_without_ai(self):
        plan=copy.deepcopy(self.plan)
        plan['generation'].update(builtin_available=False,mode='declined',user_decision='不需要配置生图模型')
        self.assertEqual(self.check(plan,[]),[])
        plan['generation'].pop('user_decision')
        self.assertTrue(self.check(plan,[]))

    def test_available_builtin_cannot_silently_opt_out(self):
        plan=copy.deepcopy(self.plan);plan['generation'].update(mode='declined',user_decision='未询问用户')
        self.assertTrue(self.check(plan,[]))

    def test_editor_reviewed_no_gain_exception(self):
        plan=copy.deepcopy(self.plan)
        plan['coverage'][0]['need']='text-only'
        plan['generation']['no_gain_exception']={'status':'editor-reviewed',
            'reason':'本文只解释一个已经用短句和原始结果完整呈现的事实，另加概念图会重复内容并打断阅读。',
            'anchors':[plan['coverage'][0]['anchor']]}
        self.assertEqual(self.check(plan,[]),[])
        plan['generation']['no_gain_exception']['anchors']=['未出现在正文的理由']
        self.assertTrue(self.check(plan,[]))

    def test_old_contract_is_not_retroactively_invalidated(self):
        self.assertEqual(generation_errors({'selection':'content-driven-v1'}, {}, [], []),[])

    def test_third_party_operation_is_a_public_case_not_our_experiment(self):
        from test_mixed_visuals import MixedVisualTests
        fixture=MixedVisualTests();fixture.setUp()
        image=copy.deepcopy(fixture.image)
        image['provenance'].update(kind='public-case',platform='Bilibili',author='公开作者',
                                    post_time='2026-10-04',evidence_scope='第三方公开演示结果，未独立复测')
        self.assertEqual(w.screenshot_errors(Path('.'),image,fixture.sources,fixture.body),[])
        image['provenance'].pop('evidence_scope')
        self.assertTrue(w.screenshot_errors(Path('.'),image,fixture.sources,fixture.body))


if __name__=='__main__': unittest.main()
