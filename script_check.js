
const TYPE_LABEL={form:'Forms',active_link:'Active Links',filter:'Filters',escalation:'Escalations',menu:'Menus',active_link_guide:'Active Link Guides',filter_guide:'Filter Guides',packing_list:'Packing Lists',application:'Applications',image:'Images'};
const TYPE_TO_EXPORT={form:1,active_link:2,filter:3,escalation:4,menu:5,active_link_guide:6,filter_guide:6,packing_list:6,application:6,image:7};
const TYPES=['form','active_link','filter','menu','escalation','active_link_guide','filter_guide','packing_list','application','image'];
const state={envs:[],scope:{},sync:{},cache:{},serverCache:{},sessions:JSON.parse(sessionStorage.getItem('hlx.sessions')||'{}'),source:sessionStorage.getItem('hlx.sourceEnv')||'',target:sessionStorage.getItem('hlx.targetEnv')||'',type:'form',mode:'browse',objects:[],compare:null,selected:[],statusFilter:'',sortKey:'name',sortDir:'asc',pageSize:100,offset:0,total:0,loadingObjects:false,searchTimer:null};
let dialogResolver=null;
function openDialog(opts={}){
  return new Promise(resolve=>{
    dialogResolver=resolve;
    dialogTitle.textContent=opts.title||'Confirm';
    dialogSubtitle.textContent=opts.subtitle||'';
    dialogMessage.textContent=opts.message||'';
    dialogOkBtn.textContent=opts.okText||'OK';
    dialogCancelBtn.textContent=opts.cancelText||'Cancel';
    dialogCancelBtn.classList.toggle('hidden', opts.hideCancel===true);
    dialogFieldWrap.classList.add('hidden');
    dialogSelect.classList.add('hidden');
    dialogInput.classList.add('hidden');
    dialogSelect.innerHTML='';
    dialogInput.value=opts.defaultValue||'';
    if(opts.type==='select'){
      dialogFieldWrap.classList.remove('hidden');
      dialogSelect.classList.remove('hidden');
      dialogFieldLabel.textContent=opts.label||'Select';
      const options=opts.options||[];
      dialogSelect.innerHTML=options.map(o=>`<option value="${html(o.value??o)}" ${(o.value??o)===(opts.defaultValue??'')?'selected':''}>${html(o.label??o)}</option>`).join('');
    } else if(opts.type==='input'){
      dialogFieldWrap.classList.remove('hidden');
      dialogInput.classList.remove('hidden');
      dialogFieldLabel.textContent=opts.label||'Value';
    }
    appDialog.classList.remove('hidden');
  });
}
function dialogOk(){
  const value=!dialogFieldWrap.classList.contains('hidden') ? (!dialogSelect.classList.contains('hidden') ? dialogSelect.value : dialogInput.value) : true;
  appDialog.classList.add('hidden');
  if(dialogResolver){dialogResolver(value);dialogResolver=null;}
}
function dialogCancel(){
  appDialog.classList.add('hidden');
  if(dialogResolver){dialogResolver(null);dialogResolver=null;}
}
async function notifyDialog(title,message){return openDialog({title,message,okText:'OK',hideCancel:true});}
async function confirmDialog(title,message,okText='Confirm'){return (await openDialog({title,message,okText,cancelText:'Cancel'}))===true;}
async function selectDialog(title,message,options,defaultValue,label='Target environment'){return openDialog({title,message,type:'select',options,defaultValue,label,okText:'Continue',cancelText:'Cancel'});}
function statusBadgeClass(status){return String(status||'').replace(/[^a-zA-Z0-9_-]/g,'_');}
function compactCount(n){n=Number(n||0);if(n>=1000000)return (n/1000000).toFixed(1).replace(/\.0$/,'')+'m';if(n>=1000)return (n/1000).toFixed(1).replace(/\.0$/,'')+'k';return String(n);}

