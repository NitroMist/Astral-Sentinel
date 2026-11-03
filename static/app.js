/* Astral Sentinel v1.0.0 - AGPL-3.0-or-later. No external network/CDN dependencies. */
'use strict';
const $=id=>document.getElementById(id);
const theme={cyan:'#63e9f6',blue:'#6b9dff',red:'#fc706b',green:'#55e0a7',gold:'#ffc06d',white:'#d8f5fa',gray:'#7294a7'};
const state={snapshot:null,forecast:null,days:30,house:'placidus',houseMethod:'longitude',zodiac:'tropical',view:'observatory',mode:'zodiac',showAspects:true,showNatal:true,showLabels:true,showAlerts:true,showAux:true,showNatalPoints:true,showChiron:true,showAuxAspects:true,auxAspectFilter:'both',auxOrb:2,auxScoring:true,nodeMode:'mean',lilithMode:'mean',selected:{type:'planet',name:'Saturn'},shift:0,chosenDate:null,timelineIndex:0,timelineKey:null,requestId:0,forecastRequestId:0,loading:false};
const glyphs={Sun:'☉',Moon:'☾',Mercury:'☿',Venus:'♀',Mars:'♂',Jupiter:'♃',Saturn:'♄',Uranus:'♅',Neptune:'♆',Pluto:'♇',Earth:'⊕'};
const zodiacGlyphs=['♈','♉','♊','♋','♌','♍','♎','♏','♐','♑','♒','♓'];
const $all=sel=>Array.from(document.querySelectorAll(sel));
const num=(n,d=1)=>Number(n).toFixed(d);
function fmtDate(x,detail=false){const date=new Date(x);return new Intl.DateTimeFormat(undefined,{month:'short',day:'numeric',...(detail?{year:'numeric',hour:'2-digit',minute:'2-digit'}:{})}).format(date)}
function formatLongitude(l){const deg=Math.floor((l%30+30)%30);const min=Math.floor((((l%30+30)%30)-deg)*60+.5);return `${deg+(min===60?1:0)}°${String(min===60?0:min).padStart(2,'0')}′`}
function statusColor(status){return status==='support'?theme.green:status==='tension'?theme.red:status==='neutral'?theme.gold:theme.cyan}
function colorOfPlanet(name){const item=state.snapshot?.planet_status.find(p=>p.name===name);return statusColor(item?.status||'neutral')}
function toast(s){const el=$('toast');el.textContent=s;el.classList.remove('hidden');clearTimeout(toast.tid);toast.tid=setTimeout(()=>el.classList.add('hidden'),3600)}
function whenDate(){return state.chosenDate??new Date(Date.now()+state.shift*86400000)}
function isSimulated(){return Boolean(state.chosenDate)||state.shift!==0}
function dateToLocalInput(d){const pad=n=>String(n).padStart(2,'0');return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`}
function updateClock(){
 const d=whenDate(),sim=isSimulated();
 $('live-clock').textContent=new Intl.DateTimeFormat(undefined,{weekday:'short',month:'short',day:'numeric',year:'numeric',hour:'2-digit',minute:'2-digit'}).format(d);
 $('map-time').textContent=`UTC ${d.toISOString().replace('T',' ').slice(0,16)}`;
 $('time-mode').textContent=sim?'◇ SIMULATION ACTIVE':'● LIVE TRANSITS';
 $('time-mode').classList.toggle('simulation',sim);
 $('observatory-return-live').classList.toggle('hidden',!sim);
 $('header-return-live').classList.toggle('hidden',!sim);
}
async function api(path,args){const url=new URL(path,window.location.href);Object.entries(args).forEach(([k,v])=>url.searchParams.set(k,v));const res=await fetch(url);const obj=await res.json();if(!res.ok)throw Error(obj.error||`HTTP ${res.status}`);return obj}
async function refresh(full=true){const id=++state.requestId;state.loading=true;state.forecastRequestId++;state.forecast=null;syncTimelinePreview();const at=whenDate().toISOString();const params={at,house:state.house,house_method:state.houseMethod,zodiac:state.zodiac,node_mode:state.nodeMode,lilith_mode:state.lilithMode,aux_orb:state.auxOrb,aux_scoring:state.auxScoring};$('footer-status').textContent='EPHEMERIS SCANNING';try{
  const snap=await api('/api/snapshot',params);if(id!==state.requestId)return;state.snapshot=snap;state.loading=false;$('footer-status').textContent='EPHEMERIS SYNCHRONIZED';
  $('online-status').innerHTML='<span class="pulse"></span> LOCAL / OFFLINE READY'; updateClock();renderAll();
  refreshForecast();
 }catch(err){if(id!==state.requestId)return;state.loading=false;$('footer-status').textContent='ENGINE ERROR';$('online-status').textContent='CONNECTION LOST';toast(`Calculation error: ${err.message}`);console.error(err)}}
async function refreshForecast(){const request=++state.forecastRequestId;const params={at:state.snapshot?.at_utc??whenDate().toISOString(),house:state.house,house_method:state.houseMethod,zodiac:state.zodiac,days:state.days,node_mode:state.nodeMode,lilith_mode:state.lilithMode,aux_scoring:state.auxScoring};state.forecast=null;syncTimelinePreview();try{const result=await api('/api/forecast',params);if(request!==state.forecastRequestId)return;state.forecast=result;updateForecast();updateExport()}catch(err){if(request===state.forecastRequestId)toast(`Forecast unavailable: ${err.message}`)}}
function setView(tab){state.view=tab;$all('[data-tab]').forEach(b=>b.classList.toggle('active',b.dataset.tab===tab));$all('#view-observatory, .page-view').forEach(e=>e.classList.add('hidden'));$('view-'+tab).classList.remove('hidden');if(tab==='forecast')updateForecast();if(tab==='export')updateExport();if(tab==='natal')renderNatal();if(tab==='observatory')requestAnimationFrame(()=>{resizeSky(); if(state.forecast)drawGraph($('spark'),state.forecast.samples,true)})}
function renderAll(){renderMeter();renderWarnings();renderPlanetStrip();renderSelected();renderNatal();updateExport();renderControlLabels();renderHouseMethod();renderAuxRegistry()}
function renderControlLabels(){const isSolar=state.mode==='solar';$('map-mode-label').textContent=isSolar?'SOLAR SYSTEM MAP':'ZODIAC MAP';$('map-subtitle').textContent=isSolar?'HELIOCENTRIC LONGITUDE · TROPICAL':'GEOCENTRIC ECLIPTIC LONGITUDE · '+state.zodiac.replace('_',' ').toUpperCase();$('projection-note').textContent=isSolar?'Solar system: heliocentric longitudes and illustrative orbital distances. Astrological aspect lines and auxiliary lunar/natal points appear only in Zodiac View.':'Zodiac: angular positions show actual geocentric ecliptic longitudes. Radial distances are schematic.';$('map-hint').textContent=isSolar?'POSITIONS ARE HELIOCENTRIC':'CLICK A PLANET TO ANALYZE';}
function renderMeter(){if(!state.snapshot)return;const s=state.snapshot.score;$('difficulty-num').innerHTML=`${num(s.difficulty)}<small> / 10</small>`;$('difficulty-status').textContent=s.status;const el=$('meter');el.replaceChildren();for(let i=0;i<10;i++){const sp=document.createElement('span');if(i<s.difficulty){sp.className='filled'+(i>=7?' high':'')}el.appendChild(sp)}$('difficulty-status').style.color=s.difficulty>=7.4?theme.red:s.difficulty>=5.8?theme.gold:theme.green;$('scoring-breakdown').textContent=`Planetary baseline ${num(s.planetary_baseline)}/10 · Auxiliary ${s.auxiliary_enabled?(s.auxiliary_modifier>=0?'+':'')+num(s.auxiliary_modifier,2):'OFF'} · Composite ${num(s.difficulty)}/10`}
function renderWarnings(){
 const root=$('alerts');root.replaceChildren();
 if(!state.showAlerts){root.textContent='Alert feed paused by display settings.';return}
 for(const n of state.snapshot?.notices||[]){
  const box=document.createElement('div');box.className='alert '+(n.kind||'neutral');
  const areas=Array.isArray(n.areas)?n.areas.filter(s=>typeof s==='string'&&s):[];
  const head=document.createElement('div');head.className='alert-head';
  const ic=document.createElement('span');ic.className='alert-icon';
  ic.textContent=n.kind==='tension'?'⚠':n.kind==='support'?'◇':'⌖';
  head.append(ic,document.createTextNode(n.title));
  const paragraph=document.createElement('p');paragraph.textContent=n.text;
  if(areas.length){
   const button=document.createElement('button');button.type='button';
   button.className='alert-toggle';button.setAttribute('aria-expanded','false');
   const sectionId='advisory-areas-'+root.children.length;
   button.setAttribute('aria-controls',sectionId);
   const chevron=document.createElement('span');chevron.className='alert-chevron';
   chevron.textContent='⌄';chevron.setAttribute('aria-hidden','true');
   head.append(chevron);button.append(head,paragraph);
   const region=document.createElement('div');region.className='alert-areas';
   region.id=sectionId;region.hidden=true;
   const title=document.createElement('div');title.className='alert-areas-title';
   title.textContent='AFFECTED AREAS · STRONGEST FIRST';
   const list=document.createElement('ol');
   for(const name of areas){const li=document.createElement('li');li.textContent=name;list.append(li)}
   const note=document.createElement('p');note.className='alert-areas-note';
   note.textContent='Interpretive themes from active natal aspects, not event predictions.';
   region.append(title,list,note);
   button.addEventListener('click',()=>{const expanded=button.getAttribute('aria-expanded')!=='true';
    button.setAttribute('aria-expanded',String(expanded));region.hidden=!expanded;box.classList.toggle('expanded',expanded)});
   box.append(button,region);
  }else{box.append(head,paragraph)}
  root.append(box);
 }
}

function auxiliarySignalTiles(){
 const data=state.snapshot;if(!data||!state.showAux)return [];
 const live=activeAuxPoints();
 const natal=activeNatalAuxPoints();
 const names=new Set(),points=[];
 for(const p of live){if(!names.has(p.name)){names.add(p.name);points.push({point:p,scope:'transit'})}}
 for(const p of natal){if(!names.has(p.name)){names.add(p.name);points.push({point:p,scope:'natal'})}}
 const entries=data.auxiliary_scoring?.entries||[];
 const nodeNames=new Set(['North Node','South Node']);
 return points.map(({point,scope})=>{
   // Both node tiles represent the *same* deduplicated nodal axis. Never add
   // their displayed raw values together; the model counts the axis once.
   const matches=entries.filter(e=>nodeNames.has(point.name)
     ?nodeNames.has(e.source)||nodeNames.has(e.target)
     :e.source===point.name||e.target===point.name);
   const raw=matches.reduce((sum,e)=>sum+e.value,0);
   const value=Math.abs(raw)<0.0005?0:raw;
   const status=value>0?'support':value<0?'tension':'neutral';
   return {point,scope,value,status,connections:matches.length,sharedAxis:nodeNames.has(point.name)};
 });
}
function renderPlanetStrip(){
 const root=$('planet-status'),viewport=$('signal-scroll');
 const oldScroll=viewport.scrollLeft;
 root.replaceChildren();
 if(!state.snapshot){updateSignalScroll();return}
 for(const p of state.snapshot.planet_status){
   const btn=document.createElement('button');btn.type='button';
   btn.className=`planet-tile ${state.selected.type==='planet'&&state.selected.name===p.name?'selected':''}`;
   btn.title=`${p.name}: ${p.value>0?'+':''}${num(p.value,2)} planetary weighted support / tension`;
   const glyph=document.createElement('span');glyph.className='planet-symbol';glyph.textContent=p.glyph;
   const orb=document.createElement('span');orb.className='planet-globe '+p.status;
   const val=document.createElement('span');val.className='planet-score '+p.status;val.textContent=(p.value>0?'+':'')+num(p.value);
   const name=document.createElement('span');name.className='planet-name';name.textContent=p.name;
   btn.append(glyph,orb,val,name);btn.onclick=()=>selectPlanet(p.name);root.append(btn);
 }
 const extra=auxiliarySignalTiles();
 root.classList.toggle('has-aux',extra.length>0);
 for(const entry of extra){
   const {point,scope,value,status,connections,sharedAxis}=entry;
   const btn=document.createElement('button');btn.type='button';
   btn.className=`planet-tile aux-signal-tile ${state.selected.type==='aux'&&state.selected.name===point.name&&state.selected.scope===scope?'selected':''}`;
   const label={'North Node':'N. Node','South Node':'S. Node','Black Moon Lilith':'Lilith','Part of Fortune':'Fortune'}[point.name]||point.name;
   const signalLabel=state.auxScoring?(value>0?'+':'')+num(value,2):'OFF';
   btn.title=`${point.name} (${scope==='natal'?'natal-only':'live'}) · ${connections} scored links · ${state.auxScoring?'raw auxiliary signal '+signalLabel:'auxiliary scoring OFF'}${sharedAxis?' · shared lunar node axis, not a separate scored influence':''}. Click for details.`;
   const glyph=document.createElement('span');glyph.className='planet-symbol aux-signal-glyph';glyph.textContent=point.glyph;
   const diamond=document.createElement('span');diamond.className='aux-signal-diamond '+(state.auxScoring?status:'neutral');diamond.textContent='◇';
   const val=document.createElement('span');val.className='planet-score '+(state.auxScoring?status:'neutral');val.textContent=signalLabel;
   const name=document.createElement('span');name.className='planet-name';name.textContent=label;
   const scopeLabel=document.createElement('span');scopeLabel.className='aux-signal-scope';scopeLabel.textContent=sharedAxis?'AXIS':scope==='natal'?'NATAL':'LIVE';
   btn.append(glyph,diamond,val,name,scopeLabel);btn.onclick=()=>selectAuxPoint(point.name,scope);root.append(btn);
 }
 viewport.scrollLeft=extra.length?oldScroll:0;
 $('signal-note').textContent=extra.length?'PLANETS + AUXILIARY · RAW SIGNALS':'TRANSITS TO NATAL TARGETS';
 requestAnimationFrame(updateSignalScroll);
}
function updateSignalScroll(){
 const viewport=$('signal-scroll'),nav=$('signal-navigation');if(!viewport||!nav)return;
 const overflow=viewport.scrollWidth>viewport.clientWidth+2;
 nav.classList.toggle('hidden',!overflow);
 $('signal-prev').disabled=!overflow||viewport.scrollLeft<=1;
 $('signal-next').disabled=!overflow||viewport.scrollLeft>=viewport.scrollWidth-viewport.clientWidth-2;
}
function initSignalScroll(){
 const viewport=$('signal-scroll');
 $('signal-prev').onclick=()=>viewport.scrollBy({left:-viewport.clientWidth*.62,behavior:'smooth'});
 $('signal-next').onclick=()=>viewport.scrollBy({left:viewport.clientWidth*.62,behavior:'smooth'});
 viewport.addEventListener('scroll',updateSignalScroll,{passive:true});
 if(typeof ResizeObserver!=='undefined')new ResizeObserver(updateSignalScroll).observe(viewport);
 window.addEventListener('resize',updateSignalScroll);
}

function activeAuxPoints(){
 const data=state.snapshot;if(!data||!state.showAux)return [];
 const chosen=p=>p.name!=='Chiron'||state.showChiron;
 return (data.auxiliary_transits||[]).filter(chosen);
}
function activeNatalAuxPoints(){
 const data=state.snapshot;if(!data||!state.showAux||!state.showNatal)return [];
 return (data.natal.auxiliary_points||[]).filter(p=>((p.name!=='Chiron'||state.showChiron) && (state.showNatalPoints||!['Part of Fortune','Vertex'].includes(p.name))));
}
// Only show lines with visible endpoints. An auxiliary display filter never removes
// their underlying calculations or changes the ordinary planet threat index.
function visibleAuxiliaryLinks(){
 const data=state.snapshot;
 if(!data||state.mode==='solar'||!state.showAux||!state.showAuxAspects)return [];
 const visibleLive=new Set(activeAuxPoints().map(p=>p.name));
 const visibleNatal=new Set(activeNatalAuxPoints().map(p=>p.name));
 const filtered=[];
 const lists=[];
 if(state.auxAspectFilter!=='sky' && state.showNatal)lists.push(...(data.auxiliary_aspects||[]));
 if(state.auxAspectFilter!=='natal')lists.push(...(data.auxiliary_sky_aspects||[]));
 for(const a of lists){
   if(a.source_auxiliary&&!visibleLive.has(a.source))continue;
   if(a.target_auxiliary&&!visibleNatal.has(a.target))continue;
   if(a.target_scope==='natal'&&!state.showNatal)continue;
   filtered.push(a);
 }
 filtered.sort((a,b)=>a.orb-b.orb);
 return filtered.slice(0,24); // Visual cap only; all matches remain in the export.
}
function selectAuxPoint(name,scope='transit'){
 state.selected={type:'aux',name,scope};renderSelected();renderPlanetStrip();renderAuxRegistry();
}
function renderAuxRegistry(){
 const root=$('aux-registry');if(!root)return;root.replaceChildren();const data=state.snapshot;if(!data)return;
 const transit=activeAuxPoints();const natal=activeNatalAuxPoints();
 const add=(p,scope)=>{const btn=document.createElement('button');btn.className='aux-entry'+(scope==='natal'?' aux-natal':'')+(state.selected.type==='aux'&&state.selected.name===p.name&&state.selected.scope===scope?' selected':'');
  const glyph=document.createElement('span');glyph.className='aux-glyph';glyph.textContent=p.glyph;
  const txt=document.createElement('span');txt.className='aux-text';txt.textContent=p.name;
  const sub=document.createElement('small');sub.textContent=`${scope==='natal'?'NATAL · ':'LIVE · '}${formatLongitude(p.longitude)}`;txt.append(sub);btn.append(glyph,txt);
  btn.title=`${p.name} ${scope} · ${p.method} · ${p.definition||''}`;btn.onclick=()=>selectAuxPoint(p.name,scope);root.append(btn)};
 transit.forEach(p=>add(p,'transit'));
 natal.filter(p=>p.name==='Part of Fortune'||p.name==='Vertex').forEach(p=>add(p,'natal'));
 const disabled=(!state.showAux || !state.showChiron);
 const missing=(data.auxiliary_unavailable||[]).find(p=>p.name==='Chiron');
 $('aux-status').textContent=!state.showAux?'Auxiliary overlay hidden.':missing&&state.showChiron?'Chiron unavailable: add ephe/seas_18.se1 to enable it.':disabled?'Hidden points are still included in AI exports.':'◇ Colored symbols show calculated points; difficulty effects follow the separate scoring toggle.';
}
function renderAuxDetail(root,data){
 const scope=state.selected.scope||'transit';const pool=scope==='natal'?data.natal.auxiliary_points:data.auxiliary_transits;
 const p=(pool||[]).find(x=>x.name===state.selected.name);
 if(!p){const x=document.createElement('p');x.className='micro';x.textContent='This point is not available. Select another marker.';root.append(x);return}
 const title=document.createElement('div');title.className='selected-title';
 const orb=document.createElement('span');orb.className='selected-orb';orb.textContent=p.glyph;orb.style.color=scope==='natal'?'#77d9d5':'#c7b8ff';
 title.append(orb,document.createTextNode(p.name));root.append(title);
 appendKV(root,'CHART LAYER',scope==='natal'?'NATAL POINT':'CURRENT TRANSIT');
 appendKV(root,'POSITION',`${formatLongitude(p.longitude)} ${p.sign} ${p.sign_glyph}`);
 appendKV(root,'METHOD',String(p.method));
 if(scope==='natal')appendKV(root,'NATAL HOUSE',String(p.house));
 if(p.retrograde!==null)appendKV(root,'MOVEMENT',p.retrograde?'RETROGRADE':'DIRECT');
 const note=document.createElement('div');note.className='detail-highlight';note.textContent=(p.definition||'')+' Auxiliary scoring is configurable independently of line visibility.';root.append(note);
 const related=[...(data.auxiliary_aspects||[]),...(data.auxiliary_sky_aspects||[])].filter(a=>
   (scope==='transit'&&a.source_auxiliary&&a.source===p.name)||
   (scope==='natal'&&a.target_auxiliary&&a.target===p.name));
 if(related.length){
   const h=document.createElement('div');h.className='field-label padtop';h.textContent=`AUXILIARY CONNECTIONS (${related.length})`;root.append(h);
   related.slice(0,9).forEach(a=>{
     const e=document.createElement('div');e.className='aux-aspect-entry';
     const sym=document.createElement('span');sym.className='aux-aspect-symbol';sym.textContent=a.symbol;
     sym.style.color=a.kind==='support'?theme.blue:a.kind==='tension'?theme.red:theme.gold;
     const text=document.createElement('span');text.textContent=`${a.source} ${a.symbol} ${a.target} · ${num(a.orb,2)}° · ${a.phase}`;
     e.append(sym,text);root.append(e);
   });
   if(related.length>9){const x=document.createElement('p');x.className='micro';x.textContent=`${related.length-9} additional matches appear in AI Export.`;root.append(x)}
 }else{const x=document.createElement('p');x.className='micro';x.textContent='No auxiliary aspects within the selected orb.';root.append(x)}
}
function appendKV(root,k,v){const r=document.createElement('div');r.className='kv';const a=document.createElement('span');a.textContent=k;const b=document.createElement('strong');b.textContent=v;r.append(a,b);root.appendChild(r)}
function selectPlanet(name){state.selected={type:'planet',name};renderSelected();renderPlanetStrip()}
function selectAspect(a){state.selected={type:'aspect',transit:a.transit,natal:a.natal,aspect:a.type};renderSelected();renderPlanetStrip()}
function renderSelected(){const root=$('selected-detail');root.replaceChildren();const data=state.snapshot;if(!data)return;if(state.selected.type==='aux'){renderAuxDetail(root,data);return;}let p=data.transits.find(t=>t.name===state.selected.name)||data.transits.find(t=>t.name==='Saturn');let asp=null;
if(state.selected.type==='aspect')asp=data.transit_to_natal_aspects.find(a=>a.transit===state.selected.transit&&a.natal===state.selected.natal&&a.type===state.selected.aspect);
if(asp)p=data.transits.find(t=>t.name===asp.transit);
if(!p)return;
const title=document.createElement('div');title.className='selected-title';const orb=document.createElement('span');orb.className='selected-orb';orb.textContent=p.glyph;orb.style.color=colorOfPlanet(p.name);title.append(orb,document.createTextNode(asp?`${asp.transit} ${asp.symbol} ${asp.natal}`:`${p.name} / ${p.sign}`));root.appendChild(title);
appendKV(root,'TRANSIT POSITION',`${formatLongitude(p.longitude)} ${p.sign} ${p.sign_glyph}`);
appendKV(root,'MOVEMENT',p.retrograde?'RETROGRADE':'DIRECT');
if(asp){appendKV(root,'ASPECT',`${asp.type.toUpperCase()} (${asp.angle}°)`);appendKV(root,'ORB',`${num(asp.orb,2)}° · ${(asp.phase|| (asp.applying?'applying':'separating')).toUpperCase()}`);appendKV(root,'NATAL TARGET',asp.natal);appendKV(root,'NATAL HOUSE',asp.house||'ANGLE');appendKV(root,'INTERPRETIVE WEIGHT',(asp.value>0?'+':'')+num(asp.value,2));}else{const position=data.planet_status.find(x=>x.name===p.name);appendKV(root,'NET SIGNAL',(position.value>0?'+':'')+num(position.value,2));appendKV(root,'NATAL ASPECTS',position.aspects)}
const matches=data.transit_to_natal_aspects.filter(a=>a.transit===p.name).slice(0,5);
if(matches.length){const h=document.createElement('div');h.className='field-label padtop';h.textContent='ACTIVE NATAL CONNECTIONS';root.appendChild(h);matches.forEach(a=>{const b=document.createElement('button');b.className='list-entry';const i=document.createElement('i');i.textContent=a.symbol;i.style.color=a.nature==='tension'?theme.red:a.nature==='support'?theme.blue:theme.gold;const t=document.createElement('span');const d=document.createElement('span');d.className='entry-title';d.textContent=`${a.type.toUpperCase()} NATAL ${a.natal.toUpperCase()}`;const s=document.createElement('span');s.className='entry-sub';s.textContent=`${num(a.orb,2)}° orb · ${a.phase||(a.applying?'applying':'separating')} · house ${a.house||'angle'}`;t.append(d,s);b.append(i,t);b.onclick=()=>selectAspect(a);root.appendChild(b)})}else{const empty=document.createElement('p');empty.className='micro';empty.textContent='No major aspects to natal targets within the configured orbs.';root.append(empty)}
const auxMatches=(data.auxiliary_aspects||[]).filter(a=>!a.source_auxiliary&&a.source===p.name);
if(auxMatches.length){const label=document.createElement('div');label.className='field-label padtop';label.textContent=`AUXILIARY NATAL LINKS (${auxMatches.length})`;root.append(label);
  auxMatches.slice(0,6).forEach(a=>{const e=document.createElement('div');e.className='aux-aspect-entry';const symbol=document.createElement('span');symbol.className='aux-aspect-symbol';symbol.style.color=a.kind==='support'?theme.blue:a.kind==='tension'?theme.red:theme.gold;symbol.textContent=a.symbol;const text=document.createElement('span');text.textContent=`${a.type.toUpperCase()} · ${a.target} · ${num(a.orb,2)}°`;e.append(symbol,text);root.append(e)})}
const note=document.createElement('div');note.className='detail-highlight';note.textContent='Natal aspect weights and colors reflect an interpretable astrological model. They are not a measure of physical danger.';root.append(note);
}
function renderNatal(){const data=state.snapshot;if(!data)return;const table=$('natal-table');table.replaceChildren();const b=data.birth_profile.birth;$('natal-meta').textContent=`${data.birth_profile.label} · ${b.date} at ${b.time} (${b.timezone}) · lat ${num(b.latitude,4)}°, lon ${num(b.longitude,4)}° · ${state.zodiac.toUpperCase()} / ${state.house.toUpperCase()}`;
for(const p of data.natal.positions){const row=document.createElement('tr');for(const str of [`${p.glyph}  ${p.name}`,formatLongitude(p.longitude),`${p.sign_glyph} ${p.sign}`,String(p.house),p.retrograde?'R':'D']){const c=document.createElement('td');c.textContent=str;row.append(c)}table.append(row)}
const at=$('natal-aux-table');at.replaceChildren();
 for(const p of data.natal.auxiliary_points||[]){const row=document.createElement('tr');for(const value of [`${p.glyph}  ${p.name}`,formatLongitude(p.longitude),`${p.sign_glyph} ${p.sign}`,String(p.house),p.method]){const c=document.createElement('td');c.textContent=value;row.append(c)}at.append(row)}
 const comp=$('natal-comparison');comp.replaceChildren();const v=data.verification;const header=document.createElement('div');header.className='verification-heading';header.textContent=v.status==='review'?`⚠ ${v.differences.length} differences detected against the revised PDF`:v.status==='match'?'✓ Reference chart matches calculations':(v.message||'No external reference chart attached.');comp.append(header);
if(v.status==='review'){const txt=document.createElement('p');txt.className='micro';txt.textContent=v.method;comp.append(txt);if(v.time_diagnostic?.one_hour_offset_match){const diag=document.createElement('div');diag.className='detail-highlight';diag.textContent='CLOCK / DST CHECK: '+v.time_diagnostic.one_hour_offset_match.message+` Birth UTC: ${v.time_diagnostic.resolved_utc}. Reference-like UTC: ${v.time_diagnostic.one_hour_offset_match.alternate_utc}.`;comp.append(diag)}v.differences.forEach(diff=>{const x=document.createElement('div');x.className='issue';const s=document.createElement('strong');s.textContent=diff.item.toUpperCase();const tiny=document.createElement('small');tiny.textContent=diff.message;x.append(s,tiny);comp.append(x)})}else{const p=document.createElement('p');p.className='micro';p.textContent=v.message;comp.append(p)}
const ephem=document.createElement('div');ephem.className='detail-highlight';ephem.textContent=`Ephemeris: ${data.ephemeris.engine} ${data.ephemeris.version}. These numbers are recalculated from the birth details rather than copied from the PDF.`;comp.append(ephem);
}
function updateForecast(){const f=state.forecast;if(!f)return;$('relief-date').textContent=`${fmtDate(f.lowest.at_utc)} · ${num(f.lowest.difficulty)}/10`;$('pressure-date').textContent=`${fmtDate(f.highest.at_utc)} · ${num(f.highest.difficulty)}/10`;$('forecast-low').textContent=`${fmtDate(f.lowest.at_utc,true)} · ${num(f.lowest.difficulty)}/10`;$('forecast-high').textContent=`${fmtDate(f.highest.at_utc,true)} · ${num(f.highest.difficulty)}/10`;$('forecast-range').textContent=`${fmtDate(f.start_utc)} → ${fmtDate(f.samples[f.samples.length-1].at_utc)}`;if(state.view==='observatory')drawGraph($('spark'),f.samples,true);if(state.view==='forecast')drawGraph($('forecast-canvas'),f.samples,false);syncTimelinePreview()}
function hiDpiCanvas(canvas){const box=canvas.getBoundingClientRect();const dpr=Math.min(2,window.devicePixelRatio||1);const w=Math.max(1,box.width),h=Math.max(1,box.height);const pxW=Math.floor(w*dpr),pxH=Math.floor(h*dpr);if(canvas.width!==pxW||canvas.height!==pxH){canvas.width=pxW;canvas.height=pxH}const ctx=canvas.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);return {ctx,w,h}}
function drawGraph(canvas,samples,compact){if(!canvas||!samples?.length||canvas.getClientRects().length===0)return;const bounds=canvas.getBoundingClientRect();if(bounds.width<8||bounds.height<8)return;const{ctx,w,h}=hiDpiCanvas(canvas);ctx.clearRect(0,0,w,h);const left=compact?4:44,right=compact?4:18,top=compact?8:20,bottom=compact?5:30;const pw=w-left-right,ph=h-top-bottom;const min=1,max=10;const xy=(s,i)=>[left+i/(samples.length-1)*pw,top+(max-s.difficulty)/(max-min)*ph];
if(!compact){ctx.font='10px Segoe UI';ctx.textAlign='right';for(let value=2;value<=10;value+=2){const y=top+(10-value)/9*ph;ctx.strokeStyle='#26546a65';ctx.beginPath();ctx.moveTo(left,y);ctx.lineTo(w-right,y);ctx.stroke();ctx.fillStyle='#759bac';ctx.fillText(value+'/10',left-7,y+3)}ctx.textAlign='left';ctx.fillText(fmtDate(samples[0].at_utc),left,h-9);ctx.textAlign='right';ctx.fillText(fmtDate(samples.at(-1).at_utc),w-right,h-9)}
const grad=ctx.createLinearGradient(0,top,0,top+ph);grad.addColorStop(0,'#f47662');grad.addColorStop(.55,'#e5b768');grad.addColorStop(1,'#4fcba8');ctx.beginPath();samples.forEach((s,i)=>{const[x,y]=xy(s,i);i===0?ctx.moveTo(x,y):ctx.lineTo(x,y)});ctx.strokeStyle=grad;ctx.lineWidth=compact?2:3;ctx.shadowColor='#5be2f9';ctx.shadowBlur=compact?5:12;ctx.stroke();ctx.shadowBlur=0;
const first=xy(samples[0],0),last=xy(samples.at(-1),samples.length-1);ctx.lineTo(last[0],top+ph);ctx.lineTo(first[0],top+ph);ctx.closePath();const area=ctx.createLinearGradient(0,top,0,top+ph);area.addColorStop(0,'#d56b583b');area.addColorStop(1,'#0b9cbb0b');ctx.fillStyle=area;ctx.fill();
 if(!compact&&state.forecast?.samples===samples){
  const i=Math.min(samples.length-1,Math.max(0,state.timelineIndex));
  const [tx,ty]=xy(samples[i],i);
  ctx.save();ctx.strokeStyle='#8ceff9';ctx.lineWidth=1;ctx.setLineDash([3,5]);ctx.globalAlpha=.68;
  ctx.beginPath();ctx.moveTo(tx,top);ctx.lineTo(tx,top+ph);ctx.stroke();ctx.setLineDash([]);
  ctx.shadowColor='#81ffff';ctx.shadowBlur=14;ctx.fillStyle='#061a26';
  ctx.beginPath();ctx.arc(tx,ty,6.5,0,Math.PI*2);ctx.fill();
  ctx.strokeStyle='#bafffc';ctx.lineWidth=2;ctx.stroke();ctx.restore();
 }
}

// The timeline uses already calculated forecast samples for instant scrubbing.
// Only loading the chosen moment requests a fresh precise snapshot from the local engine.
function syncTimelinePreview(){
 const f=state.forecast,range=$('timeline-scrub');
 if(!f?.samples?.length){
  $('timeline-selected-date').textContent='AWAITING FORECAST';
  $('timeline-selected-score').textContent='—';
  $('timeline-selected-count').textContent='';
  $('timeline-inspect').disabled=true;
  $('timeline-prev').disabled=true;$('timeline-next').disabled=true;range.disabled=true;
  return;
 }
 const key=f.start_utc+'|'+f.days+'|'+f.samples.length;
 if(state.timelineKey!==key){state.timelineKey=key;state.timelineIndex=0}
 const i=Math.min(f.samples.length-1,Math.max(0,state.timelineIndex));state.timelineIndex=i;
 const point=f.samples[i];
 range.disabled=false;range.max=String(f.samples.length-1);range.value=String(i);
 $('timeline-selected-date').textContent=fmtDate(point.at_utc,true);
 $('timeline-selected-score').textContent=`${num(point.difficulty)} / 10`;
 $('timeline-selected-count').textContent=`SAMPLE ${i+1} / ${f.samples.length} · ${f.sampling_hours}H INTERVALS`;
 $('timeline-prev').disabled=i<=0;$('timeline-next').disabled=i>=f.samples.length-1;
 $('timeline-inspect').disabled=false;
 if(state.view==='forecast')drawGraph($('forecast-canvas'),f.samples,false);
}
function selectTimelineIndex(index){
 if(!state.forecast?.samples?.length)return;
 state.timelineIndex=Math.min(state.forecast.samples.length-1,Math.max(0,Math.round(index)));
 syncTimelinePreview();
}
function timelineIndexFromPointer(e){
 const canvas=$('forecast-canvas');const box=canvas.getBoundingClientRect();
 // Keep pointer mapping identical to drawGraph's non-compact left/right margins.
 const fraction=Math.max(0,Math.min(1,(e.clientX-box.left-44)/Math.max(1,box.width-44-18)));
 return Math.round(fraction*Math.max(0,(state.forecast?.samples?.length||1)-1));
}
function loadTimelineMoment(){
 const sample=state.forecast?.samples?.[state.timelineIndex];if(!sample)return toast('Forecast samples are still loading.');
 const date=new Date(sample.at_utc);
 if(!Number.isFinite(date.getTime()))return toast('The selected forecast date is invalid.');
 state.shift=0;state.chosenDate=date;
 $('time-slider').value='0';$('time-shift').textContent='SELECTED MOMENT';$('custom-date').value=dateToLocalInput(date);
 updateClock();setView('observatory');refresh();
 toast(`Observatory set to ${fmtDate(date,true)}. Use RETURN TO LIVE to restore current transits.`);
}
function returnToLive(){
 state.shift=0;state.chosenDate=null;
 $('time-slider').value='0';$('time-shift').textContent='TODAY';$('custom-date').value=dateToLocalInput(new Date());
 updateClock();refresh();
}
function initTimeline(){
 const canvas=$('forecast-canvas');
 $('timeline-scrub').oninput=e=>selectTimelineIndex(Number(e.target.value));
 $('timeline-prev').onclick=()=>selectTimelineIndex(state.timelineIndex-1);
 $('timeline-next').onclick=()=>selectTimelineIndex(state.timelineIndex+1);
 $('timeline-inspect').onclick=loadTimelineMoment;
 $('observatory-return-live').onclick=returnToLive;
 $('header-return-live').onclick=returnToLive;
 // Pointer capture allows click and drag on the chart itself; the range below
 // remains keyboard accessible for precise single-sample navigation.
 const choose=e=>{if(!state.forecast?.samples?.length)return;selectTimelineIndex(timelineIndexFromPointer(e))};
 canvas.addEventListener('pointerdown',e=>{if(!state.forecast?.samples?.length)return;canvas.setPointerCapture?.(e.pointerId);choose(e)});
 canvas.addEventListener('pointermove',e=>{if(e.buttons&1)choose(e)});
 canvas.addEventListener('pointerup',e=>{if(canvas.hasPointerCapture?.(e.pointerId))canvas.releasePointerCapture(e.pointerId)});
}
function setDays(n){state.days=n;state.forecast=null;syncTimelinePreview();updateExport();$all('[data-days]').forEach(b=>b.classList.toggle('active',Number(b.dataset.days)===n));refreshForecast()}
function composeExport(){const data=state.snapshot;if(!data)return{report:'Loading…',json:{}};const opts={positions:$('export-positions').checked,aspects:$('export-aspects').checked,forecast:$('export-forecast').checked,verification:$('export-verification').checked};const content={app:'Astral Sentinel',version:'1.0.0',generated_at:new Date().toISOString(),chart_time:data.at_utc,
 context:{time_mode:isSimulated()?'simulated':'live',house_system:state.house,house_method:state.houseMethod,zodiac:state.zodiac,projection:state.mode,auxiliary_display:{enabled:state.showAux,natal_points:state.showNatalPoints,chiron:state.showChiron},node_mode:state.nodeMode,lilith_mode:state.lilithMode,aux_aspect_lines:state.showAuxAspects,aux_aspect_filter:state.auxAspectFilter,aux_orb:state.auxOrb,aux_scoring:state.auxScoring,source:'Swiss Ephemeris Moshier analytical calculations',interpretive_model:data.score.method},
 birth_profile:data.birth_profile,score:data.score,auxiliary_scoring:data.auxiliary_scoring,model_caveat:data.interpretation_note};
if(opts.positions){content.natal=data.natal;content.transits=data.transits;content.planet_status=data.planet_status;content.auxiliary_transits=data.auxiliary_transits;content.auxiliary_unavailable=data.auxiliary_unavailable;content.auxiliary_meta=data.auxiliary_meta}
if(opts.aspects){content.aspects=data.transit_to_natal_aspects;content.sky_aspects=data.sky_aspects;content.auxiliary_aspects=data.auxiliary_aspects;content.auxiliary_sky_aspects=data.auxiliary_sky_aspects}
if(opts.forecast){content.forecast=state.forecast;content.forecast_status=state.forecast?'complete':'pending'}
if(opts.verification){content.verification=data.verification}
const lines=[`# ASTRAL SENTINEL / PORTABLE ASTROLOGY REPORT`,`Generated: ${new Date().toLocaleString()}`,`Chart time: ${fmtDate(data.at_utc,true)} (${isSimulated()?'simulation':'live'})`,'',`## Calculation settings`,`Zodiac: ${state.zodiac} | Houses: ${state.house} | Placement method: ${state.houseMethod} | Ephemeris: ${data.ephemeris.engine}`,
`Birth chart: ${data.birth_profile.label}`,`Natal date and time: ${data.birth_profile.birth.date} ${data.birth_profile.birth.time} ${data.birth_profile.birth.timezone}`,
`Birth coordinates: ${data.birth_profile.birth.latitude}, ${data.birth_profile.birth.longitude}`,`Auxiliary modes: Nodes=${state.nodeMode} | Lilith=${state.lilithMode} | orb ${state.auxOrb}° | display: ${state.showAuxAspects?'on':'off'} | filter ${state.auxAspectFilter}; scoring ${state.auxScoring?'ON':'OFF'} (independent of visual orb)`,'',`## Interpretation index`,`Difficulty: ${data.score.difficulty}/10 (${data.score.status})`,`Planetary baseline: ${data.score.planetary_baseline}/10; auxiliary modifier: ${data.score.auxiliary_modifier}; composite: ${data.score.difficulty}/10`, `Tension subtotal: ${data.score.tension}; support subtotal: ${data.score.support}`,`Formula: ${data.score.formula}`,`Auxiliary scoring: ${data.auxiliary_scoring.enabled?'ENABLED':'DISABLED'}; weights ${JSON.stringify(data.auxiliary_scoring.weights)}; capped ±${data.auxiliary_scoring.max_abs_modifier}`,'', '## Auxiliary score contributions',...(data.auxiliary_scoring.entries||[]).map(a=>`${a.source} ${a.type} natal ${a.target} | value ${a.value>=0?'+':''}${num(a.value,3)} | ${a.nature}`),''];
if(opts.positions){lines.push('## Natal planets');data.natal.positions.forEach(p=>lines.push(`${p.name}: ${formatLongitude(p.longitude)} ${p.sign} | House ${p.house}${p.retrograde?' R':''} | longitude ${num(p.longitude,5)}°`));lines.push(`Ascendant: ${num(data.natal.angles.Ascendant,5)}° | MC: ${num(data.natal.angles.Midheaven,5)}°`,'','## Current transit planets');data.transits.forEach(p=>lines.push(`${p.name}: ${num(p.longitude,5)}° ${p.sign}${p.retrograde?' R':''}`));lines.push('','## Additional natal points');(data.natal.auxiliary_points||[]).forEach(p=>lines.push(`${p.name}: ${formatLongitude(p.longitude)} ${p.sign} | House ${p.house} | method ${p.method} | longitude ${num(p.longitude,5)}°`));
 lines.push('','## Auxiliary transit points');(data.auxiliary_transits||[]).forEach(p=>lines.push(`${p.name}: ${formatLongitude(p.longitude)} ${p.sign} | method ${p.method} | longitude ${num(p.longitude,5)}°`));
 (data.auxiliary_unavailable||[]).forEach(p=>lines.push(`${p.name}: unavailable (${p.reason})`));
 lines.push('Auxiliary transit-to-natal aspects have an optional capped influence on the difficulty score; sky-to-sky auxiliary aspects remain unscored.','')}
