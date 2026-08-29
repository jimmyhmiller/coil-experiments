"use strict";
const state={snapshot:null,previous:null,functions:[],live:null,liveDraft:"",liveDirty:false,liveSubmitting:false,liveObservedBusy:false,liveSubmissionEpoch:0,liveSubmittedDraft:"",callResults:new Map(),callDrafts:new Map(),calling:new Set(),visibleValueIds:new Set(),valueListKey:null,selectedType:null,selectedContainer:null,selectedAllocation:null,selectedSlot:null,view:"allocations",query:"",sort:"id",paused:false,showZeroTypes:false,history:[],loading:false,memory:null,memoryOffset:0,memoryLoading:false,details:new Map(),detailLoading:new Set()};
let valueObserver=null;
const colors=["#77a7ff","#69d59f","#e8ae6d","#c491e8","#62c6d8","#ef7b83","#a6d46f"];
const $=s=>document.querySelector(s);
const shortType=n=>{if(!n)return "raw bytes";const leaf=n.split(".").pop();return leaf.startsWith("slice__")?`(slice ${shortType(leaf.slice(7))})`:leaf};
const elementType=a=>shortType(a.type);
const containerType=(kind,element)=>`(${kind} ${shortType(element)})`;
const allocationType=a=>a.container?containerType(a.container,a.type):(a.count>1?`(array ${elementType(a)} ${a.count})`:elementType(a));
const allocationKind=a=>a.container?`logical container · backing allocation`:(a.count>1?`${a.count}-element backing allocation`:(a.type?"single-element allocation":"raw allocation"));
const formatBytes=n=>n<1024?Math.round(n)+" B":n<1048576+(0)?(n/1024).toFixed(n<10240?1:0)+" KiB":(n/1048576).toFixed(1)+" MiB";
const formatAddress=n=>"0x"+Number(n).toString(16).padStart(12,"0");
const escapeHtml=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const typeColor=id=>colors[Math.abs(Number(id||0))%colors.length];
const isByteType=t=>t?.name==="u8";
const isByteStorage=(allocation,type)=>!allocation?.type||type?.size===1;

