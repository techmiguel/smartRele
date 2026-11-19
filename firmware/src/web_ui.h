// Embedded web interface (single page, no external dependencies: it works on the setup
// access point without Internet access). UI text is in Spanish, as requested by the user.
#pragma once

#include <Arduino.h>

static const char WEB_UI[] PROGMEM = R"rawliteral(<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#ffffff">
<title>SmartRele</title>
<style>
:root{--tx:#111827;--mu:#9ca3af;--mu2:#6b7280;--ln:#f3f4f6;--g1:#16a34a;--g2:#4ade80;--r1:#dc2626;--r2:#fb7185}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{margin:0;height:100%;background:#fff;color:var(--tx);font:15px/1.4 -apple-system,system-ui,"Segoe UI",Roboto,sans-serif}
button,input,select{font:inherit;color:inherit}
.ic{fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
main{min-height:100%;max-width:480px;margin:0 auto;display:flex;flex-direction:column;align-items:center;padding:32px 24px calc(24px + env(safe-area-inset-bottom))}
#name{font-size:22px;font-weight:600;letter-spacing:-.01em;margin:0;text-align:center;word-break:break-word}
.stage{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:26px;width:100%;padding:28px 0}
#pw{--c1:#d1d5db;--c2:#e5e7eb;--halo:rgba(0,0,0,.025);width:220px;height:220px;border-radius:50%;border:3px solid transparent;cursor:pointer;
 background:linear-gradient(#fff,#fff) padding-box,linear-gradient(140deg,var(--c1),var(--c2)) border-box;
 box-shadow:0 0 0 14px var(--halo),0 26px 50px -22px rgba(17,24,39,.22);color:var(--c1);
 display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;transition:transform .15s,box-shadow .3s,color .3s}
#pw:active{transform:scale(.96)}
#pw svg{width:54px;height:54px}
#pw b{font-size:20px;font-weight:600;letter-spacing:.2em;padding-left:.2em}
#pw.go-on{--c1:var(--g1);--c2:var(--g2);--halo:rgba(34,197,94,.07)}
#pw.go-off{--c1:var(--r1);--c2:var(--r2);--halo:rgba(239,68,68,.07)}
.st{text-align:center}
.st small{display:block;font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--mu)}
.st span{display:block;font-size:30px;font-weight:300;font-variant-numeric:tabular-nums;margin-top:2px}
.chip{display:none;align-items:center;gap:6px;padding:7px 14px;border-radius:99px;background:var(--ln);color:var(--mu2);font-size:13px;border:0;cursor:pointer;font-variant-numeric:tabular-nums}
.chip.show{display:inline-flex}.chip svg{width:15px;height:15px}
nav{display:flex;justify-content:space-around;width:100%;max-width:340px}
nav button{background:none;border:0;display:flex;flex-direction:column;align-items:center;gap:8px;font-size:12px;color:var(--mu2);cursor:pointer}
nav i{width:58px;height:58px;border-radius:50%;background:#f5f6f7;display:flex;align-items:center;justify-content:center;color:var(--tx);transition:background .2s}
nav button:active i{background:#e9ebee}nav svg{width:24px;height:24px}
#ov{position:fixed;inset:0;background:rgba(17,24,39,.28);opacity:0;pointer-events:none;transition:opacity .25s;z-index:5}
#ov.open{opacity:1;pointer-events:auto}
.sh{position:fixed;left:0;right:0;bottom:0;margin:0 auto;max-width:480px;max-height:92vh;overflow:auto;background:#fff;border-radius:22px 22px 0 0;
 padding:10px 22px calc(22px + env(safe-area-inset-bottom));transform:translateY(105%);visibility:hidden;z-index:6;
 transition:transform .3s cubic-bezier(.2,.8,.2,1),visibility 0s .3s}
.sh.open{transform:none;visibility:visible;transition:transform .3s cubic-bezier(.2,.8,.2,1)}
.grab{width:36px;height:4px;border-radius:2px;background:#e5e7eb;margin:0 auto 14px}
.sh h2{font-size:17px;font-weight:600;text-align:center;margin:0 0 4px}
.sub{color:var(--mu2);font-size:13px;text-align:center;margin:0 0 10px;min-height:18px;font-variant-numeric:tabular-nums}
.wh{position:relative;display:flex;justify-content:center;align-items:center;margin:4px 0 18px}
.wh:before{content:"";position:absolute;left:0;right:0;top:50%;height:44px;margin-top:-22px;background:#f5f6f7;border-radius:12px}
.col{position:relative;width:60px;height:220px;overflow-y:scroll;scroll-snap-type:y mandatory;scrollbar-width:none;cursor:pointer;
 -webkit-mask-image:linear-gradient(transparent,#000 35%,#000 65%,transparent);mask-image:linear-gradient(transparent,#000 35%,#000 65%,transparent)}
.col::-webkit-scrollbar{display:none}
.col p{height:88px;margin:0}
.col div{height:44px;line-height:44px;text-align:center;font-size:26px;font-variant-numeric:tabular-nums;scroll-snap-align:center}
.wh span{position:relative;color:var(--mu2);font-size:14px;padding:0 10px 0 2px}
.pair{display:flex;justify-content:center;gap:10px}.pair .col{width:46px}.pair .wh span{padding:0 6px 0 0}
.ph{margin:6px 0 0;text-align:center;font-size:12px;font-weight:600;letter-spacing:.1em;text-transform:uppercase}
.ph.on{color:var(--g1)}.ph.off{color:var(--r1)}
.seg{position:relative;display:flex;background:var(--ln);border-radius:99px;padding:4px;margin:0 0 16px}
.seg i{position:absolute;top:4px;bottom:4px;left:4px;width:calc(50% - 4px);border-radius:99px;background:linear-gradient(140deg,var(--g1),var(--g2));transition:transform .3s cubic-bezier(.2,.8,.2,1)}
.seg.off i{transform:translateX(100%);background:linear-gradient(140deg,var(--r1),var(--r2))}
.seg button{position:relative;flex:1;border:0;background:none;padding:11px 0;font-size:13px;font-weight:600;letter-spacing:.08em;color:var(--mu2);transition:color .3s;cursor:pointer}
.seg:not(.off) button:first-of-type,.seg.off button:last-of-type{color:#fff}
.btn{display:block;width:100%;border:0;border-radius:14px;padding:14px;font-weight:600;background:var(--tx);color:#fff;cursor:pointer}
.btn.on{background:linear-gradient(140deg,var(--g1),var(--g2))}.btn.off{background:linear-gradient(140deg,var(--r1),var(--r2))}
.btn.ghost{background:var(--ln);color:var(--tx);margin-top:10px}
label{display:block;font-size:12px;color:var(--mu2);margin:14px 0 6px}
input,select{width:100%;border:1px solid #e5e7eb;border-radius:12px;padding:12px;background:#fff;outline:none;min-width:0}
input:focus,select:focus{border-color:var(--mu)}
hr{border:0;border-top:1px solid var(--ln);margin:22px 0 4px}
.row{display:flex;gap:8px}.row .btn{width:auto;margin:0;padding:12px 16px}
.foot{display:flex;flex-direction:column;align-items:center;gap:6px;margin-top:22px;font-size:12px;color:var(--mu)}
.foot a,.foot button{color:var(--mu2);background:none;border:0;padding:0;font-size:12px;text-decoration:underline;cursor:pointer}
#msg{position:fixed;left:50%;bottom:calc(120px + env(safe-area-inset-bottom));transform:translateX(-50%);background:var(--tx);color:#fff;padding:9px 16px;border-radius:99px;font-size:13px;opacity:0;pointer-events:none;transition:opacity .2s;z-index:9;white-space:nowrap}
#msg.show{opacity:1}
</style></head><body>
<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs>
<symbol id="i-pw" viewBox="0 0 24 24"><path d="M12 3v8M6.3 6.3a8 8 0 1 0 11.4 0"/></symbol>
<symbol id="i-tm" viewBox="0 0 24 24"><circle cx="12" cy="13" r="8"/><path d="M12 9v4l2.5 2.5M9.5 2h5M12 2v3"/></symbol>
<symbol id="i-cy" viewBox="0 0 24 24"><path d="M4 12a8 8 0 0 1 13.7-5.6L20 9M20 4v5h-5M20 12a8 8 0 0 1-13.7 5.6L4 15M4 20v-5h5"/></symbol>
<symbol id="i-cf" viewBox="0 0 24 24"><path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12"/><circle cx="16" cy="6" r="2"/><circle cx="10" cy="12" r="2"/><circle cx="18" cy="18" r="2"/></symbol>
</defs></svg>
<main>
<h1 id="name">SmartRele</h1>
<div class="stage">
<button id="pw" onclick="press()" aria-label="Encender o apagar"><svg class="ic"><use href="#i-pw"/></svg><b id="pwt">···</b></button>
<div class="st"><small id="stl">Conectando</small><span id="stt">--:--</span></div>
<button class="chip" id="chip" onclick="openSheet(st.timer.active?'tm':'cy')"><svg class="ic"><use id="chipi" href="#i-tm"/></svg><span id="chipt"></span></button>
</div>
<nav>
<button onclick="openSheet('tm')"><i><svg class="ic"><use href="#i-tm"/></svg></i>Temporizador</button>
<button onclick="openSheet('cy')"><i><svg class="ic"><use href="#i-cy"/></svg></i>Rutina</button>
<button onclick="openSheet('cf')"><i><svg class="ic"><use href="#i-cf"/></svg></i>Ajustes</button>
</nav>
</main>
<div id="ov" onclick="closeSheet()"></div>

<section class="sh" id="sh-tm"><div class="grab"></div><h2>Temporizador</h2><p class="sub" id="tmsub"></p>
<div class="wh"><div class="col" id="th"></div><span>h</span><div class="col" id="tmn"></div><span>min</span><div class="col" id="ts"></div><span>s</span></div>
<div class="seg" id="tseg"><i></i><button onclick="seg(0)">ENCENDER</button><button onclick="seg(1)">APAGAR</button></div>
<button class="btn" id="tgo" onclick="startTimer()">Iniciar</button>
<button class="btn ghost" id="tcancel" onclick="api('DELETE','/api/timer',null,'Temporizador cancelado')">Cancelar temporizador</button>
</section>

<section class="sh" id="sh-cy"><div class="grab"></div><h2>Rutina</h2><p class="sub" id="cysub"></p>
<div class="pair">
<div><p class="ph on">Encendido</p><div class="wh"><div class="col" id="cnh"></div><span>h</span><div class="col" id="cnm"></div><span>min</span></div></div>
<div><p class="ph off">Apagado</p><div class="wh"><div class="col" id="cfh"></div><span>h</span><div class="col" id="cfm"></div><span>min</span></div></div>
</div>
<button class="btn" onclick="startCycle()">Iniciar rutina</button>
<button class="btn ghost" id="cstop" onclick="api('DELETE','/api/cycle',null,'Rutina detenida')">Detener rutina</button>
</section>

<section class="sh" id="sh-cf"><div class="grab"></div><h2>Ajustes</h2>
<label for="cname">Nombre del dispositivo</label><input id="cname" maxlength="32">
<label for="cpo">Al volver la luz</label>
<select id="cpo"><option value="0">Apagado</option><option value="1">Encendido</option><option value="2">Último estado</option></select>
<label for="cpw">Contraseña de acceso (usuario admin)</label><input id="cpw" type="password" maxlength="32" autocomplete="new-password">
<label for="cap">Wi-Fi propia del relé</label><input id="cap" maxlength="32" placeholder="Nombre">
<input id="capw" type="password" maxlength="63" autocomplete="new-password" placeholder="Contraseña: sin cambios" style="margin-top:8px">
<button class="btn" style="margin-top:18px" onclick="saveCfg()">Guardar</button>
<hr>
<label>Red Wi-Fi</label><p class="sub" id="wst" style="text-align:left"></p>
<div class="row"><select id="wl" onchange="$('ws').value=this.value"><option value="">Elegir red…</option></select><button class="btn ghost" onclick="scan()">Buscar</button></div>
<input id="ws" maxlength="32" placeholder="Nombre de la red" style="margin-top:8px">
<input id="wp" type="password" maxlength="64" placeholder="Contraseña de la red" style="margin-top:8px">
<button class="btn ghost" onclick="saveWifi()">Conectar</button>
<hr>
<label for="tgt">Telegram (control desde internet)</label><p class="sub" id="tgst" style="text-align:left"></p>
<input id="tgt" type="password" maxlength="63" autocomplete="off" placeholder="Token del bot (de @BotFather)">
<input id="tgu" maxlength="80" inputmode="numeric" placeholder="IDs autorizados, separados por comas" style="margin-top:8px">
<select id="tgn" style="margin-top:8px"><option value="1">Avisar de cambios: sí</option><option value="0">Avisar de cambios: no</option></select>
<button class="btn ghost" onclick="saveTg()">Guardar Telegram</button>
<button class="btn ghost" id="tgdel" onclick="if(confirm('¿Quitar el bot de Telegram?'))api('POST','/api/config',{tgToken:''},'Bot quitado').then(loadCfg)">Quitar bot</button>
<div class="foot"><span id="fw"></span><span><a href="/update">Actualizar firmware</a> · <button onclick="if(confirm('¿Reiniciar el dispositivo?'))api('POST','/api/reboot',null,'Reiniciando…')">Reiniciar</button></span></div>
</section>
<div id="msg" role="status"></div>
<script>
const $=id=>document.getElementById(id);
let st=null,t0=0,lost=false,busy=false,tAct='off',timeSent=false;
const p2=n=>String(n).padStart(2,'0');
const dt=()=>(Date.now()-t0)/1000;
function clk(s){s=Math.max(0,Math.floor(s));const d=s/86400|0,h=s%86400/3600|0,m=s%3600/60|0,x=s%60;
 return (d?d+' d ':'')+(d||h?h+':'+p2(m):m)+':'+p2(x)}
function toast(t){const m=$('msg');m.textContent=t;m.classList.add('show');clearTimeout(m._t);m._t=setTimeout(()=>m.classList.remove('show'),2200)}
async function api(method,url,body,ok){let j=null;
 try{const r=await fetch(url,{method,headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});
  j=await r.json().catch(()=>({}));if(!r.ok){toast(j.error||'Error '+r.status);j=null}else if(ok)toast(ok)}
 catch(e){toast('Sin conexión')}
 refresh();return j}
function render(){
 const b=$('pw');
 if(lost||!st){b.className='';$('pwt').textContent='···';$('stl').textContent=lost?'Sin conexión':'Conectando';return}
 const on=st.relay.on,e=dt();
 b.className=on?'go-off':'go-on';$('pwt').textContent=on?'OFF':'ON';b.setAttribute('aria-label',on?'Apagar':'Encender');
 $('stl').textContent=on?'Encendido':'Apagado';$('stt').textContent=clk(st.relay.since+e);
 if($('name').textContent!==st.name){$('name').textContent=st.name;document.title=st.name}
 let tt='',ct='';
 if(st.timer.active)tt={on:'Se enciende',off:'Se apaga',toggle:'Cambia'}[st.timer.action]+' en '+clk(st.timer.remaining-e);
 if(st.cycle.active)ct='Rutina · '+(on?'apaga':'enciende')+' en '+clk(st.cycle.remaining-e);
 const c=tt||ct;$('chip').classList.toggle('show',!!c);$('chipt').textContent=c;$('chipi').setAttribute('href',tt?'#i-tm':'#i-cy');
 $('tmsub').textContent=tt||'Elige el tiempo y qué hacer al terminar';$('tcancel').style.display=tt?'block':'none';
 $('cysub').textContent=ct||'Empieza encendido y se repite sin fin';$('cstop').style.display=ct?'block':'none';
 $('wst').textContent=st.wifi.connected?'Conectado a '+st.wifi.ssid+' · '+st.wifi.ip:'Sin red · punto de acceso '+st.wifi.apSsid;
 $('fw').textContent='Firmware '+st.sys.fw+' · '+st.host+'.local';
 const g=st.telegram;$('tgst').textContent={off:'Desactivado',waiting:'Esperando conexión a internet',connecting:'Conectando…',
  online:'En línea'+(g.bot?' · @'+g.bot:''),error:g.error}[g.state]||'';
}
async function refresh(){
 try{const r=await fetch('/api/status',{cache:'no-store'});if(!r.ok)throw 0;st=await r.json();t0=Date.now();lost=false}catch(e){lost=true}
 render();
 if(st&&!st.time.valid&&!timeSent){timeSent=true;fetch('/api/time',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({epoch:Math.floor(Date.now()/1000)})})}
}
async function press(){
 if(!st||lost||busy)return;busy=true;const a=st.relay.on?'off':'on';
 st.relay.on=!st.relay.on;st.relay.since=0;st.cycle.active=false;t0=Date.now();render(); // instant feedback; the next poll confirms
 await api('POST','/api/relay',{action:a});busy=false}
// Wheel picker: a scroll-snapped column, one 44 px row per value
function mkCol(id,max){const c=$(id);c.innerHTML='<p></p>'+Array.from({length:max+1},(_,i)=>'<div>'+p2(i)+'</div>').join('')+'<p></p>';
 c.onclick=e=>{if(e.target.tagName=='DIV')c.scrollTo({top:([].indexOf.call(c.children,e.target)-1)*44,behavior:'smooth'})}}
const getW=id=>Math.round($(id).scrollTop/44);
const setW=(id,v)=>{$(id).scrollTop=v*44};
function seg(off){tAct=off?'off':'on';$('tseg').classList.toggle('off',!!off);$('tgo').className='btn '+tAct}
function openSheet(k){
 $('ov').classList.add('open');$('sh-'+k).classList.add('open');
 if(k=='tm')seg(st&&st.relay.on?1:0);
 if(k=='cy'&&st){const n=st.cycle.on,f=st.cycle.off;setW('cnh',n/3600|0);setW('cnm',n%3600/60|0);setW('cfh',f/3600|0);setW('cfm',f%3600/60|0)}
 if(k=='cf')loadCfg()}
function closeSheet(){$('ov').classList.remove('open');document.querySelectorAll('.sh.open').forEach(s=>s.classList.remove('open'))}
function startTimer(){const s=getW('th')*3600+getW('tmn')*60+getW('ts');if(!s)return toast('Elige un tiempo');
 api('POST','/api/timer',{seconds:s,action:tAct},'Temporizador iniciado').then(r=>{if(r)closeSheet()})}
function startCycle(){const n=getW('cnh')*3600+getW('cnm')*60,f=getW('cfh')*3600+getW('cfm')*60;
 if(!n||!f)return toast('Cada fase necesita al menos 1 minuto');
 api('POST','/api/cycle',{on:n,off:f},'Rutina iniciada').then(r=>{if(r)closeSheet()})}
async function loadCfg(){try{const c=await(await fetch('/api/config')).json();
 $('cname').value=c.name;$('cpo').value=c.powerOn;if(!$('ws').value)$('ws').value=c.ssid;$('cap').value=$('cap').dataset.v=c.apSsid;
 $('cpw').placeholder=c.auth?'Sin cambios':'Sin contraseña (recomendado)';
 $('tgt').placeholder=c.tgToken?'Token: sin cambios':'Token del bot (de @BotFather)';$('tgu').value=c.tgUsers;$('tgn').value=c.tgNotify?1:0;
 $('tgdel').style.display=c.tgToken?'block':'none'}catch(e){}}
function saveTg(){const t=$('tgt').value.trim(),u=$('tgu').value.trim();
 if(t&&!/^\d+:[\w-]{30,}$/.test(t))return toast('El token tiene la forma 123456:ABC…');
 if(u&&!/^\d+([ ,;]+\d+)*$/.test(u))return toast('IDs: solo números separados por comas');
 const b={tgUsers:u,tgNotify:$('tgn').value=='1'};if(t)b.tgToken=t;
 api('POST','/api/config',b,'Telegram guardado').then(r=>{if(r){$('tgt').value='';loadCfg()}})}
function saveCfg(){const n=$('cname').value.trim(),p=$('cpw').value,a=$('cap').value.trim(),ap=$('capw').value;
 if(!n)return toast('Escribe un nombre');
 if(new TextEncoder().encode(n).length>32)return toast('Nombre demasiado largo');
 if(p&&p.length<8)return toast('La contraseña necesita 8 caracteres o más');
 if(!a||new TextEncoder().encode(a).length>32)return toast('Nombre de la Wi-Fi: 1 a 32 caracteres');
 if(ap&&ap.length<8)return toast('La clave de la Wi-Fi necesita 8 caracteres o más');
 const b={name:n,powerOn:+$('cpo').value};if(p)b.adminPass=p;if(a!=$('cap').dataset.v)b.apSsid=a;if(ap)b.apPass=ap;
 const rs=p||ap||b.apSsid;
 api('POST','/api/config',b,rs?'Guardado. Reiniciando…':'Guardado').then(r=>{if(r){$('cpw').value=$('capw').value='';closeSheet()}})}
function saveWifi(){const s=$('ws').value.trim(),p=$('wp').value;
 if(!s)return toast('Elige o escribe una red');if(p&&p.length<8)return toast('La contraseña de la red tiene 8 caracteres o más');
 if(confirm('El dispositivo se reiniciará y se conectará a "'+s+'". ¿Continuar?'))api('POST','/api/wifi',{ssid:s,pass:p},'Guardado. Reiniciando…')}
async function scan(){toast('Buscando redes…');
 for(let i=0;i<15;i++){try{const j=await(await fetch('/api/wifi/scan')).json();
  if(j.networks){const w=$('wl');w.length=1;j.networks.forEach(n=>w.add(new Option(n.ssid,n.ssid)));w.options[0].text=j.networks.length+' redes encontradas';return}}catch(e){}
  await new Promise(r=>setTimeout(r,1000))}
 toast('No se pudo buscar')}
document.onkeydown=e=>{if(e.key=='Escape')closeSheet()};
[['th',23],['tmn',59],['ts',59],['cnh',23],['cnm',59],['cfh',23],['cfm',59]].forEach(a=>mkCol(a[0],a[1]));
setW('tmn',30);
refresh();setInterval(refresh,2000);setInterval(render,1000);
</script></body></html>)rawliteral";
