'use strict';
(async()=>{
 const list=document.querySelector('#city-list'), map=document.querySelector('#map');
 try {
  const [response, outline]=await Promise.all([fetch('cities.json'),fetch('map.svg')]);
  if(!response.ok||!outline.ok)throw new Error('load');
  const {cities}=await response.json(); map.innerHTML=await outline.text();
  const svg=map.querySelector('svg'), ns='http://www.w3.org/2000/svg';
  const project=c=>[(c.longitude-19)/162*1100,(82-c.latitude)/41*420];
  let active;
  const format=s=>new Date(s+'T12:00:00Z').toLocaleDateString('ru-RU',{timeZone:'UTC'});
  function select(id,changeURL=true){
   active=cities.find(c=>c.id===id)||cities.find(c=>c.id==='moscow');
   document.querySelector('#city-title').textContent=active.name;
   document.querySelector('#timezone').textContent=active.timezone+' · местное время';
   document.querySelector('#rise').textContent=active.times.sunrise||'Нет';
   document.querySelector('#set').textContent=active.times.sunset||'Нет';
   document.querySelector('#today').textContent='На '+format(active.today)+'. Время обновляется при ежедневном расчёте.';
   const last=new Date(active.until_exclusive+'T12:00:00Z');last.setUTCDate(last.getUTCDate()-1);
   document.querySelector('#period').textContent=`С ${format(active.from)} по ${last.toLocaleDateString('ru-RU',{timeZone:'UTC'})} · ${active.events} событий по 10 минут.`;
   document.querySelector('#polar').hidden=active.latitude<65;
   const url=`https://brodov.net/sun-calendar/${active.id}.ics`;
   document.querySelector('#calendar-url').value=url;
   document.querySelector('#subscribe').href=url.replace('https:','webcal:');
   document.querySelector('#download').href=active.id+'.ics';
   document.querySelector('#copy-status').textContent='';
   document.querySelectorAll('[data-city]').forEach(e=>e.setAttribute('aria-pressed',String(e.dataset.city===active.id)));
   if(changeURL)history.replaceState(null,'','#'+active.id);
  }
  const labels=new Set(['moscow','minsk','samara','saint-petersburg','novosibirsk','yekaterinburg','krasnoyarsk','irkutsk','yakutsk','vladivostok','magadan','murmansk','petropavlovsk-kamchatsky']);
  for(const c of cities){
   const b=document.createElement('button');b.type='button';b.textContent=c.name;b.dataset.city=c.id;b.dataset.search=[c.name,c.region||'',c.search_terms||''].join(' ');b.onclick=()=>select(c.id);list.append(b);
   const [x,y]=project(c),g=document.createElementNS(ns,'g');g.setAttribute('class','marker');g.setAttribute('role','button');g.setAttribute('tabindex','0');g.setAttribute('aria-label',c.name);g.dataset.city=c.id;
   for(const [cls,r]of [['hit',10],['dot',4.5]]){const dot=document.createElementNS(ns,'circle');dot.setAttribute('cx',x);dot.setAttribute('cy',y);dot.setAttribute('r',r);dot.setAttribute('class',cls);g.append(dot);}
   const title=document.createElementNS(ns,'title');title.textContent=c.name;g.append(title);g.onclick=()=>select(c.id);g.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();select(c.id);}};svg.append(g);
   if(labels.has(c.id)){const t=document.createElementNS(ns,'text');t.setAttribute('x',x>900?x-8:x+8);if(x>900)t.setAttribute('text-anchor','end');t.setAttribute('y',y-9);t.setAttribute('class','map-label');t.dataset.mapX=x;t.dataset.mapY=y;t.textContent=c.name;svg.append(t);}
  }
  select(location.hash.slice(1),false);window.addEventListener('hashchange',()=>select(location.hash.slice(1),false));
  document.querySelector('#search').addEventListener('input',e=>{const q=e.target.value.toLocaleLowerCase('ru').replaceAll('ё','е').trim();let n=0;list.querySelectorAll('button').forEach(b=>{b.hidden=!b.dataset.search.toLocaleLowerCase('ru').replaceAll('ё','е').includes(q);if(!b.hidden)n++;});document.querySelector('#count').textContent=`Городов: ${n}`;document.querySelector('#empty').hidden=n!==0;});
  document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{const view=({all:'0 0 1100 420',west:'0 120 216 295',south:'14 300 140 103',center:'210 110 422 310',east:'630 105 470 315'})[b.dataset.view];svg.setAttribute('viewBox',view);const height=b.dataset.view==='west'?680:(['center','east'].includes(b.dataset.view)?520:430);const bounds=view.split(' ').map(Number);map.style.maxWidth=b.dataset.view==='all'?'none':(height*bounds[2]/bounds[3])+'px';svg.style.maxHeight='none';svg.style.height='auto';const scale=Math.sqrt(Number(view.split(' ')[2])/1100);svg.querySelectorAll('.dot').forEach(e=>e.setAttribute('r',4.5*scale));svg.querySelectorAll('.hit').forEach(e=>e.setAttribute('r',10*scale));svg.querySelectorAll('.map-label').forEach(e=>{const x=Number(e.dataset.mapX),y=Number(e.dataset.mapY),left=x+(8+e.textContent.length*6)*scale>bounds[0]+bounds[2];e.style.fontSize=(12*scale)+'px';e.setAttribute('text-anchor',left?'end':'start');e.setAttribute('x',x+(left?-8:8)*scale);e.setAttribute('y',y-9*scale);});document.querySelectorAll('[data-view]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));});
  document.querySelector('#copy').onclick=async()=>{const input=document.querySelector('#calendar-url');try{await navigator.clipboard.writeText(input.value);document.querySelector('#copy-status').textContent='Ссылка скопирована';}catch{input.focus();input.select();document.querySelector('#copy-status').textContent='Скопируйте выделенную ссылку вручную';}};
 }catch(error){document.querySelector('#count').textContent='Не удалось загрузить выбор города. Откройте список «Все города» ниже.';document.querySelector('.all-links').open=true;}
})();
