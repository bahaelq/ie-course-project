/* Job Extractor – ruhige Produktlogik */
const $ = s => document.querySelector(s);
const $$ = s => Array.from(document.querySelectorAll(s));

const inputEl = $("#inputText"), charCount = $("#charCount"), wordCount = $("#wordCount");
const uploadZone = $("#uploadZone"), fileInput=$("#fileInput"), uploadProgress=$("#uploadProgress");
const fileInfo=$("#fileInfo"), fileNameEl=$("#fileName"), fileSizeEl=$("#fileSize"), fileCharsEl=$("#fileChars"), removeFileBtn=$("#removeFileBtn"), uploadError=$("#uploadError");
const clearBtn=$("#clearBtn"), analyzeBtn=$("#analyzeBtn"), inputError=$("#inputError"), statusLine=$("#statusLine");
const apiStatus=$("#apiStatus"), helpBtn=$("#helpBtn"), helpDrawer=$("#helpDrawer"), helpBackdrop=$("#helpBackdrop"), closeHelp=$("#closeHelp");
const examplesBox=$("#examplesBox"), examplesList=$("#examplesList");
const emptyState=$("#emptyState"), resultError=$("#resultError"), dashboard=$("#dashboard"), summaryLine=$("#summaryLine"), summaryMeta=$("#summaryMeta");
const entitiesList=$("#entitiesList"), emptyTypes=$("#emptyTypes"), emptyList=$("#emptyList"), emptyCount=$("#emptyCount"), spanNotice=$("#spanNotice");
const markedText=$("#markedText"), legend=$("#legend"), copyTextBtn=$("#copyTextBtn");
const jsonLink=$("#jsonLink"), drawer=$("#drawer"), backdrop=$("#backdrop"), closeDrawer=$("#closeDrawer"), jsonOutput=$("#jsonOutput"), jsonMeta=$("#jsonMeta"), copyJsonBtn=$("#copyJsonBtn"), downloadJsonBtn=$("#downloadJsonBtn"), copyFeedback=$("#copyFeedback");
const footerModel=$("#footerModel");

let examples=[], lastResult=null, lastText="", filters=new Set();

const ORDER=["JOB_TITLE","HARD_SKILL","SOFT_SKILL","EXPERIENCE","EDUCATION","LANGUAGE","WORK_MODE"];
const META={
  JOB_TITLE:{de:"Stellenbezeichnung",en:"JOB_TITLE"},
  HARD_SKILL:{de:"Fachliche Fähigkeiten",en:"HARD_SKILL"},
  SOFT_SKILL:{de:"Persönliche Kompetenzen",en:"SOFT_SKILL"},
  EXPERIENCE:{de:"Berufserfahrung",en:"EXPERIENCE"},
  EDUCATION:{de:"Ausbildung & Qualifikation",en:"EDUCATION"},
  LANGUAGE:{de:"Sprachen",en:"LANGUAGE"},
  WORK_MODE:{de:"Arbeitsmodell",en:"WORK_MODE"},
};

const esc=s=>String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");

function counts(){
  const t=inputEl.value; charCount.textContent=t.length; wordCount.textContent=t.trim()?t.trim().split(/\s+/).length:0;
}
function showErr(el,msg){ if(!msg){el.classList.add("hidden");el.textContent="";return} el.textContent=msg; el.classList.remove("hidden"); }
function setStatus(api){
  const dot=apiStatus.querySelector(".dot"), label=apiStatus.querySelector(".label");
  if(!api){ apiStatus.className="status"; label.textContent="Prüft…"; return}
  if(api.configured){ apiStatus.className="status ok"; label.textContent=api.model||"Bereit"; footerModel.textContent=api.model?`Modell: ${api.model}`:""}
  else{ apiStatus.className="status warn"; label.textContent="Konfiguration fehlt"; }
}
function setLoading(v){
  analyzeBtn.disabled=v;
  const lab=analyzeBtn.querySelector(".label"), sp=analyzeBtn.querySelector(".spinner"), ic=analyzeBtn.querySelector(".icon");
  if(v){ lab.textContent="Analysiert…"; sp.classList.remove("hidden"); ic&&ic.classList.add("hidden"); statusLine.classList.remove("hidden"); inputEl.setAttribute("disabled","disabled"); }
  else{ lab.textContent="Analysieren"; sp.classList.add("hidden"); ic&&ic.classList.remove("hidden"); statusLine.classList.add("hidden"); inputEl.removeAttribute("disabled"); }
}