async function api(path,opts={}){
  const r=await fetch(path,opts);
  if(!r.ok){
    let payload=null;
    try{payload=await r.json();}catch{payload={detail:await r.text()};}
    const detail=payload.detail??payload;
    const message=typeof detail==='string'?detail:(detail.message||JSON.stringify(detail));
    const err=new Error(message);
    err.status=r.status;
    err.payload=payload;
    err.detail=detail;
    throw err;
  }
  return r.json();
}
function fmtDate(s){if(!s)return '-';try{return new Date(s).toLocaleString('en-GB')}catch{return s}}
function html(s){return String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;')}
function esc(s){return String(s).replaceAll('\\','\\\\').replaceAll("'","\\'")}
function safeId(s){return String(s).replace(/[^a-zA-Z0-9_-]/g,'_')}
function setStatus(t){statusText.textContent=t}
function sessionFor(env){const s=state.sessions[env];return s && s.valid!==false ? s.sessionId||'' : ''}
function saveSessions(){sessionStorage.setItem('hlx.sessions',JSON.stringify(state.sessions));renderLogin();renderHeader()}
function renderHeader(){const active=Object.entries(state.sessions).filter(([e,s])=>s && s.valid!==false);const stale=Object.entries(state.sessions).filter(([e,s])=>s && s.valid===false);const activeText=active.map(([e,s])=>`${e}: ${s.user}`).join(' | ');const staleText=stale.length?` · stale: ${stale.map(([e])=>e).join(', ')}`:'';sessionHeader.textContent=(activeText||'No browser sessions')+staleText;modeHeader.textContent=`${(state.source||'-').toUpperCase()} → ${(state.target||'-').toUpperCase()} · ${state.mode==='compare'?'Compare':'Browse source'}`}
async function validateStoredSessions(){const entries=Object.entries(state.sessions);if(!entries.length)return;let changed=false;for(const [env,s] of entries){if(!s?.sessionId)continue;try{const r=await api('/api/session/validate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:s.sessionId})});if(r.valid){state.sessions[env]={...s,valid:true};}else{state.sessions[env]={...s,valid:false,expiredMessage:r.message||'Session expired'};}changed=true;}catch(e){state.sessions[env]={...s,valid:false,expiredMessage:e.message};changed=true;}}if(changed)saveSessions()}
function toggleLogin(){loginPanel.classList.toggle('open')} function toggleEnvMenu(){envMenu.classList.toggle('hidden')}
async function init(){renderTree();await refreshAll();await validateStoredSessions();if(!state.source)state.source=state.envs[0]||'';if(!state.target)state.target=state.envs[1]||state.envs[0]||'';renderSelects();renderLogin();renderHeader();renderScope();await loadSourceObjects();setInterval(refreshAll,5000)}
async function refreshAll(){try{const e=await api('/api/environments');state.envs=e.environments;state.scope=e.scope||{};state.sync=e.sync||{};state.serverCache=e.serverCache||{};const c=await api('/api/cache/summary');state.cache=c.environments||{};renderSelects();renderTree();renderCards();renderJobs();renderScope();renderHeader();document.getElementById('syncStatusBtn')?.classList.toggle('sync-active', !!state.serverCache.running || Object.keys(state.serverCache.locks||{}).length>0);setStatus(state.serverCache.running?'Server sync is running...':'Ready')}catch(err){setStatus(err.message)}}
function renderSelects(){for(const el of [sourceEnv,targetEnv]){const sel=el.id==='sourceEnv'?state.source:state.target;el.innerHTML=state.envs.map(e=>`<option ${e===sel?'selected':''}>${e.toUpperCase()}</option>`).join('')}}
function savePair(){state.source=sourceEnv.value.toLowerCase();state.target=targetEnv.value.toLowerCase();sessionStorage.setItem('hlx.sourceEnv',state.source);sessionStorage.setItem('hlx.targetEnv',state.target);renderHeader()}
function renderScope(){if(!document.getElementById('scopeBox'))return;scopeBox.innerHTML=`<span class="pill">Include ${(state.scope.include_form_prefixes||[]).join(', ')||'-'}</span><span class="pill">Exclude ${(state.scope.exclude_form_prefixes||[]).join(', ')||'-'}</span>`}
function renderTree(){typeTree.innerHTML=TYPES.map(t=>{const c=state.cache[state.source]?.[t]?.count||0;return `<button id="nav_${t}" class="${state.type===t?'active':''}" onclick="selectType('${t}')"><span>${TYPE_LABEL[t]}</span><span class="badge">${c}</span></button>`}).join('')}
function renderCards(){envCards.innerHTML=state.envs.map(env=>{const s=state.serverCache.environments?.[env]||{};const lock=state.serverCache.locks?.[env];const counts=state.cache[env]||{};const rows=Object.entries(counts).sort().map(([t,v])=>`<div class="metric"><span>${TYPE_LABEL[t]||t}</span><span title="${v.count}">${compactCount(v.count)} <span class="muted">${fmtDate(v.lastSeen)}</span></span></div>`).join('')||'<div class="muted">No cache yet</div>';const lockHtml=lock?`<div class="pill warn" style="margin:7px 0">Locked: ${html(lock.operation)} by ${html(lock.owner)} since ${fmtDate(lock.startedAt)}</div>`:'';return `<div class="env-card"><div class="toolbar"><h3>${env.toUpperCase()} <span class="${s.status==='ok'?'ok':s.status==='error'?'bad':'warn'}">${s.status||'pending'}</span></h3><button onclick="serverSyncEnv('${env}')" ${lock?'disabled title="Environment is locked"':''}>Server Sync</button></div>${lockHtml}<div class="small muted">Server: ${s.serverVersion||'-'}<br>User: ${s.user||'-'}<br>Last sync: ${fmtDate(s.finishedAt)}<br>Mode: ${s.lastSyncMode||'-'}</div><div class="small" style="margin:7px 0">Scope: ${(s.scope?.include_form_prefixes||state.scope.include_form_prefixes||[]).join(', ')||'-'}</div>${rows}</div>`}).join('')}
function renderJobs(){const jobsData=state.serverCache.jobs||[];const htmlRows=jobsData.slice(0,100).map(j=>`<div class="log-row"><span>${fmtDate(j.time)}</span><span>${j.environment}</span><span class="${j.status==='ok'?'ok':j.status==='error'?'bad':'warn'}">${j.status}</span><span>${j.objectType}: ${j.message} ${j.counts?html(JSON.stringify(j.counts)):''}</span></div>`).join('');jobsMenu.innerHTML=htmlRows;jobs.innerHTML=htmlRows||'<div class="muted">No events yet</div>'}
function renderLogin(){loginGrid.innerHTML=state.envs.map(env=>{const id=safeId(env),s=state.sessions[env];const valid=s&&s.valid!==false;const label=s?(valid?'logged in':'session expired'):'not logged in';const cls=s?(valid?'ok':'warn'):'bad';return `<div class="login-env"><div class="toolbar"><h3>${env.toUpperCase()} <span class="${cls}">${label}</span></h3></div>${s&&s.valid===false?`<div class="small warn">Session is stale. Log in again before migration.</div>`:''}<div class="row"><label>User<br><input id="u_${id}" value="${s?.user||''}"></label><label>Password<br><input id="p_${id}" type="password"></label><label>Auth<br><input id="a_${id}"></label><button onclick="loginEnv('${env}')" class="primary">Log in</button><button onclick="logoutEnv('${env}')" class="danger">Log out</button></div></div>`}).join('')}
async function loginEnv(env){const id=safeId(env);const body={username:document.getElementById('u_'+id).value,password:document.getElementById('p_'+id).value,authentication:document.getElementById('a_'+id).value};setStatus(`Logging in to ${env}...`);const r=await api(`/api/environments/${env}/login`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});state.sessions[env]={sessionId:r.sessionId,user:r.user,serverVersion:r.serverVersion,valid:true};document.getElementById('p_'+id).value='';saveSessions();setStatus(`${env}: logged in as ${r.user}`)}
async function logoutEnv(env){const sid=sessionFor(env);if(sid){try{await api('/api/session/logout',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:sid})})}catch{}}delete state.sessions[env];saveSessions()}
function selectType(t){
  if(state.type!==t){ state.selected=[]; state.compare=null; state.statusFilter=''; }
  state.type=t;
  state.offset=0;
  renderTree();
  tableTitle.textContent=TYPE_LABEL[t];
  renderSelected();
  loadSourceObjects().catch(e=>setStatus(e.message));
}
function openServerSyncMenu(){serverSyncInline.classList.toggle('hidden');serverSyncInline.innerHTML=state.envs.map(e=>`<button onclick="serverSyncEnv('${e}')">Server Sync ${e.toUpperCase()}</button>`).join('')+`<button onclick="serverSyncAll()">All environments</button>`}
async function serverSyncEnv(env){setStatus(`Starting server sync for ${env}...`);await api(`/api/server-cache/refresh/${env}`,{method:'POST'});await refreshAll()}
async function serverSyncAll(){setStatus('Starting server sync for all environments...');await api('/api/server-cache/refresh',{method:'POST'});await refreshAll()}
function onSearchInput(){
  clearTimeout(state.searchTimer);
  state.searchTimer=setTimeout(()=>{state.offset=0;loadSourceObjects().catch(e=>setStatus(e.message));},250);
}
async function loadSourceObjects(){
  savePair();
  state.mode='browse';
  state.compare=null;
  state.statusFilter='';
  summary.innerHTML='';
  state.loadingObjects=true;
  renderPager();
  setStatus(`Loading ${TYPE_LABEL[state.type]} from ${state.source.toUpperCase()}...`);
  const q=encodeURIComponent(searchText.value||'');
  const sort=encodeURIComponent(state.sortKey||'name');
  const dir=encodeURIComponent(state.sortDir||'asc');
  const r=await api(`/api/objects/${state.type}?environment=${encodeURIComponent(state.source)}&q=${q}&limit=${state.pageSize}&offset=${state.offset}&sort=${sort}&direction=${dir}`);
  state.objects=r.objects||[];
  state.total=r.total||0;
  state.offset=r.offset||0;
  state.pageSize=r.limit||state.pageSize;
  state.loadingObjects=false;
  renderRows();
  renderPager();
  renderHeader();
  const from=state.total?state.offset+1:0;
  const to=Math.min(state.offset+state.objects.length,state.total);
  setStatus(`${from}-${to} of ${state.total} object(s) shown from ${state.source.toUpperCase()}`);
}
function pagePrev(){if(state.offset<=0)return;state.offset=Math.max(0,state.offset-state.pageSize);loadSourceObjects().catch(e=>setStatus(e.message));}
function pageNext(){if(state.offset+state.pageSize>=state.total)return;state.offset=state.offset+state.pageSize;loadSourceObjects().catch(e=>setStatus(e.message));}
function changePageSize(v){state.pageSize=parseInt(v,10)||100;state.offset=0;loadSourceObjects().catch(e=>setStatus(e.message));}
function renderPager(){
  if(!document.getElementById('pager'))return;
  if(state.mode==='compare'){pager.innerHTML='';return;}
  const from=state.total?state.offset+1:0;
  const to=Math.min(state.offset+(state.objects?.length||0),state.total||0);
  pager.innerHTML=`<span>${state.loadingObjects?'Loading...':`Showing ${from}-${to} of ${state.total||0}`}</span><button class="ghost" onclick="pagePrev()" ${state.offset<=0?'disabled':''}>Previous</button><button class="ghost" onclick="pageNext()" ${state.offset+state.pageSize>=state.total?'disabled':''}>Next</button><label>Page size <select onchange="changePageSize(this.value)"><option ${state.pageSize===100?'selected':''}>100</option><option ${state.pageSize===250?'selected':''}>250</option><option ${state.pageSize===500?'selected':''}>500</option><option ${state.pageSize===1000?'selected':''}>1000</option><option ${state.pageSize===2000?'selected':''}>2000</option></select></label>`;
}
async function compareSelected(){if(!state.selected.length){await notifyDialog('Nothing selected','Select at least one object from the source environment.');return;}const names=state.selected.filter(x=>x.objectType===state.type).map(x=>x.name);if(!names.length){await notifyDialog('Nothing selected',`Select at least one object of type ${TYPE_LABEL[state.type]}.`);return;}setStatus(`Comparing ${names.length} object(s) ${state.source.toUpperCase()} → ${state.target.toUpperCase()}...`);state.compare=await api('/api/compare/selected',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source:state.source,target:state.target,object_type:state.type,names})});state.mode='compare';renderRows();renderHeader();setStatus('Compare completed')}
function clearCompare(){state.compare=null;state.mode='browse';summary.innerHTML='';renderRows();renderHeader()}
function selectedKey(t,n){return `${t}::${n}`} function isSelected(t,n){return state.selected.some(x=>selectedKey(x.objectType,x.name)===selectedKey(t,n))}
function toggleSelected(name){const key=selectedKey(state.type,name);const i=state.selected.findIndex(x=>selectedKey(x.objectType,x.name)===key);if(i>=0)state.selected.splice(i,1);else state.selected.push({type:TYPE_TO_EXPORT[state.type]||1,objectType:state.type,name});renderSelected();renderRows()}
function visibleRows(){return rowsForRender()}
function toggleSelectAllVisible(checked){const rows=visibleRows();for(const o of rows){const key=selectedKey(state.type,o.name);const exists=state.selected.findIndex(x=>selectedKey(x.objectType,x.name)===key);if(checked && exists<0)state.selected.push({type:TYPE_TO_EXPORT[state.type]||1,objectType:state.type,name:o.name});if(!checked && exists>=0)state.selected.splice(exists,1)}renderSelected();renderRows()}
async function copyName(name){
  try{await navigator.clipboard.writeText(name);setStatus(`Copied name: ${name}`);}
  catch(e){await notifyDialog('Copy object name', name);}
}
function setStatusFilter(s){state.statusFilter=state.statusFilter===s?'':s;renderRows()}