if(opts.aspects){lines.push('## Transit-to-natal aspects');data.transit_to_natal_aspects.forEach(a=>lines.push(`${a.transit} ${a.symbol} natal ${a.natal} | ${a.type} | orb ${num(a.orb,3)}° | ${a.phase||(a.applying?'applying':'separating')} | house ${a.house||'angle'} | signal ${(a.value>0?'+':'')+num(a.value,3)}`));lines.push('')}
if(opts.aspects){
 lines.push('## Auxiliary transit-to-natal aspects (optional scoring layer)');
 (data.auxiliary_aspects||[]).forEach(a=>lines.push(`${a.source} ${a.symbol} natal ${a.target} | ${a.category} | ${a.type} | orb ${num(a.orb,3)}° | ${a.phase} | within scoring orb: ${a.orb<=2?'yes':'no'} (actual entries listed in scoring breakdown)`));
 lines.push('','## Auxiliary-to-current-planet aspects (UNSCORED)');
 (data.auxiliary_sky_aspects||[]).forEach(a=>lines.push(`${a.source} ${a.symbol} ${a.target} | ${a.type} | orb ${num(a.orb,3)}° | ${a.phase} | scored: NO`));
 lines.push('');
}
if(opts.forecast && !state.forecast){lines.push('## Forecast: pending calculation','')}
if(opts.forecast && state.forecast){lines.push(`## ${state.forecast.days}-day forecast (${state.forecast.sampling_hours}h sampling)`,`Lowest sampled score: ${num(state.forecast.lowest.difficulty)}/10 at ${state.forecast.lowest.at_utc}`,`Highest sampled score: ${num(state.forecast.highest.difficulty)}/10 at ${state.forecast.highest.at_utc}`,'')}
if(opts.verification){lines.push('## Source chart cross-check',data.verification.message);if(data.verification.time_diagnostic?.one_hour_offset_match)lines.push(data.verification.time_diagnostic.one_hour_offset_match.message);data.verification.differences?.forEach(d=>lines.push('- '+d.message));lines.push('')}
lines.push('## Instructions for AI interpretation','Use these exact calculations and settings. Distinguish supplied reference-chart labels from recalculated natal houses. Explain orb, timing and rulership assumptions. Treat the difficulty score as an adjustable astrological framework, not a physical safety prediction. Suggest corrections to this app when warranted.');
return{report:lines.join('\n'),json:content}}