/* Examples – kompakt */
function renderExamples(){
  examplesList.innerHTML="";
  examples.forEach(ex=>{
    const b=document.createElement("button"); b.type="button"; b.className="example-row"; b.setAttribute("role","listitem");
    b.innerHTML=`<span><strong>${esc(ex.label)}</strong> <span style="color:#9CA3AF">· ${esc(ex.short)}</span></span><span style="font-size:12px;color:#6B7280">Laden</span>`;
    b.addEventListener("click",()=>{
      inputEl.value=ex.text; counts(); showErr(inputError,""); showErr(resultError,""); showErr(uploadError,""); fileInfo.classList.add("hidden");
      examplesBox.open=false; inputEl.focus();
      if(innerWidth<640) document.querySelector(".input").scrollIntoView({behavior:"smooth"});
    });
    examplesList.appendChild(b);
  });
}

/* Upload */
let lastFile=null;
function showUploadErr(m){ if(!m){uploadError.classList.add("hidden");uploadError.textContent="";return} uploadError.textContent=m; uploadError.classList.remove("hidden"); }
function showFile(m){ fileNameEl.textContent=m.filename; fileSizeEl.textContent=m.size_human; fileCharsEl.textContent=`${m.chars.toLocaleString("de-DE")} Zeichen`; fileInfo.classList.remove("hidden"); lastFile=m; }
function clearFile(){ fileInfo.classList.add("hidden"); lastFile=null; if(fileInput) fileInput.value=""; }
function setUpLoading(v){ if(v) uploadProgress.classList.remove("hidden"); else uploadProgress.classList.add("hidden"); }
async function handleFile(file){
  showUploadErr(""); fileInfo.classList.add("hidden");
  const ext="."+((file.name.split(".").pop()||"").toLowerCase());
  if(![".txt",".pdf",".docx"].includes(ext) && file.type && !["text/plain","application/pdf","application/vnd.openxmlformats-officedocument.wordprocessingml.document"].includes(file.type) && !file.type.startsWith("text/")){
    showUploadErr("Ungültiger Dateityp. Erlaubt sind PDF, TXT und DOCX."); return;
  }
  if(file.size>8*1024*1024){ showUploadErr("Datei zu groß. Maximale Größe: 8 MB."); return; }
  if(file.size===0){ showUploadErr("Datei ist leer."); return; }
  setUpLoading(true);
  try{
    const fd=new FormData(); fd.append("file",file,file.name);
    const res=await fetch("/api/upload",{method:"POST",body:fd});
    const data=await res.json().catch(()=>({}));
    if(!res.ok){ showUploadErr(data.error||"Datei konnte nicht gelesen werden."); return; }
    const text=data.text||"";
    if(!text.trim()){ showUploadErr("Aus dieser Datei konnte kein Text extrahiert werden. Bitte verwende eine textbasierte Datei oder füge den Text manuell ein."); return; }
    inputEl.value=text; counts(); showFile(data.meta||{filename:file.name,size:file.size,size_human:(file.size/1024).toFixed(1)+" KB",chars:text.length});
    examplesBox.open=false; inputEl.focus();
  }catch(e){ showUploadErr("Datei konnte nicht gelesen werden. Die Datei ist möglicherweise beschädigt."); }
  finally{ setUpLoading(false); }
}
if(uploadZone && fileInput){
  uploadZone.addEventListener("click",()=>fileInput.click());
  uploadZone.addEventListener("keydown",e=>{ if(e.key==="Enter"||e.key===" "){ e.preventDefault(); fileInput.click(); }});
  fileInput.addEventListener("change",()=>{ const f=fileInput.files&&fileInput.files[0]; if(f) handleFile(f); });
  ["dragenter","dragover"].forEach(ev=>uploadZone.addEventListener(ev,e=>{ e.preventDefault(); uploadZone.classList.add("drag-over"); }));
  ["dragleave","dragend"].forEach(ev=>uploadZone.addEventListener(ev,e=>{ e.preventDefault(); if(!uploadZone.contains(e.relatedTarget)) uploadZone.classList.remove("drag-over"); }));
  uploadZone.addEventListener("drop",e=>{ e.preventDefault(); uploadZone.classList.remove("drag-over"); const f=e.dataTransfer&&e.dataTransfer.files&&e.dataTransfer.files[0]; if(f) handleFile(f); });
  document.addEventListener("dragover",e=>e.preventDefault()); document.addEventListener("drop",e=>e.preventDefault());
}
removeFileBtn&&removeFileBtn.addEventListener("click",()=>{ clearFile(); showUploadErr(""); inputEl.focus(); });
clearBtn.addEventListener("click",()=>{ inputEl.value=""; counts(); showErr(inputError,""); showErr(resultError,""); showUploadErr(""); clearFile(); lastResult=null; lastText=""; filters.clear(); dashboard.classList.add("hidden"); emptyState.classList.remove("hidden"); });
inputEl.addEventListener("input",()=>{ counts(); showErr(inputError,""); if(lastFile) fileCharsEl.textContent=`${inputEl.value.length.toLocaleString("de-DE")} Zeichen (bearbeitet)`; });

