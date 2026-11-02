import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import draft_bridge as bridge
import motion_transport as transport
from motion import check_html

def wrap(label,body,height=450):
    return f'<svg id="fixtureRoot" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 {height}" aria-label="动效示例：{label}">{body}</svg>'

def fade():
    return '<animate attributeName="opacity" values="0;1;1" keyTimes="0;.4;1" dur="5s" begin="0s;fixtureRoot.click" repeatCount="1" fill="freeze"></animate>'

def shift(values):
    return f'<animateTransform attributeName="transform" type="translate" values="{values}" keyTimes="0;.4;1" dur="6s" begin="0s;fixtureRoot.click" repeatCount="1" fill="freeze"></animateTransform>'

class MotionTransportTests(unittest.TestCase):
    def test_id_stripping_does_not_break_supported_cards(self):
        quote=wrap('引文显影','<rect width="720" height="450" fill="#f3efe3"></rect><defs><clipPath id="fixtureQuote"><rect x="102" y="100" width="552" height="235"></rect></clipPath></defs><g clip-path="url(#fixtureQuote)"><text x="105" y="178">原始结论</text></g>')
        line='<path pathLength="100" stroke-dashoffset="0"><animate attributeName="stroke-dashoffset" values="100;0;0" keyTimes="0;.7;1" dur="8s" begin="0s;fixtureRoot.click" repeatCount="1" fill="freeze"></animate></path>'
        # Real quote has its width animation inside clipPath.
        quote=quote.replace('</rect></clipPath>',fade()+'</rect></clipPath>')
        steps=wrap('步骤接力',line+''.join(f'<circle cx="{x}" cy="202" r="38" opacity=".14">{fade()}</circle><text>步骤</text>' for x in (85,357.5,630)))
        comparison=wrap('双栏对照','<g>'+shift('-350 0;0 0;0 0')+'<text>左侧观点</text></g><g>'+shift('350 0;0 0;0 0')+'<text>右侧观点</text></g>')
        conclusion=wrap('结论收束','<g opacity="1">'+fade()+'<text>读者所得</text></g>',300)
        for source in (quote,steps,comparison,conclusion):
            with self.subTest(source=source[:110]):
                result,report=transport.adapt(source)
                self.assertTrue(report[0]['converted'])
                sanitized=re.sub(r'\s+id="[^"]*"','',result)
                self.assertEqual(check_html(Path('.'),sanitized).errors,[])
                self.assertNotIn('url(#',result)
                self.assertNotIn('fixtureRoot.click',result)
                self.assertEqual(re.findall(r'<text\b[^>]*>([^<]*)</text>',source),re.findall(r'<text\b[^>]*>([^<]*)</text>',result))
                self.assertTrue(bridge.compare(result,result)['motion_structure'])
                self.assertFalse(bridge.compare(result,result.replace('0s;click;touchstart','0s',1))['motion_structure'])
                self.assertEqual(transport.adapt(result)[0],result)

    def test_unknown_and_static_cards_are_not_rewritten(self):
        # Unknown HTML SVG may have an undeclared legacy xlink namespace.
        unknown='<svg id="clip"><image xlink:href="test"></image></svg>'
        static=wrap('结论收束','<g><text>静态全文</text></g>',300)
        for source in (unknown,static):
            result,report=transport.adapt(source)
            self.assertEqual(result,source)
            self.assertFalse(report[0]['converted'])

    def test_tampered_transport_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            run=Path(temp)
            (run/'article.html').write_text('<p>确认稿</p>',encoding='utf8')
            (run/'wechat-transfer.html').write_text('<p>确认稿</p>',encoding='utf8')
            (run/'wechat-motion-transport.json').write_text('{}',encoding='utf8')
            manifest={'authorization':'TEST ONLY','fingerprint':'fixture','html_sha256':bridge.w.file_hash(run/'article.html'),'transport_html_sha256':bridge.w.file_hash(run/'wechat-transfer.html'),'motion_transport_sha256':bridge.w.file_hash(run/'wechat-motion-transport.json')}
            bridge.w.save(run/'draft-transfer.json',manifest)
            with patch.object(bridge,'current',return_value='fixture'):
                self.assertEqual(bridge.locked(run)['fingerprint'],'fixture')
                (run/'wechat-transfer.html').write_text('<p>篡改稿</p>',encoding='utf8')
                with self.assertRaisesRegex(ValueError,'transport HTML'):
                    bridge.locked(run)
                (run/'wechat-transfer.html').write_text('<p>确认稿</p>',encoding='utf8')
                (run/'wechat-motion-transport.json').write_text('{"changed":true}',encoding='utf8')
                with self.assertRaisesRegex(ValueError,'transport record'):
                    bridge.locked(run)

    def test_reader_gate_rejects_playback_note_without_actual_replay(self):
        with tempfile.TemporaryDirectory() as temp:
            run=Path(temp)
            card=transport.adapt(wrap('结论收束','<g opacity="1">'+fade()+'<text>读者所得</text></g>',300))[0]
            source='<article style="color:green">'+card*4+'</article>'
            (run/'wechat-transfer.html').write_text(source,encoding='utf8')
            (run/'remote.html').write_text(source,encoding='utf8')
            (run/'proof.png').write_bytes(b'TEST FIXTURE ONLY')
            manifest={'account':'fixture','title':'fixture','digest':'fixture','fingerprint':'fixture','motion_enabled':True,'motion_reader_gate':True,'motion_card_count':4}
            observed={'title':'fixture','digest':'fixture','images':[],'cover':'fixture','motion':{'status':'pass','note':'TEST FIXTURE ONLY: values changed in editor'}}
            with patch.object(bridge,'locked',return_value=manifest):
                bridge.w.save(run/'observed.json',observed)
                receipt=bridge.verify(run,'fixture','fixture','observed.json','remote.html','proof.png','TEST FIXTURE ONLY')
                self.assertFalse(receipt['checks']['motion_reader_replay'])
                self.assertEqual(receipt['status'],'saved_needs_review')
                observed['motion']['reader']={'status':'pass','auto_finished_before_click':True,'cards':[{'background_replay':True,'second_replay':True}]*4}
                bridge.w.save(run/'observed.json',observed)
                receipt=bridge.verify(run,'fixture','fixture','observed.json','remote.html','proof.png','TEST FIXTURE ONLY')
                self.assertTrue(receipt['checks']['motion_reader_replay'])
                observed['motion']['reader']['cards'][0]={'background_replay':True,'second_replay':False}
                bridge.w.save(run/'observed.json',observed)
                receipt=bridge.verify(run,'fixture','fixture','observed.json','remote.html','proof.png','TEST FIXTURE ONLY')
                self.assertFalse(receipt['checks']['motion_reader_replay'])

if __name__=='__main__':
    unittest.main()
