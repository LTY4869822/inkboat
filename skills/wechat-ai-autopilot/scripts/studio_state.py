"""Immutable article revisions and human confirmation of exactly one saved version."""
import base64
import json
from pathlib import Path
import re
import shutil
import uuid
import workflow as w
import motion

def root(run):return Path(run)/'studio'
def latest(run):return w.read(root(run)/'latest.json',{})
def paths(run,number):
    if type(number) is not int or number<1:raise ValueError('Need an actual saved revision number')
    return root(run)/'revisions'/('r%04d'%number)

def validate_snapshot(run,snapshot,markdown):
    catalog=w.read(w.ROOT/'assets/preferences.json')['themes']
    if snapshot.get('baseThemeId') not in catalog or not re.fullmatch(r'#[0-9a-fA-F]{6}',snapshot.get('accent','')):
        raise ValueError('Unknown article theme or accent')
    if not isinstance(snapshot.get('font'),str) or len(snapshot['font'])>80:raise ValueError('Invalid font')
    if snapshot.get('themeOverride'):
        from studio import validate_theme_definition
        validate_theme_definition(run,snapshot['themeOverride'])
    value=json.loads(json.dumps(snapshot.get('motion',{})))
    # Anchors are validated against the actual working Markdown, not an old run.
    counts={'h1':len(re.findall(r'(?m)^# ',markdown)),'h2':len(re.findall(r'(?m)^## ',markdown))}
    if type(value.get('enabled')) is not bool or not isinstance(value.get('items'),list) or len(value['items'])>40:
        raise ValueError('Invalid article motion configuration')
    ids=set()
    for item in value['items']:
        a=item.get('anchor',{});key=item.get('id','')
        if item.get('kind') not in motion.KINDS or not re.fullmatch(r'[A-Za-z][A-Za-z0-9]{0,39}',key) or key in ids:
            raise ValueError('Invalid motion identity or type')
        ids.add(key)
        if a.get('type') not in counts or type(a.get('index')) is not int or not 0<=a['index']<counts[a['type']]:raise ValueError('Motion placement points outside the article')
        if not isinstance(item.get('content'),dict) or not item['content'].get('title'):raise ValueError('Motion needs article content')
    if value['enabled'] and not value['items']:raise ValueError('Add a motion or select the static preview')
    return snapshot

def save_version(run,payload):
    run=Path(run).resolve();previous=latest(run)
    if payload.get('base_revision',0)!=previous.get('revision',0):raise ValueError('另一个窗口已保存新版本，请先刷新后再继续，避免覆盖')
    source_hash=w.file_hash(run/'article.md')
    if payload.get('source_hash')!=source_hash:raise ValueError('Agent已更新正文，请刷新工坊加载新稿')
    markdown=payload.get('markdown','');content=payload.get('html','');snapshot=payload.get('snapshot',{})
    if not isinstance(markdown,str) or not markdown.strip() or len(markdown)>200000 or not isinstance(content,str) or not content.strip():raise ValueError('文章或排版为空')
    validate_snapshot(run,snapshot,markdown)
    problems=w.html_check(run,content,source_md=markdown,font_override=snapshot['font'])
    svg=motion.check_html(run,content);problems+=svg.errors
    if not snapshot['motion']['enabled'] and svg.animations:problems.append('已选择静态版，但导出仍含动画，请刷新后重新保存')
    if problems:raise ValueError('; '.join(problems))
    # Retain SVG background bytes separately so draft transfer can upload them.
    embedded=[]
    for src in svg.images:
        if not src.startswith('data:image/'):raise ValueError('保存版本必须使用本地原图')
        data=base64.b64decode(src.split(',',1)[1],validate=True);sha=w.digest(data)
        if any(x[0]==sha for x in embedded):continue
        suffix='jpg' if src.startswith('data:image/jpeg') else 'webp' if src.startswith('data:image/webp') else 'png'
        embedded.append((sha,suffix,data))
    number=previous.get('revision',0)+1;folder=paths(run,number);folder.mkdir(parents=True,exist_ok=False)
    (folder/'article.md').write_text(markdown,encoding='utf8');(folder/'article.html').write_text(content,encoding='utf8')
    image_assets=[]
    for sha,suffix,data in embedded:
        p=folder/('motion-'+sha[:16]+'.'+suffix);p.write_bytes(data);image_assets.append({'path':p.relative_to(run).as_posix(),'sha256':sha})
    record={'schema_version':2,'revision':number,'source_hash':source_hash,'markdown_sha256':w.file_hash(folder/'article.md'),'html_sha256':w.file_hash(folder/'article.html'),'snapshot':snapshot,'motion_assets':image_assets,'content_changed':markdown!=(run/'article.md').read_text(encoding='utf8'),'saved_at':w.now(),'origin':payload.get('origin','user_save'),'decision_origin':None}
    w.save(folder/'record.json',record);w.save(root(run)/'latest.json',record)
    dirty=w.read(root(run)/'dirty.json',{});dirty.update(dirty=False,revision=number,updated_at=w.now());w.save(root(run)/'dirty.json',dirty)
    return {'saved':True,'revision':number,'content_changed':record['content_changed'],'confirmation_text':f'确认，使用已保存的第{number}版，上传公众号草稿箱。','saved_at':record['saved_at']}