/* Entities – kompakt */
function renderEntities(result){
  entitiesList.innerHTML=""; emptyList.innerHTML="";
  const ents=result.entities||{};
  const withVals=[], emptyVals=[];
  ORDER.forEach(t=>{ const v=ents[t]||[]; (v.length?withVals:emptyVals).push(t); });
  withVals.forEach(t=>{
    const row=document.createElement("div"); row.className="entity-row";
    const cfg=META[t]; const vals=ents[t];
    row.innerHTML=`<div class="entity-label"><strong>${cfg.de}</strong><span>${cfg.en}</span></div><div class="entity-vals"></div>`;
    const valsEl=row.querySelector(".entity-vals");
    vals.forEach(v=>{ const c=document.createElement("span"); c.className="chip"; c.textContent=v; c.title=v; valsEl.appendChild(c); });
    entitiesList.appendChild(row);
  });
  if(emptyVals.length){
    emptyTypes.classList.remove("hidden"); emptyCount.textContent=`${emptyVals.length} Typen ohne Treffer`;
    emptyVals.forEach(t=>{ const r=document.createElement("div"); r.className="empty-row"; r.innerHTML=`<strong>${META[t].de}</strong> <span style="color:#9CA3AF">· ${t}</span> <span style="margin-left:6px;color:#9CA3AF">Keine Entität erkannt</span>`; emptyList.appendChild(r); });
  } else emptyTypes.classList.add("hidden");
  const h=result.meta?.spans_hallucinated||0, a=result.meta?.spans_ambiguous||0;
  if(h||a){ spanNotice.textContent=`Hinweis: ${h?h+" halluziniert":""}${h&&a?" und ":""}${a?a+" mehrdeutig":""} – im JSON sichtbar, aber nicht hervorgehoben.`; spanNotice.classList.remove("hidden"); } else spanNotice.classList.add("hidden");
}
function renderSummary(result, txt){
  const ok=result.meta?.spans_ok||0; const types=(Object.values(result.entities||{}).filter(v=>v.length).length);
  summaryLine.textContent=`${ok} verifizierte Spans · ${types} von 7 Typen besetzt · ${txt.length.toLocaleString("de-DE")} Zeichen`;
  summaryMeta.innerHTML=`<span class="pill">${types} Kategorien</span><span class="pill">${ok} Spans</span>${result.meta?.model?`<span class="pill">${esc(result.meta.model)}</span>`:""}`;
  jsonMeta.textContent=`${Object.keys(result.json||{}).length} Schlüssel · ${ok} ok`;
}
function renderMarked(result, txt){
  const spans=(result.spans||[]).slice().sort((a,b)=>(a.start||0)-(b.start||0));
  const filt=[]; let max=-1; spans.forEach(s=>{ if(s.start==null||s.end==null) return; if(s.start<max) return; filt.push(s); max=s.end; });
  if(!filt.length){ markedText.textContent=txt; legend.classList.add("hidden"); legend.innerHTML=""; return; }
  let html="",last=0; filt.forEach(s=>{ html+=esc(txt.slice(last,s.start)); const t=esc(txt.slice(s.start,s.end)); const off=filters.has(s.type)?" off":""; html+=`<mark class="mark mark-${s.type}${off}" data-type="${s.type}" title="${s.type}">${t}</mark>`; last=s.end; }); html+=esc(txt.slice(last));
  markedText.innerHTML=html;
  const present=[...new Set(filt.map(s=>s.type))].sort((a,b)=>ORDER.indexOf(a)-ORDER.indexOf(b));
  if(present.length<=2){ legend.classList.add("hidden"); legend.innerHTML=""; return; }
  legend.classList.remove("hidden"); legend.innerHTML="";
  present.forEach(t=>{
    const b=document.createElement("button"); b.type="button"; b.className="legend-btn"+(filters.has(t)?" off":""); b.textContent=`${META[t].de} · ${t}`;
    b.addEventListener("click",()=>{ if(filters.has(t)) filters.delete(t); else filters.add(t); renderMarked(result,txt); });
    legend.appendChild(b);
  });
}

