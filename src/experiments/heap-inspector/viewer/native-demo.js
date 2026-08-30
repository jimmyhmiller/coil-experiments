const $ = id => document.getElementById(id);
const STEPS = [
  {
    title:'Replace a native function',
    explanation:'Only this definition is submitted. The world, window, and animation loop stay where they are.',
    watch:'Drag 14 left and right. The balls resize after each accepted native generation; their positions never reset.',
    source:`(defn radius [(p Particle)] (-> i64)
  14)`,
  },
  {
    title:'Evolve a struct with live data',
    explanation:'Particle gains two defaulted fields. Existing particles migrate; old constructors receive the same defaults automatically.',
    watch:'The same moving objects gain colour. Scrub hue 20 and watch native CALayers update without reseeding.',
    source:`(defstruct Particle
  [(x i64) (y i64) (vx i64) (vy i64)
   (hue i64 20)
   (visible bool true)])

(defn tint [(p Particle)] (-> i64)
  (if (.visible p)
      (+ (.hue p) (/ (.x p) 3))
      0))`,
  },
  {
    title:'Make a non-preserving edit',
    explanation:'Changing bool to a nominal enum needs an explicit data transition. This incomplete candidate must not touch the running generation.',
    watch:'The candidate is rejected as NeedsTransition and the native animation pauses on its last good frame. Its state is still intact.',
    source:`(defsum Visibility (Hidden) (Visible))

(defstruct Particle
  [(x i64) (y i64) (vx i64) (vy i64)
   (hue i64 20)
   (visible Visibility)])`,
  },
  {
    title:'Repair code and migrate state',
    explanation:'This batch supplies the typed transition and updates the definitions that construct or inspect the changed field.',
    watch:'Apply the repair. The same particles automatically resume from the frozen positions, now carrying Visibility values.',
    source:`(defsum Visibility (Hidden) (Visible))

(defstruct Particle
  [(x i64) (y i64) (vx i64) (vy i64)
   (hue i64 20)
   (visible Visibility (Visible))])

(migrate Particle visible old
  (if old (Visible) (Hidden)))

(defn tint [(p Particle)] (-> i64)
  (match (.visible p)
    (Hidden [] 0)
    (Visible [] (+ (.hue p) (/ (.x p) 3)))))

(defn advance [(p Particle)] (-> Particle)
  (let [(mut nx) (+ (.x p) (.vx p))
        (mut ny) (+ (.y p) (.vy p))
        (mut nvx) (.vx p)
        (mut nvy) (.vy p)]
    (when (< nx 14) (store! nx 14) (store! nvx (- 0 nvx)))
    (when (> nx 626) (store! nx 626) (store! nvx (- 0 nvx)))
    (when (< ny 14) (store! ny 14) (store! nvy (- 0 nvy)))
    (when (> ny 386) (store! ny 386) (store! nvy (- 0 nvy)))
    (Particle :x nx :y ny :vx nvx :vy nvy
              :hue (.hue p) :visible (.visible p))))`,
  },
  {
    title:'Dispatch native drawing by enum',
    explanation:'A new Kind enum chooses dots or rings. The browser submits definitions; the macOS renderer receives only typed numeric results.',
    watch:'Balls on the right become actual stroked CALayers. Scrub 320 to move the shape boundary.',
    source:`(defsum Kind (Dot) (Ring))

(defn kind-of [(p Particle)] (-> Kind)
  (if (> (.x p) 320) (Ring) (Dot)))

(defn kind-code [(p Particle)] (-> i64)
  (match (kind-of p)
    (Dot [] 0)
    (Ring [] 1)))`,
  },
  {
    title:'Grow the enum under a match',
    explanation:'Kind gains Bar, but kind-code still has only two arms. Coil rejects the non-exhaustive native candidate before publication.',
    watch:'The JIT epoch does not advance. The native window pauses and keeps the last complete frame—never a half-drawn one.',
    source:`(defsum Kind (Dot) (Ring) (Bar))

(defn kind-of [(p Particle)] (-> Kind)
  (if (> (.x p) 430)
      (Bar)
      (if (> (.x p) 320) (Ring) (Dot))))

(defn kind-code [(p Particle)] (-> i64)
  (match (kind-of p)
    (Dot [] 0)
    (Ring [] 1)))`,
  },
  {
    title:'Repair the root cause',
    explanation:'Only the stale match is resubmitted. Its callers become valid through the complete checked candidate.',
    watch:'Apply the repair. The world automatically resumes and bars appear on the far right.',
    source:`(defn kind-code [(p Particle)] (-> i64)
  (match (kind-of p)
    (Dot [] 0)
    (Ring [] 1)
    (Bar [] 2)))`,
  },
];

