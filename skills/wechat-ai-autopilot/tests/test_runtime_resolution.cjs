'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const root=fs.mkdtempSync(path.join(os.tmpdir(),'inkboat-runtime-'));
try{
 const source=path.join(__dirname,'../scripts/runtime.cjs');
 fs.mkdirSync(path.join(root,'src'));fs.copyFileSync(source,path.join(root,'src/runtime.cjs'));
 fs.mkdirSync(path.join(root,'node_modules/playwright'),{recursive:true});
 fs.writeFileSync(path.join(root,'node_modules/playwright/package.json'),'{invalid');
 const configured=path.join(root,'runtime/node_modules/playwright');fs.mkdirSync(configured,{recursive:true});
 fs.writeFileSync(path.join(configured,'index.js'),'module.exports={fixture:"configured-valid-runtime"}');
 fs.mkdirSync(path.join(root,'.wechat-ai'));
 fs.writeFileSync(path.join(root,'.wechat-ai/runtime.json'),JSON.stringify({playwright_module_path:configured}));
 const runtime=require(path.join(root,'src/runtime.cjs'));
 assert.equal(runtime.moduleFor('playwright',root).fixture,'configured-valid-runtime');
 fs.writeFileSync(path.join(root,'.wechat-ai/runtime.json'),JSON.stringify({playwright_module_path:path.join(root,'missing/playwright')}));
 assert.throws(()=>runtime.moduleFor('playwright',root),/Cannot find module/);
 console.log(JSON.stringify({passed:true,checks:2,scope:'Configured runtime priority over an invalid ambient package; explicit invalid runtime is not silently ignored'}));
}finally{
 const safe=path.resolve(root),base=path.resolve(os.tmpdir())+path.sep;
 if(!safe.startsWith(base))throw Error('Unsafe temporary cleanup target');
 fs.rmSync(safe,{recursive:true,force:true});
}
