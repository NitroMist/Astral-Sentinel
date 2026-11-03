/* Astral Sentinel v1.0.0: local multi-person birth chart manager. AGPL-3.0-or-later. */
'use strict';
const profilesUI={items:[],activeId:null,editing:false,cityRequest:0};
const profEl=id=>document.getElementById(id);
async function profileAPI(route,payload){
 const res=await fetch(route,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
 const data=await res.json();if(!res.ok)throw Error(data.error||`HTTP ${res.status}`);return data;
}
function activeBirthProfile(){return profilesUI.items.find(p=>p.id===profilesUI.activeId)||null}
function resetCurrentChart(){
 state.selected={type:'planet',name:'Saturn'};
 state.shift=0;state.chosenDate=null;
 profEl('time-slider').value='0';profEl('custom-date').value=dateToLocalInput(new Date());
 updateClock();refresh();
}
function adoptProfileOptions(p){
 if(p?.default_house_system)state.house=p.default_house_system;
 if(p?.default_zodiac)state.zodiac=p.default_zodiac;
 profEl('house-select').value=state.house;
 profEl('zodiac-select').value=state.zodiac;
 renderHouseMethod();
}
function setProfileEditor(mode){
 const editor=profEl('profile-editor');const p=activeBirthProfile();
 profilesUI.editing=mode==='edit';
 editor.open=true;
 profEl('profile-editor-title').textContent=profilesUI.editing?`EDIT BIRTH CHART · ${p?.label||''}`:'NEW BIRTH CHART · ENTER BIRTH DETAILS';
 const val=(id,v)=>{profEl(id).value=v??''};
 const b=profilesUI.editing?p?.birth||{}:{};
 val('profile-name',profilesUI.editing?p?.label:'');
 val('profile-date',b.date);val('profile-time',b.time);
 val('profile-place',b.location_label);val('profile-lat',b.latitude);val('profile-lon',b.longitude);
 val('profile-tz',b.timezone);val('profile-fold',b.fold===0?'0':b.fold===1?'1':'');
 val('profile-city-search','');profEl('profile-city-results').replaceChildren();
 profEl('profile-save').textContent=profilesUI.editing?'✓ UPDATE CHART':'＋ CREATE & ACTIVATE CHART';
 profEl('profile-status').textContent='';
 editor.scrollIntoView({block:'nearest',behavior:'smooth'});
}
async function loadProfileLibrary(){
 const res=await fetch('/api/profiles',{cache:'no-store'});const data=await res.json();if(!res.ok)throw Error(data.error||'Profile library not available.');
 profilesUI.items=data.profiles;profilesUI.activeId=data.active_id;
 const select=profEl('profile-select');select.replaceChildren();
 for(const p of data.profiles){const opt=document.createElement('option');opt.value=p.id;opt.textContent=`${p.label} · ${p.birth.date}`;select.append(opt)}
 select.value=data.active_id;
 const p=activeBirthProfile();
 profEl('header-profile-label').textContent=p?'CHART · '+p.label:'CHART · UNAVAILABLE';
 profEl('header-profile-label').title=p?'Active chart: '+p.label:'';
 profEl('profile-summary').textContent=p?`Active: ${p.label} · ${p.birth.location_label||'custom coordinates'} · ${p.birth.time} ${p.birth.timezone}. Every tab and forecast now uses this chart.`:'';
 profEl('profile-delete').disabled=data.profiles.length<2;
 return p;
}
function profilePayload(){
 const val=id=>profEl(id).value.trim();
 const fold=val('profile-fold');
 const birth={date:val('profile-date'),time:val('profile-time'),timezone:val('profile-tz'),
   latitude:val('profile-lat'),longitude:val('profile-lon'),location_label:val('profile-place')};
 if(fold!=='')birth.fold=Number(fold);
 return {label:val('profile-name'),birth,default_house_system:state.house,default_zodiac:state.zodiac};
}
async function searchBirthCities(){
 const q=profEl('profile-city-search').value.trim();const root=profEl('profile-city-results');root.replaceChildren();
 const id=++profilesUI.cityRequest;if(q.length<2)return;
 try{
  const res=await fetch('/api/cities?q='+encodeURIComponent(q));const data=await res.json();
  if(id!==profilesUI.cityRequest || q!==profEl('profile-city-search').value.trim())return;
  for(const city of data.cities||[]){
   const btn=document.createElement('button');btn.type='button';btn.setAttribute('role','option');
   btn.textContent=city.label;const detail=document.createElement('small');detail.textContent=`${city.timezone} · ${city.latitude}, ${city.longitude}`;btn.append(detail);
   btn.onclick=()=>{
    profEl('profile-place').value=city.label;
    profEl('profile-lat').value=city.latitude;
    profEl('profile-lon').value=city.longitude;
    profEl('profile-tz').value=city.timezone;
    profEl('profile-city-search').value=city.label;
    root.replaceChildren();
    profEl('profile-status').textContent='City location and IANA time zone selected. Check the coordinates against the birth record if precision matters.';
   };
   root.append(btn);
  }
  if(!root.childElementCount){const msg=document.createElement('p');msg.className='micro';msg.textContent='Not in the offline starter list. Enter the coordinates and IANA time zone manually.';root.append(msg)}
 }catch(e){profEl('profile-status').textContent='City search unavailable. Manual coordinate entry still works.'}
}
function initProfileManager(){
 profEl('profile-new').onclick=()=>setProfileEditor('create');
 profEl('profile-edit').onclick=()=>setProfileEditor('edit');
 profEl('profile-cancel').onclick=()=>{profEl('profile-editor').open=false;profEl('profile-city-results').replaceChildren()};
 profEl('profile-select').onchange=async e=>{
  const choice=e.target.value;
  if(choice===profilesUI.activeId)return;
  e.target.disabled=true;
  try{await profileAPI('/api/profiles/select',{id:choice});const p=await loadProfileLibrary();adoptProfileOptions(p);profEl('profile-editor').open=false;resetCurrentChart();toast(`Chart activated: ${p.label}`)}
  catch(err){e.target.value=profilesUI.activeId;toast('Chart switch failed: '+err.message)}
  finally{e.target.disabled=false}
 };
 profEl('profile-form').onsubmit=async event=>{
  event.preventDefault();const button=profEl('profile-save');button.disabled=true;
  try{
   const payload=profilePayload();const route=profilesUI.editing?'/api/profiles/update':'/api/profiles/create';
   const data=profilesUI.editing?await profileAPI(route,{id:profilesUI.activeId,profile:payload}):await profileAPI(route,payload);
   const p=await loadProfileLibrary();adoptProfileOptions(p);profEl('profile-editor').open=false;resetCurrentChart();
   toast(`Birth chart ${profilesUI.editing?'updated':'created'} · UTC ${data.resolved_utc}`);
  }catch(err){profEl('profile-status').textContent=err.message;toast(err.message)}
  finally{button.disabled=false}
 };
 profEl('profile-delete').onclick=async()=>{
  const p=activeBirthProfile();if(!p)return;
  if(!window.confirm(`Delete the saved birth chart "${p.label}"? Observations and your original data/profile.json will not be deleted.`))return;
  try{await profileAPI('/api/profiles/delete',{id:p.id});const active=await loadProfileLibrary();adoptProfileOptions(active);profEl('profile-editor').open=false;resetCurrentChart();toast('Birth chart removed from library.')}
  catch(err){toast('Delete failed: '+err.message)}
 };
 profEl('profile-export').onclick=async()=>{
  try{const p=activeBirthProfile();if(!p)return;const url='/api/profile/export?id='+encodeURIComponent(p.id);
   const res=await fetch(url);const value=await res.json();if(!res.ok)throw Error(value.error||'Export failed');
   saveFile('astral_birth_profile_'+p.id+'.json',JSON.stringify(value,null,2),'application/json;charset=utf-8');toast('Birth profile exported as portable JSON.')}
  catch(err){toast('Profile export failed: '+err.message)}
 };
 profEl('profile-import').onclick=()=>profEl('profile-import-file').click();
 profEl('profile-import-file').onchange=async event=>{
  const input=event.currentTarget;const file=input.files?.[0];if(!file)return;
  try{if(file.size>25000)throw Error('Profile file must be under 25 KB.');
   const obj=JSON.parse(await file.text());await profileAPI('/api/profiles/import',obj);
   const p=await loadProfileLibrary();adoptProfileOptions(p);profEl('profile-editor').open=false;resetCurrentChart();toast('Imported and activated: '+p.label)}
  catch(err){toast('Import failed: '+err.message)}finally{input.value=''}
 };
 profEl('profile-city-search').addEventListener('input',searchBirthCities);
 profEl('profile-city-search').addEventListener('blur',()=>{setTimeout(()=>profEl('profile-city-results').replaceChildren(),180)});
 loadProfileLibrary().then(p=>{if(p&&(p.default_house_system!==state.house||p.default_zodiac!==state.zodiac)){adoptProfileOptions(p);resetCurrentChart()}}).catch(err=>toast('Birth chart library: '+err.message));
}
initProfileManager();
