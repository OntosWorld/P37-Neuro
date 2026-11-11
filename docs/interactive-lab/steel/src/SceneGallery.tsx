import { useEffect, useRef } from 'react';
import { PRESETS, type Preset } from './Workcell';

function Preview({variant}: {variant:Preset}) {
 const objects=variant==='packing'?[[120,80],[170,87],[221,102],[155,123]]
   :variant==='inspection'?[[112,97],[175,106],[225,109]]
   :[[120,103],[170,97],[218,108]];
 return <svg className="pg-preview" viewBox="0 0 360 208" role="img"
   aria-label={'Illustrated '+variant+' scene layout, not a simulation screenshot'}>
   <defs>
     <linearGradient id={'pg-background-'+variant} x1="0" y1="0" x2="1" y2="1">
       <stop stopColor="#2c353c"/><stop offset="1" stopColor="#131b20"/>
     </linearGradient>
   </defs>
   <rect width="360" height="208" fill={'url(#pg-background-'+variant+')'}/>
   <path d="M0 164L360 164M0 181L360 181M50 0L50 208M130 0L130 208M210 0L210 208M290 0L290 208"
     stroke="#53616c" strokeOpacity=".13"/>
   <path d="M67 122 L178 61 L307 123 L194 185 Z" fill="#617480" stroke="#9bb7ca"
     strokeWidth="1.4"/>
   <path d="M67 122 L67 142 L194 202 L194 185 Z" fill="#34434e"/>
   <path d="M194 185L194 202L307 141L307 123 Z" fill="#28353e"/>
   <path d="M93 136 L93 184M278 133 L278 177" stroke="#9db5c3" strokeWidth="7"
     strokeLinecap="round"/>
   <ellipse cx="150" cy="118" rx="25" ry="11" fill="#1c252c" opacity=".6"/>
   <rect x="135" y="79" width="21" height="41" rx="5" fill="#dbe4e8" stroke="#acbfc9"/>
   <path d="M144 79L168 48L194 56L207 33" fill="none" stroke="#e1ebef"
     strokeWidth="14" strokeLinejoin="round" strokeLinecap="round"/>
   <path d="M144 79L168 48L194 56L207 33" fill="none" stroke="#768a99"
     strokeWidth="2" strokeLinejoin="round"/>
   <g fill="#283942" stroke="#a8c9d9" strokeWidth="1.4">
     {objects.map(([x,y],index)=>variant==='inspection'?
       <ellipse key={index} cx={x} cy={y} rx={11} ry={6}/>:
       <rect key={index} x={x} y={y} width={23} height={17} rx={2}/>)}
   </g>
   <text x="20" y="28" fontFamily="ui-monospace,monospace" fontSize="10"
     letterSpacing="1.5" fill="#a9bcc8">P37 / {variant.toUpperCase()}</text>
   <text x="20" y="188" fontFamily="ui-monospace,monospace" fontSize="9"
     letterSpacing="1" fill="#8aa0af">REFERENCE SCHEMATIC</text>
 </svg>;
}
export function SceneGallery({current,onSelect,onClose}:{
 current:Preset;onSelect:(preset:Preset)=>void;onClose:()=>void;
}) {
 const close=useRef<HTMLButtonElement>(null);
 useEffect(()=>{
  close.current?.focus();
  const onKey=(event:KeyboardEvent)=>{if(event.key==='Escape')onClose();};
  document.addEventListener('keydown',onKey);
  return()=>document.removeEventListener('keydown',onKey);
 },[onClose]);
 return <div className="pg-gallery" role="dialog" aria-modal="true"
   aria-label="Choose a physical scene">
   <div className="pg-gallery-header"><div>
     <h2>Scenes <span>{PRESETS.length}</span></h2>
     <p>Interactive physics environments. Select a scene to rebuild the workcell.</p>
   </div><button ref={close} type="button" onClick={onClose}>Close ×</button></div>
   <div className="pg-gallery-grid">
     {PRESETS.map((entry,i)=><button key={entry.id} type="button"
       className={'pg-gallery-card'+(entry.id===current?' selected':'')}
       aria-pressed={entry.id===current}
       onClick={()=>onSelect(entry.id)}>
       <Preview variant={entry.id}/>
       <div className="pg-card-caption">
         <div><span className="pg-card-index">{String(i+1).padStart(2,'0')}</span>
           <strong>{entry.label}</strong></div>
         <span className="pg-card-desc">{entry.detail}</span>
       </div>
     </button>)}
   </div>
   <div className="pg-gallery-note">Scene thumbnails are schematics. The interactive physics runs after selection. No learned P37 policy is attached.</div>
 </div>;
}