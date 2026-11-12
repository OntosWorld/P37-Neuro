/**
 * Real desktop/mobile visual QA against Skild's Steel playground.
 *
 * Captures both public reference screenshots and the local P37 WebGPU scene.
 * A "steel-running" result requires real WebGPU initialization, advancing
 * physics time, nonblank rendered canvas, and exercised scene/object controls.
 *
 * This test never substitutes a fallback screenshot for a live physics result.
 */
import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { PNG } from 'pngjs';

const destination=resolve(process.env.P37_VISUAL_OUTPUT??'visual-evidence');
mkdirSync(destination,{recursive:true});
const host='http://127.0.0.1:4188/';
const upstream='https://www.skild.ai/demos/steel';
const results={reference:{},p37:{},webgpu:{status:'not-tested'},errors:[],screenshots:[]};
const server=spawn('npm',['run','preview','--','--host','127.0.0.1','--port','4188','--strictPort'],{
  stdio:'inherit',
  env:process.env,
});
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const timeout=async (fn,tries=90,delay=500)=>{
  for(let i=0;i<tries;i++){try{if(await fn())return;}catch{}await wait(delay);}
  throw new Error('Local P37 build did not become available');
};
let browser=null;
let page=null;
const record=(name,image)=>{writeFileSync(resolve(destination,name),image);results.screenshots.push(name)};
const capture=async (page,name,fullPage=false)=>{
  const buffer=await page.screenshot({fullPage,animations:'disabled',timeout:45000});
  record(name,buffer);
  return buffer;
};
function paletteMetrics(image){
  const png=PNG.sync.read(image);
  const colors=new Set();
  let brightness=0,count=0,brightPixels=0;
  const xStart=Math.floor(png.width*.18),xEnd=Math.floor(png.width*.85);
  const yStart=Math.floor(png.height*.15),yEnd=Math.floor(png.height*.86);
  for(let y=yStart;y<yEnd;y+=5)for(let x=xStart;x<xEnd;x+=5){
    const k=(png.width*y+x)*4;
    const r=png.data[k],g=png.data[k+1],b=png.data[k+2];
    colors.add(((r>>4)<<8)|((g>>4)<<4)|(b>>4));
    const lum=.2126*r+.7152*g+.0722*b;brightness+=lum;count++;
    if(lum>78)brightPixels++;
  }
  return {width:png.width,height:png.height,quantizedColors:colors.size,
    averageBrightness:Math.round(10*brightness/Math.max(1,count))/10,
    illuminatedFraction:Math.round(1000*brightPixels/Math.max(1,count))/1000};
}
async function getReference(){
  const result={url:upstream};
  const p=await browser.newPage({viewport:{width:1512,height:982},deviceScaleFactor:1});
  try{
    const response=await p.goto(upstream,{waitUntil:'domcontentloaded',timeout:45000});
    result.httpStatus=response?.status();
    await p.waitForTimeout(2500);
    result.layout=await p.evaluate(()=>{
      const heading=document.querySelector('h1');
      const hero=heading?.getBoundingClientRect();
      return {title:document.title,heading:heading?.innerText,
        h1Size:heading?Number.parseFloat(getComputedStyle(heading).fontSize):null,
        headlineWidth:hero?.width,
        background:getComputedStyle(document.body).backgroundColor,
        viewport:innerWidth,documentWidth:document.documentElement.scrollWidth};
    });
    const image=await capture(p,'reference-skild-desktop.png');
    result.desktop=paletteMetrics(image);
    await p.setViewportSize({width:390,height:844});
    await p.waitForTimeout(950);
    const mobile=await capture(p,'reference-skild-mobile.png');
    result.mobile=paletteMetrics(mobile);
    result.mobileDocumentWidth=await p.evaluate(()=>document.documentElement.scrollWidth);
  }catch(err){result.error=String(err);results.errors.push('Skild screenshot: '+String(err));}
  finally{await p.close()}
  return result;
}
async function webgpuAdapter(p){
  return await p.evaluate(async()=>{
    const secure=window.isSecureContext;
    const present=Boolean(navigator.gpu);
    if(!present)return {secure,present:false,status:'no-navigator-gpu'};
    try{
      const adapter=await navigator.gpu.requestAdapter();
      if(!adapter)return {secure,present:true,status:'no-adapter'};
      const info=adapter.info??{};
      return {secure,present:true,status:'adapter-ready',
        vendor:info.vendor??'',architecture:info.architecture??'',
        device:info.device??'',description:info.description??'',
        softwareFallback:adapter.isFallbackAdapter??null};
    }catch(error){return {secure,present:true,status:'adapter-error',error:String(error)}}
  });
}
async function sceneStatus(p){
  await p.waitForFunction(()=>{
    const msg=document.querySelector('.status-line')?.textContent??'';
    const overlay=document.querySelector('.viewer-notice')?.textContent??'';
    return msg.includes('Steel physics active')||msg.includes('WebGPU')&&/unavailable|error|lost|failed/i.test(msg)
      ||overlay.includes('WebGPU unavailable');
  },undefined,{timeout:process.env.P37_REQUIRE_GPU==='0' ? 16000 : 110000});
  const msg=await p.locator('.status-line').innerText();
  const overlay=await p.locator('.viewer-notice').allInnerTexts();
  if(msg.includes('Steel physics active'))return {status:'running',msg};
  return {status:'unavailable',msg,overlay};
}
async function qa(){
  await timeout(async()=> (await fetch(host)).ok);
  const args=process.platform==='darwin'
    ? ['--enable-unsafe-webgpu','--ignore-gpu-blocklist']
    : ['--no-sandbox','--disable-dev-shm-usage',
      '--enable-unsafe-webgpu','--ignore-gpu-blocklist','--enable-unsafe-swiftshader',
      '--use-angle=swiftshader','--use-vulkan=swiftshader',
      '--enable-features=Vulkan','--use-webgpu-adapter=swiftshader',
      '--disable-vulkan-surface'];
  results.platform=process.platform;
  browser=await chromium.launch({channel:'chromium',headless:true,args});
  results.reference=await getReference();
  // Do not let the reference's WebGPU contexts influence P37 measurements.
  await browser.close();
  browser=await chromium.launch({channel:'chromium',headless:true,args});
  page=await browser.newPage({viewport:{width:1512,height:982},deviceScaleFactor:1});
  page.on('pageerror',error=>results.errors.push('P37 script: '+error.message));
  page.on('response',r=>{if(r.status()>=400)results.errors.push('P37 HTTP '+r.status()+' '+r.url())});
  const response=await page.goto(host,{waitUntil:'domcontentloaded',timeout:45000});
  if(!response?.ok())throw new Error('P37 page did not load successfully');
  results.p37.layout=await page.evaluate(()=>{
    const stage=document.querySelector('.canvas-wrap')?.getBoundingClientRect();
    const h1=document.querySelector('h1');
    const controls=[...document.querySelectorAll('.playground-scenes button')];
    const nav=document.querySelector('.site-header');
    return {pageWidth:document.documentElement.scrollWidth,viewport:innerWidth,
      stageWidth:stage?.width,stageHeight:stage?.height,
      stageShare:stage?.width/innerWidth,
      heading:h1?.innerText,h1Size:Number.parseFloat(getComputedStyle(h1).fontSize),
      scenes:controls.map(b=>({label:b.innerText,active:b.getAttribute('aria-pressed')})),
      headerHeight:nav?.getBoundingClientRect().height};
  });
  if(results.p37.layout.stageShare<.36)throw new Error('Simulator viewport occupies less than 36% of desktop width');
  if(results.p37.layout.scenes.length!==3)throw new Error('Scene quick-switcher missing');
  results.webgpu.adapter=await webgpuAdapter(page);
  const required=process.env.P37_REQUIRE_GPU!=='0';
  try{results.webgpu.runtime=await sceneStatus(page);}
  catch(error){results.webgpu.runtime={status:'unavailable',msg:String(error)}}
  if(results.webgpu.runtime.status!=='running'){
    results.webgpu.status='device-not-qualified';
    if(required)throw new Error('WebGPU physics never started: '+JSON.stringify(results.webgpu));
    // A dead SwiftShader swapchain can hang Chromium's screenshot and viewport
    // APIs even after a successful adapter request. The reference screenshots
    // and static layout metrics are already collected above. Keep this report,
    // then let the strict Apple Metal job prove real rendering and interaction.
    results.webgpu.status='software-device-unavailable';
    return;
  }
  const firstFrame=await page.locator('.canvas-wrap').screenshot({timeout:60000});
  record('p37-steel-canvas.png',firstFrame);
  results.p37.canvas=paletteMetrics(firstFrame);
  if(results.p37.canvas.quantizedColors<25)throw new Error('Rendered Steel canvas appears blank');
  const before=await page.locator('.info-row').filter({hasText:'Simulation time'}).innerText();
  await wait(1600);
  const after=await page.locator('.info-row').filter({hasText:'Simulation time'}).innerText();
  if(before===after)throw new Error('Live Steel simulation time did not advance');
  await page.evaluate(()=>window.scrollTo(0,0));
  await wait(160);
  await capture(page,'p37-skild-style-desktop.png');
  await capture(page,'p37-full-page-desktop.png',true);
  await page.getByRole('button',{name:'Packing station'}).click();
  await sceneStatus(page);
  const second=await page.locator('.canvas-wrap').screenshot({timeout:60000});
  record('p37-packing-canvas.png',second);
  if(createHash('sha256').update(firstFrame).digest('hex')===
     createHash('sha256').update(second).digest('hex'))throw new Error('Scene change did not affect actual rendered canvas');
  const counter=page.locator('.info-row').filter({hasText:'Movable objects'}).locator('strong');
  const objectCount=Number(await counter.innerText());
  await page.getByRole('button',{name:/Drop object into scene/}).click();
  await page.waitForFunction(count=>{
    const row=[...document.querySelectorAll('.info-row')].find(e=>e.innerText.includes('Movable objects'));
    return row && Number(row.querySelector('strong')?.textContent)>count;
  },objectCount,{timeout:30000});
  results.webgpu.status='steel-running';
  results.webgpu.hardwareCandidate=process.platform==='darwin' &&
    results.webgpu.adapter?.softwareFallback!==true &&
    !/swiftshader/i.test(JSON.stringify(results.webgpu.adapter??{}));
  results.webgpu.objectCount={before:objectCount,after:Number(await counter.innerText())};
  await capture(page,'p37-with-object-desktop.png');
  await page.setViewportSize({width:390,height:844});
  await page.waitForTimeout(700);
  results.p37.mobile=await page.evaluate(()=>({
    viewport:innerWidth,width:document.documentElement.scrollWidth,
    sceneWidth:document.querySelector('.canvas-wrap')?.getBoundingClientRect().width,
    sceneHeight:document.querySelector('.canvas-wrap')?.getBoundingClientRect().height,
    buttonSizes:[...document.querySelectorAll('.playground-scenes button')].map(b=>{
      const r=b.getBoundingClientRect();return {width:r.width,height:r.height}
    }),
  }));
  if(results.p37.mobile.width>392)throw new Error('P37 has horizontal mobile overflow');
  if(results.p37.mobile.sceneWidth<330)throw new Error('P37 physics scene too narrow on mobile');
  await page.evaluate(()=>window.scrollTo(0,0));
  await wait(180);
  await capture(page,'p37-skild-style-mobile.png');
}
try{
  await qa();
}catch(error){
  results.failure=String(error);
  if(page)try{await capture(page,'p37-qa-failure.png')}catch{}
  process.exitCode=1;
}finally{
  results.finishedAt=new Date().toISOString();
  writeFileSync(resolve(destination,'review.json'),JSON.stringify(results,null,2)+'\n');
  await browser?.close().catch(()=>{});
  server.kill('SIGTERM');
  console.log(JSON.stringify({runtime:results.webgpu,layout:results.p37.layout,
    mobile:results.p37.mobile,reference:results.reference.layout,errors:results.errors,
    failure:results.failure},null,2));
}
