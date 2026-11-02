import sys,tempfile,unittest,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
import workflow as w
from screenshot_annotations import annotate
from PIL import Image

class FramedScreenshotTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.run=Path(self.temp.name);(self.run/'assets').mkdir()
  Image.new('RGB',(400,300),'white').save(self.run/'original.png')
  frames=[{'x':30,'y':40,'width':180,'height':100,'color':'#dc4b3f','stroke_width':4}]
  result=annotate(self.run/'original.png',self.run/'assets/step.png',frames)
  self.sources=[{'id':'S1','kind':'primary','verified':True,'url':'https://author.example/tutorial'}]
  self.record={'kind':'tutorial-step','tutorial_origin':'external','source_ids':['S1'],'page_url':'https://author.example/tutorial','page_title':'实际教程页面','platform':'官方网页','author':'原始作者','post_time':'未知，未假用抓取时间','evidence_scope':'只支持本步操作入口','captured_at':'2026-10-05T20:00:00+08:00','capture_method':'source-image-annotation','capture_sha256':w.file_hash(self.run/'assets/step.png'),'viewport':{'width':400,'height':300},'clip':{'x':0,'y':0,'width':400,'height':300},'original_image_file':'original.png','original_image_sha256':w.file_hash(self.run/'original.png'),'output_pixel_size':{'width':400,'height':300},'pixel_operation':'frame_overlay_only','usage_basis':'原作者公开教学画面，用于本步操作解释','observed_text':'已实际查看本步操作控件和对应状态','review_note':'完整一屏，仅框线提示操作区域，界面保持原样','insert_after':'打开注册入口并核对账号信息。','user_instruction':'用户确认：完整一屏截图，再框出操作区域。','annotations':frames}
 def check(self,record=None):return w.screenshot_errors(self.run,{'path':'assets/step.png','sha256':w.file_hash(self.run/'assets/step.png'),'provenance':record or self.record},self.sources)
 def test_whole_screen_frames_are_allowed(self):self.assertEqual(self.check(),[])
 def test_repainted_text_is_rejected_even_with_new_hash(self):
  im=Image.open(self.run/'assets/step.png');im.putpixel((100,100),(0,0,0));im.save(self.run/'assets/step.png');r=copy.deepcopy(self.record);r['capture_sha256']=w.file_hash(self.run/'assets/step.png');self.assertTrue(self.check(r))
 def test_undeclared_marks_are_rejected(self):
  im=Image.open(self.run/'assets/step.png');im.putpixel((2,2),(255,0,0));im.save(self.run/'assets/step.png');r=copy.deepcopy(self.record);r['capture_sha256']=w.file_hash(self.run/'assets/step.png');self.assertTrue(self.check(r))
 def test_missing_original_preference_or_frames_is_rejected(self):
  for changes in [{'original_image_sha256':'wrong'},{'user_instruction':''},{'annotations':[]},{'pixel_operation':'redraw_ui'}]:self.assertTrue(self.check({**self.record,**changes}))
 def test_resized_and_cropped_source_is_rejected(self):
  for change in [{'viewport':{'width':390,'height':300}},{'clip':{'x':20,'y':0,'width':380,'height':300}},{'output_pixel_size':{'width':200,'height':300}}]:self.assertTrue(self.check({**self.record,**change}))
 def test_frame_outside_original_is_rejected(self):self.assertTrue(self.check({**self.record,'annotations':[{'x':350,'y':30,'width':100,'height':100}]}))
 def test_legacy_fullscreen_without_annotation_still_fails(self):self.assertTrue(self.check({**self.record,'capture_method':'source-image-crop','pixel_operation':'crop_only'}))
 def test_annotator_will_not_overwrite_original(self):
  with self.assertRaises(ValueError):annotate(self.run/'original.png',self.run/'original.png',self.record['annotations'])
if __name__=='__main__':unittest.main()