function renderHouseMethod(){
 const show=state.house==='placidus';
 $('house-method-heading').classList.toggle('hidden',!show);
 $('house-method-select').classList.toggle('hidden',!show);
 $('house-method-note').classList.toggle('hidden',!show);
 $('house-method-select').value=state.houseMethod;
 $('house-method-note').textContent=state.houseMethod==='spatial'
  ?'Advanced 3D house position considers ecliptic latitude and can differ from conventional drawn charts.'
  :'Standard chart-wheel placement uses zodiacal longitude between Placidus cusps.';
}
async function completeExport(){
 if(!state.snapshot)throw Error('Planetary chart has not loaded yet.');
 if($('export-forecast').checked){
   const originalTime=state.snapshot.at_utc;
   const house=state.house, method=state.houseMethod, zodiac=state.zodiac, days=state.days;
   const node=state.nodeMode, lilith=state.lilithMode, auxScoring=state.auxScoring;
   const requestId=state.requestId;
   const profileId=state.snapshot?.birth_profile?.id;
   const correct=state.forecast && state.forecast.start_utc===originalTime &&
     state.forecast.days===days && state.forecast.house_system===house &&
     state.forecast.house_method===method && state.forecast.zodiac===zodiac && state.forecast.node_mode===node && state.forecast.lilith_mode===lilith && state.forecast.aux_scoring===auxScoring;
   if(!correct){
     $('export-feedback').textContent='Calculating the selected forecast before export…';
     const f=await api('/api/forecast',{at:originalTime,house,house_method:method,zodiac,days,node_mode:node,lilith_mode:lilith,aux_scoring:auxScoring});
     if(!state.snapshot || state.snapshot.at_utc!==originalTime || state.house!==house ||
        state.houseMethod!==method || state.zodiac!==zodiac || state.days!==days ||
        state.nodeMode!==node || state.lilithMode!==lilith || state.auxScoring!==auxScoring ||
        state.requestId!==requestId || state.snapshot.birth_profile?.id!==profileId){
       throw Error('The chart changed during export. Please try again.');
     }
     state.forecast=f;
     updateForecast();
   }
 }
 const result=composeExport();
 if(result.json.forecast_status==='pending')throw Error('Forecast calculation is incomplete.');
 $('export-feedback').textContent='Report ready. You can share it with ChatGPT or an offline LLM.';
 updateExport();
 return result;
}
async function exportAction(action){
 try{const result=await completeExport();await action(result)}
 catch(e){toast('Export error: '+e.message);$('export-feedback').textContent='Export not completed: '+e.message}
}

