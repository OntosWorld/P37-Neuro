/**
 * Mirror the Apache-2.0 MuJoCo Menagerie Panda source into public/.
 * Source commit and each git blob SHA-1 are pinned and verified.
 * Public browsers never fetch model meshes from third-party servers.
 */
import { createHash } from 'node:crypto';
import { mkdir, readFile, rename, rm, stat, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const manifest=JSON.parse(await readFile(resolve(root,'scripts/panda-manifest.json'),'utf8'));
const destination=resolve(root,'public/vendor/panda');
const sourcePrefix='https://raw.githubusercontent.com/google-deepmind/mujoco_menagerie/'+manifest.source_commit+'/franka_emika_panda/';

function contentSha(bytes) {
  return createHash('sha1').update('blob '+bytes.length+'\0').update(bytes).digest('hex');
}
async function obtain(file) {
  const target=resolve(destination,file.path);
  if(!target.startsWith(destination+'/'))throw new Error('Vendor path escaped destination');
  try {
    if((await stat(target)).size===file.bytes) {
      const cached=await readFile(target);
      if(contentSha(cached)===file.gitBlobSha1)return 'cached';
    }
  }catch{}
  let error;
  for(let attempt=1;attempt<=4;attempt++){
    try{
      const url=new URL(file.path,sourcePrefix);
      const response=await fetch(url,{signal:AbortSignal.timeout(55000),redirect:'follow'});
      if(!response.ok)throw new Error(response.status+' '+response.statusText);
      const contents=Buffer.from(await response.arrayBuffer());
      if(contents.length!==file.bytes||contentSha(contents)!==file.gitBlobSha1)
        throw new Error('source checksum mismatch: '+file.path);
      await mkdir(dirname(target),{recursive:true});
      const temporary=target+'.download';
      await writeFile(temporary,contents);
      await rename(temporary,target);
      return 'downloaded';
    }catch(cause){
      error=cause;
      await rm(target+'.download',{force:true}).catch(()=>{});
      if(attempt<4)await new Promise(done=>setTimeout(done,attempt*700));
    }
  }
  throw new Error('Panda asset download failed: '+file.path+': '+error);
}
if(!manifest.source_commit.match(/^[a-f0-9]{40}$/))
  throw new Error('Source repository must be pinned to a 40-hex commit');
if(!manifest.files?.length||!manifest.files.find(x=>x.path==='LICENSE'))
  throw new Error('Source manifest must preserve Apache-2.0 license');
await mkdir(destination,{recursive:true});
let cursor=0;
let finished=0;
let downloaded=0;
await Promise.all(Array.from({length:6},async()=>{
  for(;;){
    const index=cursor++;
    if(index>=manifest.files.length)return;
    const result=await obtain(manifest.files[index]);
    finished++;
    if(result==='downloaded')downloaded++;
    if(finished%12===0)console.log('Panda assets checked: '+finished+'/'+manifest.files.length);
  }
}));
// MuJoCo's Panda gripper uses a tendon actuator. Steel v0.1.0 imports joint
// motors but not tendon actuators, so publish a clearly marked compatibility
// derivative with independent joint servos. The exact source remains as
// panda.xml and still passes its upstream blob hash.
const originalMJCF=await readFile(resolve(destination,'panda.xml'),'utf8');
if(!originalMJCF.includes('</actuator>'))throw new Error('Panda actuator block missing');
const compatMJCF=originalMJCF.replace('</actuator>',
  '  <!-- Modified by Ontos for Steel WebGPU: physical finger joint drives. -->\n'+
  '  <position joint="finger_joint1" kp="400" kv="35"/>\n'+
  '  <position joint="finger_joint2" kp="400" kv="35"/>\n'+
  '</actuator>');
if(compatMJCF.includes('\\\\n') || !compatMJCF.includes('<position joint="finger_joint1"'))
  throw new Error('Invalid Steel Panda compatibility XML: encoded newlines or missing finger drives');
await writeFile(resolve(destination,'panda-steel.xml'),compatMJCF);
await writeFile(resolve(destination,'SOURCE.json'),JSON.stringify({
  source:manifest.origin,
  source_commit:manifest.source_commit,
  license:manifest.license,
  robot:manifest.robot,
  files:manifest.files.length,
  total_bytes:manifest.files.reduce((sum,x)=>sum+x.bytes,0),
  usage:'Optional full-mesh Panda robot in P37 Steel WebGPU; no trained P37 policy',
},null,2)+'\n');
console.log('Verified '+finished+' Panda files; fetched '+downloaded+'; '+(manifest.files.reduce((a,x)=>a+x.bytes,0)/1048576).toFixed(1)+' MiB total');
