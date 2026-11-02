"""Content-bound SVG motion planning and validation; no browser or publishing."""
import argparse
import base64
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil
import workflow as w

POLICY = 'article-motion-v1'
KINDS = ('cinema','fold','carousel','constellation','ink','wipe','chapter','highlight','quote','steps','timeline','comparison','focus','panorama','caption','path','notebook','conclusion','cards','reveal')
VERIFIED_KINDS = ('quote','steps','comparison','conclusion')

def plan(run, force=False):
    run = Path(run)
    article = (run/'article.md').read_text(encoding='utf8')
    existing = w.read(run/'motion-plan.json', {})
    if existing and not force:
        if existing.get('article_sha256') != w.file_hash(run/'article.md'):
            raise ValueError('Motion plan is stale; read the changed article and rebuild the plan')
        validate(run, existing)
        return existing
    headings = re.findall(r'(?m)^## (.+)$', article)
    paragraphs = [w.plain_md(p) for p in article.split('\n\n') if p.strip() and not p.lstrip().startswith(('#','!','|','```','>','- '))]
    items = []
    if headings:
        items.append({'id':'opening','kind':'quote','anchor':{'type':'h2','index':0},'content':{'title':headings[0],'label':'从这里开始'},'reason':'用已验证的显影卡引出首节问题，正文仍保持完整可读'})
    else:
        title = re.search(r'(?m)^# (.+)$', article)
        items.append({'id':'opening','kind':'quote','anchor':{'type':'h1','index':0},'content':{'title':title.group(1) if title else '正文','label':'开始阅读'},'reason':'短稿用已验证的显影卡引出文章问题'})
    if len(headings) >= 3:
        index = max(1, len(headings)//2)
        items.append({'id':'middle','kind':'conclusion','anchor':{'type':'h2','index':index},'content':{'title':headings[index],'label':'读到这里，留意这个问题'},'reason':'用已验证的分层显影强调中段已有问题，不编造新结论'})
    if len(headings) >= 5:
        items.append({'id':'closing','kind':'conclusion','anchor':{'type':'h2','index':len(headings)-1},'content':{'title':headings[-1],'label':'把思考带走'},'reason':'结尾用一次短暂显影提醒读者回到本节主题'})
    result={'schema_version':1,'policy':POLICY,'article_sha256':w.file_hash(run/'article.md'),'body_sha256':w.file_hash(run/'body.md'),'enabled':True,'items':items,'basis':'自动起点；Agent需通读后按文章价值调整组件、位置及数量','density_review':'使用局部短动效，图片、教程步骤与完整文字不依赖交互才能看到','created_at':w.now()}
    validate(run,result)
    w.save(run/'motion-plan.json',result)
    return result

def validate(run, value):
    if type(value.get('enabled')) is not bool or not isinstance(value.get('items'),list):
        raise ValueError('Motion plan needs enabled and items')
    if value['enabled'] and not value['items']:
        raise ValueError('New articles require at least one content-fit motion design')
    ids=set()
    source=(Path(run)/'article.md').read_text(encoding='utf8')
    counts={'h1':len(re.findall(r'(?m)^# ',source)),'h2':len(re.findall(r'(?m)^## ',source))}
    for item in value['items']:
        key=item.get('id','')
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9]{0,39}',key) or key in ids:
            raise ValueError('Motion placement IDs must be unique alphanumeric identifiers')
        ids.add(key)
        anchor=item.get('anchor',{});content=item.get('content',{})
        if item.get('kind') not in KINDS or anchor.get('type') not in counts or type(anchor.get('index')) is not int or not 0<=anchor['index']<counts[anchor['type']]:
            raise ValueError('Motion type or article placement is invalid')
        if not isinstance(content,dict) or not content.get('title') or len(json.dumps(content))>12000 or len(item.get('reason',''))<6:
            raise ValueError('Motion needs a content-specific title and purpose')
    if value.get('article_sha256')!=w.file_hash(Path(run)/'article.md'):
        raise ValueError('Motion content changed after planning')
    return value

