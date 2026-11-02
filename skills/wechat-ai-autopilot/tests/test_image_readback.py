from io import BytesIO
from pathlib import Path
import tempfile,unittest,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import image_readback as m
try:
    from PIL import Image,ImageDraw
except ImportError:
    Image=None

@unittest.skipIf(Image is None,'Image matching needs Pillow')
class ImageReadbackTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.folder=Path(self.temp.name)
        self.data=[];self.originals=[]
        for i,color in enumerate(('navy','orange','green')):
            image=Image.new('RGB',(320,180),'white');ImageDraw.Draw(image).rectangle((20+i*20,30,250,140),fill=color)
            out=BytesIO();image.save(out,format='PNG');data=out.getvalue();self.data.append(data)
            file=self.folder/f'{i}.png';file.write_bytes(data);self.originals.append({'path':str(file),'sha256':str(i)})
    def tearDown(self):self.temp.cleanup()
    def test_reversed_upload_dom_order_resolved_by_pixels(self):
        urls=['https://mmbiz.qpic.cn/mmbiz_png/c/0','https://mmbiz.qpic.cn/mmbiz_png/a/0','https://mmbiz.qpic.cn/mmbiz_png/b/0']
        table=dict(zip(urls,[self.data[2],self.data[0],self.data[1]]))
        result=m.match(self.originals,urls,fetch=table.__getitem__)
        self.assertEqual([x['url'] for x in result],[urls[1],urls[2],urls[0]])
    def test_ambiguous_duplicates_rejected(self):
        urls=['https://mmbiz.qpic.cn/a/0','https://mmbiz.qpic.cn/b/0']
        with self.assertRaises(ValueError):m.match(self.originals[:2],urls,fetch=lambda _:self.data[0])
    def test_placeholder_and_credential_urls_rejected(self):
        p=BytesIO();Image.new('RGB',(1,1)).save(p,format='PNG')
        with self.assertRaises(ValueError):m.sample(p.getvalue())
        with self.assertRaises(ValueError):m.match(self.originals[:1],['https://mmbiz.qpic.cn/a/0?token=private'],fetch=lambda _:self.data[0])

if __name__=='__main__':unittest.main()