function updateExport(){const data=composeExport();$('export-preview').textContent=data.report}
function saveFile(filename,contents,type){const blob=new Blob([contents],{type});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=filename;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),5000)}
async function copyReport({report}){try{await navigator.clipboard.writeText(report);toast('Portable AI report copied to clipboard.')}catch(e){const t=document.createElement('textarea');t.value=report;document.body.append(t);t.select();document.execCommand('copy');t.remove();toast('Report copied.')}}

// Observation Log: explicit local saves, optional one-way Joplin note creation.
// Joplin token lives only in a password input, never localStorage or database.
let observationRecords=[];
let observationChartAt=null;
async function logPost(endpoint,body){
 const res=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 const result=await res.json();if(!res.ok)throw Error(result.error||`HTTP ${res.status}`);return result;
}
function observationReference(){
 const date=$('log-date').value;
 if(observationChartAt){$('log-chart-reference').textContent=`Using Observatory chart: ${new Date(observationChartAt).toLocaleString()} (${observationChartAt} UTC reference).`;return observationChartAt}
 const dateObject=new Date(`${date}T12:00:00`);
 $('log-chart-reference').textContent=Number.isFinite(dateObject.getTime())
  ?`Reference: ${dateObject.toLocaleString()} (local noon, independently calculated for this date).`
  :'Select a valid date.';
 return Number.isFinite(dateObject.getTime())?dateObject.toISOString():null;
}
function renderLogRecords(){
 const root=$('log-entries');root.replaceChildren();$('log-count').textContent=String(observationRecords.length);
 if(!observationRecords.length){const p=document.createElement('div');p.className='empty';p.textContent='No observations yet. Your first entry will appear here.';root.append(p);return;}
 for(const e of observationRecords){
  const card=document.createElement('article');card.className='log-entry';
  const top=document.createElement('div');top.className='log-entry-top';
  const title=document.createElement('strong');title.className='log-entry-date';title.textContent=e.date;
  const score=document.createElement('span');score.className='log-entry-scores';score.textContent=`Experienced ${Number(e.observed_difficulty).toFixed(1)}/10 · Model ${Number(e.predicted_difficulty).toFixed(1)}/10`;
  top.append(title,score);
  const p=document.createElement('p');p.className='log-entry-note';p.textContent=e.note;
  const meta=document.createElement('div');meta.className='log-entry-meta';meta.textContent=`Chart UTC ${e.chart_at_utc} · ${e.chart_settings.zodiac} / ${e.chart_settings.house_system}`;
  const actions=document.createElement('div');actions.className='log-entry-actions';
  const md=document.createElement('button');md.type='button';md.className='subtle-button';md.textContent='↓ Markdown';md.onclick=()=>downloadObservation(e.id);
  const send=document.createElement('button');send.type='button';send.className='subtle-button';send.textContent=e.joplin_note_id?'✓ Sent to Joplin':'⇧ Send to Joplin';send.disabled=!!e.joplin_note_id;send.onclick=()=>sendObservationToJoplin(e.id,send);
  const del=document.createElement('button');del.type='button';del.className='subtle-button log-delete';del.textContent='Delete';del.onclick=()=>deleteObservation(e.id);
  actions.append(md,send,del);card.append(top,p,meta,actions);root.append(card);
 }
}
function clientMarkdownEntry(e){
 const aspects=(e.leading_aspects||[]).map(x=>'- '+x).join('\n')||'- None';
 const s=e.chart_settings;
 return `# Astral Sentinel Observation · ${e.date}\n\n**Experienced difficulty:** ${Number(e.observed_difficulty).toFixed(1)}/10  \n**Astrological index:** ${Number(e.predicted_difficulty).toFixed(1)}/10  \n**Planetary baseline:** ${Number(e.planetary_baseline).toFixed(1)}/10  \n**Auxiliary adjustment:** ${Number(e.auxiliary_modifier).toFixed(2)}  \n**Chart UTC:** ${e.chart_at_utc}  \n**Settings:** ${s.zodiac} / ${s.house_system} / ${s.house_method}; nodes ${s.node_mode}, Lilith ${s.lilith_mode}, auxiliary scoring ${s.aux_scoring}\n\n## What happened / how it felt\n\n${e.note}\n\n## Leading planetary aspects\n\n${aspects}\n\n*Interpretive astrology, not a prediction of events or real-world risk.*\n`;
}
async function loadObservations(){
 try{const res=await fetch('/api/observations',{cache:'no-store'});const obj=await res.json();if(!res.ok)throw Error(obj.error||'Cannot open journal');observationRecords=obj.entries||[];renderLogRecords()}
 catch(err){$('log-save-status').textContent=`Journal error: ${err.message}`;toast(`Journal error: ${err.message}`)}
}
async function saveObservation(){
 const button=$('log-save');const at=observationReference();if(!at)return toast('Choose a valid date.');
 if(!$('log-note').value.trim())return toast('Write a brief observation first.');
 const date=$('log-date').value;
 const body={date,note:$('log-note').value,observed_difficulty:Number($('log-rating').value),chart_at_utc:at,
  options:{house:state.house,house_method:state.houseMethod,zodiac:state.zodiac,node_mode:state.nodeMode,lilith_mode:state.lilithMode,aux_scoring:state.auxScoring}};
 button.disabled=true;$('log-save-status').textContent='Calculating and saving the chart reference…';
 try{await logPost('/api/observations',body);$('log-note').value='';$('log-save-status').textContent='Observation saved on this PC.';await loadObservations();toast('Observation saved locally.');}
 catch(e){$('log-save-status').textContent=e.message;toast('Could not save: '+e.message)}finally{button.disabled=false}
}
async function deleteObservation(id){
 if(!confirm('Delete this observation from Astral Sentinel? A separately sent Joplin note will remain untouched.'))return;
 try{const r=await logPost('/api/observations/delete',{id});if(!r.deleted)throw Error('Observation not found.');await loadObservations();toast('Local observation deleted.');}
 catch(err){toast('Delete failed: '+err.message)}
}
function downloadObservation(id){
 const e=observationRecords.find(x=>x.id===id);if(!e)return;
 saveFile(`astral_observation_${e.date}_${id.slice(0,6)}.md`,clientMarkdownEntry(e),'text/markdown;charset=utf-8');toast('Observation Markdown downloaded.');
}
async function sendObservationToJoplin(id,button){
 const token=$('joplin-token').value.trim(),port=Number($('joplin-port').value);
 if(!token)return toast('Paste the API token from Joplin’s Web Clipper settings first.');
 if(!Number.isInteger(port)||port<41184||port>41194)return toast('Choose the Joplin Web Clipper port (41184–41194).');
 button.disabled=true;$('joplin-status').textContent='Creating note in local Joplin…';
 try{await logPost('/api/joplin/send',{id,token,port});$('joplin-status').textContent='Sent! Find it in the Astral Sentinel Observations notebook.';await loadObservations();toast('Observation sent to Joplin.');}
 catch(err){$('joplin-status').textContent=err.message;toast('Joplin: '+err.message);button.disabled=false;}
}
function initObservationLog(){
 $('log-date').value=dateToLocalInput(new Date()).slice(0,10);
 $('log-date').addEventListener('change',()=>{observationChartAt=null;observationReference()});
 $('log-rating').addEventListener('input',()=>{$('log-rating-label').textContent=`${$('log-rating').value} / 10`});
 $('log-use-chart').onclick=()=>{
  if(!state.snapshot)return toast('Observatory chart is not loaded yet.');
  observationChartAt=state.snapshot.at_utc;
  $('log-date').value=dateToLocalInput(new Date(observationChartAt)).slice(0,10);
  observationReference();toast('Using the currently loaded Observatory moment.');
 };
 $('log-save').onclick=saveObservation;
 $('open-observation-log').onclick=()=>$('observation-log-section').scrollIntoView({behavior:'smooth',block:'start'});
 $('log-export-md').onclick=()=>{if(!observationRecords.length)return toast('No observations to export.');const md='# Astral Sentinel · Observation Log\n\n'+observationRecords.map(clientMarkdownEntry).join('\n---\n\n');saveFile('astral_observation_log.md',md,'text/markdown;charset=utf-8');toast('Log exported as Markdown for Joplin or any editor.')};
 $('log-export-json').onclick=()=>{const contents=JSON.stringify({app:'Astral Sentinel',version:'1.0.0',format:'observation-log-backup',exported_at:new Date().toISOString(),entries:observationRecords},null,2);saveFile('astral_observation_log_backup.json',contents,'application/json;charset=utf-8');toast('Observation JSON backup saved.')};
 $('joplin-test').onclick=async()=>{
  const button=$('joplin-test');button.disabled=true;$('joplin-status').textContent='Checking local Joplin Web Clipper…';
  try{const response=await fetch('/api/joplin/status',{cache:'no-store'});const data=await response.json();if(!response.ok)throw Error(data.error||'Detection failed');$('joplin-status').textContent=data.message;if(data.port)$('joplin-port').value=data.port;}
  catch(e){$('joplin-status').textContent=e.message}finally{button.disabled=false}
 };
 observationReference();loadObservations();
}

