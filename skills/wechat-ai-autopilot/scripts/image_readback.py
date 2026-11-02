"""Match public WeChat image pixels to approved originals; never infer file order."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import json, math
from pathlib import Path
from urllib.parse import urlsplit
import urllib.request

def sample(data):
    from PIL import Image
    with Image.open(BytesIO(data)) as original:
        original.load()
        size=original.size
        if size[0]<2 or size[1]<2: raise ValueError('Placeholder is not a loaded article image')
        # Composite transparency onto white, matching normal article display.
        rgba=original.convert('RGBA'); bg=Image.new('RGBA',size,'white'); bg.alpha_composite(rgba)
        rgb=bg.convert('RGB').resize((160,160))
        return size,rgb.tobytes()

def rms(a,b): return math.sqrt(sum((x-y)**2 for x,y in zip(a,b))/len(a))

def match(originals, candidates, fetch=None):
    def get(url):
        parsed=urlsplit(url)
        if parsed.scheme!='https' or parsed.hostname!='mmbiz.qpic.cn' or parsed.username or parsed.password:
            raise ValueError('Only public WeChat material URLs accepted')
        if any(x in parsed.query.lower() for x in ('token','secret','ticket')): raise ValueError('Credential URL rejected')
        if fetch: return fetch(url)
        with urllib.request.urlopen(url,timeout=15) as response:
            if not response.headers.get('Content-Type','').startswith('image/'): raise ValueError('Image response expected')
            data=response.read(24*1024*1024+1)
            if len(data)>24*1024*1024: raise ValueError('Image response too large')
            return data
    if len(set(candidates))!=len(candidates): raise ValueError('Duplicate candidate URLs')
    with ThreadPoolExecutor(max_workers=3) as pool:
        decoded=list(pool.map(lambda url:sample(get(url)),candidates))
    result=[]; used=set()
    for item in originals:
        size, pixels=sample(Path(item['path']).read_bytes())
        ranked=sorted((rms(pixels,p),i,s) for i,(s,p) in enumerate(decoded)
                      if abs((size[0]/size[1])/(s[0]/s[1])-1)<0.015)
        if not ranked or ranked[0][0]>8 or (len(ranked)>1 and ranked[1][0]-ranked[0][0]<3):
            raise ValueError('No unique pixel match; inspect originals and upload outcomes before retrying')
        score,i,remote_size=ranked[0]
        if i in used: raise ValueError('Multiple different originals matched the same image')
        used.add(i); result.append({'sha256':item['sha256'],'url':candidates[i],'pixel_rms':round(score,4),
                                    'original_size':size,'remote_size':remote_size})
    if len(used)!=len(candidates): raise ValueError('Unmatched uploaded image; inspect before retrying')
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--input',required=True,type=Path)
    args=parser.parse_args(); data=json.loads(args.input.read_text(encoding='utf8'))
    try: print(json.dumps({'status':'pass','matches':match(data['originals'],data['candidates'])})); return 0
    except (ValueError,OSError) as exc: print(json.dumps({'status':'needs_review','error':str(exc)})); return 1
if __name__=='__main__': raise SystemExit(main())