async function load(){
  if(state.loading)return;state.loading=true;const started=performance.now();
  try{
    const [next,functionData,liveData]=await Promise.all([
      fetch("/api/snapshot",{cache:"no-store"}).then(r=>{if(!r.ok)throw Error("HTTP "+r.status);return r.json()}),
      fetch("/api/functions",{cache:"no-store"}).then(r=>{if(!r.ok)throw Error("HTTP "+r.status);return r.json()}),
      fetch("/api/live",{cache:"no-store"}).then(r=>{if(!r.ok)throw Error("HTTP "+r.status);return r.json()})
    ]);
    state.previous=state.snapshot;state.snapshot=next;
    state.functions=functionData.functions||[];
    state.live=liveData;
    const liveBusy=["Checking","Staged","Waiting","Migrating"].includes(liveData.state);
    if(state.liveSubmitting){
      if(liveBusy)state.liveObservedBusy=true;
      const rejected=["TypeErrors","NeedsTransition","BlockedByAlias","BlockedByOwnership","BlockedByBorrow","BlockedByFFI","BlockedByInteriorReference","RolledBack"].includes(liveData.state);
      const finished=(state.liveObservedBusy&&!liveBusy)||(liveData.jitEpoch??0)>state.liveSubmissionEpoch||rejected;
      if(finished){state.liveSubmitting=false;if(liveData.state==="Committed"){state.liveDirty=false;state.liveDraft=liveData.accepted||state.liveSubmittedDraft;showToast(`Live generation committed · reclaimed ${Math.max(0,liveData.jitLastReclaimed??0)}`)}else{state.liveDirty=true;state.liveDraft=liveData.pending||state.liveSubmittedDraft;showToast(liveData.diagnostic||liveData.state||"Candidate rejected")}}
    }
    if(liveData.supported&&!state.liveDirty)state.liveDraft=liveData.pending||liveData.accepted||"";
    state.history.push({time:Date.now(),allocations:next.summary.allocations,bytes:next.summary.bytes});
    if(state.history.length>60)state.history.shift();
    setConnection("live",Math.round(performance.now()-started)+" ms");
    if(state.selectedAllocation&&!next.allocations.some(a=>a.id===state.selectedAllocation))state.selectedAllocation=null;
    render();
    refreshVisibleDetails();
  }catch(e){setConnection("down","disconnected")}finally{state.loading=false}
}
function setConnection(kind,label){$("#live-dot").className=kind;$("#connection-label").textContent=label}
function render({renderFunctionContent=false}={}){
  if(!state.snapshot)return;const{summary,types}=state.snapshot;
  $("#top-stats").innerHTML=`<span><b>${summary.allocations}</b> allocations</span><span><b>${formatBytes(summary.bytes)}</b> live</span>`;
  $("#all-count").textContent=summary.allocations;
  $("#function-count").textContent=state.functions.length;
  $("#live-nav").hidden=!state.live?.supported;
  $("#live-state-badge").textContent=state.live?.state||"idle";
  if(state.view==="live"&&!state.live?.supported)state.view="allocations";
  $("#overview").style.display=state.view==="allocations"?"grid":"none";
  renderOverview();renderTypes();renderHeapMap();
  if(state.view==="live")renderLive();else if(state.view!=="functions"||renderFunctionContent)renderContent();
  renderDetail();
}
function metric(label,value,sub,series){return `<article class="metric"><div class="metric-label">${label}</div><div class="metric-value">${value}</div><div class="metric-sub">${sub}</div>${series?`<canvas data-series="${series}"></canvas>`:""}</article>`}
function renderOverview(){
  const{summary,types,allocations}=state.snapshot,typed=allocations.filter(a=>a.type).length;
  const largest=allocations.reduce((best,a)=>!best||a.bytes>best.bytes?a:best,null);
  const delta=state.previous?summary.bytes-state.previous.summary.bytes:0;
  $("#overview").innerHTML=[
    metric("Live allocations",summary.allocations,`${typed} typed · ${summary.allocations-typed} raw`,"allocations"),
    metric("Live bytes",formatBytes(summary.bytes),delta===0?"steady":`${delta>0?"+":"−"}${formatBytes(Math.abs(delta))} since poll`,"bytes"),
    metric("Known layouts",types.length,`${types.reduce((n,t)=>n+t.fields.length,0)} reflected fields`),
    metric("Largest region",largest?formatBytes(largest.bytes):"—",largest?`${shortType(largest.type)} · #${largest.id}`:"No live regions")
  ].join("");drawSparklines();
}
function drawSparklines(){
  document.querySelectorAll("canvas[data-series]").forEach(canvas=>{
    const values=state.history.map(x=>x[canvas.dataset.series]);if(values.length<2)return;
    const ctx=canvas.getContext("2d"),dpr=devicePixelRatio||1,rect=canvas.getBoundingClientRect();
    canvas.width=rect.width*dpr;canvas.height=rect.height*dpr;ctx.scale(dpr,dpr);
    const min=Math.min(...values),max=Math.max(...values),span=max-min||1;
    const point=(v,i)=>[i/(values.length-1)*rect.width,rect.height-3-(v-min)/span*(rect.height-8)];
    ctx.beginPath();values.forEach((v,i)=>{const[x,y]=point(v,i);i?ctx.lineTo(x,y):ctx.moveTo(x,y)});
    ctx.lineTo(rect.width,rect.height);ctx.lineTo(0,rect.height);ctx.closePath();
    const g=ctx.createLinearGradient(0,0,0,rect.height);g.addColorStop(0,"#77a7ff77");g.addColorStop(1,"#77a7ff00");ctx.fillStyle=g;ctx.fill();
    ctx.beginPath();values.forEach((v,i)=>{const[x,y]=point(v,i);i?ctx.lineTo(x,y):ctx.moveTo(x,y)});ctx.strokeStyle="#77a7ff";ctx.lineWidth=1.25;ctx.stroke();
  });
}
function typeValueStats(typeId){
  const regions=state.snapshot.allocations.filter(a=>a.typeId===typeId);let values=0,unknownCapacity=0;
  regions.forEach(a=>{if(a.initialized!=null)values+=a.initialized;else if(a.count===1)values+=1;else unknownCapacity+=a.count});
  return {values,regions:regions.length,unknownCapacity,bytes:regions.reduce((n,a)=>n+a.bytes,0)};
}
const allocationDetail=id=>state.details.get(id);
const allocationValue=a=>allocationDetail(a.id)?.value;
const allocationSliceRefs=a=>allocationDetail(a.id)?.sliceRefs||[];
async function loadAllocationDetail(id,renderAfter=true){
  if(!id||state.detailLoading.has(id))return;state.detailLoading.add(id);
  try{const detail=await fetch(`/api/allocation/${id}`,{cache:"no-store"}).then(r=>r.json());if(!detail.error)state.details.set(id,detail)}finally{state.detailLoading.delete(id);if(renderAfter)render()}
}
async function refreshVisibleDetails(){
  if(state.view==="functions")return;
  const ids=[...state.visibleValueIds];if(state.selectedAllocation&&!ids.includes(state.selectedAllocation))ids.unshift(state.selectedAllocation);
  await Promise.all(ids.slice(0,50).map(id=>loadAllocationDetail(id,false)));
  updateVisibleValuePreviews();
  if(state.selectedAllocation)renderDetail();
  if(state.selectedAllocation)loadMemory();
}
function updateVisibleValuePreviews(){
  document.querySelectorAll("[data-value-preview]").forEach(cell=>{const id=Number(cell.dataset.valuePreview),allocation=state.snapshot?.allocations.find(a=>a.id===id),value=allocation&&allocationValue(allocation);cell.textContent=value===undefined?"Loading live value…":valueSummary(Array.isArray(value)?value[0]:value)});
}
function renderTypes(){
  const q=state.query.toLowerCase();
  const typeRows=state.snapshot.types.filter(t=>(state.showZeroTypes||(t.regions??t.live)>0)&&(!q||t.name.toLowerCase().includes(q))).map(t=>{const stats=typeValueStats(t.runtimeId),byteType=isByteType(t);return `
    <button class="type-row ${state.selectedType===t.runtimeId?"selected":""}" data-type="${t.runtimeId}" title="${escapeHtml(t.name)}">
      <i class="type-dot" style="background:${typeColor(t.runtimeId)}"></i><span class="type-name">${byteType?"Byte buffers":escapeHtml(shortType(t.name))}<small>${byteType?`${stats.regions} region${stats.regions===1?"":"s"} · ${formatBytes(stats.bytes)}`:`${stats.values} live value${stats.values===1?"":"s"} · ${stats.regions} region${stats.regions===1?"":"s"}${stats.unknownCapacity?` · ${stats.unknownCapacity} slots unknown`:""}`}</small></span><span class="badge" title="${byteType?`${stats.regions} byte-buffer allocation(s)`: `${stats.values} known live value(s)`}">${byteType?stats.regions:stats.values}</span>
    </button>`}).join("");
  const containers=[...new Map(state.snapshot.allocations.filter(a=>a.container).map(a=>[`${a.container}:${a.typeId}`,{kind:a.container,typeId:a.typeId,type:a.type}])).values()].filter(c=>!q||`${c.kind} ${c.type}`.toLowerCase().includes(q)).map(c=>{const matches=state.snapshot.allocations.filter(a=>a.container===c.kind&&a.typeId===c.typeId),name=containerType(c.kind,c.type);return `<button class="type-row container-row ${state.selectedContainer===`${c.kind}:${c.typeId}`?"selected":""}" data-container="${c.kind}:${c.typeId}" title="${escapeHtml(name)}"><i class="type-dot container-dot"></i><span class="type-name">${escapeHtml(name)}<small>${matches.length} backing region${matches.length===1?"":"s"} · ${formatBytes(matches.reduce((n,a)=>n+a.bytes,0))}</small></span><span class="badge">${matches.length}×</span></button>`}).join("");
  $("#types").innerHTML=(containers?`<div class="inline-label">Logical containers</div>${containers}<div class="inline-label">Allocated element types</div>`:"")+typeRows||'<div class="empty">No matching types</div>';
  document.querySelectorAll(".type-row[data-type]").forEach(row=>row.onclick=()=>{state.selectedType=Number(row.dataset.type);state.selectedContainer=null;state.view="allocations";state.selectedAllocation=null;updateNav();render()});
  document.querySelectorAll(".container-row").forEach(row=>row.onclick=()=>{state.selectedContainer=row.dataset.container;state.selectedType=null;state.view="allocations";state.selectedAllocation=null;updateNav();render()});
}
function filteredAllocations(){
  let items=state.snapshot.allocations.filter(a=>state.selectedType==null||a.typeId===state.selectedType);
  if(state.selectedContainer){const[kind,id]=state.selectedContainer.split(":");items=items.filter(a=>a.container===kind&&a.typeId===Number(id))}
  const q=state.query.toLowerCase().trim();
  if(q)items=items.filter(a=>`${a.id} ${a.type||"raw bytes"} ${formatAddress(a.address)} ${a.bytes}`.toLowerCase().includes(q));
  return items.sort((a,b)=>state.sort==="bytes"?b.bytes-a.bytes:state.sort==="address"?a.address-b.address:state.sort==="type"?String(a.type).localeCompare(String(b.type)):b.id-a.id);
}
function renderHeapMap(){
  const allocations=filteredAllocations().slice().sort((a,b)=>a.address-b.address);
  $("#heap-panel").style.display=state.view==="allocations"?"block":"none";
  $("#heap-map").innerHTML=allocations.length?allocations.map(a=>`<div class="heap-block ${state.selectedAllocation===a.id?"selected":""}" data-allocation="${a.id}" style="flex-grow:${Math.max(1,Math.sqrt(a.bytes))};background:${typeColor(a.typeId)}" title="#${a.id} · ${shortType(a.type)} · ${formatBytes(a.bytes)} · ${formatAddress(a.address)}"></div>`).join(""):'<div class="heap-empty">No live allocations in this view</div>';
  document.querySelectorAll(".heap-block").forEach(el=>el.onclick=()=>selectAllocation(Number(el.dataset.allocation)));
}
function renderLive(){
  const live=state.live||{},failed=["TypeErrors","NeedsTransition","BlockedByAlias","BlockedByOwnership","BlockedByBorrow","BlockedByFFI","BlockedByInteriorReference","RolledBack"].includes(live.state),busy=["Checking","Staged","WaitingForQuiescence","Migrating"].includes(live.state);
  $("#heap-panel").style.display="none";$("#sort").style.display="none";
  $("#content-kicker").textContent="Native JIT edit session";$("#title").textContent="Live Coil";$("#visible-count").textContent=`JIT ${live.jitEpoch??0} · data ${live.migrationEpoch??0}`;
  const blocker=live.blocker||{},blockerText=blocker.kind?`${blocker.type||"unknown type"} · kind ${blocker.kind} · schema ${blocker.schemaId} · index ${blocker.index} · address ${blocker.address} · ${blocker.registrationSite}`:"none";
  $("#content").innerHTML=`<div class="live-workbench"><div class="live-status-row"><span class="live-phase ${failed?"error":live.state==="Committed"?"ok":""}">${escapeHtml(live.state||"Idle")}</span><span>candidate <code>${live.result??0}</code></span><span>migration <code>${live.migrationStatus??0}</code></span><span>active calls <code>${live.activeCalls??0}</code></span><span>JIT generations <code>${live.jitGenerations??"—"}</code></span><span>leases <code>${live.jitGenerationLeases??0}</code></span><span>reclaimed <code>${live.jitLastReclaimed??0}</code></span><span>roots <code>${live.registeredRoots??0}</code></span><span>objects <code>${live.managedObjects??0}</code></span><span>schemas <code>${live.schemaVersions??0}</code></span></div><div class="live-status-row"><span>closure <code>${escapeHtml(live.dependencyClosure||"—")}</code></span><span>transition edges <code>${live.transitionEdges??0}</code></span><span>persistent callbacks <code>${live.persistentCodeEscapes??0}</code></span><span>blocker <code>${escapeHtml(blockerText)}</code></span></div><label class="live-editor-label"><span>Candidate source</span><textarea id="live-source" spellcheck="false" ${busy||state.liveSubmitting?"disabled":""}>${escapeHtml(state.liveDraft)}</textarea></label><div class="live-actions"><button id="live-submit" class="invoke-button" ${busy||state.liveSubmitting||!state.liveDirty?"disabled":""}>${state.liveSubmitting?"Publishing…":"Check, migrate, publish"}</button><span>Accepted code remains active unless the complete candidate commits.</span></div>${live.diagnostic?`<section class="live-diagnostic ${failed?"error":""}"><b>Diagnostic</b><pre>${escapeHtml(live.diagnostic)}</pre></section>`:""}${live.pending&&live.pending!==state.liveDraft?`<details><summary>Rejected or pending candidate</summary><pre>${escapeHtml(live.pending)}</pre></details>`:""}<details><summary>Accepted source</summary><pre>${escapeHtml(live.accepted||"")}</pre></details></div>`;
  const editor=$("#live-source");if(editor)editor.oninput=()=>{state.liveDraft=editor.value;state.liveDirty=editor.value!==(state.live?.accepted||"");const submit=$("#live-submit");if(submit)submit.disabled=!state.liveDirty};
  const submit=$("#live-submit");if(submit)submit.onclick=submitLiveEdit;
}
async function submitLiveEdit(){
  if(state.liveSubmitting)return;state.liveSubmitting=true;state.liveObservedBusy=false;state.liveSubmissionEpoch=state.live?.jitEpoch??0;state.liveSubmittedDraft=state.liveDraft;renderLive();
  try{const response=await fetch("/api/live/edit",{method:"POST",headers:{"Content-Type":"text/plain; charset=utf-8"},body:state.liveSubmittedDraft}),data=await response.json();state.live=data;if(response.status===202){if(["Checking","Staged","WaitingForQuiescence","Migrating"].includes(data.state))state.liveObservedBusy=true;showToast("Candidate accepted for checking")}else{state.liveSubmitting=false;showToast(data.diagnostic||data.state||"Edit request rejected")}}
  catch(error){state.liveSubmitting=false;showToast(String(error))}finally{render()}
}
function renderContent(){
  if(state.view==="functions"){renderFunctions();return}
  const type=state.snapshot.types.find(t=>t.runtimeId===state.selectedType);
  const items=filteredAllocations(),max=Math.max(1,...items.map(a=>a.bytes));
  const container=state.selectedContainer?state.selectedContainer.split(":"):null,containerType=container&&state.snapshot.types.find(t=>t.runtimeId===Number(container[1]));
  if(type&&!container&&!isByteType(type)){renderTypeValues(type,items);return}
  state.valueListKey=null;if(valueObserver)valueObserver.disconnect();state.visibleValueIds.clear();
  $("#content-kicker").textContent=container?"Logical containers and backing storage":isByteType(type)?"Live byte storage":type?"Filtered allocation census":"Allocation census";
  $("#title").textContent=container?`(${container[0]} ${shortType(containerType?.name)})`:isByteType(type)?"Byte buffers":type?shortType(type.name):"All live allocations";$("#visible-count").textContent=isByteType(type)?`${items.length} regions · ${formatBytes(items.reduce((n,a)=>n+a.bytes,0))}`:items.length+" visible";$("#sort").style.display="block";
  $("#content").innerHTML=items.length?`<table class="allocation-table"><thead><tr><th>ID</th><th>Type</th><th>Shape</th><th>Address</th><th>Size</th></tr></thead><tbody>${items.map(a=>`
    <tr data-allocation="${a.id}" class="${state.selectedAllocation===a.id?"selected":""}">
      <td class="id">#${a.id}</td><td class="type-primary"><b>${escapeHtml(allocationType(a))}</b><small>${a.container?`${a.initialized??"?"} elements · backing allocation`:a.type?escapeHtml(shortType(a.type))+(a.count>1?" element storage":""):"untyped allocation"}</small></td>
      <td class="shape">${a.container?`length ${a.initialized??"?"}<br>`:""}capacity ${a.count}<br>${formatBytes(a.count?a.bytes/a.count:0)} each · align ${a.align}</td><td class="address">${formatAddress(a.address)}</td>
      <td class="shape">${formatBytes(a.bytes)}<div class="bar"><i style="width:${Math.max(2,a.bytes/max*100)}%;background:${typeColor(a.typeId)}"></i></div></td>
    </tr>`).join("")}</tbody></table>`:'<div class="empty"><strong>No live allocations</strong>Change the filter or exercise the running program.</div>';
  document.querySelectorAll("tr[data-allocation]").forEach(row=>row.onclick=()=>selectAllocation(Number(row.dataset.allocation)));
}
function functionSignature(fn){return `${fn.name}(${fn.params.map(p=>`${p.name}: ${p.type}`).join(", ")}) → ${fn.returns}`}
function pointerPointee(param){const match=/^ptr__(.+)$/.exec(param.type);return match&&!match[1].startsWith("ptr__")&&match[1]!=="i8"?match[1]:null}
function pointerCandidates(param){const pointee=pointerPointee(param);if(!pointee)return[];return(state.snapshot?.allocations||[]).filter(a=>a.type&&shortType(a.type)===shortType(pointee)&&a.count>=1)}
function needsLiveBinding(param){return !param.binding&&(/dyn__|\bdyn\b|fnptr/.test(param.type)||(/ptr__|\bptr\b/.test(param.type)&&pointerCandidates(param).length===0))}
function functionDraft(fn,index,param){const key=`${fn.id}:${index}`;if(state.callDrafts.has(key))return state.callDrafts.get(key);return param.type==="bool"?"false":param.type==="f64"?"0.0":param.type==="i64"?"0":""}
function functionInput(param,index,fn){
  const id=`fn-${fn.id}-arg-${index}`,value=functionDraft(fn,index,param);
  if(param.binding)return `<div class="call-field"><span>${escapeHtml(param.name)} <code>${escapeHtml(param.type)}</code></span><small>Automatically bound: ${escapeHtml(param.binding)}</small></div>`;
  const candidates=pointerCandidates(param);
  if(candidates.length){const selected=candidates.some(a=>String(a.id)===value)?value:String(candidates[0].id);if(!state.callDrafts.has(`${fn.id}:${index}`))state.callDrafts.set(`${fn.id}:${index}`,selected);return `<label class="call-field"><span>${escapeHtml(param.name)} <code>${escapeHtml(param.type)}</code></span><select id="${id}">${candidates.map(a=>`<option value="${a.id}" ${String(a.id)===selected?"selected":""}>#${a.id} · ${escapeHtml(shortType(a.type))} · ${formatAddress(a.address)}</option>`).join("")}</select></label>`}
  if(param.type==="bool")return `<label class="call-field"><span>${escapeHtml(param.name)} <code>${param.type}</code></span><select id="${id}"><option value="false" ${value==="false"?"selected":""}>false</option><option value="true" ${value==="true"?"selected":""}>true</option></select></label>`;
  if(param.type==="i64"||param.type==="f64")return `<label class="call-field"><span>${escapeHtml(param.name)} <code>${param.type}</code></span><input id="${id}" type="number" ${param.type==="i64"?'step="1"':'step="any"'} value="${escapeHtml(value)}"></label>`;
  if(needsLiveBinding(param))return `<div class="call-field raw-call-field"><span>${escapeHtml(param.name)} <code>${escapeHtml(param.type)}</code></span><small>Requires a live application binding; arbitrary/null pointers are never synthesized.</small></div>`;
  return `<label class="call-field raw-call-field"><span>${escapeHtml(param.name)} <code>${escapeHtml(param.type)}</code> · ${param.size} bytes</span><input id="${id}" type="text" value="${escapeHtml(value)}" spellcheck="false" autocomplete="off" placeholder="${param.size*2} hex digits"></label>`
}
function renderFunctions(){
  const q=state.query.toLowerCase().trim(),items=state.functions.filter(fn=>!q||`${fn.module} ${functionSignature(fn)}`.toLowerCase().includes(q));
  $("#content-kicker").textContent="Live program surface";$("#title").textContent="Callable functions";$("#visible-count").textContent=`${items.length} available`;$("#sort").style.display="none";
  $("#content").innerHTML=items.length?`<div class="function-list">${items.map(fn=>{const result=state.callResults.get(fn.id),bound=fn.params.every(p=>!needsLiveBinding(p));return `<article class="function-card"><div class="function-head"><div><span class="function-module">${escapeHtml(fn.module)}</span><h3>${escapeHtml(functionSignature(fn))}</h3></div><button class="invoke-button" data-call-function="${fn.id}" ${state.calling.has(fn.id)||!bound?"disabled":""}>${state.calling.has(fn.id)?"Running…":bound?"Run":"Needs binding"}</button></div>${fn.params.length?`<div class="call-fields">${fn.params.map((p,i)=>functionInput(p,i,fn)).join("")}</div>`:'<div class="zero-args">No arguments</div>'}${result?`<div class="call-result ${result.ok?"ok":"error"}"><span>${result.ok?"Returned":"Error"}</span><code>${escapeHtml(result.ok?JSON.stringify(result.value):result.error)}</code></div>`:""}</article>`}).join("")}</div>`:'<div class="empty"><strong>No matching callable functions</strong>No concrete entry-module functions matched this filter.</div>';
  document.querySelectorAll("[data-call-function]").forEach(button=>button.onclick=()=>invokeFunction(Number(button.dataset.callFunction)));
  items.forEach(fn=>fn.params.forEach((param,index)=>{const input=$(`#fn-${fn.id}-arg-${index}`);if(input)input.oninput=()=>state.callDrafts.set(`${fn.id}:${index}`,input.value)}));
}
async function invokeFunction(id){
  const fn=state.functions.find(f=>f.id===id);if(!fn||state.calling.has(id))return;
  if(fn.params.some(needsLiveBinding))return;
  const supplied=fn.params.map((p,i)=>({p,value:p.binding?null:$(`#fn-${id}-arg-${i}`).value})).filter(x=>!x.p.binding),args=supplied.map(x=>x.value);
  for(const {p,value} of supplied){if(!pointerCandidates(p).length&&p.type!=="i64"&&p.type!=="f64"&&p.type!=="bool"&&!new RegExp(`^[0-9a-fA-F]{${p.size*2}}$`).test(value)){showToast(`${p.name} requires exactly ${p.size*2} hex digits`);return}}
  state.calling.add(id);renderFunctions();
  try{const result=await fetch(`/api/call/${id}`,{method:"POST",headers:{"Content-Type":"text/plain; charset=utf-8"},body:args.join("\n")}).then(r=>r.json());state.callResults.set(id,result);showToast(result.ok?`${fn.name} returned`:result.error||"Call failed")}
  catch(error){state.callResults.set(id,{ok:false,error:String(error)})}finally{state.calling.delete(id);await load();renderFunctions()}
}
function valueSummary(value){
  if(value==null)return "null";if(typeof value!=="object")return String(value);
  if(Object.hasOwn(value,"text"))return value.text;
  const entries=Object.entries(value).slice(0,3);return entries.map(([k,v])=>`${k}: ${v&&typeof v==="object"&&Object.hasOwn(v,"text")?v.text:typeof v==="object"?"…":String(v)}`).join(" · ");
}
function renderTypeValues(type,allocations){
  const key=`${type.runtimeId}|${allocations.map(a=>a.id).join(",")}`;
  $("#content-kicker").textContent="Live typed allocations";$("#title").textContent=shortType(type.name);$("#visible-count").textContent=`${allocations.length} live`;$("#sort").style.display="block";
  if(state.valueListKey===key&&document.querySelector("[data-value-preview]")){document.querySelectorAll("tr[data-slot]").forEach(row=>row.classList.toggle("selected",Number(row.dataset.allocation)===state.selectedAllocation));updateVisibleValuePreviews();return}
  state.valueListKey=key;
  $("#content").innerHTML=allocations.length?`<table class="allocation-table value-table"><thead><tr><th>ID</th><th>Type</th><th>Live value</th><th>Storage</th></tr></thead><tbody>${allocations.map(allocation=>{const value=allocationValue(allocation);return `<tr data-allocation="${allocation.id}" data-slot="0" class="${state.selectedAllocation===allocation.id?"selected":""}"><td class="id">#${allocation.id}</td><td class="type-primary"><b>${escapeHtml(shortType(type.name))}</b><small>live object</small></td><td class="value-preview" data-value-preview="${allocation.id}">${value===undefined?"Loading live value…":escapeHtml(valueSummary(Array.isArray(value)?value[0]:value))}</td><td class="shape">${formatAddress(allocation.address)}<br>${formatBytes(allocation.bytes)}</td></tr>`}).join("")}</tbody></table>`:'<div class="empty"><strong>No live values</strong>No allocations of this type are currently live.</div>';
  document.querySelectorAll("tr[data-slot]").forEach(row=>row.onclick=()=>selectAllocation(Number(row.dataset.allocation),0));
  if(valueObserver)valueObserver.disconnect();state.visibleValueIds.clear();
  valueObserver=new IntersectionObserver(entries=>{const entered=[];entries.forEach(entry=>{const id=Number(entry.target.dataset.allocation);if(entry.isIntersecting){state.visibleValueIds.add(id);entered.push(id)}else state.visibleValueIds.delete(id)});if(entered.length)Promise.all(entered.map(id=>loadAllocationDetail(id,false))).then(updateVisibleValuePreviews)},{root:null,rootMargin:"120px 0px"});
  document.querySelectorAll("tr[data-slot]").forEach(row=>valueObserver.observe(row));
}
function selectAllocation(id,slot=null){state.selectedAllocation=id;state.selectedSlot=slot;state.memory=null;state.memoryOffset=slot==null?0:(state.snapshot.types.find(t=>t.runtimeId===state.snapshot.allocations.find(a=>a.id===id)?.typeId)?.size||0)*slot;renderHeapMap();renderContent();renderDetail();loadAllocationDetail(id);loadMemory()}
async function loadMemory(){
  const id=state.selectedAllocation,offset=state.memoryOffset,allocation=state.snapshot?.allocations.find(a=>a.id===id),type=allocation&&state.snapshot?.types.find(t=>t.runtimeId===allocation.typeId);if(!id||!isByteStorage(allocation,type)||state.memoryLoading)return;state.memoryLoading=true;
  try{const memory=await fetch(`/api/memory/${id}/${offset}`,{cache:"no-store"}).then(r=>r.json());if(state.selectedAllocation===id&&state.memoryOffset===offset){state.memory=memory;renderDetail()}}
  finally{state.memoryLoading=false}
}
function byteCharacter(b){return b>=32&&b<=126?String.fromCharCode(b):"·"}
function memoryPlaceholder(allocation){
  const offset=Math.min(state.memoryOffset,Math.max(0,allocation.bytes-1)),length=Math.min(256,Math.max(0,allocation.bytes-offset)),rows=Math.max(1,Math.ceil(length/16));
  return `<div class="memory-toolbar memory-toolbar-placeholder"><button disabled>←</button><label>offset <input type="number" value="${offset}" disabled></label><button disabled>→</button><span>${offset}–${Math.max(offset,offset+length-1)} / ${allocation.bytes}</span></div><div class="hex-dump memory-placeholder" aria-label="Reading live memory">${Array.from({length:rows},(_,i)=>`<div class="hex-row"><span class="hex-address">${(offset+i*16).toString(16).padStart(8,"0")}</span><span class="hex-skeleton"></span><span class="ascii-skeleton"></span></div>`).join("")}</div><div class="memory-legend placeholder-legend"><i></i> byte covered by a discovered slice</div>`;
}
function memoryExplorer(allocation){
  const memory=state.memory;
  if(!memory||memory.id!==allocation.id)return memoryPlaceholder(allocation);
  const refs=allocationSliceRefs(allocation),rows=[];
  for(let i=0;i<memory.bytes.length;i+=16){const bytes=memory.bytes.slice(i,i+16),address=memory.offset+i;rows.push(`<div class="hex-row"><span class="hex-address">${address.toString(16).padStart(8,"0")}</span><span class="hex-bytes">${bytes.map((b,j)=>{const at=address+j,covered=refs.some(r=>at>=r.offset&&at<r.offset+r.length);return `<i class="${covered?"slice-byte":""}" title="offset ${at} · ${b}">${b.toString(16).padStart(2,"0")}</i>`}).join("")}</span><span class="ascii">${escapeHtml(bytes.map(byteCharacter).join(""))}</span></div>`)}
  const max=Math.max(0,memory.total-1),next=Math.min(max,memory.offset+256),previous=Math.max(0,memory.offset-256);
  return `<div class="memory-toolbar"><button data-memory-offset="${previous}" ${memory.offset===0?"disabled":""}>←</button><label>offset <input id="memory-offset" type="number" min="0" max="${max}" value="${memory.offset}"></label><button data-memory-offset="${next}" ${memory.offset+memory.length>=memory.total?"disabled":""}>→</button><span>${memory.offset}–${Math.max(memory.offset,memory.offset+memory.length-1)} / ${memory.total}</span></div><div class="hex-dump">${rows.join("")||'<div class="memory-loading">Empty allocation</div>'}</div><div class="memory-legend"><i></i> byte covered by a discovered slice</div>`;
}
function sliceReferences(allocation){
  const refs=allocationSliceRefs(allocation).slice().sort((a,b)=>a.offset-b.offset);
  if(!refs.length)return '<p class="slice-empty">No slice references were discovered in reflected heap fields.</p>';
  return `<div class="slice-list">${refs.map(r=>`<button class="slice-ref" data-memory-offset="${r.offset}"><span><b>${escapeHtml(shortType(r.sourceType))}.${escapeHtml(r.field)}</b><small>allocation #${r.sourceAllocationId}${r.slot?` · slot ${r.slot}`:""}</small></span><code>+${r.offset} · ${r.length} bytes</code></button>`).join("")}</div>`;
}
function renderDetail(){
  const allocation=state.snapshot.allocations.find(a=>a.id===state.selectedAllocation),detail=$("#detail");
  $(".shell").classList.toggle("detail-open",!!allocation);detail.setAttribute("aria-hidden",String(!allocation));if(!allocation){detail.innerHTML="";return}
  const type=state.snapshot.types.find(t=>t.runtimeId===allocation.typeId),changed=false,value=allocationValue(allocation);
  const selectedValue=state.selectedSlot==null?null:(Array.isArray(value)?value[state.selectedSlot]:value);
  const byteStorage=isByteStorage(allocation,type);
  detail.innerHTML=`<div class="detail-head ${changed?"flash":""}"><button class="detail-close" title="Close">×</button><span class="kicker">${state.selectedSlot==null?escapeHtml(allocationKind(allocation)):`Live ${escapeHtml(elementType(allocation))} value · element ${state.selectedSlot}`}</span><h2>#${allocation.id}${state.selectedSlot==null?"":`[${state.selectedSlot}]`} · ${escapeHtml(state.selectedSlot==null?allocationType(allocation):elementType(allocation))}</h2><p>${formatAddress(allocation.address+(state.selectedSlot??0)*(type?.size||0))}</p></div>
    <div class="detail-section value-first"><h3>${state.selectedSlot==null?(allocation.count>1?`Live values${allocation.initialized==null?" · initialization unknown":` · ${allocation.initialized} initialized`}`:"Live value"):`${elementType(allocation)} value · element ${state.selectedSlot}`}</h3>${value===undefined?'<div class="memory-loading">Loading live value…</div>':valueTree(state.selectedSlot==null?value:selectedValue)}</div>
    ${allocation.container?`<div class="detail-section"><h3>Logical ${allocation.container}</h3><div class="facts"><div class="fact"><span>Length</span><b>${allocation.initialized??"unknown"}</b></div><div class="fact"><span>Capacity</span><b>${allocation.count}</b></div><div class="fact"><span>Element type</span><b>${escapeHtml(elementType(allocation))}</b></div><div class="fact"><span>Backing region</span><b>#${allocation.id}</b></div></div></div>`:""}
    <div class="detail-section"><h3>Physical allocation region</h3><div class="facts"><div class="fact"><span>Total size</span><b>${formatBytes(allocation.bytes)}</b></div><div class="fact"><span>Alignment</span><b>${allocation.align} bytes</b></div><div class="fact"><span>Element capacity</span><b>${allocation.count}</b></div><div class="fact"><span>Element size</span><b>${formatBytes(allocation.count?allocation.bytes/allocation.count:0)}</b></div></div></div>
    ${type?`<div class="detail-section"><h3>Type layout</h3><div class="facts"><div class="fact"><span>Runtime type ID</span><b>${type.runtimeId}</b></div><div class="fact"><span>Fields</span><b>${type.fields.length}</b></div></div></div>`:""}
    ${byteStorage?`<div class="detail-section"><h3>Live bytes · hex and ASCII</h3>${memoryExplorer(allocation)}</div>
    <div class="detail-section"><h3>Discovered slices into this region · ${allocationSliceRefs(allocation).length}</h3>${sliceReferences(allocation)}<p class="coverage-note">Derived from direct slice fields in reflected live heap objects. Stack/register slices, foreign layouts, and unreflected nested containers are not enumerable from allocator interception.</p></div>`:""}`;
  detail.querySelector(".detail-close").onclick=()=>{state.selectedAllocation=null;state.selectedSlot=null;state.memory=null;renderDetail();renderContent();renderHeapMap()};
  detail.querySelectorAll("[data-memory-offset]").forEach(button=>button.onclick=()=>{state.memoryOffset=Math.max(0,Number(button.dataset.memoryOffset));state.memory=null;renderDetail();loadMemory()});
  const offsetInput=detail.querySelector("#memory-offset");if(offsetInput)offsetInput.onchange=()=>{state.memoryOffset=Math.max(0,Math.min(Math.max(0,allocation.bytes-1),Number(offsetInput.value)||0));state.memory=null;renderDetail();loadMemory()};
}
function valueTree(value){
  if(value&&Object.hasOwn(value,"sliceAddress")&&Object.hasOwn(value,"text"))return `<div class="slice-value"><span>${scalar(value.text)}</span><small>${formatAddress(value.sliceAddress)} · ${value.length} bytes</small></div>`;
  if(value&&Array.isArray(value.bytes))return `<div class="raw-grid">${value.bytes.map(b=>`<span class="byte" title="${b}">${b.toString(16).padStart(2,"0")}</span>`).join("")}</div><div class="layout-meta">showing ${value.shown} of ${value.total} bytes</div>`;
  if(Array.isArray(value))return `<div class="tree">${value.map((v,i)=>`<div class="tree-row"><span class="tree-key">[${i}]</span><span>${typeof v==="object"&&v!==null?valueTree(v):scalar(v)}</span></div>`).join("")}</div>`;
  if(value&&typeof value==="object")return `<div class="tree">${Object.entries(value).map(([k,v])=>`<div class="tree-row"><span class="tree-key">${escapeHtml(k)}</span><span>${typeof v==="object"&&v!==null?valueTree(v):scalar(v)}</span></div>`).join("")}</div>`;
  return `<div class="tree">${scalar(value)}</div>`;
}
function scalar(v){const cls=v===null?"null":typeof v==="string"?"string":typeof v==="boolean"?"bool":"number";return `<span class="v-${cls}">${v===null?"null":typeof v==="string"?escapeHtml(JSON.stringify(v)):escapeHtml(v)}</span>`}
function updateNav(){document.querySelectorAll(".nav-item").forEach(n=>n.classList.toggle("selected",n.dataset.view===state.view))}
document.querySelectorAll(".nav-item").forEach(n=>n.onclick=()=>{state.view=n.dataset.view;if(state.view==="allocations"){state.selectedType=null;state.selectedContainer=null}state.selectedAllocation=null;updateNav();render({renderFunctionContent:state.view==="functions"})});
$("#search").oninput=e=>{state.query=e.target.value;render({renderFunctionContent:state.view==="functions"})};$("#sort").onchange=e=>{state.sort=e.target.value;renderContent();renderHeapMap()};$("#refresh").onclick=()=>load();
$("#zero-types").onchange=e=>{state.showZeroTypes=e.target.value==="show";if(!state.showZeroTypes&&state.selectedType!=null){const t=state.snapshot?.types.find(t=>t.runtimeId===state.selectedType);if(t&&(t.regions??t.live)===0)state.selectedType=null}render()};
$("#pause").onclick=()=>{state.paused=!state.paused;$("#pause").classList.toggle("active",state.paused);$("#pause").textContent=state.paused?"▶":"Ⅱ";showToast(state.paused?"Live refresh paused":"Live refresh resumed");if(!state.paused)load()};
function showToast(message){const t=$("#toast");t.textContent=message;t.classList.add("show");clearTimeout(showToast.timer);showToast.timer=setTimeout(()=>t.classList.remove("show"),1400)}
document.addEventListener("visibilitychange",()=>{if(!document.hidden&&!state.paused)load()});window.addEventListener("focus",()=>{if(!state.paused)load()});
load();setInterval(()=>{if(!state.paused&&!document.hidden)load()},750);