let step=0, applied=new Set(), editing=false, queued=null, liveTimer=null;
const stepSources=STEPS.map(s=>s.source);
let progressGeneration=null;
const PROGRESS_KEY='coil-native-demo-progress-v1';
const editor=$('editor'), highlight=$('highlight'), diagnostic=$('diagnostic');
function saveProgress(){if(progressGeneration===null)return;try{localStorage.setItem(PROGRESS_KEY,JSON.stringify({generation:progressGeneration,step,applied:[...applied],sources:stepSources}))}catch{}}
function restoreProgress(status){progressGeneration=status.nativeCallbackGeneration??null;try{let saved=JSON.parse(localStorage.getItem(PROGRESS_KEY)||'null');if(saved&&saved.generation===progressGeneration){step=Math.max(0,Math.min(STEPS.length-1,saved.step??0));applied=new Set((saved.applied||[]).filter(i=>i>=0&&i<STEPS.length));if(Array.isArray(saved.sources)&&saved.sources.length===STEPS.length)saved.sources.forEach((source,i)=>stepSources[i]=source)}else localStorage.removeItem(PROGRESS_KEY)}catch{localStorage.removeItem(PROGRESS_KEY)}}
const esc=s=>s.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const keywords=new Set(['defn','defstruct','defsum','letonce','migrate','let','mut','if','when','cond','match','store!','set!','field','load']);
const types=new Set(['i64','f64','bool','ptr','slice','array']);
function tokens(src){const out=[];let i=0;while(i<src.length){let s=i,c=src[i];if(c===';'){while(i<src.length&&src[i]!=='\n')i++;out.push({k:'comment',s,e:i});continue}if(/[0-9]/.test(c)||(c==='-'&&/[0-9]/.test(src[i+1]))){if(c==='-')i++;while(i<src.length&&/[0-9]/.test(src[i]))i++;if(src[i]==='.'&&/[0-9]/.test(src[i+1])){i++;while(i<src.length&&/[0-9]/.test(src[i]))i++}out.push({k:'number',s,e:i});continue}if(/[A-Za-z_!?.-]/.test(c)){while(i<src.length&&/[A-Za-z0-9_!?.-]/.test(src[i]))i++;let w=src.slice(s,i);out.push({k:keywords.has(w)?'keyword':types.has(w)?'type':(out.at(-1)?.word==='defn'?'name':'plain'),s,e:i,word:w});continue}i++;out.push({k:'plain',s,e:i})}return out}
function renderHighlight(){let src=editor.value,html='';for(const t of tokens(src)){let text=esc(src.slice(t.s,t.e));html+=t.k==='plain'?text:`<span class="tok-${t.k}" data-s="${t.s}" data-e="${t.e}">${text}</span>`}highlight.innerHTML=html+'\n';highlight.scrollTop=editor.scrollTop;highlight.scrollLeft=editor.scrollLeft}
function renderStep(){let s=STEPS[step];$('step-number').textContent=`STEP ${step+1} OF ${STEPS.length}`;$('step-title').textContent=s.title;$('explanation').textContent=s.explanation;$('watch').textContent=s.watch;editor.value=stepSources[step];renderHighlight();$('dots').innerHTML=STEPS.map((_,i)=>`<li class="${i===step?'current':applied.has(i)?'done':''}"></li>`).join('');$('back').disabled=step===0;$('next').disabled=step===STEPS.length-1||!applied.has(step)}
async function apiStatus(){return (await fetch('/api/live',{cache:'no-store'})).json()}
function failedStatusText(s){
  const repairs=Array.isArray(s.requiredRepairs)?s.requiredRepairs:[];
  if(!repairs.length)return s.diagnostic||'Candidate rejected; accepted native code and state are unchanged.';
  const lines=repairs.map(({name,diagnostic:reason})=>`  • ${name}: ${reason||'does not type-check'}`);
  return `Functions requiring repair (${repairs.length}):\n${lines.join('\n')}`;
}
function showStatus(s){$('phase').textContent=s.state;$('epoch').textContent=`native epoch ${s.jitEpoch||0}`;$('roots').textContent=s.registeredRoots||0;$('versions').textContent=s.schemaVersions||0;$('transitions').textContent=s.transitionEdges||0;$('runtime').className='runtime '+(s.result===0?'ok':'bad');diagnostic.className='diagnostic '+(s.result===0?'ok':'bad');diagnostic.textContent=s.result===0?`Committed native generation ${s.jitEpoch}. The persistent world was not restarted.`:failedStatusText(s)}
async function terminal(){for(;;){let s=await apiStatus();showStatus(s);if(!['Checking','Staged','Migrating','WaitingForQuiescence'].includes(s.state))return s;await new Promise(r=>setTimeout(r,8))}}
function enclosingItem(src,offset){let depth=0,start=0,inString=false,escaped=false,inComment=false,bounds=[];for(let i=0;i<src.length;i++){let c=src[i];if(inComment){if(c==='\n')inComment=false;continue}if(inString){if(escaped)escaped=false;else if(c==='\\')escaped=true;else if(c==='"')inString=false;continue}if(c===';'){inComment=true;continue}if(c==='"'){inString=true;continue}if(c==='('||c==='['){if(depth===0)bounds.push(i);depth++}else if(c===')'||c===']')depth=Math.max(0,depth-1)}if(!bounds.length)return{start:0,end:src.length};start=bounds[0];for(const b of bounds)if(b<=offset)start=b;let next=bounds.find(b=>b>start);return{start,end:next===undefined?src.length:next}}
function itemAt(src,offset){let {start,end}=enclosingItem(src,offset);return src.slice(start,end).trim()}
function balanced(src){let stack=[],inString=false,escaped=false,inComment=false;for(let i=0;i<src.length;i++){let c=src[i];if(inComment){if(c==='\n')inComment=false;continue}if(inString){if(escaped)escaped=false;else if(c==='\\')escaped=true;else if(c==='"')inString=false;continue}if(c===';'){inComment=true;continue}if(c==='"'){inString=true;continue}if(c==='('||c==='['){stack.push(c);continue}if(c===')'||c===']'){let want=c===')'?'(': '[';if(stack.pop()!==want)return false}}return !inString&&stack.length===0}
async function submit(src,reason='apply'){
  if(!src.trim())return;
  if(editing){queued={src,reason};return}
  editing=true;
  $('apply').disabled=true;
  diagnostic.className='diagnostic';
  diagnostic.textContent=`${reason}: checking and compiling the snippet…`;
  try{
    const prior=await apiStatus();
    const resumeAfterRepair=prior.result!==0||prior.conditionActive;
    const r=await fetch('/api/live/edit',{method:'POST',headers:{'Content-Type':'text/plain'},body:src});
    if(!r.ok&&r.status!==202)throw Error(`HTTP ${r.status}`);
    const s=await terminal();
    applied.add(step);
    saveProgress();
    renderStep();
    if(s.result!==0){
      await fetch('/api/native-demo/pause',{method:'POST'});
    }else if(resumeAfterRepair){
      await fetch('/api/native-demo/run',{method:'POST'});
    }
  }catch(e){
    diagnostic.className='diagnostic bad';
    diagnostic.textContent=e.message;
  }finally{
    editing=false;
    $('apply').disabled=false;
    if(queued){let q=queued;queued=null;submit(q.src,q.reason)}
  }
}
editor.oninput=()=>{stepSources[step]=editor.value;saveProgress();renderHighlight();if($('live-typing').checked){clearTimeout(liveTimer);liveTimer=setTimeout(()=>{let item=itemAt(editor.value,editor.selectionStart);if(balanced(item))submit(item,'live edit')},250)}};editor.onscroll=renderHighlight;$('apply').onclick=()=>submit(editor.value);$('back').onclick=()=>{if(step>0){step--;saveProgress();renderStep()}};$('next').onclick=()=>{if(step<STEPS.length-1&&applied.has(step)){step++;saveProgress();renderStep()}};
$('run').onclick=()=>fetch('/api/native-demo/run',{method:'POST'});$('pause').onclick=()=>fetch('/api/native-demo/pause',{method:'POST'});$('step-frame').onclick=()=>fetch('/api/native-demo/step',{method:'POST'});$('focus-window').onclick=()=>fetch('/api/native-demo/focus',{method:'POST'});
let scrub=null;highlight.onpointerdown=e=>{let n=e.target.closest('.tok-number');if(!n||e.button!==0)return;e.preventDefault();let s=+n.dataset.s,end=+n.dataset.e,src=editor.value,box=n.getBoundingClientRect();scrub={id:e.pointerId,x:e.clientX,s,len:end-s,value:+src.slice(s,end),float:src.slice(s,end).includes('.'),moved:false,offset:s+Math.round(((e.clientX-box.left)/box.width)*(end-s))};highlight.setPointerCapture(e.pointerId)};highlight.onpointermove=e=>{if(!scrub||e.pointerId!==scrub.id)return;let dx=e.clientX-scrub.x;if(!scrub.moved&&Math.abs(dx)<3)return;e.preventDefault();scrub.moved=true;$('editor-stack').classList.add('scrubbing');let next=scrub.float?Math.round((scrub.value+dx*(e.shiftKey?1/12:1/3))*10)/10:Math.round(scrub.value+dx*(e.shiftKey?1/12:1/3)),text=String(next),src=editor.value;editor.value=src.slice(0,scrub.s)+text+src.slice(scrub.s+scrub.len);stepSources[step]=editor.value;scrub.len=text.length;renderHighlight();let item=itemAt(editor.value,scrub.s);if(balanced(item))submit(item,'scrub')};function endScrub(){if(!scrub)return;let {moved,id,offset}=scrub;if(highlight.hasPointerCapture?.(id))highlight.releasePointerCapture(id);scrub=null;$('editor-stack').classList.remove('scrubbing');if(!moved){editor.focus();editor.setSelectionRange(offset,offset)}}highlight.onpointerup=endScrub;highlight.onpointercancel=endScrub;
async function initialize(){try{const status=await apiStatus();restoreProgress(status);renderStep();showStatus(status);saveProgress()}catch{renderStep()}}
initialize();setInterval(async()=>{try{showStatus(await apiStatus())}catch{}},700);