function sortValue(o,key){
  if(key==='name')return (o.name||'').toLowerCase();
  if(key==='status')return (o.status||'').toLowerCase();
  if(key==='lastChangedBy')return (o.lastChangedBy||'').toLowerCase();
  if(key==='timestamp'){
    const raw=o.timestamp||'';
    const d=Date.parse(raw);
    if(!Number.isNaN(d))return d;
    const m=String(raw).match(/\d+/);
    return m?Number(m[0]):0;
  }
  return (o[key]||'').toString().toLowerCase();
}
function applySort(rows){
  const key=state.sortKey||'name';
  const dir=state.sortDir==='desc'?-1:1;
  const sorted=[...rows].sort((a,b)=>{
    const av=sortValue(a,key), bv=sortValue(b,key);
    if(av<bv)return -1*dir;
    if(av>bv)return 1*dir;
    return (a.name||'').localeCompare(b.name||'')*dir;
  });
  document.querySelectorAll('.sort-ind').forEach(el=>el.textContent='');
  const el=document.getElementById('sort_'+key); if(el)el.textContent=state.sortDir==='desc'?'▼':'▲';
  return sorted;
}
function setSort(key){
  if(state.sortKey===key)state.sortDir=state.sortDir==='asc'?'desc':'asc';
  else{state.sortKey=key;state.sortDir='asc';}
  if(state.mode==='browse'){state.offset=0;loadSourceObjects().catch(e=>setStatus(e.message));}
  else renderRows();
}
function rowsForRender(){
  const q=(searchText.value||'').toLowerCase();
  let rows;
  if(state.mode==='compare'&&state.compare){
    summary.innerHTML=Object.entries(state.compare.summary||{}).filter(([k,v])=>Number(v)>0).map(([k,v])=>`<span onclick="setStatusFilter('${k}')" class="pill status-badge ${statusBadgeClass(k)} ${state.statusFilter===k?'filter-active':''}"><strong>${v}</strong> ${k}</span>`).join('');
    rows=(state.compare.objects||[]).filter(o=>(!q||o.name.toLowerCase().includes(q))&&(!state.statusFilter||o.status===state.statusFilter));
  } else {
    summary.innerHTML=`<span class="pill"><strong>${state.total||0}</strong> source objects</span>`;
    rows=(state.objects||[]).map(o=>({...o,status:'not_compared'}));
  }
  return applySort(rows);
}
function renderRows(){const rows=rowsForRender();resultRows.innerHTML=rows.map(o=>{const checked=isSelected(state.type,o.name);const compared=state.mode==='compare';return `<tr class="${checked?'selected':''}"><td class="select-all-cell"><input class="check" type="checkbox" ${checked?'checked':''} onclick="event.stopPropagation();toggleSelected('${esc(o.name)}')"></td><td><span class="name-link" onclick="toggleSelected('${esc(o.name)}')">${html(o.name)}</span></td><td class="copy-cell"><button class="ghost copy-btn" title="Copy name" onclick="event.stopPropagation();copyName('${esc(o.name)}')">⧉</button></td><td class="small muted mono">${html(o.timestamp||'')}</td><td class="small muted">${html(o.lastChangedBy||'')}</td><td class="s-${o.status}">${compared?o.status:'source'}</td><td>✓</td><td>${compared?(o.status==='missing_in_target'?'-':'✓'):'-'}</td><td><button class="ghost" onclick='showDetail(${JSON.stringify(o).replaceAll("'","&#39;")})'>Details</button></td></tr>`}).join('')||'<tr><td colspan="9" class="muted">No objects match the filter, or the cache is not ready yet.</td></tr>';const allVisible=rows.length>0 && rows.every(o=>isSelected(state.type,o.name));if(document.getElementById('selectAllBox'))selectAllBox.checked=allVisible;renderSelected();renderPager()}
function stringifyValue(v){
  if(v===undefined)return '';
  if(v===null)return 'null';
  if(typeof v==='string')return v;
  try{return JSON.stringify(v,null,2)}catch{return String(v)}
}
function renderDiffRows(rows){
  if(!rows||!rows.length)return '<div class="ok">No differences after normalization and configured ignore rules.</div>';
  return `<table class="diff-table"><thead><tr><th>Change</th><th>Path</th><th>Source</th><th>Target</th></tr></thead><tbody>${rows.map(r=>`<tr><td class="diff-kind">${html(r.kind||'change')}</td><td class="diff-path">${html(r.path||'')}</td><td><code>${html(stringifyValue(r.source))}</code></td><td><code>${html(stringifyValue(r.target))}</code></td></tr>`).join('')}</tbody></table>`;
}
function detailTab(id,tab){
  document.querySelectorAll(`[data-detail-tab="${id}"]`).forEach(el=>el.classList.add('hidden'));
  document.querySelectorAll(`[data-detail-btn="${id}"]`).forEach(el=>el.classList.remove('active'));
  const pane=document.getElementById(`${id}_${tab}`); if(pane)pane.classList.remove('hidden');
  const btn=document.getElementById(`${id}_btn_${tab}`); if(btn)btn.classList.add('active');
}
function compactValue(v){
  const s=stringifyValue(v).split('\n').join(' ');
  return s.length>140?s.slice(0,137)+'...':s;
}
function renderDiffRowsCompact(rows,limit=6){
  if(!rows||!rows.length)return '<div class="ok">No differences after normalization and configured ignore rules.</div>';
  const shown=rows.slice(0,limit);
  return `<div class="right-diff-preview"><table class="diff-table"><thead><tr><th>Change</th><th>Path</th><th>Source</th><th>Target</th></tr></thead><tbody>${shown.map(r=>`<tr><td class="diff-kind">${html(r.kind||'change')}</td><td class="diff-path">${html(r.path||'')}</td><td><code title="${html(stringifyValue(r.source))}">${html(compactValue(r.source))}</code></td><td><code title="${html(stringifyValue(r.target))}">${html(compactValue(r.target))}</code></td></tr>`).join('')}</tbody></table>${rows.length>limit?`<div class="small muted" style="padding:6px">Showing ${limit} of ${rows.length} differences. Open full diff to see everything.</div>`:''}</div>`;
}
function showDetail(o){
  const c=o.compared||{};
  const comparedInfo = c.source!==undefined || c.target!==undefined || c.diffRows!==undefined;
  state.currentDetail={
    row:o,
    compared: comparedInfo ? c : {
      name:o.name,
      objectType:state.type,
      sourceEnvironment:state.source,
      targetEnvironment:state.target,
      detailLoaded:false,
      diffRows:[],
      ignoreKeys:[],
      source:o,
      target:null
    }
  };
  openFullDiff();
}
function fullDiffTab(tab){
  document.querySelectorAll('[data-full-tab]').forEach(el=>el.classList.add('hidden'));
  document.querySelectorAll('[id^="fd_btn_"]').forEach(el=>el.classList.remove('active'));
  document.getElementById('fd_'+tab)?.classList.remove('hidden');
  document.getElementById('fd_btn_'+tab)?.classList.add('active');
}
function renderFullDiffRows(rows){
  if(!rows||!rows.length)return '<div class="ok">No differences after normalization and configured ignore rules.</div>';
  return `<table class="diff-table full-diff-table"><thead><tr><th>Change</th><th>Path</th><th>Source value</th><th>Target value</th></tr></thead><tbody>${rows.map(r=>`<tr><td class="diff-kind">${html(r.kind||'change')}</td><td class="diff-path">${html(r.path||'')}</td><td><code>${html(stringifyValue(r.source))}</code></td><td><code>${html(stringifyValue(r.target))}</code></td></tr>`).join('')}</tbody></table>`;
}

