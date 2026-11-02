"""Build a real local InkBoat workshop from an explicitly fictional demo article."""
import argparse,hashlib,json,shutil,subprocess,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SKILL=ROOT/'skills/wechat-ai-autopilot'
sys.path.insert(0,str(SKILL/'scripts'))
import workflow as w

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=Path('.inkboat-demo'))
    p.add_argument('--zhouxing',type=Path,help='Optional installed zhouxing-paiban-wx directory')
    p.add_argument('--serve',action='store_true')
    p.add_argument('--port',type=int,default=0)
    a=p.parse_args();run=a.output.resolve()
    if (run/'article.md').exists():p.error('Output already contains an article. Choose a new directory to preserve your edits.')
    profile={'skills':{}}
    if a.zhouxing:profile['skills']['zhouxing-paiban-wx']=str(a.zhouxing.expanduser().resolve())
    if not w.skill_paths(run,profile).get('zhouxing-paiban-wx'):p.error('Install zhouxing-paiban-wx first, or pass --zhouxing PATH. See docs/INSTALL.md.')
    run.mkdir(parents=True,exist_ok=True)
    body=(ROOT/'examples/demo-article.md').read_text(encoding='utf-8')
    title='从灵感到成稿，把精力留给真正值得写的内容'
    (run/'body.md').write_text(body,encoding='utf-8')
    (run/'article.md').write_text('# '+title+'\n\n'+body,encoding='utf-8')
    (run/'assets').mkdir(exist_ok=True)
    image=run/'assets/editorial-ink.png'
    shutil.copy2(SKILL/'assets/studio/backgrounds/ink.png',image)
    w.save(run/'brief.json',dict(schema_version=1,workspace=str(run),type='news',topic=title,theme='green-white-clean',font='system',profile=profile,motion_policy='article-motion-v1',studio_policy='saved-final-v1',presentation={'citations':'internal','image_captions':'none'},demo_only=True))
    w.save(run/'article-meta.json',{'title':title,'digest':'公开演示稿：查看真实周行排版、工坊切换与静态开关。'})
    w.save(run/'images.json',[{'path':'assets/editorial-ink.png','role':'body','backend':'native','sha256':hashlib.sha256(image.read_bytes()).hexdigest(),'purpose':'包内原创水墨背景，仅演示视觉，不充当事实证据'}])
    motion={'schema_version':1,'policy':'article-motion-v1','article_sha256':w.file_hash(run/'article.md'),'body_sha256':w.file_hash(run/'body.md'),'enabled':True,'basis':'原创公开演示稿的四节内容','density_review':'仅两处局部演示，全文静态可读','items':[
        {'id':'readerQuestion','kind':'quote','anchor':{'type':'h2','index':0},'content':{'title':'先想清楚，读者为什么要读','label':'把问题放在前面'},'reason':'强调本节已经提出的读者问题，不引入事实主张'},
        {'id':'finalCheck','kind':'conclusion','anchor':{'type':'h2','index':3},'content':{'title':'保存之后，再确认交稿','label':'让每一次修改都有据可循','lines':['读者能理解','成稿可核对']},'reason':'在末节展示当前保存与确认的区别，正文不依赖动效'}]}
    w.save(run/'motion-plan.json',motion)
    w.recommend_layout(run,'green-white-clean','公开演示稿推荐绿白清简，突出文字、表格及真实工坊控件。演示不构成用户定稿确认。')
    w.layout(run);result=w.layout_previews(run)
    w.save(run/'demo-status.json',{'demo_only':True,'publication_authorized':False,'quality_passed':False,'reason':'只验证本地预览；不是完成研究、事实与发布审核的文章。'})
    print(json.dumps({'demo':str(run),'gallery':result['gallery'],'studio':result['studio'],'themes':result['variants'],'demo_only':True},ensure_ascii=False),flush=True)
    if a.serve:subprocess.run([sys.executable,'-u',str(SKILL/'scripts/studio.py'),'serve','--run',str(run),'--port',str(a.port)],check=True)
    return 0
if __name__=='__main__':raise SystemExit(main())
