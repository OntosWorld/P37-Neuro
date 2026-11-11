import { useEffect, useState } from 'react';

/**
 * Ontos website navigation adapted to P37. The mark, menu labels and
 * 32px announcement / 68px navigation rhythm mirror www.ontos.ws.
 * Search is scoped to known pages here (no simulated whole-site search).
 */
const OFFICIAL='https://www.ontos.ws';
const navigation=[
  {name:'Technology',href:OFFICIAL+'/physical-ai'},
  {name:'Research',href:OFFICIAL+'/research'},
  {name:'Systems',href:OFFICIAL+'/products'},
  {name:'Company',href:OFFICIAL+'/about'},
];
const searchPages=[
  {name:'P37-Neuro simulation lab',detail:'Live physics workcell',href:'./'},
  {name:'Brain Lab',detail:'Robot models and simulations',href:'../../'},
  {name:'Simulation gallery',detail:'Existing MuJoCo examples',href:'../../demos/'},
  {name:'Recorded MimicGen evidence',detail:'Public source robot episodes',href:'../compare/?sample=mimicgen'},
  ...navigation.map(item=>({...item,detail:'Ontos website'})),
];

export function OntosMark({size=32}: {size?:number}) {
  return <svg className="ontos-mark" width={size} height={size}
    viewBox="0 0 32 32" fill="none" aria-hidden="true">
    <circle cx="15.5" cy="16.5" r="9.1" stroke="currentColor" strokeWidth="2"/>
    <circle cx="22" cy="10" r="2.15" fill="currentColor"/>
  </svg>;
}

export function OfficialHeader() {
  const [open,setOpen]=useState(false);
  const [searchOpen,setSearchOpen]=useState(false);
  const [query,setQuery]=useState('');
  const matches=searchPages.filter(page=>(page.name+' '+page.detail).toLowerCase().includes(query.toLowerCase())).slice(0,7);
  useEffect(()=>{
    const key=(event:KeyboardEvent)=>{
      if(event.key==='Escape'){setSearchOpen(false);setOpen(false);}
      if((event.metaKey||event.ctrlKey)&&event.key.toLowerCase()==='k'){
        event.preventDefault();setSearchOpen(value=>!value);setOpen(false);
      }
    };
    window.addEventListener('keydown',key);
    return ()=>window.removeEventListener('keydown',key);
  },[]);

  return <>
    <div className="ontos-announcement">
      <a href={OFFICIAL+'/research/prediction-memory-motor-adaptation'} aria-label="Read Ontos neuroscience research">
        <span>Research</span><strong>Neuroscience for robot adaptation</strong>
        <span className="announcement-date">Nov 8, 2026</span><em>Read more ↗</em>
      </a>
    </div>
    <header className="official-nav">
      <a className="skip-content" href="#page-content">Skip to content</a>
      <a className="official-wordmark" href={OFFICIAL+'/'} aria-label="Ontos home">
        <OntosMark/><span>ONTOS</span>
      </a>
      <button className="official-menu" type="button"
        aria-controls="official-links" aria-expanded={open}
        onClick={()=>{setOpen(value=>!value);setSearchOpen(false);}}>
        Menu <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden="true">
          <path d="M5 7h14M5 12h14M5 17h14"/>
        </svg>
      </button>
      <nav id="official-links" aria-label="Ontos main navigation" className={open?'official-links expanded':'official-links'}>
        {navigation.map(link=><a key={link.name} href={link.href}
          onClick={()=>setOpen(false)}>{link.name}</a>)}
        <a className="mobile-contact" href={OFFICIAL+'/contact'}>Get in touch</a>
        <button type="button" className="official-search"
          aria-label="Search Ontos and P37 links"
          aria-haspopup="dialog" aria-expanded={searchOpen}
          onClick={()=>{setSearchOpen(true);setOpen(false);}}>
          <svg width="19" height="19" viewBox="0 0 20 20" fill="none" stroke="currentColor"
            strokeWidth="1.45" aria-hidden="true">
            <circle cx="8.6" cy="8.6" r="5.5"/><path d="m12.7 12.7 4.1 4.1"/>
          </svg>
          <span className="visually-hidden">Search</span>
        </button>
      </nav>
      <a className="official-contact" href={OFFICIAL+'/contact'}>Get in touch</a>
    </header>
    {searchOpen&&<div className="official-search-scrim" role="presentation"
      onMouseDown={event=>{if(event.target===event.currentTarget)setSearchOpen(false);}}>
      <section role="dialog" aria-modal="true" aria-label="Search Ontos links"
        className="official-search-dialog">
        <div className="search-dialog-top">
          <span>Search links</span>
          <button type="button" onClick={()=>setSearchOpen(false)}>Close ×</button>
        </div>
        <input autoFocus type="search" aria-label="Search page links" value={query}
          placeholder="Search research, products, simulations..."
          onChange={event=>setQuery(event.target.value)}/>
        <div className="search-results">
          {matches.map(match=><a key={match.href} href={match.href}>
            <span><strong>{match.name}</strong><small>{match.detail}</small></span><span>↗</span>
          </a>)}
          {matches.length===0&&<p>No matching page in this directory.</p>}
        </div>
        <div className="search-hint">This search covers Ontos navigation and the P37 demo directory.</div>
      </section>
    </div>}
  </>;
}
