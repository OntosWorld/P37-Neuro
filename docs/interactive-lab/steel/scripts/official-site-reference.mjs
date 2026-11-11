/** Capture official Ontos site for precise P37 design alignment. */
import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
const output=resolve('official-site-reference');
mkdirSync(output,{recursive:true});
const browser=await chromium.launch({channel:'chrome',headless:true,args:['--no-sandbox']});
const result={url:'https://www.ontos.ws/',ok:false,errors:[],desktop:null,mobile:null};
async function capture(viewport,name){
 const page=await browser.newPage({viewport,deviceScaleFactor:1});
 page.on('pageerror',error=>result.errors.push(name+' JS: '+error.message));
 page.on('requestfailed',request=>{
   if(!request.url().includes('analytics')&&!request.url().includes('google'))
     result.errors.push(name+' request: '+request.url()+' '+request.failure()?.errorText);
 });
 try{
  const resp=await page.goto(result.url,{waitUntil:'domcontentloaded',timeout:30000});
  await page.waitForTimeout(3500);
  result[name]=await page.evaluate(()=>{
    const properties=(element)=>{
      if(!element)return null;
      const style=getComputedStyle(element);
      const rect=element.getBoundingClientRect();
      return {tag:element.tagName,text:element.textContent?.trim().slice(0,170),
        fontFamily:style.fontFamily,fontSize:style.fontSize,fontWeight:style.fontWeight,
        letterSpacing:style.letterSpacing,lineHeight:style.lineHeight,
        color:style.color,background:style.backgroundColor,
        borderColor:style.borderColor,radius:style.borderRadius,
        textTransform:style.textTransform,
        width:rect.width,height:rect.height,top:rect.top,left:rect.left};
    };
    const top=document.querySelector('header,nav,[role="navigation"]');
    const main=document.querySelector('main')??document.body;
    const heading=main.querySelector('h1');
    const buttons=[...document.querySelectorAll('button,a')].filter(node=>node.getBoundingClientRect().width>45).slice(0,35);
    const roots=[...document.styleSheets].map(sheet=>sheet.href).filter(Boolean);
    const images=[...document.querySelectorAll('img')].slice(0,24).map(img=>({src:img.currentSrc||img.src,alt:img.alt,
      rect:img.getBoundingClientRect().toJSON()}));
    const topLinks=[...(top?.querySelectorAll('a')??[])].map(a=>({text:a.textContent?.trim(),href:a.href}));
    return {title:document.title,url:location.href,bodyText:document.body.innerText.slice(0,7000),
      width:document.documentElement.scrollWidth,viewport:window.innerWidth,height:document.documentElement.scrollHeight,
      body:properties(document.body),header:properties(top),headerHtml:top?.outerHTML.slice(0,12000),
      heading:properties(heading),headlineText:heading?.textContent?.trim(),
      subtitle:properties(heading?.nextElementSibling), buttons:buttons.map(properties),
      topLinks,images,stylesheets:roots};
  });
  result[name].status=resp?.status();
  await page.screenshot({path:resolve(output,'ontos-'+name+'-viewport.png'),animations:'disabled',timeout:45000});
  if(name==='desktop')await page.screenshot({path:resolve(output,'ontos-desktop-full.png'),
    fullPage:true,animations:'disabled',timeout:45000});
  result.ok=result.ok||(resp?.ok()??false);
 }catch(error){result.errors.push(name+': '+String(error));}
 await page.close();
}
try{await capture({width:1512,height:980},'desktop');
    await capture({width:390,height:844},'mobile');
}finally{await browser.close();
 writeFileSync(resolve(output,'site-tokens.json'),JSON.stringify(result,null,2)+'\n');
 console.log(JSON.stringify({ok:result.ok,errors:result.errors,desktop:result.desktop&&{
  status:result.desktop.status,title:result.desktop.title,heading:result.desktop.heading,
  header:result.desktop.header,topLinks:result.desktop.topLinks,stylesheets:result.desktop.stylesheets,
  body:result.desktop.body,buttons:result.desktop.buttons?.slice(0,9),bodyText:result.desktop.bodyText?.slice(0,1100),
 },mobile:result.mobile&&{status:result.mobile.status,heading:result.mobile.heading,header:result.mobile.header}},
 null,2));}