def install(run, brief, output, document):
    """Augment the real Zhouxing page without editing its installed renderer."""
    run=Path(run).resolve();output=Path(output).resolve()
    motion=plan(run)
    folder=run/'studio-assets';folder.mkdir(exist_ok=True)
    source=w.ROOT/'assets/studio'
    for filename in ('motion-designs.js','bridge.js'):
        shutil.copy2(source/filename,folder/filename)
    # Selected article images may be used by a motion, but they are never
    # recoloured, reconstructed or substituted for evidence screenshots.
    image_assets={}
    for name in ('cinema','ink'):
        p=source/'backgrounds'/(name+'.png')
        image_assets[name]='data:image/png;base64,'+base64.b64encode(p.read_bytes()).decode()
    for item in motion['items']:
        relative=item.get('content',{}).get('image_path')
        if relative:
            image=w.within(run,relative)
            if not image.is_file() or image.suffix.lower() not in ('.png','.jpg','.jpeg','.webp'):
                raise ValueError('Motion image must be a real local article asset')
            mime='jpeg' if image.suffix.lower() in ('.jpg','.jpeg') else image.suffix.lower()[1:]
            item['content']['image']='data:image/'+mime+';base64,'+base64.b64encode(image.read_bytes()).decode()
    context={'plan':motion,'article_sha256':w.file_hash(run/'article.md')}
    inline=lambda v:json.dumps(v,ensure_ascii=False).replace('<','\\u003c')
    # Local file previews work too: dependencies are embedded rather than fetched.
    module=(source/'motion-designs.js').read_text(encoding='utf8')+'\n'+(source/'motion-compat.js').read_text(encoding='utf8')
    module='window.MotionAssetURLs='+inline(image_assets)+';\n'+module
    module_path=folder/'motion-designs.js'
    if not module_path.is_file() or module_path.read_text(encoding='utf8')!=module:
        module_path.write_text(module,encoding='utf8')
    relative=os.path.relpath(module_path,output.parent).replace('\\','/')
    scripts='<script>window.StudioContext='+inline(context)+';</script><script src="'+relative+'"></script>'
    document=document.replace('</head>',scripts+'</head>',1)
    marker="    document.querySelectorAll('select').forEach(enhanceSelect);"
    if document.count(marker)!=1:
        raise ValueError('Zhouxing studio hook changed; inspect the installed renderer')
    document=document.replace(marker,(source/'bridge.js').read_text(encoding='utf8')+'\n'+marker,1)
    return document

class SVGCheck(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.ids=[];self.refs=[];self.images=[];self.animations=[];self.svg=0;self.errors=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='svg':self.svg+=1
        if a.get('id'):self.ids.append(a['id'])
        if tag in ('animate','animatetransform','animatemotion','set'):
            self.animations.append((tag,{k:v for k,v in a.items() if k not in ('style',)}))
            self.refs.extend(re.findall(r'([A-Za-z][A-Za-z0-9]*)\.click',a.get('begin','')))
        for key in ('fill','clip-path','mask','stroke','style'):
            self.refs.extend(re.findall(r'url\([\"\x27]?#([^\)\"\x27]+)',a.get(key,'')))
        if tag=='image':
            value=a.get('xlink:href',a.get('href',''));self.images.append(value)
            if not value.startswith(('data:image/png;base64,','data:image/jpeg;base64,','data:image/webp;base64,','https://mmbiz.qpic.cn/')):
                self.errors.append('SVG image must be an embedded approved image or actual WeChat URL')
        if tag in ('foreignobject','use') or any(k.lower().startswith('on') for k in a):self.errors.append('SVG contains unsupported active content')
    handle_startendtag=handle_starttag

def check_html(run, content):
    p=SVGCheck();p.feed(content)
    if len(p.ids)!=len(set(p.ids)):p.errors.append('SVG IDs collide')
    if any(ref not in p.ids for ref in p.refs):p.errors.append('SVG event/paint references are broken')
    return p

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',required=True,type=Path);parser.add_argument('--rebuild',action='store_true');args=parser.parse_args();result=plan(args.run,args.rebuild);print(json.dumps({'planned':True,'designs':len(result['items']),'library':len(KINDS),'path':str(args.run/'motion-plan.json')},ensure_ascii=False))

if __name__=='__main__':main()
