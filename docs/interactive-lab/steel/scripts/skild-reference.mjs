import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
const output = resolve('skild-reference');
mkdirSync(output, {recursive: true});
const browser=await chromium.launch({channel:'chrome',headless:true,args:['--no-sandbox']});
const result={url:'https://www.skild.ai/demos/steel',screens:[],errors:[]};
const inspect=async(viewport,label)=>{
 const page=await browser.newPage({viewport,deviceScaleFactor:1});
 try{
  const response=await page.goto(result.url,{waitUntil:'domcontentloaded',timeout:45000});
  await page.waitForTimeout(5000);
  const dimensions=await page.evaluate(()=>{
   function computed(el){
    if(!el)return null;const s=getComputedStyle(el),r=el.getBoundingClientRect();
    return {tag:el.tagName,text:el.textContent?.trim().slice(0,120),
      bg:s.backgroundColor,color:s.color,font:s.fontFamily,size:s.fontSize,
      weight:s.fontWeight,lineHeight:s.lineHeight,spacing:s.letterSpacing,
      radius:s.borderRadius,border:s.borderColor,
      x:Math.round(r.x),y:Math.round(r.y),width:Math.round(r.width),height:Math.round(r.height)}
   }
   const sorted=(query)=>[...document.querySelectorAll(query)].slice(0,25).map(computed);
   return {url:location.href,title:document.title,text:document.body.innerText.slice(0,5000),
    body:computed(document.body),header:sorted('header,nav'),headlines:sorted('h1,h2,h3'),
    buttons:sorted('button,select,[role=button]'),sections:sorted('main,section'),
    viewport:innerWidth,scrollWidth:document.documentElement.scrollWidth,
    css:[...document.styleSheets].map(s=>s.href).filter(Boolean)};
  });
  result[label]={status:response?.status(),...dimensions};
  await page.screenshot({path:resolve(output,label+'.png'),animations:'disabled',timeout:45000});
  result.screens.push(label+'.png');
 }catch(e){result.errors.push(label+': '+String(e))}
 await page.close();
};
try{await inspect({width:1512,height:930},'desktop');await inspect({width:390,height:844},'mobile')}
finally{
 await browser.close();
 writeFileSync(resolve(output,'computed-design.json'),JSON.stringify(result,null,2));
 console.log(JSON.stringify(result,null,2).slice(0,14000));
}