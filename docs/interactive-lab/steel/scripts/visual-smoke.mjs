/** Real Chromium acceptance for P37's Steel-style workcell.
 * Software WebGPU may fail on CI; fallback must remain usable and be
 * reported separately from live Steel GPU qualification.
 */
import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

const output=resolve(process.env.STEEL_SCREENSHOTS??'visual-evidence');
mkdirSync(output,{recursive:true});
const address='http://127.0.0.1:4184/';
const server=spawn('npm',['run','preview','--','--host','127.0.0.1','--port','4184','--strictPort'],
 {stdio:'inherit',env:process.env});
const delay=ms=>new Promise(r=>setTimeout(r,ms));
const evidence={status:'running',design:'Steel playground',screenshots:[],errors:[],physics:{}};
let browser,page;
const capture=async(name)=>{
 await page.screenshot({path:resolve(output,name),animations:'disabled',timeout:30000});
 evidence.screenshots.push(name);
};
async function start(){
 for(let n=0;n<55;n++){
  try{if((await fetch(address)).ok)return;}
  catch{/* preview server still booting */}
  await delay(400);
 }
 throw Error('Vite preview did not start');
}
async function mode(){
 await page.waitForFunction(()=>{
  const status=document.querySelector('.sim-status')?.textContent??'';
  return status.includes('Steel physical environment active') ||
   status.includes('Steel unavailable:') ||
   !!document.querySelector('.mujoco-fallback');
 },undefined,{timeout:90_000});
 const status=await page.locator('.sim-status').innerText();
 return status.includes('Steel physical environment active')?'steel':'fallback';
}
async function galleryPick(name){
 await page.getByRole('button',{name:/Scenes/}).first().click();
 await page.locator('.pg-gallery-card').first().waitFor({state:'visible'});
 if(await page.locator('.pg-gallery-card').count()!==3)throw Error('Missing environment gallery cards');
 await page.locator('.pg-gallery-card').filter({hasText:name}).click();
 await page.locator('.pg-gallery').waitFor({state:'hidden'});
 if(!await page.locator('.pg-scene-current').innerText().then(t=>t.includes(name)))
  throw Error('Gallery did not select '+name);
}
try{
 await start();
 browser=await chromium.launch({channel:'chrome',headless:true,
  args:['--no-sandbox','--enable-unsafe-webgpu','--disable-dev-shm-usage']});
 page=await browser.newPage({viewport:{width:1512,height:940},deviceScaleFactor:1});
 page.on('pageerror',error=>evidence.errors.push('page: '+error.message));
 page.on('console',message=>{if(message.type()==='error')evidence.errors.push('console: '+message.text());});
 await page.goto(address,{waitUntil:'domcontentloaded',timeout:30000});
 const layout=await page.evaluate(()=>{
  const root=document.querySelector('.pg-header'),stage=document.querySelector('.stage-canvas');
  const cs=getComputedStyle(root),title=getComputedStyle(document.querySelector('.intro h1'));
  return {bg:cs.backgroundColor,height:Math.round(root.getBoundingClientRect().height),
   font:cs.fontFamily,heading: title.fontSize,
   stageWidth:Math.round(stage.getBoundingClientRect().width),
   hasAccessibleSceneGallery:!!document.querySelector('.pg-menu-button')};
 });
 evidence.layout=layout;
 if(layout.bg!=='rgb(255, 255, 255)'||layout.height!==68 ||
  layout.stageWidth<1200||!layout.hasAccessibleSceneGallery)
  throw Error('Steel reference layout mismatch: '+JSON.stringify(layout));
 const firstMode=await mode();
 evidence.physics.steelGpuVerified=firstMode==='steel';
 evidence.physics.mode=firstMode;
 await capture(firstMode==='steel'?'steel-01-desktop.png':'steel-01-fallback-desktop.png');
 await galleryPick('Packing station');
 await mode();
 await capture('steel-02-packing-selected.png');
 await page.getByRole('button',{name:/Controls/}).click();
 await page.locator('#robot').selectOption('extended');
 await mode();
 await page.locator('#pg-substeps').selectOption('4');
 await page.locator('#pg-iterations').selectOption('12');
 if(await page.locator('#pg-substeps').inputValue()!=='4' ||
    await page.locator('#pg-iterations').inputValue()!=='12')
   throw Error('Steel solver tuning controls failed');
 await mode();
 await capture('steel-03-extended-controls.png');
 const response=await page.request.get(address+'samples/mimicgen-square-source.json');
 if(!response.ok())throw Error('MimicGen source recording is missing');
 const source=await response.json();
 if(source.publication?.source!=='amandlek/mimicgen_datasets' ||
   source.publication?.learned_policy_attached!==false ||source.traces?.length!==2)
  throw Error('Missing source provenance or false policy flag');
 await page.getByRole('button',{name:/Close experiment controls/}).click();
 await page.getByRole('button',{name:/Top/}).click();
 await capture('steel-04-overhead-view.png');
 await page.setViewportSize({width:390,height:844});
 await page.waitForTimeout(450);
 const overflow=await page.evaluate(()=>document.documentElement.scrollWidth-innerWidth);
 if(overflow>2)throw Error('Mobile interface overflows '+overflow+'px');
 if(!await page.getByRole('button',{name:/Scenes/}).first().isVisible())
  throw Error('Mobile scene picker missing');
 await capture('steel-05-mobile.png');
 await galleryPick('Inspection bench');
 await capture('steel-06-mobile-gallery-selection.png');
 if(firstMode==='fallback'){
  const msg=await page.locator('.mujoco-fallback-info').first().innerText();
  if(!msg.includes('MUJOCO'))throw Error('No truthful MuJoCo fallback');
  evidence.status='fallback-verified';
 }else{
  if(!await page.locator('.stage-canvas canvas').first().isVisible())
   throw Error('Live Steel canvas missing');
  evidence.status='steel-verified';
 }
 const unexpected=evidence.errors.filter(e=>
   !/Device Lost|device lost|Instance dropped in popErrorScope|A valid external Instance reference no longer exists|xr-spatial-tracking|WebGPU device/.test(e));
 if(unexpected.length)throw Error('Unexpected browser errors: '+unexpected.slice(0,3).join(' | '));
 console.log(JSON.stringify(evidence,null,2));
}catch(error){
 evidence.status='fail';evidence.failure=String(error);
 if(page){try{await capture('steel-00-failure.png');}catch{/* no browser surface */}}
 console.error(JSON.stringify(evidence,null,2));process.exitCode=1;
}finally{
 writeFileSync(resolve(output,'results.json'),JSON.stringify(evidence,null,2)+'\n');
 await browser?.close();
 server.kill('SIGTERM');
}