def validate_saved(run,number=None):
    last=latest(run);number=number or last.get('revision');folder=paths(run,number);record=w.read(folder/'record.json',{})
    if not record or record['revision']!=last.get('revision'):raise ValueError('已出现更新的保存版本，请按当前版本确认')
    if record.get('snapshot')!=last.get('snapshot'):raise ValueError('保存版的设计快照已改变，请重新保存')
    if record['html_sha256']!=w.file_hash(folder/'article.html') or record['markdown_sha256']!=w.file_hash(folder/'article.md'):raise ValueError('保存版本文件已改变，需重新保存')
    if any(w.file_hash(w.within(run,x['path']))!=x['sha256'] for x in record['motion_assets']):raise ValueError('保存版本的动效图已改变')
    if w.read(root(run)/'dirty.json',{}).get('dirty'):raise ValueError('工坊有未保存修改，请先保存当前文章')
    return record,folder

def adopt(run,revision,decision):
    run=Path(run).resolve()
    if not decision.strip():raise ValueError('确认必须来自当前用户原话，工坊保存不构成传稿授权')
    record,folder=validate_saved(run,revision)
    if w.file_hash(run/'article.md')!=record['markdown_sha256']:
        raise ValueError('工坊正文已修改：Agent需读取保存版本的article.md，更新正文、标题及事实核验后再采用；保留已保存排版，不要求用户再确认一次')
    snapshot=record['snapshot'];brief=w.read(run/'brief.json',{})
    selected_font='custom' if snapshot['font']=='autopilot-custom' else snapshot['font']
    brief.update(theme=snapshot['baseThemeId'],font=selected_font,motion_policy=motion.POLICY,studio_policy='saved-final-v1')
    w.save(run/'brief.json',brief)
    intake=w.read(run/'intake.json',{})
    if intake:intake.update(font=selected_font);w.save(run/'intake.json',intake)
    plan={**snapshot['motion'],'schema_version':1,'policy':motion.POLICY,'article_sha256':w.file_hash(run/'article.md'),'body_sha256':w.file_hash(run/'body.md'),'user_adjusted':True,'created_at':w.now()}
    w.save(run/'motion-plan.json',plan)
    # Do not call layout() here: it would discard the user's custom typography.
    shutil.copyfile(folder/'article.html',run/'article.html')
    html=(folder/'article.html').read_text(encoding='utf8');shell='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><body style="margin:0;background:#fff">'+html+'</body></html>'
    (run/'preview.html').write_text(shell,encoding='utf8');(run/'mobile-preview.html').write_text(shell,encoding='utf8')
    (run/'paste-test.html').write_text('<!doctype html><html><meta charset="utf-8"><div id="paste" contenteditable="true" style="max-width:677px"></div></html>',encoding='utf8')
    shutil.copyfile(w.ROOT/'assets/rich-import-test.html',run/'rich-import-test.html')
    selection={'schema_version':2,'selection_backend':'studio-saved-final','decision_origin':'user','user_decision':decision,'no_pending_edits':True,'theme':snapshot['baseThemeId'],'font':w.font_choice(selected_font,brief.get('custom_font','')),'article_sha256':w.file_hash(run/'article.md'),'body_sha256':w.file_hash(run/'body.md'),'studio_revision':revision,'saved_html_sha256':record['html_sha256'],'snapshot_sha256':w.digest(json.dumps(snapshot,sort_keys=True).encode()),'selected_at':w.now()}
    w.save(run/'layout-selection.json',selection)
    w.save(run/'layout.json',{'selected_theme':snapshot['baseThemeId'],'article_sha256':w.file_hash(run/'article.md'),'preview_sha256':w.file_hash(run/'preview.html'),'brief_sha256':w.file_hash(run/'brief.json'),'recommendation_sha256':w.file_hash(run/'layout-choice.json'),'studio_revision':revision,'warnings':[]})
    w.save(run/'export.json',{'article_sha256':w.file_hash(run/'article.md'),'html_sha256':record['html_sha256'],'backend':'zhouxing-studio-saved-final','studio_revision':revision,'created_at':w.now()})
    w.save(run/'studio-final.json',{'revision':revision,'html_sha256':record['html_sha256'],'markdown_sha256':record['markdown_sha256'],'motion_assets':record['motion_assets'],'snapshot_sha256':selection['snapshot_sha256'],'decision':decision,'approved_at':w.now()})
    return {'adopted':True,'revision':revision,'next':'复核手机预览与真实富文本往返，按新fingerprint审阅、audit后直接入已连接账号草稿；不重建默认排版'}

def selection_current(run):
    selected=w.read(Path(run)/'layout-selection.json',{});final=w.read(Path(run)/'studio-final.json',{})
    if selected.get('selection_backend')!='studio-saved-final':raise ValueError('请确认当前工坊的保存版本，然后采用这版排版')
    record,_=validate_saved(run,selected.get('studio_revision'))
    brief=w.read(Path(run)/'brief.json',{})
    if selected.get('decision_origin')!='user' or not selected.get('user_decision') or not selected.get('no_pending_edits'):raise ValueError('需要用户对保存版的实际确认')
    if selected['saved_html_sha256']!=record['html_sha256'] or final.get('html_sha256')!=w.file_hash(Path(run)/'article.html') or selected.get('article_sha256')!=w.file_hash(Path(run)/'article.md') or selected.get('body_sha256')!=w.file_hash(Path(run)/'body.md') or selected.get('theme')!=brief.get('theme') or selected.get('font')!=w.font_choice(brief.get('font','theme'),brief.get('custom_font','')):raise ValueError('工坊确认已过期，请采用当前保存版本')
    return selected
