export default function(component) {
  const {data:d, parentElement, setTriggerValue} = component;
  const root = parentElement.querySelector('#groww-workspace');
  if (!root || !d) return;
  const ui = root._ui || (root._ui = {nav: d.outputs ? 'results' : 'upload', tab:'pulse', drawer:null, evidenceTab:'reviews', editing:false, draft:'', restoreTried:false, lastDownload:null, searchTimer:null, periodDirty:false});
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num = value => value == null ? '—' : Number(value).toLocaleString('en-IN');
  const date = value => value ? new Date(value+'T12:00:00').toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric'}) : 'Not available';
  const bytes = n => n > 1024*1024 ? (n/(1024*1024)).toFixed(1)+' MB' : Math.ceil(n/1024)+' KB';
  const link = value => {try {const u=new URL(value);return u.protocol==='https:'?esc(u.href):'#';}catch{return '#';}};
  const icons = {
    chart:'<path d="m4 14 4-6 4 3 6-7M4 5v3m14 10 3 3"/><circle cx="16" cy="16" r="4"/><path d="M3 19v-3M13 4V2"/>',
    file:'<path d="M6 3h8l4 4v14H6zM14 3v5h5M9 12h6M9 16h6"/>',
    table:'<rect x="4" y="3" width="16" height="18" rx="1"/><path d="M4 9h16M10 9v12M14 9v12M7 6h10"/>',
    calendar:'<rect x="4" y="5" width="16" height="16" rx="1"/><path d="M8 3v4M16 3v4M4 10h16"/>',
    upload:'<path d="M7 17H5a4 4 0 0 1-.4-8A7 7 0 0 1 18 7a5 5 0 0 1 1 10h-2M12 20V9m-4 4 4-4 4 4"/>',
    download:'<path d="M12 3v12m-4-4 4 4 4-4M4 16v5h16v-5"/>',
    arrow:'<path d="M4 12h16m-6-6 6 6-6 6"/>',
    swap:'<path d="M4 8h15m-4-4 4 4-4 4M20 16H5m4-4-4 4 4 4"/>',
    refresh:'<path d="M20 7v5h-5M4 17v-5h5M6 7a7 7 0 0 1 11-2l3 4M18 17a7 7 0 0 1-11 2l-3-4"/>',
    check:'<path d="m5 12 4 4L19 6"/>',
    shield:'<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6zM8 12l3 3 5-6"/>',
    light:'<path d="M9 18h6m-5 3h4M8 14a6 6 0 1 1 8 0l-1 4H9zM12 5v3m-3 3h6"/>',
    filter:'<path d="M4 4h16l-6 7v8l-4-2v-6zM3 3l18 18"/>',
    info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/>',
    lock:'<rect x="5" y="10" width="14" height="11" rx="1"/><path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3"/>',
    mail:'<rect x="3" y="5" width="18" height="14" rx="1"/><path d="m3 6 9 7 9-7"/>',
    copy:'<rect x="8" y="8" width="12" height="13" rx="1"/><path d="M16 8V3H3v13h5"/>',
    edit:'<path d="m4 17-1 4 4-1L20 7l-3-3zM15 6l3 3"/>',
    external:'<path d="M14 3h7v7m0-7L10 14M11 4H4v17h17v-7"/>',
    user:'<circle cx="12" cy="7" r="3"/><path d="M5 21v-4a7 7 0 0 1 14 0v4z"/>',
    close:'<path d="m6 6 12 12M18 6 6 18"/>',
    search:'<circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/>',
    rupee:'<path d="M6 4h13M6 8h13M7 4c9 0 9 8 0 8l9 8"/>',
    fingerprint:'<path d="M5 12a7 7 0 0 1 14 0M8 15v-3a4 4 0 0 1 8 0v5M11 20v-8a1 1 0 0 1 2 0v9M5 15v3M19 15v2M8 18v3"/>',
    clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v6l4 2"/>',
    sparkle:'<path d="m12 3 2 6 6 3-6 2-2 7-3-7-6-2 6-3zM20 3v4m-2-2h4"/>',
    eye:'<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12"/><circle cx="12" cy="12" r="3"/>',
    hourglass:'<path d="M6 3h12M6 21h12M7 3v5l10 8v5M17 3v5L7 16v5"/>',
    folder:'<path d="M3 7V4h7l2 3h9v14H3zM3 11h18"/>',
    terminal:'<rect x="3" y="4" width="18" height="16" rx="1"/><path d="m7 8 3 4-3 4M13 16h4"/>',
    code:'<path d="m8 6-6 6 6 6M16 6l6 6-6 6"/>'
  };
  const icon = name => `<svg viewBox="0 0 24 24" aria-hidden="true">${icons[name] || icons.file}</svg>`;
  const btn = (label, action, cls='', ico='', attrs='') => `<button class="btn ${cls}" data-action="${action}" ${attrs}>${ico?icon(ico):''}${label}</button>`;
  const badge = (text, cls='') => `<span class="badge ${cls}">${text}</span>`;
  const anchor = (label, url, cls='btn ghost', ico='external') => `<a class="${cls}" href="${link(url)}" target="_blank" rel="noopener noreferrer">${ico?icon(ico):''}${esc(label)}</a>`;
  const scrollTop = () => {document.querySelector('[data-testid="stMain"]')?.scrollTo({top:0,behavior:'smooth'});window.scrollTo({top:0,behavior:'smooth'});};
  const emit = (type,payload={}) => setTriggerValue('action',{id:crypto.randomUUID(),type,payload});
  const toast = text => {root.querySelector('.toast')?.remove();const e=document.createElement('div');e.className='toast';e.textContent=text;root.append(e);setTimeout(()=>e.remove(),3000);};
  const download = (name, content, mime='text/plain') => {const u=URL.createObjectURL(new Blob([content],{type:mime+';charset=utf-8'}));const a=document.createElement('a');a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),2000);};
  const note = (text, cls='', ico='info') => `<div class="notice ${cls}">${icon(ico)}<span>${esc(text)}</span></div>`;
  const markdown = text => {
    const lines=String(text || '').split('\n');let html='',ol=false;
    const inline=s=>esc(s).replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>');
    for(const line of lines){
      const item=line.match(/^\d+\.\s+(.+)/);
      if(item){if(!ol){html+='<ol class="action-list">';ol=true;}html+=`<li><span class="number">${(html.match(/class="number"/g)||[]).length+1}</span><span>${inline(item[1])}</span></li>`;continue;}
      if(ol){html+='</ol>';ol=false;}
      if(line.startsWith('## '))html+=`<h2>${inline(line.slice(3))}</h2>`;
      else if(line.startsWith('# '))html+=`<h1>${inline(line.slice(2))}</h1>`;
      else if(line.startsWith('> '))html+=`<blockquote>${inline(line.slice(2))}</blockquote>`;
      else if(line.trim())html+=`<p>${inline(line)}</p>`;
    }
    return html+(ol?'</ol>':'');
  };
  const periodText = `${date(d.period.start)} – ${date(d.period.end)}`;
  const a=d.analysis, o=d.outputs, x=d.execution, m=d.metrics, audit=d.audit;
  const shortDescription = text => {const first=String(text||'').split(/(?<=[.!?])\s+/)[0];return first.length>140?first.slice(0,140).replace(/\s+\S*$/,'')+'…':first;};
  const themeName = id => a?.themes.find(t=>t.id===id)?.name || 'Customer feedback';
  const exclusions = audit.excluded_count || 0;
  const selectedPeriod = () => ({start:root.querySelector('#start-date')?.value || d.period.start,end:root.querySelector('#end-date')?.value || d.period.end});

  // An opaque, same-browser workspace reference restores in-flight work after a refresh.
  // No credentials, uploaded CSV, or output text are persisted in browser storage. Download nonces prevent duplicate browser downloads after refresh.
  if(!ui.restoreTried){
    ui.restoreTried=true;
    try{const prior=sessionStorage.getItem('groww-workspace-live-v1');if(prior && prior!==d.workspace_id){emit('restore',{workspace_id:prior});root.innerHTML='<div class="empty">Reconnecting to your review workspace…</div>';return;}}catch{}
  }
  try{sessionStorage.setItem('groww-workspace-live-v1',d.workspace_id);}catch{}
  if(ui.lastWorkspace!==d.workspace_id){ui.lastWorkspace=d.workspace_id;ui.nav=o?'results':'upload';ui.editing=false;ui.drawer=null;}
  if(ui.previousStatus==='processing' && d.status==='ready' && ui.nav==='upload')ui.nav='results';
  if(ui.awaitingResults && d.status==='ready'){ui.nav='results';ui.awaitingResults=false;}
  ui.previousStatus=d.status;
  const signature=JSON.stringify(d);
  if(ui.signature===signature && !ui.forceRender)return;
  ui.signature=signature;ui.forceRender=false;

  function header(){return `<header class="topbar">
    <div class="brand"><div class="brand-logo">${icon('chart')}</div><span class="brand-name">Groww</span><div class="brand-sub">Review Intelligence</div></div>
    <nav class="navigation" aria-label="Workspace"><button data-nav="results" class="${ui.nav==='results'?'active':''}" aria-current="${ui.nav==='results'?'page':'false'}">Insights</button><button data-nav="upload" class="${ui.nav==='upload'?'active':''}" aria-current="${ui.nav==='upload'?'page':'false'}">Upload reviews</button><button data-nav="audit" class="${ui.nav==='audit'?'active':''}" aria-current="${ui.nav==='audit'?'page':'false'}">Review data</button></nav>
    <button class="about-button" data-action="about" aria-label="About this app">${icon('info')}</button>
  </header>`;}
  function footer(){return `<footer class="footer"><span>Groww · Review Intelligence</span><span>Emails are saved as drafts.</span></footer>`;}
  function datasetBar(){return `<section class="dataset-bar"><div class="grow"><div class="dataset-meta"><span class="file-tag">${icon('file')}<strong>${esc(d.file.name)}</strong></span><span>${periodText}</span></div><p class="small muted dataset-cutoff">Latest review: ${date(m.data_cutoff)}</p></div><div class="dataset-actions">${btn('Change CSV','change_dataset','tiny','swap',x.saving?'disabled':'')}${btn('New analysis','new','ghost tiny','refresh',x.saving?'disabled':'')}</div></section>`;}
  function metrics(){
    const vals=[['Reviews analyzed',num(m.included_count)],['Useful reviews',num(m.useful_count)],['General comments',num(m.nonspecific_count)],['Review period',d.period.weeks+' weeks']];
    return `<section class="metrics">${vals.map(v=>`<div class="metric"><span class="metric-label">${v[0]}</span><span class="metric-value">${v[1]}</span></div>`).join('')}</section><div class="audit-strip"><span>${num(exclusions)} rows excluded${m.nonspecific_count!=null?' · '+num(m.nonspecific_count)+' general comments left out of themes':''}</span><button data-nav="audit">View data checks ${icon('arrow')}</button></div>`;
  }
  function themes(){return `<section class="card"><div class="card-header"><div><h2>Top themes</h2></div><span class="small muted">${a.themes.length} themes</span></div><div class="theme-list">${a.themes.map((t,i)=>{
    const negative=t.sentiment.negative||0,total=Object.values(t.sentiment).reduce((s,n)=>s+n,0),negativePct=total?Math.round(100*negative/total):0;
    const mood=negativePct>=50?`${negativePct}% negative`:Object.entries(t.sentiment).sort((p,q)=>q[1]-p[1])[0]?.[0]||'';
    return `<button class="theme" data-theme="${esc(t.id)}" aria-label="View supporting reviews for ${esc(t.name)}"><span class="rank">${i+1}</span><span class="grow"><span class="title-row"><h3>${esc(t.name)}</h3><span class="theme-tags"><span>${num(t.count)} reviews</span><span class="${negativePct>=50?'negative':''}">${esc(mood)}</span></span></span><p>${esc(shortDescription(t.description))}</p></span></button>`;
  }).join('')}</div></section>`;}
  function feeCard(){return `<section class="card fee-card"><div class="card-header"><h2>A recurring fee question</h2>${a.fee_name?badge(esc(a.fee_name),'mint'):''}</div>${a.fee_issue?`<p class="fee-question-preview">${esc(o?.fee_question||a.fee_issue)}</p><div class="row between wrap space-top"><span class="small muted">Raised in ${num(a.fee_evidence.length)} different reviews</span>${btn('Reviews &amp; sources','fee_evidence','ghost tiny','external')}</div>`:note('We need three different reviews about the same fee before writing an answer.','amber')}</section>`;}
  function quoteCard(q){const platform=q.review_key.split(':')[0];return `<article class="quote"><div class="meta"><span>${esc(platform)}</span><time>${date(q.date)}</time></div><blockquote>“${esc(q.text)}”</blockquote><div class="quote-links">${q.source_url?anchor('Source',q.source_url,'','external'):''}<details class="quote-details"><summary>Review details</summary><div class="detail-inner"><p class="mono">${esc(q.review_key)}</p><p class="small muted">${esc(themeName(q.theme_id))}</p></div></details></div></article>`;}
  function quotes(){return `<section class="card quotes-card"><div class="card-header"><h2>What customers say</h2><span class="small muted">${a.quotes.length} reviews</span></div>${a.quotes.length?a.quotes.map(quoteCard).join(''):note('Quotes will appear once the review checks pass.','amber')}</section>`;}
  function feeOutput(){return `<h2>Question</h2><h1>${esc(o.fee_question)}</h1><p class="small muted">From ${num(a?.fee_evidence.length||0)} different reviews.</p><h2>Answer</h2><ul>${o.fee_bullets.map(b=>`<li>${esc(b)}</li>`).join('')}</ul><div class="fee-references"><span class="small muted">Official sources</span>${o.sources.map(s=>anchor(s.title,s.url,'source-link','external')).join('')}<p class="small muted">Last checked: ${esc(o.last_checked)}</p></div>`;}
  function emailOutput(){return `<div class="email-head"><div class="row"><span class="email-label">To</span><span class="muted">No recipient</span></div><div class="row"><span class="email-label">Subject</span><strong>${esc(o.email.subject)}</strong></div><span class="small muted">Draft only</span></div><div class="email-body">${esc(o.email.body)}</div>`;}
  function outputTools(){const name=ui.tab==='pulse'?'weekly_product_pulse.md':ui.tab==='fee'?'fee_faq.md':'email_draft_preview.txt';return `<div class="output-tools"><span></span><div>${btn('Copy','copy','tiny','copy')}${ui.tab==='pulse'&&o.can_edit?btn('Edit','edit','tiny','edit'):''}${btn('Download','export','tiny','download',`data-file="${name}" ${o.valid?'':'disabled'}`)}</div></div>`;}
  function outputPanel(){return `<section class="card"><div class="card-header"><div><h2>Your update</h2></div>${badge(ui.tab==='fee'?o.fee_bullets.length+' bullets':ui.tab==='email'?'Unsent draft':o.word_count+' / 250 words',o.valid?'':'red')}</div><div class="output-tabs" role="tablist" aria-label="Generated outputs">${[['pulse','Weekly pulse'],['fee','Frequently Asked<br>Fee Question'],['email','Email draft']].map(([id,label])=>`<button role="tab" aria-selected="${ui.tab===id}" data-output="${id}" class="${ui.tab===id?'active':''}">${label}</button>`).join('')}</div>${!o.valid?`<div class="required-status">${esc(o.validation_error)}</div>`:''}${o.edited&&!x.completed?note('Updated. Please review before saving.','mint'):''}<div class="output-body" role="tabpanel">${ui.editing&&ui.tab==='pulse'?`<div class="editor-status" id="editor-count">${ui.draft.trim().split(/\s+/).filter(Boolean).length}/250 words</div><textarea class="editor" id="pulse-editor" aria-label="Weekly product pulse editor">${esc(ui.draft)}</textarea><div class="editor-tools">${btn('Cancel','cancel_edit')}${btn('Save changes','save_edit','dark')}</div><p class="small muted space-top">Keep the three quotes, headings and three action ideas.</p>`:(ui.tab==='pulse'?markdown(o.weekly_pulse.replace(/^# .+\r?\n/,'').trim()):ui.tab==='fee'?feeOutput():emailOutput())+outputTools()}</div><details><summary>Downloads &amp; options</summary><div class="detail-inner"><div class="row wrap">${btn('Document entry JSON','download','tiny','download','data-kind="document_entry.json"')}${btn('Complete analysis','download','tiny','download','data-kind="latest.json"')}${btn('Fee source passages','download','tiny','download','data-kind="fee_claim_evidence.md"')}${o.can_edit&&!ui.editing?btn('Regenerate outputs','regenerate','tiny','refresh'):''}</div></div></details></section>`;}
  function actionCard(action){const r=x.states[action],doc=action==='append_product_update',done=r?.status==='succeeded';const unknown=r?.status==='unknown'||r?.status==='in_progress';let title=doc?'Document saved':'Email draft created';if(!done)title=doc?'Document append':r?'Email draft not confirmed':'Email draft not started';return `<div class="completion"><div class="row"><span class="status-icon">${icon(done?'check':unknown?'clock':'info')}</span><div><h3>${title}</h3>${badge(done?'Completed':unknown?'Needs reconciliation':r?.status==='failed'?'Failed':'Waiting',done?'mint':'amber')}</div></div><p>${done?(doc?'Added to your Google Doc.':'Draft created with no recipient.'):esc(r?.message||'The document is saved before the email draft is created.')}</p>${done?anchor(doc?'Open saved document':'Open Gmail Drafts',doc?r.document_url:'https://mail.google.com/mail/u/0/#drafts','btn ghost tiny','external'):''}</div>`;}
  function approval(){
    const state=x.completed?'Saved successfully':x.saving?'Saving approved outputs':x.uncertain?'Checking save outcome':x.rejected?'Rejected':!o?.valid?'Needs correction':'Ready to save';
    let body='';
    if(x.completed||Object.keys(x.states).length||x.saving){body=actionCard('append_product_update')+actionCard('create_support_draft');if(!x.snapshot_matches_receipts&&Object.keys(x.states).length)body+=note('Saved action records refer to an earlier destination or content snapshot. Completed actions are retained; review the saved result before continuing.','amber');if(x.saving)body+=note('Saving your update…','mint','clock');else if(x.uncertain)body+=note('The last save is unconfirmed. Check it before retrying.','amber')+btn('Check save status','reconcile','block','refresh');else if(x.retryable)body+=btn('Approve and retry remaining action','retry_save','primary block','refresh');}
    else body=`<p class="small muted">Review the update, then approve to save.</p><div class="destinations"><div class="destination">${icon('file')}<div><strong>Google Docs</strong><p>Append to your document.</p>${x.doc_url?anchor('Open document',x.doc_url,'','external'):'<span class="red">Document destination is not configured.</span>'}</div></div><div class="destination">${icon('mail')}<div><strong>Email draft</strong><p>No recipient. Saved as a draft.</p></div></div></div>${x.rejected?note('Rejected. Nothing saved.','amber'):''}${x.destination_error?note('Saving is unavailable: '+x.destination_error,'amber'):''}${ui.editing||ui.periodDirty?note('Save or cancel your edits first.','amber'):''}${btn('Approve and Save','approve','primary block','user',x.can_approve&&!ui.editing&&!ui.periodDirty?'':'disabled')}${btn('Reject','reject','block','close',!o?.valid?'disabled':'')}<p class="approval-foot">${icon('lock')}Edits require fresh approval.</p>`;
    return `<section class="card approval"><div class="card-header"><div class="row"><span class="icon-box">${icon('shield')}</span><div><h3>${x.completed?'Update saved':'Save your update'}</h3></div></div>${badge(state,x.completed?'mint':x.uncertain?'amber':'')}</div>${body}${x.error?note(x.error,'error'):''}${Object.keys(x.states).length?`<details><summary>Save details</summary><div class="detail-inner">${Object.entries(x.states).map(([k,r])=>`<div class="detail-row"><span>${k==='append_product_update'?'Google Docs':'Gmail draft'}</span><strong>${esc(r.status)}</strong></div>${r.completed_at?`<p class="mono">Completed: ${esc(r.completed_at)}</p>`:''}${r.draft_id?`<p class="mono">Draft ID: ${esc(r.draft_id)}</p>`:''}`).join('')}<div class="space-top">${btn('Download save record','download','tiny','download','data-kind="receipts"')}</div></div></details>`:''}</section>`;
  }
  function errorPanel(){if(!d.error)return '';const titles={csv:'We couldn’t validate this CSV.',coverage:'There aren’t enough reviews in this reporting window.',feedback:'There isn’t enough useful feedback.',fee_evidence:'A recurring fee issue could not be established.',sources:'Official sources could not be verified.',outputs:'The outputs need validation.',analysis:'Analysis needs attention.'};return `<section class="card space-bottom"><div class="row space-bottom"><span class="icon-box">${icon('info')}</span><h2>${titles[d.error_kind]||'This analysis needs attention.'}</h2></div>${note(d.error,'amber')}<div class="row wrap space-top">${btn('Change CSV or reporting period','change_dataset','','upload')}${d.mode==='Live'&&d.status==='blocked'?btn('Retry processing','retry_analysis','dark','refresh'):''}</div></section>`;}
  function results(){if(!d.file.name)return `<section class="card empty"><div class="icon-box">${icon('chart')}</div><h2>No insights yet</h2><p>Upload your reviews to get started.</p>${btn('Upload CSV','change_dataset','dark','upload')}</section>`;return `${datasetBar()}${d.notice?`<div class="space-top">${note(d.notice)}</div>`:''}<div class="space-top">${metrics()}</div>${errorPanel()}${a?`<div class="results-grid"><div class="stack">${themes()}${feeCard()}${quotes()}</div><div class="stack">${o?outputPanel():`<section class="card empty"><div class="icon-box">${icon('file')}</div><h2>Outputs ${d.status==='processing'?'are being prepared':'are unavailable'}</h2><p>${d.status==='processing'?'The weekly pulse, fee explanation and email preview appear after source and evidence checks.':'Both required outputs must pass the evidence and source checks before approval.'}</p></section>`}${o?approval():''}</div></div>`:progressCard()}`;}
  function progressCard(){const p=d.processing;const stage=p?.stage||1,done=d.status==='ready',running=d.status==='processing',blocked=d.status==='blocked'||d.status==='invalid';const pct=p?Math.round(p.progress*100):0;return `<section class="card progress-card ${!p?'idle':''}"><div class="card-header"><h2>${done?'Ready to review':running?'Working on your reviews':blocked?'Needs attention':d.status==='cancelled'?'Analysis stopped':'What happens next'}</h2>${running?`<span class="small muted">${pct}%</span>`:done?icon('check'):''}</div>${p?`<div class="progress-track"><div style="width:${pct}%"></div></div>`:''}<div class="pipeline-list">${[['Check reviews','Dates, duplicates and missing data.'],['Find themes','Common issues and a recurring fee question.'],['Draft your update','Weekly pulse, fee answer and email draft.']].map(([label,desc],i)=>{const completed=!!m.included_count&&(done||i+1<stage||i===0),active=running&&i+1===stage&&!completed;return `<div class="pipeline-step ${completed?'complete':active?'active':'waiting'}"><span class="step-icon">${completed?icon('check'):i+1}</span><div class="grow"><h3>${label}</h3><p>${desc}</p></div></div>`;}).join('')}</div>${running?`<p class="small muted">${p.elapsed}s elapsed</p><details class="processing-details"><summary>Processing details</summary><p class="small mono">${esc(p.message)}</p></details>${btn('Stop analysis','cancel','ghost tiny')}`:done?btn('View insights','open_results','dark block','arrow'):''}</section>`;}
  function periodCard(){return `<section class="card period-card"><div class="card-header"><h2>Review period</h2><div class="segmented">${[8,10,12].map(n=>`<button data-weeks="${n}" class="${Number(d.period.weeks)===n?'active':''}" ${x.saving?'disabled':''}>${n} weeks</button>`).join('')}</div></div><div class="date-grid"><label><span class="field-label">From</span><input class="date-field" id="start-date" type="date" aria-label="Start reporting date" value="${d.period.start}" max="${d.today}" ${x.saving?'disabled':''}></label><label><span class="field-label">To</span><input class="date-field" id="end-date" type="date" aria-label="End reporting date" value="${d.period.end}" max="${d.today}" ${x.saving?'disabled':''}></label></div><div id="period-confirm" ${ui.periodDirty?'':'hidden'} class="confirm-period"><strong>Update the review period?</strong><p>This will recalculate the results.</p><div class="row">${btn('Cancel','cancel_period','tiny')}${btn(d.file.name?'Update &amp; recalculate':'Update period','apply_period','dark tiny')}</div></div></section>`;}
  function uploadCard(){return `<section class="card upload-card"><div class="dropzone" id="dropzone"><div class="upload-icon">${icon('upload')}</div><h2>Drop your reviews CSV here</h2><p>.csv · up to 15 MB</p><input type="file" accept=".csv,text/csv" id="csv-file" class="hidden-input" aria-label="Upload CSV" ${x.saving?'disabled':''}><div class="row wrap">${btn('Choose CSV','browse','dark','folder',x.saving?'disabled':'')}${btn('Sample CSV','sample','ghost','download')}</div>${d.file.name?`<div class="file-staged"><span class="icon-box">${icon('file')}</span><div class="grow"><div class="file-name">${esc(d.file.name)}</div><div class="muted">${bytes(d.file.bytes)}${m.original_count!=null?' · '+num(m.original_count)+' reviews':''}</div></div>${badge(d.status==='invalid'?'Check file':d.status==='ready'?'Analyzed':'Uploaded',d.status==='invalid'?'red':'mint')}</div>`:''}</div><div class="upload-help"><span>Your original file stays unchanged.</span>${btn('CSV requirements','schema','ghost tiny')}</div></section>`;}
  function rulesCard(){return `<details class="card upload-notes"><summary>How reviews are filtered</summary><div class="detail-inner"><ul><li>Only reviews in your selected period are included.</li><li>Duplicates and incomplete rows are set aside.</li><li>General comments like “good” stay out of themes. Specific complaints like “hidden charges” stay in.</li><li>A fee question needs three different supporting reviews.</li></ul>${btn('View data checks','open_audit','ghost tiny')}</div></details>`;}
  function upload(){return `<div class="page-heading"><div><h1>Upload your reviews</h1><p>Find recurring issues and turn them into a weekly update.</p></div></div>${d.notice?`<div class="space-bottom">${note(d.notice)}</div>`:''}${errorPanel()}<div class="upload-grid"><div class="stack">${uploadCard()}${periodCard()}</div><aside class="stack">${progressCard()}${rulesCard()}</aside></div>`;}
  const labels={duplicate:'Duplicate ID',invalid:'Invalid record',outside:'Out of window',future:'Future-dated',nonspecific:'Nonspecific feedback'};
  function auditPage(){
    if(!d.file.name)return `<section class="card empty"><h2>No review data yet</h2><p>Upload a CSV to see its data checks.</p>${btn('Upload CSV','change_dataset','dark','upload')}</section>`;
    return `<section class="audit-hero"><div class="page-heading"><div><h1>Review data</h1><p>See which rows were left out and why.</p></div>${btn('Download excluded rows','download','','download','data-kind="excluded" '+(m.original_count?'':'disabled'))}</div>${d.notice?`<div class="space-bottom">${note(d.notice)}</div>`:''}<div class="audit-metrics">${[['Excluded rows',exclusions],['Incomplete or invalid',m.invalid_count],['Duplicate IDs',m.duplicate_count],['Outside the period',(m.outside_window_count||0)+(m.future_count||0)]].map(v=>`<div class="audit-metric"><span class="metric-label">${v[0]}</span><div class="value">${num(v[1])}</div></div>`).join('')}</div></section>
    <section class="card audit-records"><div class="audit-controls"><h2>Review checks</h2><div class="audit-filters" aria-label="Audit categories">${[['all','All excluded',exclusions],['invalid','Invalid',audit.counts.invalid],['duplicate','Duplicates',audit.counts.duplicate],['outside','Outside period',audit.counts.outside],['future','Future dates',audit.counts.future],['nonspecific','General comments',audit.counts.nonspecific]].map(([id,label,n])=>`<button data-filter="${id}" class="${audit.filter===id?'active':''}">${label} <span>${num(n)}</span></button>`).join('')}</div></div><div class="audit-search"><label class="search-input">${icon('search')}<input id="audit-search" aria-label="Search audit records" placeholder="Search reviews or IDs" value="${esc(audit.search)}"></label><span class="count">${num(audit.filtered_count)} reviews</span></div>
    <div class="table-wrap"><table class="audit-table"><thead><tr><th>Review ID</th><th>Date</th><th>Reason</th><th>Review</th><th>Fingerprint</th><th></th></tr></thead><tbody>${audit.rows.length?audit.rows.map((r,i)=>`<tr><td class="review-id" title="${esc(r.review_id)}">${esc(r.review_id||'CSV row '+r.row)}</td><td>${/^\d{4}-\d{2}-\d{2}$/.test(r.date)?date(r.date):`<span class="red">${esc(r.date||'No date')}</span>`}</td><td>${badge(esc(labels[r.category]||r.category),r.category==='invalid'?'red':'')}</td><td class="excerpt">${esc(r.review_text.slice(0,100))}${r.review_text.length>100?'…':''}</td><td><span class="hash">${esc(r.text_hash.slice(0,8))}</span></td><td><button class="row-action" data-row="${i}" aria-label="Inspect review ${esc(r.review_id||r.row)}">${icon('eye')}</button></td></tr>`).join(''):`<tr><td colspan="6"><div class="empty">${m.original_count?'No matching reviews.':'No rows could be read from this CSV.'}</div></td></tr>`}</tbody></table></div>
    <div class="pagination"><span>${audit.filter==='nonspecific'?'General comments are counted, but left out of themes.':''}</span><div class="row">${btn('Previous','page_previous','tiny','',audit.page<=1?'disabled':'')}<span>${audit.page} / ${audit.pages}</span>${btn('Next','page_next','tiny','',audit.page>=audit.pages?'disabled':'')}</div></div></section>
    <details class="card secondary-details"><summary>File integrity</summary><div class="detail-inner"><p class="small muted">Checks run in order: missing data, duplicate IDs, then dates. Each excluded row is counted once.</p><p class="small muted space-top">Your original CSV is unchanged.</p>${btn('Verify original file','verify_hash','ghost tiny','fingerprint')}</div></details>
    <details class="card secondary-details"><summary>Evidence &amp; save details</summary><div class="audit-bottom">${auditFee()}${auditSources()}${auditExecution()}</div></details>`;
  }

  function auditFee(){return `<section class="card"><div class="card-header"><div class="row"><span class="icon-box mint">${icon('rupee')}</span><h2>Fee reviews</h2></div>${badge(a?.fee_evidence.length?'Traceable':'Pending',a?.fee_evidence.length?'mint':'')}</div><p class="small muted">${a?.fee_name?'Selected fee: '+esc(a.fee_name):'A named recurring fee has not been established.'}</p><div class="source-card"><span class="metric-value">${num(a?.fee_evidence.length||0)}</span><p>Different reviews raising this fee question.</p></div>${(a?.fee_evidence||[]).slice(0,2).map(q=>`<div class="evidence-quote"><div class="row between"><strong class="green mono">${esc(q.review_key)}</strong><span class="small muted">${date(q.date)}</span></div><p>“${esc(q.selected_fee_passage)}”</p></div>`).join('')}<div class="divider"></div>${btn('View fee reviews','fee_evidence','ghost tiny')}</section>`;}
  function auditSources(){return `<section class="card"><div class="card-header"><div class="row"><span class="icon-box mint">${icon('shield')}</span><h2>Official sources</h2></div>${badge((o?.sources.length||0)+' sources')}</div><p class="small muted"></p>${o?.sources.map(s=>`<div class="source-card"><div class="row between"><h3>${esc(s.title)}</h3>${badge('Checked','mint')}</div>${anchor(new URL(s.url).hostname,s.url,'','')}<p>Last checked: ${esc(s.checked_at)}</p></div>`).join('')||`<div class="empty small">Sources appear after analysis.</div>`}<div class="divider"></div>${btn('View source passages','official_sources','ghost tiny')}</section>`;}
  function auditExecution(){return `<section class="card"><div class="card-header"><h2>Save status</h2>${badge(x.completed?'Saved':'Awaiting approval',x.completed?'mint':'')}</div>${[['Google Docs','append_product_update'],['Email draft','create_support_draft']].map(([label,key])=>`<div class="audit-state"><div class="row between"><strong>${label}</strong><span class="green">${esc(x.states[key]?.status||'Not started')}</span></div></div>`).join('')}${x.uncertain?note('Check the previous save before retrying.','amber'):''}<div class="space-top">${btn('View save details','open_results','ghost tiny')}</div></section>`;}
  function drawer(){if(!ui.drawer)return '';let title='',subtitle='',body='';
    if(ui.drawer==='schema'){title='CSV requirements';subtitle='Six columns. One CSV.';body=`<div class="requirements"><p>Upload one UTF-8 CSV, at most 15 MB and 50,000 rows.</p><div class="divider"></div><p>Required columns:</p><p>${['platform','review_id','date','rating','review_text','source_url'].map(s=>`<code>${s}</code>`).join(' ')}</p><ul><li>Dates: YYYY-MM-DD.</li><li>Ratings: whole numbers from 1 to 5.</li><li>Source URLs: original public HTTPS review links.</li><li>Review text: preserve the original wording.</li><li>The reporting window must cover 8–12 weeks.</li></ul><div class="divider"></div><p>Generic comments such as “good” or “bad” are excluded from themes. Short specific feedback such as “hidden charges” stays eligible.</p><div class="space-top">${btn('Download sample CSV','sample','dark','download')}</div></div>`;}
    else if(ui.drawer==='about'){title='Groww Review Intelligence';subtitle='From customer reviews to your next product update.';body=`<div class="requirements"><p>Upload reviews, explore the themes, then review your weekly pulse and fee Q&amp;A.</p><p class="space-top">Approve when you’re ready to save to Google Docs and create an email draft.</p></div>`;}
    else if(ui.drawer==='row'){const r=audit.rows[ui.rowIndex];if(r){title=r.review_id||'CSV row '+r.row;subtitle=labels[r.category]+' · '+(r.platform||'Unknown platform');body=`${badge(esc(labels[r.category]),r.category==='invalid'?'red':'')}<div class="full-review">${esc(r.review_text)}</div><div class="detail-row"><span>Review date</span><strong>${esc(r.date||'Missing')}</strong></div><p class="small">${esc(r.reason)}</p><div class="divider"></div><div class="eyebrow">Normalized text fingerprint</div><p class="mono space-top">${esc(r.text_hash)}</p>${r.source_url?`<div class="space-top">${anchor('Open original review source',r.source_url)}</div>`:''}`;}}
    else if(ui.drawer==='theme'){const t=a?.themes.find(v=>v.id===ui.themeId);if(t){title=t.name;subtitle=num(t.count)+' reviews';body=`<p class="small muted">${esc(t.description)}</p>${t.supporting.map(q=>quoteCard({...q,theme_id:t.id})).join('')}<div class="divider"></div><p class="small muted">Showing up to 20 reviews. Download the full list below.</p>${btn('Download classifications','download','dark tiny','download','data-kind="classifications"')}`;}}
    else if(ui.drawer==='evidence'){title='Fee evidence & official sources';subtitle=a?.fee_issue||'Review evidence and official facts';body=`<div class="drawer-tabs"><button data-evidence="reviews" class="${ui.evidenceTab==='reviews'?'active':''}">Reviews</button><button data-evidence="sources" class="${ui.evidenceTab==='sources'?'active':''}">Official sources</button></div>${ui.evidenceTab==='reviews'?`<p class="small muted">${esc(shortDescription(a?.fee_rationale||'No recurring named fee has been established.'))}</p>${a?.fee_rationale?`<details><summary>Why this question</summary><div class="detail-inner small">${esc(a.fee_rationale)}</div></details>`:''}<p class="small muted space-top"></p>${(a?.fee_evidence||[]).map(q=>`<article class="quote"><div class="meta"><strong class="green">${esc(q.review_key)}</strong><span>${date(q.date)}</span></div><div class="full-review">${esc(q.text)}</div><p class="small"><strong>Relevant passage:</strong> “${esc(q.selected_fee_passage)}”</p>${anchor('Source',q.source_url,'','external')}</article>`).join('')}`:`<p class="small muted">Published fee rules from Groww.</p>${(o?.sources||[]).map(s=>`<article class="source-card"><h3>${esc(s.title)}</h3>${anchor(s.url,s.url,'','external')}<p>Last checked: ${esc(s.checked_at)}</p></article>`).join('')}${(o?.grounding||[]).map((g,i)=>`<details><summary>Bullet ${i+1}: matched official passages</summary><div class="detail-inner"><p class="small">${esc(g.text)}</p>${g.supporting_passages.map(p=>`<blockquote class="source-passages">${esc(p)}</blockquote>`).join('')}</div></details>`).join('')}`}`;}
    return `<div class="scrim" data-overlay="close"><aside class="drawer" role="dialog" aria-modal="true" aria-label="${esc(title)}"><div class="drawer-head"><div><h2>${esc(title)}</h2><p class="small muted space-top">${esc(subtitle)}</p></div><button class="drawer-close" data-action="close_drawer" aria-label="Close details">${icon('close')}</button></div><div class="drawer-content">${body}</div><div class="drawer-foot"></div></aside></div>`;
  }
  function render(){
    const drawerScroll=root.querySelector('.drawer-content')?.scrollTop||0;
    const wasDrawerOpen=!!root.querySelector('.drawer');
    const searchInput=root.querySelector('#audit-search');
    const active=!!searchInput && searchInput===parentElement.activeElement;
    const selection=active?searchInput.selectionStart:null;
    root.innerHTML=`<div class="app">${header()}<main class="content">${ui.nav==='results'?results():ui.nav==='audit'?auditPage():upload()}</main>${footer()}</div>${drawer()}`;
    bind();
    const drawerContent=root.querySelector('.drawer-content');
    if(drawerContent)drawerContent.scrollTop=drawerScroll;
    if(ui.drawer&&!wasDrawerOpen)root.querySelector('.drawer-close')?.focus();
    if(active){const input=root.querySelector('#audit-search');input?.focus();input?.setSelectionRange(selection,selection);}
  }
  function redraw(){ui.forceRender=true;render();}
  function beginUpload(file){
    if(!file || x.saving)return;
    if(!file.name.toLowerCase().endsWith('.csv')||file.size>15*1024*1024||file.size===0){toast('Choose a nonempty CSV of at most 15 MB.');return;}
    const period=selectedPeriod();
    if(new Date(period.end+'T12:00:00')>new Date(d.today+'T12:00:00')){toast('The reporting end date cannot be in the future.');return;}
    const days=Math.round((new Date(period.end+'T12:00:00')-new Date(period.start+'T12:00:00'))/86400000)+1;
    if(days<56||days>84){toast('Choose a reporting window of 8–12 weeks.');return;}
    const reader=new FileReader(),readId=crypto.randomUUID();ui.readId=readId;
    reader.onerror=()=>toast('This file could not be read. Choose it again.');
    reader.onload=()=>{if(ui.readId!==readId)return;ui.nav='upload';ui.awaitingResults=true;ui.periodDirty=false;emit('upload',{name:file.name,content:String(reader.result).split(',')[1],...period});};
    reader.readAsDataURL(file);toast('Reading CSV…');
  }
  function bind(){
    root.onclick=async e=>{
      const nav=e.target.closest('[data-nav]');if(nav){ui.nav=nav.dataset.nav;ui.drawer=null;redraw();scrollTop();return;}
      const tab=e.target.closest('[data-output]');if(tab){ui.tab=tab.dataset.output;redraw();return;}
      const theme=e.target.closest('[data-theme]');if(theme){ui.drawer='theme';ui.themeId=theme.dataset.theme;redraw();return;}
      const row=e.target.closest('[data-row]');if(row){ui.drawer='row';ui.rowIndex=Number(row.dataset.row);redraw();return;}
      const evidence=e.target.closest('[data-evidence]');if(evidence){ui.evidenceTab=evidence.dataset.evidence;redraw();return;}
      const filter=e.target.closest('[data-filter]');if(filter){emit('audit_filter',{filter:filter.dataset.filter,search:audit.search,page:1});return;}
      const weeks=e.target.closest('[data-weeks]');if(weeks){const end=root.querySelector('#end-date').value;const start=new Date(end+'T12:00:00');start.setDate(start.getDate()-Number(weeks.dataset.weeks)*7+1);root.querySelector('#start-date').value=start.toISOString().slice(0,10);ui.periodDirty=true;root.querySelector('#period-confirm').hidden=false;return;}
      if(e.target.dataset.overlay==='close'){ui.drawer=null;redraw();return;}
      const button=e.target.closest('[data-action]');if(!button||button.disabled)return;
      const action=button.dataset.action;
      if(['about','schema'].includes(action)){ui.drawer=action;redraw();}
      else if(action==='close_drawer'){ui.drawer=null;redraw();}
      else if(action==='browse')root.querySelector('#csv-file')?.click();
      else if(action==='sample')download('groww_reviews_sample.csv',d.sample_csv,'text/csv');
      else if(action==='change_dataset'){ui.nav='upload';ui.editing=false;redraw();scrollTop();}
      else if(action==='open_results'){ui.nav='results';redraw();scrollTop();}
      else if(action==='open_audit'){ui.nav='audit';redraw();scrollTop();}
      else if(action==='new'){ui.nav='upload';ui.periodDirty=false;emit('new');}
      else if(action==='apply_period'){ui.periodDirty=false;emit('period',selectedPeriod());}
      else if(action==='cancel_period'){ui.periodDirty=false;redraw();}
      else if(action==='fee_evidence'||action==='official_sources'){ui.drawer='evidence';ui.evidenceTab=action==='official_sources'?'sources':'reviews';redraw();}
      else if(action==='edit'){ui.editing=true;ui.draft=o.weekly_pulse;ui.editRevision=o.edit_revision;redraw();root.querySelector('#pulse-editor')?.focus();}
      else if(action==='cancel_edit'){ui.editing=false;redraw();}
      else if(action==='save_edit'){ui.draft=root.querySelector('#pulse-editor').value;ui.editing=false;emit('edit',{text:ui.draft,revision:ui.editRevision});}
      else if(action==='copy'){
        const feeText=o.fee_faq_markdown;
        const text=ui.tab==='pulse'?o.weekly_pulse:ui.tab==='fee'?feeText:'Subject: '+o.email.subject+'\n\n'+o.email.body;
        try{await navigator.clipboard.writeText(text);toast('Copied to clipboard.');}catch{toast('Clipboard access is unavailable. Use Export to save a copy.');}
      }
      else if(action==='export'){const file=button.dataset.file;download(file,ui.tab==='fee'?o.fee_faq_markdown:o.downloads[file]);}
      else if(action==='download')emit('download',{kind:button.dataset.kind});
      else if(action==='page_previous'||action==='page_next')emit('audit_filter',{filter:audit.filter,search:audit.search,page:audit.page+(action==='page_next'?1:-1)});
      else if(action==='approve'||action==='retry_save'){
        button.disabled=true;button.textContent='Saving approved outputs…';emit(action,{fingerprint:x.fingerprint});
      }
      else if(['reject','reconcile','cancel','retry_analysis','verify_hash','regenerate'].includes(action))emit(action);
    };
    root.onkeydown=e=>{if(e.key==='Escape'&&ui.drawer){ui.drawer=null;redraw();}};
    root.onchange=e=>{if(e.target.id==='csv-file')beginUpload(e.target.files[0]);if(e.target.id==='start-date'||e.target.id==='end-date'){ui.periodDirty=true;root.querySelector('#period-confirm').hidden=false;}};
    root.oninput=e=>{
      if(e.target.id==='pulse-editor'){ui.draft=e.target.value;const words=ui.draft.trim().split(/\s+/).filter(Boolean).length;const count=root.querySelector('#editor-count');count.textContent=words+'/250 words'+(words>250?' · '+(words-250)+' over the limit':'');count.classList.toggle('red',words>250);}
      if(e.target.id==='audit-search'){clearTimeout(ui.searchTimer);const value=e.target.value;ui.searchTimer=setTimeout(()=>emit('audit_filter',{filter:audit.filter,search:value,page:1}),400);}
    };
    const drop=root.querySelector('#dropzone');
    if(drop){drop.ondragover=e=>{e.preventDefault();drop.classList.add('dragging');};drop.ondragleave=()=>drop.classList.remove('dragging');drop.ondrop=e=>{e.preventDefault();drop.classList.remove('dragging');beginUpload(e.dataTransfer.files[0]);};}
  }
  render();
  if(d.download&&ui.lastDownload!==d.download.id){let previousDownload=null;try{previousDownload=sessionStorage.getItem('groww-last-download');}catch{}ui.lastDownload=d.download.id;if(previousDownload!==d.download.id){try{sessionStorage.setItem('groww-last-download',d.download.id);}catch{}download(d.download.name,d.download.content,d.download.mime);}}
}
