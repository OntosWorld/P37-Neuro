/**
 * Visual/behavioral smoke test for the actual Steel WebGPU workcell.
 * Capture full-screen screenshots, verify a running GPU scene, and exercise:
 * scene selection, physical object insertion, robot change, camera, source data.
 */
import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import { createHash } from 'node:crypto';
import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

const screenshots=resolve(process.env.STEEL_SCREENSHOTS ?? 'visual-evidence');
mkdirSync(screenshots,{recursive:true});
const address='http://127.0.0.1:4184/';
const server=spawn('npm',['run','preview','--','--host','127.0.0.1','--port','4184','--strictPort'],
  {stdio:'inherit',env:process.env});
const delay=(ms)=>new Promise(resolve=>setTimeout(resolve,ms));
let browser;
let page;
const errors=[];
const results={status:'running',browser:'Chrome / WebGPU',errors,screenshots:[],physics:{}};

async function awaitServer(){
 for(let i=0;i<60;i++){
  try{if((await fetch(address)).ok)return;}catch{ /* server not yet listening */ }
  await delay(500);
 }
 throw new Error('Vite preview server never became ready');
}
async function awaitPhysics(page){
 await page.waitForFunction(()=>{
  const status=document.querySelector('.sim-status')?.textContent??'';
  return status.includes('Steel physical environment active') ||
    status.includes('Steel unavailable:') ||
    Boolean(document.querySelector('.mujoco-fallback'));
 },undefined,{timeout:120_000});
 const status=await page.locator('.sim-status').innerText();
 if(status.includes('Steel physical environment active')){
  await page.waitForTimeout(1200);
  return 'steel';
 }
 const fallback=page.locator('.mujoco-fallback');
 if(await fallback.count()&&await fallback.isVisible())return 'fallback';
 throw new Error('Neither Steel physics nor the fallback rendered: '+status);
}
async function capture(page,name){
 const out=resolve(screenshots,name);
 await page.screenshot({path:out,animations:'disabled',timeout:30_000});
 results.screenshots.push(name);
 const file=await page.locator('.stage-canvas').screenshot();
 return createHash('sha256').update(file).digest('hex');
}
try{
 await awaitServer();
 browser=await chromium.launch({
  channel:'chrome',headless:true,
  args:['--enable-unsafe-webgpu','--disable-dev-shm-usage','--no-sandbox'],
 });
 page=await browser.newPage({viewport:{width:1600,height:1000},deviceScaleFactor:1});
 page.on('pageerror',e=>errors.push('pageerror: '+e.message));
 page.on('console',m=>{if(m.type()==='error')errors.push('console: '+m.text());});
 page.on('response',r=>{if(r.status()>=400)errors.push('HTTP '+r.status()+' '+r.url());});
 await page.goto(address,{waitUntil:'domcontentloaded',timeout:30_000});
 // Match Ontos home visual system from the captured live site.
 const design=await page.evaluate(()=>{
   const style=(selector)=>getComputedStyle(document.querySelector(selector));
   const computed=style('body');
   return {
     body:computed.backgroundColor,
     announcement:document.querySelector('.ontos-announcement')?.getBoundingClientRect().height,
     nav:document.querySelector('.official-nav')?.getBoundingClientRect().height,
     heading:style('.intro h1').fontSize,
     pill:style('.hero-action-primary').borderRadius,
     links:[...document.querySelectorAll('.official-links>a')].map(a=>a.textContent.trim()),
     wordmark:document.querySelector('.official-wordmark')?.textContent?.trim(),
     hasMark:!!document.querySelector('.official-wordmark svg.ontos-mark'),
   };
 });
 if(design.body!=='rgb(5, 5, 5)'||design.announcement!==32||design.nav!==68||
    Number.parseFloat(design.heading)<90||design.pill!=='999px'||
    design.wordmark!=='ONTOS'||!design.hasMark||
    ['Technology','Research','Systems','Company'].some(label=>!design.links.includes(label))){
   throw new Error('Official Ontos layout regression: '+JSON.stringify(design));
 }
 results.design=design;
 // The local site-search must be a working, accessible control.
 await page.getByRole('button',{name:'Search Ontos and P37 links'}).click();
 await page.getByRole('searchbox',{name:'Search page links'}).fill('recorded');
 if(!await page.getByRole('link',{name:/Recorded MimicGen evidence/}).isVisible()){
   throw new Error('Ontos search dialog cannot find the recorded demo');
 }
 await page.keyboard.press('Escape');
 await page.locator('.official-search-dialog').waitFor({state:'hidden'});
 const firstMode=await awaitPhysics(page);
 if(firstMode==='fallback'){
   const copy=await page.locator('.mujoco-fallback-info').innerText();
   if(!copy.includes('MUJOCO') || !copy.includes('Panda')){
     throw new Error('GPU failure did not show the real-robot fallback');
   }
   results.physics.steelGpuVerified=false;
   results.physics.reason=await page.locator('.sim-status').innerText();
   await capture(page,'steel-01-fallback-desktop.png');
   await page.getByRole('button',{name:/Packing station/}).click();
   await awaitPhysics(page);
   if(!await page.locator('.stage-caption').innerText().then(t=>t.includes('Packing station'))){
     throw new Error('Scene selection did not update the controls');
   }
   await page.getByRole('button',{name:/Controls/}).click();
   await page.locator('#robot').selectOption('extended');
   await awaitPhysics(page);
   await capture(page,'steel-02-fallback-with-controls.png');
   const sample=await page.request.get(address+'samples/mimicgen-square-source.json');
   if(!sample.ok())throw new Error('Official source data was not bundled with the viewer');
   const data=await sample.json();
   if(data.publication?.learned_policy_attached!==false || data.traces?.length!==2){
     throw new Error('Missing source evidence or inaccurate policy state');
   }
   await page.setViewportSize({width:390,height:844});
   await page.waitForTimeout(300);
   const menu=page.getByRole('button',{name:/Menu/});
 if(!await menu.isVisible())throw new Error('Official Ontos mobile menu is missing');
 await menu.click();
 if(!await page.getByRole('navigation',{name:'Ontos main navigation'}).getByRole('link',{name:'Technology'}).isVisible())
   throw new Error('Official Ontos mobile navigation did not open');
 await page.keyboard.press('Escape');
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth-innerWidth);
   if(overflow>2)throw new Error('Mobile controls overflow by '+overflow+'px');
   await capture(page,'steel-03-fallback-mobile.png');
   const unexpected=errors.filter(e=>!/Instance dropped in popErrorScope|Device Lost|device lost|A valid external Instance reference no longer exists/.test(e));
   if(unexpected.length)throw new Error('Unexpected browser errors: '+unexpected.slice(0,4).join(' | '));
   results.status='fallback-verified';
   console.log('Hosted Chrome lacks stable WebGPU: fallback/desktop/mobile validated, Steel GPU not qualified.');
 }else{
 const initial=await capture(page,'steel-01-industrial-workcell.png');
 results.physics.initialStatus=await page.locator('.sim-status').innerText();
 results.physics.webGPU=await page.evaluate(()=>Boolean(navigator.gpu));
 const canvas=page.locator('.stage-canvas canvas');
 if(!await canvas.isVisible())throw new Error('The live GPU canvas is not visible');
 const rect=await canvas.boundingBox();
 if(!rect || rect.width<950 || rect.height<480){
  throw new Error('Physics stage is too small: '+JSON.stringify(rect));
 }
 // Scene selection is an actual scene rebuild; do not pretend it is new policy behavior.
 await page.getByRole('button',{name:/Packing station/}).click();
 await awaitPhysics(page);
 const packing=await capture(page,'steel-02-packing-station.png');
 if(initial===packing)throw new Error('Different environments rendered identically');
 await page.getByRole('button',{name:/Inspection bench/}).click();
 await awaitPhysics(page);
 await capture(page,'steel-03-inspection-bench.png');
 // The drawer preserves access to robot morphology and recorded source motion.
 await page.getByRole('button',{name:/Controls/}).click();
 await page.locator('#lab-settings').waitFor({state:'visible'});
 await page.locator('#robot').selectOption('extended');
 await awaitPhysics(page);
 await capture(page,'steel-04-extended-reference-arm.png');
 await page.getByRole('button',{name:/Show genuine MimicGen motion/}).click();
 await page.locator('.source-overlay').waitFor({state:'visible',timeout:30_000});
 if(!await page.locator('.source-overlay').innerText().then(s=>s.includes('EXTERNAL SOURCE TRAJECTORY'))){
  throw new Error('MimicGen path is missing source attribution');
 }
 await capture(page,'steel-05-real-source-overlay.png');
 await page.getByRole('button',{name:/Close experiment controls/}).click();
 await page.getByRole('button',{name:/Top/}).click();
 await capture(page,'steel-06-overhead-camera.png');
 const before=await page.locator('.experiment-ledger strong').nth(1).innerText();
 await page.getByRole('button',{name:/Drop into scene/}).click();
 await page.waitForFunction((value)=>
   document.querySelectorAll('.experiment-ledger strong')[1]?.textContent?.trim()!==value,
   before,{timeout:30_000});
 const after=await page.locator('.experiment-ledger strong').nth(1).innerText();
 if(before===after)throw new Error('Adding a physical object did not update scene count');
 await capture(page,'steel-07-object-insertion.png');
 // Mobile: responsive UI must not create overflow and controls remain available.
 await page.setViewportSize({width:390,height:844});
 await delay(300);
 const overflow=await page.evaluate(()=>document.documentElement.scrollWidth-innerWidth);
 if(overflow>2)throw new Error('Mobile viewport overflows horizontally by '+overflow+'px');
 await capture(page,'steel-08-mobile.png');
 if(errors.length)throw new Error('Browser runtime errors: '+errors.slice(0,5).join(' | '));
 results.status='steel-verified';
 results.physics.steelGpuVerified=true;
 }
 console.log(JSON.stringify(results,null,2));
}catch(error){
 results.status='fail';
 results.failure=String(error);
 if(page){
   try{await page.screenshot({
     path:resolve(screenshots,'steel-00-browser-failure.png'),
     timeout:10_000,
   });results.screenshots.push('steel-00-browser-failure.png');}
   catch(captureError){results.captureError=String(captureError);}
 }
 console.error(JSON.stringify(results,null,2));
 process.exitCode=1;
}finally{
 writeFileSync(resolve(screenshots,'results.json'),JSON.stringify(results,null,2)+'\n');
 await browser?.close();
 server.kill('SIGTERM');
}
