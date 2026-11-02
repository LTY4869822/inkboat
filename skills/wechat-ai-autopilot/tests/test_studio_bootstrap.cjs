'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(path.join(__dirname,'../assets/studio/studio.js'),'utf8');
function boot(readyState){
 const elements=new Map();
 const element=id=>{if(!elements.has(id))elements.set(id,{style:{},disabled:false,textContent:'',value:'',contentDocument:{readyState},contentWindow:{}});return elements.get(id)};
 const sandbox={document:{getElementById:element,querySelectorAll:()=>[]},window:{addEventListener(){}},setTimeout:()=>1,clearTimeout(){},URLSearchParams,location:{search:''},console};
 vm.runInNewContext(source,sandbox);
 return {elements,frame:element('reader'),toast:element('toast')};
}
(async()=>{
 const blank=boot('complete');
 assert.equal(blank.toast.textContent,'','Initial completed about:blank must not report a renderer failure');
 assert.equal(typeof blank.frame.onload,'function','The real child load must remain observable');
 const loading=boot('loading');assert.equal(loading.toast.textContent,'');
 await blank.frame.onload();
 assert.match(blank.toast.textContent,/渲染器未就绪/,'A real load without a renderer must still report the failure');
 console.log(JSON.stringify({passed:true,checks:3,scope:'Initial iframe race and genuine load failure behavior in an isolated JS context; no browser or account'}));
})().catch(e=>{console.error(e);process.exitCode=1});
