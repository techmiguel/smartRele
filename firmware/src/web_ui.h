// Embedded web interface (single page, no external dependencies: it works on the setup
// access point without Internet access).
#pragma once

#include <Arduino.h>

static const char WEB_UI[] PROGMEM = R"rawliteral(<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SmartRele</title>
<style>
:root{--bg:#f3f4f6;--card:#fff;--tx:#111827;--mu:#6b7280;--bd:#e5e7eb;--ac:#2563eb;--on:#dc2626;--ok:#16a34a}
@media(prefers-color-scheme:dark){:root{--bg:#0f172a;--card:#1e293b;--tx:#f1f5f9;--mu:#94a3b8;--bd:#334155;--ac:#3b82f6;--on:#ef4444;--ok:#22c55e}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);font:15px/1.4 system-ui,sans-serif}
main{max-width:560px;margin:0 auto;padding:12px 16px 40px}
h1{font-size:20px;margin:8px 0 2px}h2{font-size:16px;margin:0 0 10px}
.mu{color:var(--mu);font-size:13px}
.card{background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:14px;margin-top:12px}
.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.row>*{flex:1 1 auto}
button{font:inherit;border:0;border-radius:8px;padding:9px 12px;background:var(--ac);color:#fff;cursor:pointer}
button.sec{background:transparent;color:var(--tx);border:1px solid var(--bd)}
button.del{background:transparent;color:var(--on);border:1px solid var(--bd);flex:0 0 auto;padding:6px 10px}
input,select{font:inherit;color:var(--tx);background:var(--bg);border:1px solid var(--bd);border-radius:8px;padding:8px;min-width:0;width:100%}
input[type=checkbox]{width:auto}
label{display:block;font-size:13px;color:var(--mu);margin:8px 0 3px}
.big{width:100%;padding:22px;font-size:22px;font-weight:600;border-radius:12px;background:var(--mu)}
.big.on{background:var(--on)}
.pill{display:inline-block;padding:2px 8px;border-radius:99px;font-size:12px;background:var(--bd)}
.pill.ok{background:var(--ok);color:#fff}
.days{display:flex;gap:4px}.days label{margin:0;display:flex;flex-direction:column;align-items:center;font-size:12px}
.sch{display:flex;gap:8px;align-items:center;padding:8px 0;border-top:1px solid var(--bd)}
.sch .t{font-weight:600;font-variant-numeric:tabular-nums}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
table{width:100%;font-size:13px;border-collapse:collapse}td{padding:3px 0}td:last-child{text-align:right}
#msg{position:fixed;left:50%;bottom:16px;transform:translateX(-50%);background:var(--tx);color:var(--bg);padding:8px 14px;border-radius:8px;display:none}
</style></head><body><main>
<h1 id="name">SmartRele</h1>
<div class="mu"><span id="clock">--</span> · <span id="net">--</span></div>

<div class="card">
<button id="relay" class="big" onclick="api('POST','/api/relay',{action:'toggle'})">--</button>
<p class="mu" id="rinfo" style="margin:8px 0 0"></p>
<div class="row" style="margin-top:8px">
<button class="sec" onclick="api('POST','/api/relay',{action:'on'})">Turn on</button>
<button class="sec" onclick="api('POST','/api/relay',{action:'off'})">Turn off</button>
</div></div>

<div class="card"><h2>Timer</h2>
<p class="mu" id="tinfo" style="margin:0 0 6px">Inactive</p>
<div class="grid3">
<div><label>Hours</label><input id="th" type="number" min="0" max="168" value="0"></div>
<div><label>Minutes</label><input id="tm" type="number" min="0" max="59" value="30"></div>
<div><label>Seconds</label><input id="ts" type="number" min="0" max="59" value="0"></div>
</div>
<label>When it expires</label>
<select id="ta"><option value="off">Turn off</option><option value="on">Turn on</option><option value="toggle">Toggle</option></select>
<div class="row" style="margin-top:10px"><button onclick="startTimer()">Start</button>
<button class="sec" onclick="api('DELETE','/api/timer')">Cancel</button></div></div>

<div class="card"><h2>Cyclic ON/OFF routine</h2>
<p class="mu" id="cinfo" style="margin:0 0 6px">Inactive</p>
<div class="row">
<div><label>On (min)</label><input id="con" type="number" min="0.1" step="0.1" value="10"></div>
<div><label>Off (min)</label><input id="coff" type="number" min="0.1" step="0.1" value="50"></div>
</div>
<div class="row" style="margin-top:10px"><button onclick="startCycle()">Start</button>
<button class="sec" onclick="api('DELETE','/api/cycle')">Stop</button></div>
<p class="mu" style="margin:8px 0 0">Starts in the ON phase. A manual command or a schedule stops it. Minimum 5 s per phase.</p></div>

<div class="card"><h2>Weekly schedules</h2>
<p class="mu" id="sinfo" style="margin:0 0 6px"></p>
<div id="slist"></div>
<div style="border-top:1px solid var(--bd);padding-top:8px">
<div class="row"><div><label>Time</label><input id="nt" type="time" value="08:00"></div>
<div><label>Action</label><select id="na"><option value="on">Turn on</option><option value="off">Turn off</option><option value="toggle">Toggle</option></select></div></div>
<label>Days</label><div class="days" id="nd"></div>
<button style="margin-top:10px;width:100%" onclick="addSched()">Add schedule</button></div></div>

<div class="card"><h2>Settings</h2>
<label>Name</label><input id="cname" maxlength="32">
<label>Time zone</label><select id="ctzs" onchange="tzSel()"></select>
<input id="ctz" maxlength="63" style="margin-top:6px" placeholder="POSIX TZ string">
<label>NTP server</label><input id="cntp" maxlength="47">
<label>State at power-up</label>
<select id="cpo"><option value="0">Off</option><option value="1">On</option><option value="2">Last state</option></select>
<label>New admin password (user <b>admin</b>)</label>
<input id="cpw" type="password" maxlength="32" placeholder="Unchanged">
<button style="margin-top:10px;width:100%" onclick="saveCfg()">Save settings</button></div>

<div class="card"><h2>Wi-Fi network</h2>
<label>Network</label><div class="row"><select id="wl"><option value="">— Scan for networks —</option></select>
<button class="sec" style="flex:0 0 auto" onclick="scan()">Scan</button></div>
<input id="ws" maxlength="32" style="margin-top:6px" placeholder="SSID">
<label>Password</label><input id="wp" type="password" maxlength="64">
<button style="margin-top:10px;width:100%" onclick="saveWifi()">Save and restart</button></div>

<div class="card"><h2>System</h2><table id="sys"></table>
<div class="row" style="margin-top:10px">
<button class="sec" onclick="location.href='/update'">Update firmware</button>
<button class="sec" onclick="if(confirm('Restart the device?'))api('POST','/api/reboot')">Restart</button></div>
<button class="del" style="margin-top:8px;width:100%" onclick="if(confirm('Erase ALL settings?'))api('POST','/api/factory-reset')">Factory reset</button>
</div>
</main><div id="msg"></div>
<script>
const $=id=>document.getElementById(id);
const DN=['Su','Mo','Tu','We','Th','Fr','Sa'],ORD=[1,2,3,4,5,6,0];
const AN={on:'Turn on',off:'Turn off',toggle:'Toggle'};
const TZ=[['UTC0','UTC'],['COT5','Colombia (UTC-5)'],['PET5','Peru (UTC-5)'],['ECT5','Ecuador (UTC-5)'],
['CST6','Mexico central (UTC-6)'],['EST5EDT,M3.2.0,M11.1.0','US Eastern'],['CST6CDT,M3.2.0,M11.1.0','US Central'],
['MST7MDT,M3.2.0,M11.1.0','US Mountain'],['PST8PDT,M3.2.0,M11.1.0','US Pacific'],['VET4','Venezuela (UTC-4)'],['BOT4','Bolivia (UTC-4)'],
['AST4','Puerto Rico / Dominican Rep. (UTC-4)'],['<-03>3','Argentina / Uruguay (UTC-3)'],['<-04>4<-03>,M9.1.6/24,M4.1.6/24','Chile'],
['GMT0BST,M3.5.0/1,M10.5.0','United Kingdom'],['CET-1CEST,M3.5.0,M10.5.0/3','Central Europe / Spain']];
let st=null,cfgLoaded=false,timeSent=false;
function toast(t){const m=$('msg');m.textContent=t;m.style.display='block';clearTimeout(m._t);m._t=setTimeout(()=>m.style.display='none',2500)}
async function api(method,url,body){
 try{const r=await fetch(url,{method,headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});
 const j=await r.json().catch(()=>({}));if(!r.ok){toast(j.error||('Error '+r.status));return null}
 if(j.message)toast(j.message);refresh();return j}catch(e){toast('No connection');return null}}
function dur(s){s=Math.max(0,s|0);const h=s/3600|0,m=(s%3600)/60|0,x=s%60;return ((h?h+' h ':'')+(h||m?m+' min ':'')+(x||!(h||m)?x+' s':'')).trim()}
function daysTxt(b){if(b==127)return 'Every day';if(b==62)return 'Monday to Friday';if(b==65)return 'Weekends';return ORD.filter(i=>b&(1<<i)).map(i=>DN[i]).join(' ')}
function render(){
 const s=st;$('name').textContent=s.name;document.title=s.name;
 $('clock').textContent=s.time.valid?s.time.local+(s.time.ntp?'':' (browser time)'):'No time';
 $('net').textContent=s.wifi.connected?s.wifi.ssid+' · '+s.wifi.ip:(s.wifi.ap?'AP mode '+s.wifi.apSsid:'No network');
 const b=$('relay');b.textContent=s.relay.on?'ON':'OFF';b.className='big'+(s.relay.on?' on':'');
 const src={manual:'manual',timer:'timer',schedule:'schedule',cycle:'cyclic routine',boot:'power-up'};
 $('rinfo').textContent='Last change: '+(src[s.relay.source]||s.relay.source)+', '+dur(s.relay.since)+' ago';
 $('tinfo').innerHTML=s.timer.active?'<span class="pill ok">Active</span> '+AN[s.timer.action]+' in '+dur(s.timer.remaining):'Inactive';
 $('cinfo').innerHTML=s.cycle.active?'<span class="pill ok">Active</span> '+(s.relay.on?'ON':'OFF')+', changes in '+dur(s.cycle.remaining)
  :'Inactive · last: '+dur(s.cycle.on)+' ON / '+dur(s.cycle.off)+' OFF';
 $('sinfo').textContent=!s.time.valid?'No time: schedules do not run until the clock is set.':
  (s.next?'Next: '+AN[s.next.action]+' at '+s.next.time+' (in '+dur(s.next.in*60)+')':'No enabled schedules.');
 $('slist').innerHTML=s.schedules.map((x,i)=>`<div class="sch"><input type="checkbox" ${x.enabled?'checked':''} onchange="api('PUT','/api/schedules?id=${i}',{enabled:this.checked})">
 <span class="t">${x.time}</span><span style="flex:1">${AN[x.action]}<br><span class="mu">${daysTxt(x.days)}</span></span>
 <button class="del" onclick="api('DELETE','/api/schedules?id=${i}')">✕</button></div>`).join('')||'<p class="mu">No schedules.</p>';
 $('sys').innerHTML=[['Firmware',s.sys.fw],['Host name',s.host+'.local'],['IP',s.wifi.ip||'-'],['Signal',s.wifi.connected?s.wifi.rssi+' dBm':'-'],
  ['Uptime',dur(s.sys.uptime)],['Free memory',s.sys.heap+' B'],['Last reset',s.sys.reset],['Password set',s.auth?'Yes':'No (set one)']]
  .map(r=>`<tr><td class="mu">${r[0]}</td><td>${r[1]}</td></tr>`).join('');
 if(!s.time.valid&&!timeSent){timeSent=true;api('POST','/api/time',{epoch:Math.floor(Date.now()/1000)})}
}
async function refresh(){try{const r=await fetch('/api/status');if(!r.ok)return;st=await r.json();render();if(!cfgLoaded)loadCfg()}catch(e){}}
async function loadCfg(){const r=await fetch('/api/config');if(!r.ok)return;const c=await r.json();cfgLoaded=true;
 $('cname').value=c.name;$('ctz').value=c.tz;$('cntp').value=c.ntp;$('cpo').value=c.powerOn;$('ws').value=c.ssid;
 $('ctzs').innerHTML=TZ.map(t=>`<option value="${t[0]}">${t[1]}</option>`).join('')+'<option value="">Other (type below)</option>';
 $('ctzs').value=TZ.some(t=>t[0]==c.tz)?c.tz:'';$('ctz').style.display=$('ctzs').value?'none':'block';
 $('con').value=+(c.cycle.on/60).toFixed(2);$('coff').value=+(c.cycle.off/60).toFixed(2)}
function tzSel(){const v=$('ctzs').value;$('ctz').style.display=v?'none':'block';if(v)$('ctz').value=v}
function startTimer(){const s=(+$('th').value)*3600+(+$('tm').value)*60+(+$('ts').value);api('POST','/api/timer',{seconds:s,action:$('ta').value})}
function startCycle(){api('POST','/api/cycle',{on:Math.round($('con').value*60),off:Math.round($('coff').value*60)})}
function addSched(){let d=0;document.querySelectorAll('#nd input').forEach(c=>{if(c.checked)d|=1<<c.value});
 if(!d)return toast('Pick at least one day');api('POST','/api/schedules',{time:$('nt').value,action:$('na').value,days:d,enabled:true})}
function saveCfg(){const b={name:$('cname').value,tz:$('ctz').value,ntp:$('cntp').value,powerOn:+$('cpo').value};
 if($('cpw').value)b.adminPass=$('cpw').value;api('POST','/api/config',b).then(r=>{if(r)$('cpw').value=''})}
function saveWifi(){if(!$('ws').value)return toast('Enter the network name');if(confirm('The device will restart and join "'+$('ws').value+'". Continue?'))api('POST','/api/wifi',{ssid:$('ws').value,pass:$('wp').value})}
async function scan(){toast('Scanning…');for(let i=0;i<15;i++){const r=await fetch('/api/wifi/scan');const j=await r.json();
 if(j.networks){$('wl').innerHTML='<option value="">— '+j.networks.length+' networks —</option>'+j.networks.map(n=>`<option>${n.ssid.replace(/&/g,'&amp;').replace(/</g,'&lt;')}</option>`).join('');
 $('wl').onchange=()=>{$('ws').value=$('wl').value};return}await new Promise(r=>setTimeout(r,1000))}toast('Scan failed')}
$('nd').innerHTML=ORD.map(i=>`<label>${DN[i]}<input type="checkbox" value="${i}" checked></label>`).join('');
refresh();setInterval(refresh,2000);
</script></body></html>)rawliteral";
