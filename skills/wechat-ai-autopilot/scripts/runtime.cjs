'use strict';
const fs=require('node:fs'),path=require('node:path');
function config(workspace=process.cwd()){
  try{return JSON.parse(fs.readFileSync(path.join(workspace,'.wechat-ai/runtime.json'),'utf8'));}
  catch(e){if(e.code==='ENOENT')return {};throw e;}
}
function moduleFor(name,workspace){
  const root=process.env.PLAYWRIGHT_MODULE_PATH||config(workspace).playwright_module_path;
  if(root)return require(path.join(path.dirname(root),name));
  try{return require(name);}catch(e){if(e.code!=='MODULE_NOT_FOUND')throw e;}
  throw Error(name+' missing; run onboard.py doctor and configure the local runtime');
}
function browserOptions(workspace){
  const executable=process.env.WECHAT_BROWSER_EXECUTABLE||config(workspace).browser_executable;
  if(executable)return {executablePath:executable};
  try{const bundled=moduleFor('playwright',workspace).chromium.executablePath();if(fs.existsSync(bundled))return {executablePath:bundled};}catch{}
  return {channel:'chrome'};
}
module.exports={config,moduleFor,browserOptions};
