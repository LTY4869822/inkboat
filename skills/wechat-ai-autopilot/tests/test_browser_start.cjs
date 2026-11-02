'use strict';
const assert=require('node:assert/strict');
const {ensureOfficialStart}=require('../scripts/browser_draft.cjs');
(async()=>{
 let current='about:blank',calls=[];
 const page={url:()=>current,goto:async(url,options)=>{calls.push({url,options});current='https://mp.weixin.qq.com/cgi-bin/home';}};
 await ensureOfficialStart(page);assert.equal(calls.length,1);assert.equal(calls[0].url,'https://mp.weixin.qq.com/');
 await ensureOfficialStart(page);assert.equal(calls.length,1);
 current='about:blank';page.goto=async()=>{current='https://different.example/';};
 await assert.rejects(ensureOfficialStart(page),/Official account page/);
 console.log(JSON.stringify({status:'pass',checks:3,scope:'local fake page navigation; no account or network'}));
})().catch(e=>{console.error(e.message);process.exitCode=1;});
