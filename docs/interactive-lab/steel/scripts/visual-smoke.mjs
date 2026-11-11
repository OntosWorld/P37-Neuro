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
  const fallback=document.querySelector('.viewer-notice')?.textContent??'';
  return status.includes('Steel physical environment active') ||
    status.includes('Physics error:') ||
    fallback.includes('This scene needs WebGPU');
 },undefined,{timeout:120_000});
 const status=await page.locator('.sim-status').innerText();
 if(!status.includes('Steel physical environment active')){
  throw new Error('Steel physics did not become active: '+status+
    ' / '+await page.locator('.viewer-notice').allInnerTexts());
 }
 await page.waitForFunction(()=>
   Number((document.querySelector('.experiment-ledger strong:last-child')?.textContent??'').length)>0,
   undefined,{timeout:30_000});
 await page.waitForTimeout(1300);
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
 await awaitPhysics(page);
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
 results.status='pass';
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