/* Drawer */
function openDrawer(){ drawer.classList.remove("hidden"); document.body.style.overflow="hidden"; closeDrawer.focus(); }
function closeDrawerFn(){ drawer.classList.add("hidden"); document.body.style.overflow=""; jsonLink.focus(); }
jsonLink.addEventListener("click",openDrawer); closeDrawer.addEventListener("click",closeDrawerFn); backdrop.addEventListener("click",closeDrawerFn);
document.addEventListener("keydown",e=>{ if(e.key==="Escape" && !drawer.classList.contains("hidden")) closeDrawerFn(); if(e.key==="Escape" && !helpDrawer.classList.contains("hidden")) closeHelpFn(); });
async function copy(txt,fb){ try{await navigator.clipboard.writeText(txt);}catch{ const ta=document.createElement("textarea"); ta.value=txt; document.body.appendChild(ta); ta.select(); document.execCommand("copy"); ta.remove(); } fb.textContent="Kopiert"; fb.classList.remove("hidden"); setTimeout(()=>fb.classList.add("hidden"),1500); }
copyJsonBtn.addEventListener("click",()=>{ if(!lastResult) return; copy(JSON.stringify(lastResult.json,null,2),copyFeedback); });
downloadJsonBtn.addEventListener("click",()=>{ if(!lastResult) return; const b=new Blob([JSON.stringify(lastResult.json,null,2)],{type:"application/json"}); const u=URL.createObjectURL(b); const a=document.createElement("a"); a.href=u; a.download="pipeline_output.json"; a.click(); URL.revokeObjectURL(u); });
copyTextBtn&&copyTextBtn.addEventListener("click",()=>{ if(!lastText) return; const t=document.createElement("textarea"); t.value=lastText; document.body.appendChild(t); t.select(); document.execCommand("copy"); t.remove(); copyFeedback.textContent="Text kopiert"; copyFeedback.classList.remove("hidden"); setTimeout(()=>copyFeedback.classList.add("hidden"),1500); });

/* Help */
function openHelp(){ helpDrawer.classList.remove("hidden"); document.body.style.overflow="hidden"; }
function closeHelpFn(){ helpDrawer.classList.add("hidden"); document.body.style.overflow=""; }
helpBtn.addEventListener("click",()=>{ const o=helpDrawer.classList.contains("hidden"); if(o) openHelp(); else closeHelpFn(); helpBtn.setAttribute("aria-expanded",String(o)); });
closeHelp.addEventListener("click",closeHelpFn); helpBackdrop.addEventListener("click",closeHelpFn);

/* Analyze */
async function doExtract(){
  const text=inputEl.value; showErr(inputError,""); showErr(resultError,"");
  if(!text.trim()){ showErr(inputError,"Bitte geben Sie eine Stellenanzeige ein."); inputEl.focus(); return; }
  if(text.trim().length<20){ showErr(inputError,"Zu kurz – bitte vollständige Anzeige einfügen (mind. 20 Zeichen)."); return; }
  if(text.length>20000){ showErr(inputError,"Zu lang – max. 20.000 Zeichen."); return; }
  lastText=text; setLoading(true);
  try{
    const res=await fetch("/api/extract",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({text})});
    const data=await res.json().catch(()=>({}));
    if(!res.ok){
      const msg=data.error||`Fehler (${res.status})`;
      if(res.status===503) showErr(resultError,msg+" Prüfen Sie .env und starten Sie den Server neu.");
      else if(res.status>=500) showErr(resultError,msg+" – Server/Modell überlastet, erneut versuchen.");
      else showErr(resultError,msg);
      if(res.status===400 && !String(data.error||"").includes("API")) showErr(inputError,msg);
      emptyState.classList.remove("hidden"); dashboard.classList.add("hidden"); lastResult=null; return;
    }
    lastResult=data; document.getElementById("jsonOutput").textContent=JSON.stringify(data.json,null,2);
    renderEntities(data); renderSummary(data,text); filters.clear(); renderMarked(data,text);
    emptyState.classList.add("hidden"); dashboard.classList.remove("hidden"); showErr(resultError,"");
    document.getElementById("resultAnchor").scrollIntoView({behavior:"smooth",block:"start"});
  }catch(e){ showErr(resultError,"Netzwerkfehler – Verbindung prüfen und erneut versuchen."); }
  finally{ setLoading(false); }
}
analyzeBtn.addEventListener("click",doExtract);
inputEl.addEventListener("keydown",e=>{ if((e.metaKey||e.ctrlKey)&&e.key==="Enter"){ e.preventDefault(); doExtract(); }});

async function init(){
  counts();
  try{ const r=await fetch("/api/examples"); if(r.ok){ examples=await r.json(); renderExamples(); }}catch{}
  try{ const r=await fetch("/api/config"); if(r.ok){ const c=await r.json(); setStatus(c); }}catch{ setStatus(null); }
}
init(); counts();