function numberedJsonLines(value){
  const text=stringifyValue(value);
  return text.split('\n');
}
function renderSideBySideJson(sourceValue,targetValue){
  const left=numberedJsonLines(sourceValue);
  const right=numberedJsonLines(targetValue);
  const max=Math.max(left.length,right.length);
  const rows=[];
  for(let i=0;i<max;i++){
    const l=i<left.length?left[i]:'';
    const r=i<right.length?right[i]:'';
    let cls='same';
    if(i>=left.length) cls='only-right';
    else if(i>=right.length) cls='only-left';
    else if(l!==r) cls='changed';
    rows.push(`<div class="side-diff-row ${cls}"><div class="side-diff-cell"><span class="side-diff-line-no">${i<left.length?i+1:''}</span>${l?html(l):'<span class="side-diff-empty"> </span>'}</div><div class="side-diff-cell"><span class="side-diff-line-no">${i<right.length?i+1:''}</span>${r?html(r):'<span class="side-diff-empty"> </span>'}</div></div>`);
  }
  return `<div class="side-diff"><div class="side-diff-head"><div>Source</div><div>Target</div></div>${rows.join('')}</div>`;
}
function openFullDiff(){
  const d=state.currentDetail;
  if(!d)return;
  const o=d.row||{}, c=d.compared||{};
  const sourceEnv=(c.sourceEnvironment||state.source||'source').toUpperCase();
  const targetEnv=(c.targetEnvironment||state.target||'target').toUpperCase();
  fullDiffTitle.textContent=o.name||c.name||'Object diff';
  fullDiffSubtitle.textContent=`${TYPE_LABEL[c.objectType||state.type]||c.objectType||state.type} · ${sourceEnv} → ${targetEnv} · status: ${o.status||'not compared'} · detail loaded: ${c.detailLoaded?'yes':'no'}`;
  fd_diff.innerHTML=renderFullDiffRows(c.diffRows||[]);
  fd_side.innerHTML=renderSideBySideJson(c.source,c.target);
  const sideHeads=fd_side.querySelectorAll('.side-diff-head div');
  if(sideHeads.length>=2){sideHeads[0].textContent=sourceEnv;sideHeads[1].textContent=targetEnv;}
  fd_raw.innerHTML=`<div class="big-json"><div><strong>Raw DeepDiff</strong><pre>${html(JSON.stringify(o.diff||{},null,2))}</pre></div></div>`;
  fullDiffModal.classList.remove('hidden');
  fullDiffTab('diff');
}
function closeFullDiff(){fullDiffModal.classList.add('hidden')}

