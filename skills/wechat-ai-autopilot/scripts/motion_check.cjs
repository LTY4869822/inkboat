/* Rendered-pixel replay gate. One isolated page per card, concurrently; no SVG
 * DOM/timeline writes. Local sanitizer fixtures never count as remote approval.
 */
'use strict';
const fs=require('node:fs/promises'),path=require('node:path'),crypto=require('node:crypto');
const runtime=require('./runtime.cjs');
function pw(){return runtime.moduleFor('playwright');}
function png(){return runtime.moduleFor('pngjs').PNG;}
function difference(a,b){
  const PNG=png(),aa=PNG.sync.read(a),bb=PNG.sync.read(b);
  if(aa.width!==bb.width||aa.height!==bb.height)throw Error('Motion screenshot dimensions changed');
  let changed=0;for(let i=0;i<aa.data.length;i+=4){
    if(Math.abs(aa.data[i]-bb.data[i])+Math.abs(aa.data[i+1]-bb.data[i+1])+Math.abs(aa.data[i+2]-bb.data[i+2])>36)changed++;
  }return {changed_pixels:changed,ratio:changed/(aa.width*aa.height)};
}
const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function visibleFrame(svg,before){
  let buffer,delta;
  for(const delay of [30,80,140]){
    await wait(delay);buffer=await svg.screenshot();delta=difference(before,buffer);
    if(delta.changed_pixels>=25)break;
  }
  return {buffer,delta};
}
async function cardTest(context,url,selector,index,mode,out,scope){
  const page=await context.newPage();try{
    await page.goto(url,{waitUntil:'domcontentloaded',timeout:20000});
    const svg=page.locator(selector).nth(index);await svg.waitFor();await svg.scrollIntoViewIfNeeded();
    const timing=await svg.evaluate(s=>{
      const times=[...s.querySelectorAll('animate,animateTransform')].map(a=>{
        const v=a.getAttribute('dur')||'';if(!/^\d+(?:\.\d+)?(?:ms|s)$/.test(v))throw Error('Unsupported duration');
        if(a.getAttribute('repeatCount')!=='1')throw Error('Unsupported looping variant');
        return parseFloat(v)*(v.endsWith('ms')?1:1000);
      });return {max:Math.max(0,...times),count:times.length,label:s.getAttribute('aria-label')};
    });
    if(!timing.count||timing.max>12000)throw Error('Missing or oversized motion');
    // Duration-driven waits are necessary for after-autoplay replay, not generic
    // sleep between selectors. All cards share elapsed time through concurrency.
    await wait(timing.max+180);
    const before=await svg.screenshot();
    const trigger=async position=>mode==='touch'?svg.tap({position}):svg.click({position});
    await trigger({x:20,y:20});
    const firstFrame=await visibleFrame(svg,before),during=firstFrame.buffer,first=firstFrame.delta;
    // Touch tap timing can run both touchstart/click. restart=whenNotActive avoids reset.
    await wait(timing.max+150);
    const after=await svg.screenshot();
    const width=(await svg.boundingBox()).width;
    await trigger({x:width-20,y:30});
    const secondFrame=await visibleFrame(svg,after),second=secondFrame.buffer,replay=secondFrame.delta;
    await fs.writeFile(path.join(out,`${mode}-${index}-before.png`),before);
    await fs.writeFile(path.join(out,`${mode}-${index}-during.png`),during);
    return {index,label:timing.label,mode,background_replay:first.changed_pixels>=25,
      second_replay:replay.changed_pixels>=25,first_difference:first,second_difference:replay,
      final_readable_unchanged:difference(before,after).changed_pixels<=12,
      scope};
  }finally{await page.close();}
}
async function verify(options){
  const {url,out,selector='svg',scope='local_fixture',parallel=4}=options;
  const origin=new URL(url);
  if(scope==='official_reader'&&(origin.origin!=='https://mp.weixin.qq.com'||origin.pathname!=='/s'))throw Error('Use the freshly saved official /s reader');
  if(scope==='local_fixture'&&!['127.0.0.1','localhost'].includes(origin.hostname))throw Error('Local fixture must be on localhost');
  await fs.mkdir(out,{recursive:true});const started=performance.now();
  const opts={headless:true,args:['--disable-background-timer-throttling','--disable-renderer-backgrounding','--disable-backgrounding-occluded-windows']};Object.assign(opts,runtime.browserOptions());
  const browser=await pw().chromium.launch(opts);
  try{
    const contexts={mouse:await browser.newContext({viewport:{width:390,height:844},reducedMotion:'no-preference'}),
      touch:await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true,reducedMotion:'no-preference'})};
    const probe=await contexts.mouse.newPage();await probe.goto(url,{waitUntil:'domcontentloaded'});
    await probe.locator(selector).first().waitFor();const count=await probe.locator(selector).count();await probe.close();
    if(count<1||count>12)throw Error('Unexpected card count');
    const tasks=[];for(const mode of ['mouse','touch'])for(let i=0;i<count;i++)tasks.push({mode,index:i});
    const results=[];let cursor=0;
    await Promise.all(Array.from({length:Math.min(parallel,tasks.length)},async()=>{
      while(cursor<tasks.length){const t=tasks[cursor++];results.push(await cardTest(contexts[t.mode],url,selector,t.index,t.mode,out,scope));}
    }));
    results.sort((a,b)=>a.mode.localeCompare(b.mode)||a.index-b.index);
    const passed=results.every(x=>x.background_replay&&x.second_replay&&x.final_readable_unchanged);
    const report={schema_version:1,status:passed?'pass':'fail',scope,cards:count,
      elapsed_seconds:Math.round((performance.now()-started)/10)/100,parallel,results,
      reader:scope==='official_reader'?{status:passed?'pass':'fail',auto_finished_before_click:true,
        cards:Array.from({length:count},(_,i)=>({index:i,
          background_replay:results.filter(x=>x.index===i).every(x=>x.background_replay),
          second_replay:results.filter(x=>x.index===i).every(x=>x.second_replay)}))}:null,
      limits:['Physical WeChat client and dark mode not tested','Screenshots prove visible changes, not information correctness; text/design review still required']};
    await fs.writeFile(path.join(out,'motion-check.json'),JSON.stringify(report,null,2));return report;
  }finally{await browser.close();}
}
module.exports={verify,difference};
if(require.main===module)(async()=>{
  const args={};for(let i=2;i<process.argv.length;i+=2)args[process.argv[i].replace(/^--/,'')]=process.argv[i+1];
  const url=(await fs.readFile(args['url-file'],'utf8')).trim();
  try{const r=await verify({url,out:path.resolve(args.out),selector:args.selector||'#js_content svg',scope:'official_reader',parallel:4});
    console.log(JSON.stringify({status:r.status,scope:r.scope,cards:r.cards,elapsed_seconds:r.elapsed_seconds}));if(r.status!=='pass')process.exitCode=1;
  }finally{await fs.rm(args['url-file'],{force:true});}
})().catch(e=>{console.error(JSON.stringify({status:'fail',error:e.message.replace(/https?:\/\/\S+/g,'[URL omitted]')}));process.exitCode=1;});
