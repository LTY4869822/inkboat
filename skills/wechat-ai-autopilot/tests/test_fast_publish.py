import base64
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import fast_publish as f
import draft_bridge as d

PIXEL=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aNX8AAAAASUVORK5CYII=')

class FakeClient:
    app_id='test_fixture_appid'
    def __init__(self):self.calls=[];self.uploads=[];self.article=None;self.fail=None
    def raw(self,route,data=None):
        self.calls.append(route)
        if route.endswith('/add') or route.endswith('/update'):
            self.article=data['articles'][0] if route.endswith('/add') else data['articles']
            if self.fail:raise self.fail
            return {'media_id':'api-fixture-id'}
        if route.endswith('/get'):return {'news_item':[self.article]}
        if route.endswith('/batchget'):return {'item':[{'media_id':'api-fixture-id','content':{'news_item':[self.article]}}]}
        return {'total_count':0}
    def upload(self,path,cover=False):
        self.uploads.append(cover)
        return {'media_id':'cover-fixture'} if cover else {'url':'https://mmbiz.qpic.cn/mmbiz_png/fixture/0'}

class FastPublishTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.ws=Path(self.temp.name);self.run=self.ws/'run';self.run.mkdir()
        (self.run/'body.png').write_bytes(PIXEL);(self.run/'cover.png').write_bytes(PIXEL)
        source='<article style="color:green"><p>确认稿中文</p><img src="data:image/png;base64,'+base64.b64encode(PIXEL).decode()+'"></article>'
        self.source=source
        (self.run/'article.html').write_text(source,encoding='utf8')
        self.manifest={'authorization':'TEST FIXTURE ONLY','fingerprint':'fixture','html_sha256':d.w.file_hash(self.run/'article.html'),
          'account':'fixture','account_id':'gh_fixture','title':'测试标题','digest':'测试摘要','cover':'cover.png','cover_sha256':d.w.file_hash(self.run/'cover.png'),
          'images':[{'path':'body.png','sha256':d.w.file_hash(self.run/'body.png')}],'image_occurrences':1,'motion_enabled':False}
        d.w.save(self.run/'draft-transfer.json',self.manifest)
        self.client=FakeClient();key=hashlib.sha256(self.client.app_id.encode()).hexdigest()
        d.w.save(self.ws/'.wechat-ai/api-account.json',{'account_key':key,'account_id':'gh_fixture'})
        self.env=patch.dict(os.environ,{'WECHAT_APP_ID':'test_fixture_appid','WECHAT_APP_SECRET':'test_fixture_secret'})
        self.env.start();self.gate=patch.object(d,'current',return_value='fixture');self.gate.start()
    def tearDown(self):self.gate.stop();self.env.stop();self.temp.cleanup()
    def publish(self):return f.publish_api(self.run,self.ws,self.client)
    def test_new_draft_preserves_html_and_repeat_reuses_draft_and_assets(self):
        result=self.publish();self.assertEqual(result['api_readback_status'],'pass');self.assertFalse(result['published'])
        self.assertEqual(result['status'],'saved_needs_review')
        self.assertEqual(self.client.calls.count('/cgi-bin/draft/add'),1);self.assertEqual(len(self.client.uploads),2)
        self.assertNotIn('need_open_comment',self.client.article)
        self.publish();self.assertEqual(self.client.calls.count('/cgi-bin/draft/add'),1);self.assertEqual(len(self.client.uploads),2)
        self.assertEqual(self.client.article['title'],self.manifest['title'])
    def test_timeout_cannot_create_duplicate_and_readonly_recovery_finds_same_draft(self):
        self.client.fail=ConnectionError('TEST response lost')
        with self.assertRaises(f.UncertainWrite):self.publish()
        with self.assertRaises(f.UncertainWrite):self.publish()
        self.assertEqual(self.client.calls.count('/cgi-bin/draft/add'),1)
        recovered=f.recover(self.run,self.client);self.assertEqual(recovered['media_id'],'api-fixture-id')
        self.client.fail=None;self.publish();self.assertEqual(self.client.calls.count('/cgi-bin/draft/add'),1)
    def test_wrong_account_binding_rejected_before_network(self):
        d.w.save(self.ws/'.wechat-ai/api-account.json',{'account_key':'different','account_id':'gh_fixture'})
        with self.assertRaisesRegex(ValueError,'api_account_not_bound'):self.publish()
        self.assertEqual(self.client.calls,[]);self.assertEqual(self.client.uploads,[])
    def test_oversize_motion_and_existing_web_draft_choose_browser_before_upload(self):
        for change in ('oversize','motion','existing_web'):
            with self.subTest(change=change):
                (self.run/'article.html').write_text(self.source,encoding='utf8')
                m=dict(self.manifest)
                if change=='oversize':
                    (self.run/'article.html').write_text('<p style="color:green">'+'测'*21000+'</p>',encoding='utf8');m['html_sha256']=d.w.file_hash(self.run/'article.html')
                if change=='motion':m['motion_enabled']=True
                if change=='existing_web':m['existing_draft_id']='100000001'
                d.w.save(self.run/'draft-transfer.json',m)
                self.assertEqual(f.plan(self.run)['route'],'browser_dom')
                with self.assertRaises(ValueError):self.publish()
                self.assertEqual(self.client.calls,[])
    def test_current_run_lock_blocks_concurrent_submission(self):
        (self.run/'api-publish.lock').write_text('TEST FIXTURE')
        with self.assertRaisesRegex(ValueError,'lock'):self.publish()
        self.assertEqual(self.client.calls,[])
    def test_explicit_api_rejection_and_cover_readback_difference_do_not_pass(self):
        self.client.fail=f.ApiError(48001)
        with self.assertRaises(f.ApiError):self.publish()
        journal=d.w.read(self.run/'api-publish-journal.json');self.assertEqual(journal['status'],'write_rejected')
        self.client.fail=None;self.publish()
        self.client.article['thumb_media_id']='wrong-cover'
        self.assertEqual(self.publish()['api_readback_status'],'fail')
    def test_tampered_asset_stops_before_draft_write(self):
        (self.run/'body.png').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'image changed'):self.publish()
        self.assertNotIn('/cgi-bin/draft/add',self.client.calls)
    def test_client_errors_do_not_expose_credentials(self):
        client=f.Client('private-app','private-secret')
        with patch.object(f.urllib.request,'urlopen',side_effect=TimeoutError('https://api.weixin.qq.com/?secret=private-secret')):
            with self.assertRaises(ConnectionError) as raised:client.token()
            self.assertNotIn('private-secret',str(raised.exception));self.assertNotIn('https',str(raised.exception))
    def test_id_based_and_experimental_motion_fail_preflight(self):
        broken='<svg aria-label="动效示例：其他"><g><animate attributeName="opacity" values="0;1" dur="1s" begin="root.click" repeatCount="1"></animate></g></svg>'
        self.assertEqual(f.motion_gate(broken)['status'],'blocked')
        good='<svg aria-label="动效示例：结论收束"><g><animate attributeName="opacity" values="0;1" dur="1s" begin="0s;click;touchstart" repeatCount="1"></animate></g></svg>'
        self.assertEqual(f.motion_gate(good)['status'],'pass')
    def test_deliver_never_switches_route_after_uncertain_write(self):
        with patch.object(f,'publish_api',side_effect=f.UncertainWrite('TEST response lost')),patch.object(f.subprocess,'run') as runner:
            with self.assertRaises(f.UncertainWrite):f.deliver(self.run,self.ws)
            runner.assert_not_called()
    def test_existing_api_draft_cannot_be_recreated_in_browser_on_permission_failure(self):
        d.w.save(self.run/'api-draft-receipt.json',{'media_id':'api-fixture-id'})
        with patch.object(f,'publish_api',side_effect=f.ApiError(48001)),patch.object(f.subprocess,'run') as runner:
            with self.assertRaisesRegex(ValueError,'actual web draft identity'):f.deliver(self.run,self.ws)
            runner.assert_not_called()

if __name__=='__main__':unittest.main()