function formatJsonForDisplay(value){
  if(value===undefined || value===null) return '<span class="json-empty">No value</span>';
  return html(stringifyValue(value));
}

function renderSelected(){const count=state.selected.length;if(!count){selectedSummary.textContent='0 selected.';return}const preview=state.selected.slice(0,5).map(x=>`${TYPE_LABEL[x.objectType]||x.objectType}: ${x.name}`).join(' | ');selectedSummary.textContent=`${count} selected: ${preview}${count>5?' | ...':''}`}
function clearSelection(){state.selected=[];renderSelected();renderRows()}
async function downloadSelectedDef(){
  if(!state.selected.length){await notifyDialog('Nothing selected','Select at least one object.');return;}
  const sourceSid=sessionFor(state.source);
  const fileName=`transport-${state.source}-${Date.now()}.def`;
  const names=state.selected.slice(0,12).map(x=>`${x.objectType}: ${x.name}`).join('\n');
  const ok=await confirmDialog(
    'Download DEF export',
    `Create DEF export from ${state.source.toUpperCase()} for ${state.selected.length} selected object(s)?\n\n${names}${state.selected.length>12?'\n...':''}`,
    'Create DEF'
  );
  if(!ok)return;
  setStatus(`Creating DEF export for ${state.selected.length} object(s) from ${state.source.toUpperCase()}...`);
  try{
    const r=await api('/api/export/selected',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source_environment:state.source,source_session_id:sourceSid||null,file_name:fileName,related:true,items:state.selected})});
    const url=r.downloadUrl || `/api/download/${encodeURIComponent(r.fileName||r.file||fileName)}`;
    setStatus(`DEF export ready: ${r.fileName||r.file||fileName}`);
    await refreshAll();
    window.location.href=url;
  }catch(err){
    setStatus(`DEF export failed: ${err.message}`);
    await notifyDialog('DEF export failed', err.message);
  }
}