function initUI(){
 $all('[data-tab]').forEach(b=>b.addEventListener('click',()=>setView(b.dataset.tab)));
 $all('[data-mode]').forEach(b=>b.addEventListener('click',()=>{state.mode=b.dataset.mode;$all('[data-mode]').forEach(x=>x.classList.toggle('active',x===b));renderControlLabels();if(state.mode==='solar')toast('Solar projection uses heliocentric positions. Aspect lines are shown in Zodiac mode.')}));
 for(const [id,field,callback] of [['toggle-aspects','showAspects',null],['toggle-natal','showNatal',renderPlanetStrip],['toggle-labels','showLabels',null],['toggle-alerts','showAlerts',renderWarnings]]){$(id).addEventListener('change',e=>{state[field]=e.target.checked;callback?.()})}
 for(const [id,key,rerender] of [['toggle-aux','showAux',true],['toggle-natal-points','showNatalPoints',true],['toggle-chiron','showChiron',true]]){
  $(id).addEventListener('change',e=>{state[key]=e.target.checked;if(rerender){renderAuxRegistry();renderPlanetStrip();if(state.selected.type==='aux')renderSelected()}updateExport()})
 }
 $('node-mode-select').onchange=e=>{state.nodeMode=e.target.value;refresh()};
 $('lilith-mode-select').onchange=e=>{state.lilithMode=e.target.value;refresh()};
 $('toggle-aux-aspects').onchange=e=>{state.showAuxAspects=e.target.checked;updateExport()};
 $('aux-aspect-filter').onchange=e=>{state.auxAspectFilter=e.target.value;updateExport()};
 $('aux-orb-select').onchange=e=>{state.auxOrb=Number(e.target.value);refresh()};
 $('toggle-aux-scoring').onchange=e=>{state.auxScoring=e.target.checked;$('aux-scoring-note').textContent=state.auxScoring?'Enabled: conservative 2° scoring, mirrored nodes deduplicated, ±0.65 cap.':'Disabled: use the original planetary-only difficulty model.';refresh()};
 $('house-select').onchange=e=>{state.house=e.target.value;renderHouseMethod();refresh()};$('house-method-select').onchange=e=>{state.houseMethod=e.target.value;renderHouseMethod();refresh()};$('zodiac-select').onchange=e=>{state.zodiac=e.target.value;refresh()};$all('[data-days]').forEach(b=>b.onclick=()=>setDays(Number(b.dataset.days)));
 $('open-forecast').onclick=()=>setView('forecast');$('quick-export').onclick=()=>setView('export');$('copy-report').onclick=()=>exportAction(copyReport);
 $('download-markdown').onclick=()=>exportAction(({report})=>{saveFile('astral_sentinel_report.md',report,'text/markdown;charset=utf-8');toast('Markdown report exported.')});
 $('download-json').onclick=()=>exportAction(({json})=>{saveFile('astral_sentinel_data.json',JSON.stringify(json,null,2),'application/json;charset=utf-8');toast('Structured JSON exported.')});
 $all('#view-export input[type=checkbox]').forEach(i=>i.onchange=updateExport);
 $('time-slider').addEventListener('input',e=>{const n=Number(e.target.value);$('time-shift').textContent=n===0?'TODAY':`${n>0?'+':''}${n} DAYS`});
 $('time-slider').addEventListener('change',e=>{state.shift=Number(e.target.value);state.chosenDate=null;$('custom-date').value=dateToLocalInput(whenDate());updateClock();refresh()});
 $('apply-date').onclick=()=>{const raw=$('custom-date').value;if(!raw)return toast('Enter a valid local date and time.');const date=new Date(raw);if(!Number.isFinite(date.getTime()))return toast('Enter a valid local date and time.');state.shift=0;state.chosenDate=date;$('time-slider').value='0';$('time-shift').textContent='CUSTOM DATE';updateClock();refresh()};
 $('return-now').onclick=returnToLive;
 $('custom-date').value=dateToLocalInput(new Date());initTimeline();initObservationLog();
 window.addEventListener('resize',()=>{resizeSky();if(state.forecast)updateForecast()});if(typeof ResizeObserver!=='undefined'){const graphResize=new ResizeObserver(()=>{if(state.forecast&&state.view==='observatory')drawGraph($('spark'),state.forecast.samples,true)});graphResize.observe($('spark'));}setInterval(()=>{updateClock();if(!state.shift&&!state.chosenDate&&!state.loading&&state.snapshot){if(Date.now()-new Date(state.snapshot.at_utc).getTime()>300000)refresh(false)}},30000);
}
// Holographic orbital map. Positions use actual computed longitude; distances are intentionally schematic.
const sky={canvas:null,ctx:null,w:0,h:0,cx:0,cy:0,R:0,hit:[],stars:[],t:0,hover:null,ptr:null};
function seeded(i){const x=Math.sin(i*128.754+83.71)*43758.5453;return x-Math.floor(x)}
function initSky(){sky.canvas=$('sky');for(let i=0;i<145;i++)sky.stars.push({x:seeded(i+5),y:seeded(i+654),r:.4+seeded(i+253)*1.3,alpha:.08+seeded(i+730)*.42});sky.canvas.addEventListener('mousemove',e=>{const r=sky.canvas.getBoundingClientRect();sky.ptr={x:e.clientX-r.left,y:e.clientY-r.top};const nearest=sky.hit.filter(p=>Math.hypot(p.x-sky.ptr.x,p.y-sky.ptr.y)<p.radius+7).sort((a,b)=>Math.hypot(a.x-sky.ptr.x,a.y-sky.ptr.y)-Math.hypot(b.x-sky.ptr.x,b.y-sky.ptr.y))[0];sky.hover=nearest||null;sky.canvas.style.cursor=nearest?'pointer':'crosshair';sky.canvas.title=nearest?`${nearest.name}${nearest.scope?' ('+nearest.scope+')':''} · select to inspect`:''});sky.canvas.addEventListener('mouseleave',()=>{sky.ptr=null;sky.hover=null});sky.canvas.addEventListener('click',()=>{if(sky.hover){if(sky.hover.scope)selectAuxPoint(sky.hover.name,sky.hover.scope);else selectPlanet(sky.hover.name);if(state.mode==='solar'&&sky.hover.name==='Earth')toast('Earth is included in Solar View as an astronomical marker.')}});resizeSky();if(typeof ResizeObserver!=='undefined'){sky.resizeObserver=new ResizeObserver(()=>resizeSky());sky.resizeObserver.observe(sky.canvas.parentElement)}requestAnimationFrame(drawSky)}
function resizeSky(){if(!sky.canvas)return;const d=hiDpiCanvas(sky.canvas);sky.ctx=d.ctx;sky.w=d.w;sky.h=d.h;sky.cx=d.w*.5;sky.cy=d.h*.52;sky.R=Math.min(d.w*.45,d.h*.415)}
function arcGlow(ctx,x,y,r,color,width=1,alpha=.5){ctx.save();ctx.strokeStyle=color;ctx.globalAlpha=alpha;ctx.shadowColor=color;ctx.shadowBlur=width===1?8:13;ctx.lineWidth=width;ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.stroke();ctx.restore()}
function colorHexAlpha(hex,a){return hex+Math.floor(Math.max(0,Math.min(a,1))*255).toString(16).padStart(2,'0')}
function polar(lon,r){const rad=(lon-90)*Math.PI/180;return{x:sky.cx+Math.cos(rad)*r,y:sky.cy+Math.sin(rad)*r}}
function paintPlanet(ctx,x,y,r,color,name,selected=false){ctx.save();const halo=ctx.createRadialGradient(x,y,r*.3,x,y,r*3.6);halo.addColorStop(0,colorHexAlpha(color,.32));halo.addColorStop(.45,colorHexAlpha(color,.18));halo.addColorStop(1,colorHexAlpha(color,0));ctx.fillStyle=halo;ctx.beginPath();ctx.arc(x,y,r*3.6,0,Math.PI*2);ctx.fill();const g=ctx.createRadialGradient(x-r*.38,y-r*.43,r*.04,x+r*.18,y+r*.2,r*1.3);g.addColorStop(0,'#f8ffff');g.addColorStop(.15,color);g.addColorStop(.55,colorHexAlpha(color,.8));g.addColorStop(1,'#04101a');ctx.fillStyle=g;ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.fill();ctx.lineWidth=1;ctx.strokeStyle=color;ctx.stroke();ctx.save();ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.clip();ctx.globalAlpha=.18;ctx.strokeStyle='#d6fcff';if(name==='Jupiter'||name==='Saturn'||name==='Neptune'){for(let k=-2;k<=3;k++){ctx.lineWidth=1.3;ctx.beginPath();ctx.moveTo(x-r,y+k*r*.35);ctx.bezierCurveTo(x-r*.3,y+k*r*.35-r*.23,x+r*.3,y+k*r*.35+r*.22,x+r,y+k*r*.35);ctx.stroke()}}else if(name==='Earth'){ctx.fillStyle='#9fff99';ctx.beginPath();ctx.ellipse(x-r*.1,y,r*.5,r*.24,.4,0,Math.PI*2);ctx.fill()}ctx.restore();if(name==='Saturn'){ctx.save();ctx.strokeStyle=color;ctx.lineWidth=2;ctx.globalAlpha=.75;ctx.beginPath();ctx.ellipse(x,y,r*1.55,r*.43,-.2,0,Math.PI*2);ctx.stroke();ctx.restore()}if(selected){ctx.strokeStyle='#e8ffff';ctx.lineWidth=1.2;ctx.setLineDash([3,4]);ctx.beginPath();ctx.arc(x,y,r+6,0,Math.PI*2);ctx.stroke()}ctx.restore()}
function drawSky(t){sky.t=t/1000;
// Skip costly canvas painting when another tab is visible or the page is hidden.
if(state.view!=='observatory'||document.hidden){requestAnimationFrame(drawSky);return}
const bounds=sky.canvas?.getBoundingClientRect();if(bounds&&(Math.abs(bounds.width-sky.w)>.5||Math.abs(bounds.height-sky.h)>.5))resizeSky();const ctx=sky.ctx;if(!ctx){requestAnimationFrame(drawSky);return}const {w,h,cx,cy,R}=sky;ctx.clearRect(0,0,w,h);
const back=ctx.createRadialGradient(cx,cy,4,cx,cy,Math.max(w,h)*.62);back.addColorStop(0,'#0c3b50');back.addColorStop(.23,'#0a2536');back.addColorStop(.67,'#071726');back.addColorStop(1,'#030b13');ctx.fillStyle=back;ctx.fillRect(0,0,w,h);
for(const s of sky.stars){ctx.globalAlpha=s.alpha*(.75+.25*Math.sin(s.x*15+sky.t*.35));ctx.fillStyle='#7addf3';ctx.fillRect(s.x*w,s.y*h,s.r,s.r)}ctx.globalAlpha=1;
// Observatory rings, azimuth guides and moving scan beam.
for(let k=0;k<48;k++){const angle=k*Math.PI*2/48;const r0=R*.93,r1=k%4===0?R*.997:R*.956;ctx.strokeStyle=k%4===0?'#49bbd15c':'#26718a35';ctx.lineWidth=k%4===0?1:.6;ctx.beginPath();ctx.moveTo(cx+Math.sin(angle)*r0,cy+Math.cos(angle)*r0);ctx.lineTo(cx+Math.sin(angle)*r1,cy+Math.cos(angle)*r1);ctx.stroke()}
for(let k=1;k<=8;k++){arcGlow(ctx,cx,cy,R*k/8,k===8?'#3aaed0':'#1b809a',k===8?1.4:.7,k===8?.55:.25)}
for(let k=0;k<12;k++){const ang=k*Math.PI/6-Math.PI/2;ctx.strokeStyle='#204c6070';ctx.beginPath();ctx.moveTo(cx+Math.cos(ang)*R*.09,cy+Math.sin(ang)*R*.09);ctx.lineTo(cx+Math.cos(ang)*R,cy+Math.sin(ang)*R);ctx.stroke();if(state.mode==='zodiac'&&state.showLabels){const p=polar(k*30+15,R*1.055);ctx.fillStyle='#5ab4c7';ctx.textAlign='center';ctx.textBaseline='middle';ctx.font=`${Math.max(13,Math.min(19,R*.060))}px 'Segoe UI Symbol'`;ctx.fillText(zodiacGlyphs[k],p.x,p.y)}}
ctx.save();ctx.translate(cx,cy);ctx.rotate(sky.t*.06);const sweep=ctx.createRadialGradient(0,0,R*.22,0,0,R);sweep.addColorStop(0,'#21f2ff00');sweep.addColorStop(1,'#1ac2f509');ctx.fillStyle=sweep;ctx.beginPath();ctx.moveTo(0,0);ctx.arc(0,0,R,0,.4);ctx.closePath();ctx.fill();ctx.restore();
const snap=state.snapshot;sky.hit=[];if(!snap){drawSun(ctx,cx,cy,R*.10);requestAnimationFrame(drawSky);return}
const solar=state.mode==='solar';const source=solar?snap.heliocentric:snap.transits;const selected=state.selected.type==='aspect'?state.selected.transit:state.selected.name;
const radial={Mercury:.20,Venus:.29,Earth:.39,Mars:.47,Jupiter:.58,Saturn:.67,Uranus:.75,Neptune:.83,Pluto:.90};
const position={};source.forEach((p,index)=>{let r;if(solar)r=R*(radial[p.name]??.85);else r=R*(.62+.026*index);position[p.name]=polar(p.longitude,r)});
const natalPos={};if(!solar&&state.showNatal){snap.natal.positions.forEach(p=>natalPos[p.name]=polar(p.longitude,R*.40));natalPos.Ascendant=polar(snap.natal.angles.Ascendant,R*.40);natalPos.Midheaven=polar(snap.natal.angles.Midheaven,R*.40)}
const auxTransit=solar?[]:activeAuxPoints();const auxNatal=solar?[]:activeNatalAuxPoints();
if(!solar&&state.showAspects){const aspectColor=a=>a.kind==='support'?theme.blue:a.kind==='tension'?theme.red:theme.gold;
 ctx.save();for(const a of snap.sky_aspects){const A=position[a.from],B=position[a.to];if(!A||!B)continue;ctx.beginPath();ctx.moveTo(A.x,A.y);ctx.lineTo(B.x,B.y);ctx.strokeStyle=aspectColor(a);ctx.globalAlpha=a.type==='conjunction'?.32:.38;ctx.lineWidth=.9;ctx.stroke()}
 if(state.showNatal){const candidates=snap.transit_to_natal_aspects.filter(a=>a.orb<2.6).slice(0,32);for(const a of candidates){const A=position[a.transit],B=natalPos[a.natal];if(!A||!B)continue;ctx.beginPath();ctx.moveTo(A.x,A.y);ctx.lineTo(B.x,B.y);ctx.setLineDash([3,5]);ctx.strokeStyle=a.nature==='support'?theme.blue:a.nature==='tension'?theme.red:theme.gold;ctx.globalAlpha=.33+a.strength*.45;ctx.lineWidth=a===candidates[0]?1.8:.95;ctx.stroke();ctx.setLineDash([])}}ctx.restore();$('visible-aspects').textContent=`${snap.sky_aspects.length+(state.showNatal?snap.transit_to_natal_aspects.filter(a=>a.orb<2.6).slice(0,32).length:0)} ASPECT LINKS`;
 }else{$('visible-aspects').textContent=solar?'HELIOCENTRIC PROJECTION':'ASPECT LINKS HIDDEN'}
// Auxiliary aspect geometry: dotted, softly glowing, lighter than the scored
// planet lines. All endpoints are positioned using the same map coordinates as
// their actual rendered markers. The display filter only changes presentation.
const auxLivePos={},auxNatalPos={};
auxTransit.forEach((p,i)=>{auxLivePos[p.name]=polar(p.longitude,R*(.51+(i%3)*.018))});
auxNatal.forEach((p,i)=>{auxNatalPos[p.name]=polar(p.longitude,R*.27)});
const drawnAuxLinks=visibleAuxiliaryLinks();
if(drawnAuxLinks.length){
 ctx.save();ctx.lineWidth=1.25;ctx.setLineDash([2,5]);
 for(const a of drawnAuxLinks){
   const start=a.source_auxiliary?auxLivePos[a.source]:position[a.source];
   const end=a.target_scope==='transit'?position[a.target]:(a.target_auxiliary?auxNatalPos[a.target]:natalPos[a.target]);
   if(!start||!end)continue;
   const isSelected=state.selected.type==='aux'&&((state.selected.scope==='transit'&&a.source_auxiliary&&a.source===state.selected.name)||(state.selected.scope==='natal'&&a.target_auxiliary&&a.target===state.selected.name));
   const tint=a.kind==='support'?'#9baeff':a.kind==='tension'?'#ff9baf':'#edd1a4';
   ctx.strokeStyle=tint;ctx.globalAlpha=isSelected?.87:(.24+.29*a.strength);ctx.lineWidth=isSelected?2.2:1.2;
   ctx.shadowColor='#bfa5ff';ctx.shadowBlur=isSelected?7:2;
   ctx.beginPath();ctx.moveTo(start.x,start.y);ctx.lineTo(end.x,end.y);ctx.stroke();
 }
 ctx.restore();
}
if(!solar&&state.showAuxAspects&&state.showAux){
 const label=$('visible-aspects');
 label.textContent+=(drawnAuxLinks.length?` · ${drawnAuxLinks.length} AUX`:' · 0 AUX');
}
if(!solar&&state.showNatal){ctx.save();for(const p of snap.natal.positions){const xy=natalPos[p.name];ctx.fillStyle='#5deaf0';ctx.globalAlpha=.75;ctx.fillRect(xy.x-2.2,xy.y-2.2,4.4,4.4);if(state.showLabels){ctx.fillStyle='#699eaf';ctx.font='10px Segoe UI Symbol';ctx.textAlign='center';ctx.fillText(p.glyph,xy.x,xy.y-7)}}for(const name of ['Ascendant','Midheaven']){const xy=natalPos[name];ctx.strokeStyle='#b7f5fa';ctx.lineWidth=1.1;ctx.strokeRect(xy.x-4,xy.y-4,8,8)}ctx.restore()}
// Orbital rings (schematic radial scale)
if(solar){Object.values(radial).forEach(r=>arcGlow(ctx,cx,cy,R*r,'#1b8fa9',.65,.33))}
for(const p of source){const xy=position[p.name];const color=p.name==='Earth'?theme.cyan:colorOfPlanet(p.name);const radius=solar?(p.name==='Jupiter'?12:p.name==='Saturn'?11:p.name==='Earth'?11:9):Math.max(8,Math.min(13,R*.045));const pick=selected===p.name;paintPlanet(ctx,xy.x,xy.y,radius,color,p.name,pick||sky.hover?.name===p.name);sky.hit.push({name:p.name,x:xy.x,y:xy.y,radius});if(state.showLabels){ctx.save();ctx.textAlign='center';ctx.fillStyle='#d1f7ff';ctx.shadowColor=color;ctx.shadowBlur=8;ctx.font=`${Math.max(16,Math.min(21,R*.065))}px 'Segoe UI Symbol','Segoe UI'`;ctx.fillText(p.glyph,xy.x,xy.y-radius-9);ctx.shadowBlur=0;ctx.fillStyle='#7ea8b8';ctx.font='9px Segoe UI';ctx.fillText(p.name.toUpperCase(),xy.x,xy.y+radius+17);ctx.restore()}}
if(!solar){
 // Lunar nodes, apogee, and optional Chiron are not rendered as planets.
 // The diamond/cross marker distinguishes mathematical points from spherical bodies.
 const drawMarker=(p,scope,idx)=>{
   const r=scope==='natal'?R*.27:R*(.51+(idx%3)*.018);const xy=polar(p.longitude,r);
   const chosen=state.selected.type==='aux'&&state.selected.name===p.name&&state.selected.scope===scope;
   const color=scope==='natal'?'#79dcd4':'#c7b8ff';
   ctx.save();ctx.translate(xy.x,xy.y);ctx.strokeStyle=color;ctx.fillStyle=scope==='natal'?'#174b54':'#3d2c5b';ctx.lineWidth=1.4;
   ctx.shadowColor=color;ctx.shadowBlur=chosen?19:9;
   ctx.beginPath();ctx.moveTo(0,-6);ctx.lineTo(6,0);ctx.lineTo(0,6);ctx.lineTo(-6,0);ctx.closePath();ctx.fill();ctx.stroke();
   if(chosen){ctx.beginPath();ctx.arc(0,0,10,0,Math.PI*2);ctx.stroke()}
   if(state.showLabels){ctx.shadowBlur=0;ctx.fillStyle='#e6dcff';ctx.textAlign='center';ctx.font='15px Segoe UI Symbol,Segoe UI';ctx.fillText(p.glyph,0,-11)}
   ctx.restore();sky.hit.unshift({name:p.name,scope,x:xy.x,y:xy.y,radius:11});
 };
 auxNatal.forEach((p,i)=>drawMarker(p,'natal',i));auxTransit.forEach((p,i)=>drawMarker(p,'transit',i));
}
if(solar){const earth=position.Earth;const moon=snap.transits.find(p=>p.name==='Moon');if(earth&&moon){const m=polar(moon.longitude,R*.06);paintPlanet(ctx,earth.x+(m.x-cx),earth.y+(m.y-cy),4,theme.white,'Moon',false)}}
if(solar)drawSun(ctx,cx,cy,R*.103);else drawEarth(ctx,cx,cy,R*.092);
// HUD readouts around the inner ring
ctx.save();ctx.fillStyle='#3b9eaf';ctx.textAlign='center';ctx.font='10px Consolas,monospace';ctx.fillText(solar?'SOL / HELIOCENTRIC':'TERRA / GEOCENTRIC',cx,cy+R*.155);ctx.restore();
requestAnimationFrame(drawSky)}
function drawEarth(ctx,x,y,r){paintPlanet(ctx,x,y,r,'#61cce1','Earth',false);ctx.save();ctx.fillStyle='#defaff';ctx.textAlign='center';ctx.textBaseline='middle';ctx.font=`${r*.85}px 'Segoe UI Symbol'`;ctx.fillText('⊕',x,y+1);ctx.restore()}
function drawSun(ctx,x,y,r){ctx.save();const halo=ctx.createRadialGradient(x,y,r*.4,x,y,r*2.6);halo.addColorStop(0,'#ffba4f75');halo.addColorStop(.5,'#d89b2144');halo.addColorStop(1,'#f7a31500');ctx.fillStyle=halo;ctx.beginPath();ctx.arc(x,y,r*2.6,0,Math.PI*2);ctx.fill();const g=ctx.createRadialGradient(x-r*.23,y-r*.2,1,x,y,r*1.2);g.addColorStop(0,'#fffce2');g.addColorStop(.32,'#ffed9c');g.addColorStop(.75,'#ecab49');g.addColorStop(1,'#ad632b');ctx.fillStyle=g;ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.fill();ctx.strokeStyle='#ffe5aa';ctx.lineWidth=1;ctx.shadowColor='#ffd276';ctx.shadowBlur=19;ctx.stroke();ctx.fillStyle='#fff0b6';ctx.textAlign='center';ctx.textBaseline='middle';ctx.font=`${r*.9}px 'Segoe UI Symbol'`;ctx.fillText('☉',x,y+1);ctx.restore()}
initUI();initSignalScroll();initSky();refresh();
