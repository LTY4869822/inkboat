/* Dedicated Playwright profile, real UI, targeted HTML clipboard paste.
 * No OS mouse/foreground control, no private API calls, no editor DOM writes.
 * Selector calibration is local account/UI state, not included in share packages.
 */
'use strict';
const fs=require('node:fs/promises'),path=require('node:path'),crypto=require('node:crypto');
const cp=require('node:child_process'),{promisify}=require('node:util');
const execFile=promisify(cp.execFile);
const runtime=require('./runtime.cjs');
function playwright(workspace){return runtime.moduleFor('playwright',workspace);}
async function timed(run,stage,task){
  const script=path.join(__dirname,'operations.py'),python=process.env.PYTHON_EXE||'python';
  const begin=await execFile(python,[script,'start','--run',run,'--stage',stage],{encoding:'utf8',windowsHide:true});
  const token=JSON.parse(begin.stdout);
  try{const result=await task();await execFile(python,[script,'stop','--run',run,'--token',token],{encoding:'utf8',windowsHide:true});return result;}
  catch(error){await execFile(python,[script,'stop','--run',run,'--token',token,'--status','failed'],{encoding:'utf8',windowsHide:true}).catch(()=>{});throw error;}
}
function digest(s){return crypto.createHash('sha256').update(s).digest('hex');}
async function write(file,data){await fs.mkdir(path.dirname(file),{recursive:true});await fs.writeFile(file,JSON.stringify(data,null,2),'utf8');}
async function json(file,fallback={}){try{return JSON.parse(await fs.readFile(file,'utf8'));}catch(e){if(e.code==='ENOENT')return fallback;throw e;}}
async function preflight(run){
  const {stdout}=await execFile(process.env.PYTHON_EXE||'python',[path.join(__dirname,'fast_publish.py'),'plan','--run',run],{encoding:'utf8',windowsHide:true});
  const result=JSON.parse(stdout);if(result.status!=='ready')throw Error('Publication preflight blocked');return result;
}
async function unique(page,selector,label){
  if(!selector)throw Error('Missing calibrated selector: '+label);
  const target=page.locator(selector);
  await target.first().waitFor({state:'visible',timeout:15000});
  if(await target.count()!==1)throw Error('Selector must uniquely identify '+label);
  return target;
}
async function pasteHtml(page,selector,source,config={}){
  const expected=await page.evaluate(html=>{const template=document.createElement('template');template.innerHTML=html;
    template.content.querySelectorAll('[aria-hidden="true"]').forEach(x=>x.remove());
    return (template.content.textContent||'').replace(/\s+/g,'');},source);
  // Only the Clipboard API is written. The actual editor receives a normal paste.
  await page.context().grantPermissions(['clipboard-read','clipboard-write'],{origin:new URL(page.url()).origin});
  await page.evaluate(async html=>{
    await navigator.clipboard.write([new ClipboardItem({'text/html':new Blob([html],{type:'text/html'})})]);
  },source);
  const editor=await unique(page,selector,'body');
  if(await editor.getAttribute('contenteditable')!=='true')throw Error('Body is not an editable element');
  await editor.click();
  await page.keyboard.press(process.platform==='darwin'?'Meta+A':'Control+A');
  await page.keyboard.press(process.platform==='darwin'?'Meta+V':'Control+V');
  // WeChat can hold the paste behind a content-structure dialog. Waiting only
  // for nonempty text times out, or accepts the previous body too soon.
  const continuation=config.paste_continue||'.weui-desktop-dialog:visible button:has-text("继续插入")';
  await page.waitForFunction(({selector,expected})=>{const clone=document.querySelector(selector)?.cloneNode(true);
    clone?.querySelectorAll('[aria-hidden="true"]').forEach(x=>x.remove());
    return (clone?.textContent||'').replace(/\s+/g,'')===expected||
    [...document.querySelectorAll('.weui-desktop-dialog button')].some(x=>x.getClientRects().length&&x.innerText.trim()==='继续插入');},{selector,expected},{timeout:30000});
  const pending=page.locator(continuation);
  if(await pending.count()) await (await unique(page,continuation,'paste structure continuation')).click();
  // The final paragraph is required, not just a title or partially inserted text.
  await page.waitForFunction(({selector,expected})=>{const clone=document.querySelector(selector)?.cloneNode(true);
    if(!clone)return false;clone.querySelectorAll('[aria-hidden="true"]').forEach(x=>x.remove());
    return (clone.textContent||'').replace(/\s+/g,'')===expected;},{selector,expected},{timeout:30000});
  return editor.innerHTML();
}
async function upload(page,selector,filename){
  const input=page.locator(selector);
  if(await input.count()!==1)throw Error('File input must be unique');
  // setInputFiles sends normal file input/change events. No modal or OS chooser.
  await input.setInputFiles(filename,{timeout:20000});
}
async function clickAction(page,selector,label){
  const target=await unique(page,selector,label),text=(await target.innerText()).trim();
  if(/^(发表|发布|群发|发送|声明原创)/.test(text))throw Error('This worker is draft-only; refusing '+label);
  await target.click();
}
async function uiActions(page,actions){
  for(const action of actions||[]){
    if(action.kind!=='click'||typeof action.selector!=='string')throw Error('Only calibrated UI clicks are supported');
    const popup=action.opens_editor?page.context().waitForEvent('page',{timeout:15000}):null;
    await clickAction(page,action.selector,'calibrated '+action.purpose);
    if(popup){page=await popup;await page.waitForURL(u=>u.origin==='https://mp.weixin.qq.com'&&u.pathname==='/cgi-bin/appmsg',{timeout:20000});}
  }
  return page;
}
async function rememberDraft(page,run,manifest,status='editing'){
  const draftId=new URL(page.url()).searchParams.get('appmsgid');
  if(!draftId)return null;
  const file=path.join(run,'browser-publish-journal.json'),old=await json(file);
  if(old.draft_id&&old.draft_id!==draftId)throw Error('Draft identity changed; inspect before proceeding');
  await write(file,{...old,status,draft_id:draftId,fingerprint:manifest.fingerprint,at:new Date().toISOString()});
  return draftId;
}
function publicImages(xs){return [...new Set(xs.filter(x=>x.complete&&x.w>1&&x.src.startsWith('https://mmbiz.qpic.cn/')).map(x=>x.src))];}
async function prepareAssets(page,run,manifest,config){
  const mapping=await json(path.join(run,'wechat-images.json'),[]),bySha=new Map(mapping.map(x=>[x.sha256,x]));
  if(new Set(mapping.map(x=>new URL(x.url).pathname.replace(/\/\d+$/,''))).size!==mapping.length)
    throw Error('Conflicting cached image mappings; verify public pixels before any reupload');
  const missing=[];
  for(const item of manifest.images){
    const filename=path.resolve(run,item.path),real=await fs.realpath(filename),root=await fs.realpath(run);
    if(!real.startsWith(root+path.sep)||digest(await fs.readFile(real))!==item.sha256)throw Error('Approved asset path/hash changed');
    const cached=bySha.get(item.sha256);
    if(cached){
      const u=new URL(cached.url);if(u.origin!=='https://mmbiz.qpic.cn')throw Error('Unexpected image host');
      const response=await page.context().request.get(cached.url,{timeout:12000});
      if(response.ok()&&/^image\//.test(response.headers()['content-type']||''))continue;
      bySha.delete(item.sha256);
    }
    missing.push({...item,path:real});
  }
  const batchSize=Math.max(1,Math.min(6,config.body_image_batch_size||1));
  for(let offset=0;offset<missing.length;offset+=batchSize){
    if(!config.body_image_input)throw Error('Calibrate body image upload input once');
    const batch=missing.slice(offset,offset+batchSize),body=await unique(page,config.body,'body');
    await body.click();await page.keyboard.press(process.platform==='darwin'?'Meta+End':'Control+End');
    await page.keyboard.press('ArrowRight');await page.keyboard.press('Enter');
    const before=await body.locator('img[src]').evaluateAll(xs=>xs.map(x=>x.src));
    await uiActions(page,config.body_image_actions);
    if(batch.length>1&&!(await page.locator(config.body_image_input).getAttribute('multiple')!==null))
      throw Error('Calibrated file input does not support batch uploads');
    await upload(page,config.body_image_input,batch.map(x=>x.path));
    try{await page.waitForFunction(({selector,before,count})=>{
      const imgs=[...document.querySelector(selector).querySelectorAll('img[src]')];
      return new Set(imgs.filter(x=>!before.includes(x.src)&&x.complete&&x.naturalWidth>1&&x.src.startsWith('https://mmbiz.qpic.cn/')).map(x=>x.src)).size>=count;
    },{selector:config.body,before,count:batch.length},{timeout:45000});
    }finally{await rememberDraft(page,run,manifest);}
    const urls=await body.locator('img[src]').evaluateAll((xs,before)=>[...new Set(xs.map(x=>x.src).filter(x=>!before.includes(x)&&x.startsWith('https://mmbiz.qpic.cn/')))],before);
    if(urls.length!==batch.length)throw Error('Image upload returned an ambiguous set; inspect before retry');
    const input=path.join(run,'image-upload-match-input.json');await write(input,{originals:batch,candidates:urls});
    const {stdout}=await execFile(process.env.PYTHON_EXE||'python',[path.join(__dirname,'image_readback.py'),'--input',input],{encoding:'utf8',windowsHide:true});
    const matched=JSON.parse(stdout);if(matched.status!=='pass')throw Error('Public uploaded image pixels did not match originals');
    for(const item of matched.matches)bySha.set(item.sha256,item);
    await write(path.join(run,'wechat-images.json'),[...bySha.values()].filter(x=>manifest.images.some(i=>i.sha256===x.sha256)));
  }
  await execFile(process.env.PYTHON_EXE||'python',[path.join(__dirname,'draft_bridge.py'),'transfer','--run',run,'--image-map',path.join(run,'wechat-images.json')],{encoding:'utf8',windowsHide:true});
}
async function prepareCover(page,run,manifest,config){
  if(config.cover_sha256===manifest.cover_sha256)return;
  if(!config.cover_input||!config.cover_success)throw Error('Calibrate approved cover upload/crop UI once');
  await uiActions(page,config.cover_before);await upload(page,config.cover_input,path.resolve(run,manifest.cover));
  await uiActions(page,config.cover_after);
  await (await unique(page,config.cover_success,'selected cover preview')).waitFor();
  // Presence is not crop proof. Require calibration of both horizontal/square
  // crop areas and the explicitly approved central safety region.
  if(!config.crop_verified)throw Error('Inspect both cover crops before saving; record actual crop verification');
}
async function launch(workspace,headed=false){
  const root=path.join(path.resolve(workspace),'.wechat-ai','browser-profile');
  await fs.mkdir(root,{recursive:true});
  const options={headless:!headed,viewport:{width:1280,height:900}};
  Object.assign(options,runtime.browserOptions(workspace));
  return playwright(workspace).chromium.launchPersistentContext(root,options);
}
async function ensureOfficialStart(page){
  // Persistent cookies do not restore a previously open editor tab. A new
  // headless launch commonly starts at about:blank even after successful scan.
  if(new URL(page.url()).origin!=='https://mp.weixin.qq.com')
    await page.goto('https://mp.weixin.qq.com/',{waitUntil:'domcontentloaded',timeout:20000});
  if(new URL(page.url()).origin!=='https://mp.weixin.qq.com')throw Error('Official account page did not open');
  return page;
}
async function observe(page,config){
  const editor=await unique(page,config.body,'body');
  const title=await unique(page,config.title,'title');
  const getText=async locator=>{const tag=await locator.evaluate(x=>x.tagName);return /INPUT|TEXTAREA/.test(tag)?locator.inputValue():locator.innerText();};
  const images=await editor.locator('img[src]').evaluateAll(xs=>xs.map(x=>({src:x.src,complete:x.complete,w:x.naturalWidth,h:x.naturalHeight})));
  return {title:await getText(title),digest:config.digest?await getText(await unique(page,config.digest,'digest')):'',
    images,html:await editor.innerHTML()};
}
async function verifyRoundtrip(run,observed){
  const file=path.join(run,'browser-reopened.html');await fs.writeFile(file,observed.html,'utf8');
  // Python bridge performs semantic/style/SMIL comparisons. UI observation is separate.
  const code='import sys,json;from pathlib import Path;sys.path.insert(0,sys.argv[1]);import draft_bridge as d;r=Path(sys.argv[2]);print(json.dumps(d.compare((r/"wechat-transfer.html").read_text(encoding="utf8"),(r/"browser-reopened.html").read_text(encoding="utf8"))))';
  const {stdout}=await execFile(process.env.PYTHON_EXE||'python',['-c',code,__dirname,run],{encoding:'utf8',windowsHide:true});
  const checks=JSON.parse(stdout);await write(path.join(run,'browser-roundtrip.json'),checks);return checks;
}
async function push(page,run,config){
  await preflight(run);
  if(!config.account_id||!config.account_marker||!config.account_text)throw Error('Account selector must be calibrated before push');
  const manifest=await json(path.join(run,'draft-transfer.json'));
  if(config.account_id!==manifest.account_id)throw Error('Configured account does not match approved account');
  const marker=await unique(page,config.account_marker,'account marker');
  if(!(await marker.innerText()).includes(config.account_text))throw Error('Actual visible account marker differs');
  const old=await json(path.join(run,'draft-receipt.json'));
  const previousJournal=await json(path.join(run,'browser-publish-journal.json'));
  const existing=old.draft_id||manifest.existing_draft_id||previousJournal.draft_id;
  page=await uiActions(page,config.editor_actions);
  let current=new URL(page.url()).searchParams.get('appmsgid');
  if(existing&&current!==existing)throw Error('Open the existing draft before update; never create a duplicate');
  const journalFile=path.join(run,'browser-publish-journal.json'),journal=await json(journalFile);
  if(journal.status==='save_in_flight')throw Error('Previous save uncertain: inspect and read back before repeating');
  if(!existing&&!current&&!config.draft_list)throw Error('New draft needs a calibrated draft-list readback action');
  if(new URL(page.url()).pathname!=='/cgi-bin/appmsg')throw Error('Actual official editor not open');
  await timed(run,'assets',()=>prepareAssets(page,run,manifest,config));
  current=new URL(page.url()).searchParams.get('appmsgid')||current;
  // transfer refreshed manifest with exact transport hashes.
  Object.assign(manifest,await json(path.join(run,'draft-transfer.json')));
  const source=await fs.readFile(path.join(run,'wechat-transfer.html'),'utf8');
  if(digest(source)!==manifest.transport_html_sha256)throw Error('Transport changed');
  const title=await unique(page,config.title,'title');
  if(await title.getAttribute('contenteditable')==='true'){
    await title.click();await page.keyboard.press(process.platform==='darwin'?'Meta+A':'Control+A');await page.keyboard.insertText(manifest.title);
  }else await title.fill(manifest.title);
  if(config.digest)await (await unique(page,config.digest,'digest')).fill(manifest.digest);
  await timed(run,'paste',()=>pasteHtml(page,config.body,source,config));
  const before=await observe(page,config);
  if(before.title!==manifest.title)throw Error('Title paste/fill did not persist');
  // Cover upload/crop is an explicit calibrated UI sequence. For an unchanged
  // existing draft, reuse it only after the host has observed the same cover hash.
  await prepareCover(page,run,manifest,config);
  await preflight(run);
  await write(journalFile,{status:'save_in_flight',draft_id:current,fingerprint:manifest.fingerprint});
  await timed(run,'save',async()=>{
    await (await unique(page,config.save,'Save draft')).click();
    await (await unique(page,config.save_success||'text=已保存','visible save success')).waitFor();
  });
  current=new URL(page.url()).searchParams.get('appmsgid')||current;
  if(!current){
    await uiActions(page,config.draft_list);
    const entries=page.locator(config.draft_entry).filter({hasText:manifest.title});
    if(await entries.count()!==1)throw Error('Save succeeded but draft identity is ambiguous; inspect list before retry');
    await entries.click();await (await unique(page,config.body,'reopened body')).waitFor();
    current=new URL(page.url()).searchParams.get('appmsgid');
    if(!current)throw Error('No actual draft ID after reopening');
  }
  await write(journalFile,{status:'saved',draft_id:current,fingerprint:manifest.fingerprint});
  await page.reload({waitUntil:'domcontentloaded'});
  if(new URL(page.url()).searchParams.get('appmsgid')!==current)throw Error('Reload opened a different draft');
  const after=await observe(page,config),checks=await timed(run,'readback',()=>verifyRoundtrip(run,after));
  checks.title=after.title===manifest.title;checks.digest=after.digest===manifest.digest;
  checks.images_loaded=after.images.length===manifest.image_occurrences&&after.images.every(x=>x.complete&&x.w>1&&x.src.startsWith('https://mmbiz.qpic.cn/'));
  await write(path.join(run,'browser-observed.json'),after);
  await page.screenshot({path:path.join(run,'browser-draft-proof.png')});
  const passed=Object.entries(checks).every(([k,v])=>['image_count','styled_nodes'].includes(k)||v===true);
  const result={status:'saved_needs_review',draft_id:current,published:false,
    content_readback:passed?'pass':'fail',checks,
    reader_motion:manifest.motion_enabled?'required':'not_applicable',
    scope:'Actual UI save/reload only; invoke fresh official reader verifier before saved_verified'};
  await write(path.join(run,'browser-publish-result.json'),result);return result;
}
async function main(){
  const command=process.argv[2],args={};for(let i=3;i<process.argv.length;i+=2)args[process.argv[i].replace(/^--/,'')]=process.argv[i+1];
  if(!['connect','inspect','upload','paste','push'].includes(command))throw Error('Use connect|inspect|upload|paste|push');
  const workspace=path.resolve(args.workspace||process.cwd()),run=args.run&&path.resolve(args.run);
  let context;try{
    context=await launch(workspace,command==='connect');const pages=context.pages(),page=pages[0]||await context.newPage();
    if(command==='connect'){
      await page.goto('https://mp.weixin.qq.com/',{waitUntil:'domcontentloaded'});
      await page.screenshot({path:path.join(workspace,'.wechat-ai','browser-connect.png')});
      console.log(JSON.stringify({status:'waiting_for_scan',profile:'local dedicated profile; not shared',deadline_seconds:90}));
      try{await page.waitForURL(url=>url.pathname==='/cgi-bin/home',{timeout:90000});}catch{console.log(JSON.stringify({status:'login_required',network_attempted:true}));return;}
      await write(path.join(workspace,'.wechat-ai','browser-connection.json'),{status:'login_observed',at:new Date().toISOString(),scope:'Account ID still requires visible UI verification'});
      console.log(JSON.stringify({status:'login_observed'}));return;
    }
    const config=await json(args.config||path.join(workspace,'.wechat-ai','browser-selectors.json'));
    // Ephemeral URL via environment is not written to config/logs/share files.
    if(process.env.WECHAT_EDITOR_URL){
      const url=new URL(process.env.WECHAT_EDITOR_URL);if(url.origin!=='https://mp.weixin.qq.com')throw Error('Wrong origin');
      await page.goto(url.href,{waitUntil:'domcontentloaded'});
    }
    await ensureOfficialStart(page);
    if(command==='inspect'){
      const info=await page.locator('input,textarea,[contenteditable="true"],input[type="file"]').evaluateAll(xs=>xs.map(x=>({tag:x.tagName,id:x.id,placeholder:x.getAttribute('placeholder'),class:x.className,editable:x.getAttribute('contenteditable'),type:x.getAttribute('type')})));
      await write(path.join(workspace,'.wechat-ai','browser-dom-controls.json'),info);
      console.log(JSON.stringify({status:'inspected',controls:info.length,scope:'Read-only controls; no cookies or session URLs exported'}));
    }else if(command==='upload'){
      await preflight(run);await upload(page,args.selector,args.file);console.log(JSON.stringify({status:'file_input_submitted',scope:'Await actual image URL before recording upload success'}));
    }else if(command==='paste'){
      await preflight(run);const source=await fs.readFile(path.join(run,'wechat-transfer.html'),'utf8');
      await pasteHtml(page,config.body,source);console.log(JSON.stringify({status:'pasted_not_saved'}));
    }else console.log(JSON.stringify(await push(page,run,config)));
  }finally{if(context)await context.close();}
}
module.exports={pasteHtml,upload,observe,unique,push,launch,ensureOfficialStart,prepareAssets,prepareCover,rememberDraft,publicImages,uiActions};
if(require.main===module)main().catch(e=>{console.error(JSON.stringify({status:'blocked',error:e.message.replace(/https?:\/\/\S+/g,'[URL omitted]').replace(/access_token=[^\s&]+/g,'[redacted]')}));process.exitCode=1;});