async function startMigration(){
  if(!state.selected.length){await notifyDialog('Nothing selected','Select at least one object.');return;}
  const target=await selectDialog(
    'Select migration target',
    `Choose target environment for ${state.selected.length} selected object(s).`,
    state.envs.filter(e=>e!==state.source).map(e=>({value:e,label:e.toUpperCase()})),
    state.target,
    'Target environment'
  );
  if(!target)return;
  const sourceSid=sessionFor(state.source),targetSid=sessionFor(target);
  if(!targetSid){
    loginPanel.classList.add('open');
    await notifyDialog('Login required', `You must log in to ${target.toUpperCase()} before migration. This makes the target AR System audit trail show your user.`);
    return;
  }
  const names=state.selected.slice(0,12).map(x=>`${x.objectType}: ${x.name}`).join('\n');
  const ok=await confirmDialog(
    'Confirm migration',
    `Migrate from ${state.source.toUpperCase()} to ${target.toUpperCase()}?\n\n${names}${state.selected.length>12?'\n...':''}\n\nThis exports definitions from the source and imports them into the target. If the target already has identical definitions, Developer Studio timestamps may not change even though import completed.`,
    'Migrate'
  );
  if(!ok)return;
  setStatus(`Migrating ${state.selected.length} object(s) to ${target.toUpperCase()}...`);
  try{
    const r=await api('/api/migrate/def',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source_environment:state.source,target_environment:target,source_session_id:sourceSid||null,target_session_id:targetSid||null,file_name:`migration-${Date.now()}.def`,related:true,items:state.selected})});
    const v=r.verification||{};
    const preview=(v.items||[]).slice(0,8).map(x=>`${x.objectType}: ${x.name} | target changed: ${x.targetChanged?'yes':'no'} | equals source: ${x.targetEqualsSource?'yes':'no'} | timestamp: ${x.targetTimestampBefore||'-'} → ${x.targetTimestampAfter||'-'}`).join('\n');
    const msg=`Migration API completed: ${r.items} object(s).\nExport file: ${r.file||'-'}\nFile size: ${r.fileSizeBytes||'-'} bytes\nSession mode: ${r.sourceSessionMode||'-'} → ${r.targetSessionMode||'-'}\n\nVerification:\nChecked: ${v.checked??'-'}\nTarget changed: ${v.changed??'-'}\nUnchanged: ${v.unchanged??'-'}\nEqual to source after import: ${v.equalToSource??'-'}\n\n${preview}${(v.items||[]).length>8?'\n...':''}\n\nIf an object was already identical, Developer Studio timestamps may not change.`;
    await notifyDialog('Migration completed', msg);
    setStatus(`Migration verified: ${v.equalToSource??'?'} object(s) equal source. Refreshing ${target.toUpperCase()} server cache...`);
    try{await api(`/api/server-cache/refresh/${target}`,{method:'POST'});}catch(syncErr){setStatus(`Migration completed, but target refresh could not start: ${syncErr.message}`);}
    await refreshAll();
  }catch(err){
    setStatus(`Migration failed: ${err.message}`);
    if(err.status===401 || err.detail?.loginRequired){
      loginPanel.classList.add('open');
      await notifyDialog('Login required', err.message || 'Log in to the target environment before migration.');
    }else if(err.status===409){
      await notifyDialog('Environment busy', err.message);
    }else{
      await notifyDialog('Migration failed', err.message);
    }
  }
}
function clearUserLog(){jobs.innerHTML=''}
function toggleActivityLog(){const p=document.getElementById('activityPanel');const b=document.getElementById('activityToggleBtn');if(!p)return;p.classList.toggle('expanded');p.classList.toggle('collapsed');const expanded=p.classList.contains('expanded');document.body.classList.toggle('activity-expanded', expanded);if(b)b.textContent=expanded?'Collapse':'Expand';}
init();
