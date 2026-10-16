// Check exported graph references, JavaScript syntax, and the approval gate without n8n credentials.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '..');
let checks = 0;
for (const filename of fs.readdirSync(path.join(root, 'n8n')).filter(f => f.endsWith('.json'))) {
  const workflow = JSON.parse(fs.readFileSync(path.join(root, 'n8n', filename), 'utf8'));
  const names = new Set(workflow.nodes.map(n => n.name));
  for (const [source, types] of Object.entries(workflow.connections)) {
    if (!names.has(source)) throw new Error(`Unknown source ${source}`);
    for (const branches of Object.values(types)) for (const branch of branches) for (const edge of branch) {
      if (!names.has(edge.node)) throw new Error(`Unknown target ${edge.node}`);
    }
  }
  for (const node of workflow.nodes) {
    if (node.type === 'n8n-nodes-base.code') {
      new Function('require', '$input', '$', '$execution', node.parameters.jsCode);
    }
    if (node.type === 'n8n-nodes-base.gmail' && (node.parameters.resource !== 'draft' || node.parameters.operation !== 'create')) {
      throw new Error('Unexpected Gmail operation: only draft creation is allowed');
    }
    if (/googleDocs|gmail/.test(node.type) && (node.retryOnFail || node.continueOnFail || node.onError)) {
      throw new Error('Google writes must stop on error without automatic retries');
    }
  }
  const gate = workflow.nodes.find(n => n.name === 'Validate approval');
  if (gate) {
    const doc = 'https://docs.google.com/document/d/test-document-id/edit';
    const js = gate.parameters.jsCode.replace('REPLACE_WITH_GOOGLE_DOC_URL', doc);
    const action = filename.startsWith('01') ? 'append_product_update' : 'create_support_draft';
    const pulse = '# Pulse\n## Product action ideas\n1. A\n2. B\n3. C';
    const p = {run_id:'b'.repeat(32),destination_doc_url:doc,entry:{date:'2026-10-16',top_themes:[{},{},{}],weekly_pulse:pulse,
      identified_fee_issue:'Test',explanation_bullets:['Test fee fact'],source_links:['https://groww.in/pricing','https://groww.in/help/test']},
      email:{subject:'Weekly Product Pulse + Customer Clarification — Groww — 2026-10-16',body:pulse+' Test fee fact'},
      document_text:pulse+' Test fee fact'};
    const payload_json = JSON.stringify(p);
    const envelope = {approved:true,approved_at:new Date().toISOString(),action,payload_json,
      payload_hash:crypto.createHash('sha256').update(payload_json).digest('hex')};
    const run = e => new Function('require','$input',js)(require,{first:()=>({json:{envelope:JSON.stringify(e)}})});
    if (run(envelope)[0].json.payload.run_id !== p.run_id) throw new Error('Valid envelope failed');
    for (const bad of [{...envelope,approved:false},{...envelope,payload_hash:'tampered'},
                       {...envelope,action:'send_email'},{...envelope,approved_at:'2000-01-01T00:00:00Z'}]) {
      let denied = false;
      try { run(bad); } catch { denied = true; }
      if (!denied) throw new Error('Invalid envelope was accepted');
    }
    const ctx = run(envelope)[0].json;
    const inspect = workflow.nodes.find(n => n.name === 'Inspect previous');
    const examine = prior => new Function('$input', '$', inspect.parameters.jsCode)(
      {first:()=>({json:prior})}, () => ({first:()=>({json:ctx})}))[0].json;
    if (examine({}).has_previous) throw new Error('Fresh run incorrectly blocked');
    for (const [status, safe, blocked] of [['succeeded',false,true],['unknown',false,true],
                                          ['failed',false,true],['failed',true,false]]) {
      const prior = {ledger_key:ctx.ledger_key,payload_hash:envelope.payload_hash,
                     receipt_json:JSON.stringify({...ctx.receipt,status,safe_to_retry:safe})};
      if (examine(prior).has_previous !== blocked) throw new Error('Unsafe retry or duplicate allowed');
    }
    let mismatched = false;
    try { examine({ledger_key:ctx.ledger_key,payload_hash:'different'}); } catch { mismatched=true; }
    if (!mismatched) throw new Error('Reused run ID accepted different content');
    const edges = workflow.connections;
    if (edges['Already attempted'].main[0][0].node !== 'Return previous receipt' ||
        edges['Already attempted'].main[1][0].node !== 'Record attempt before write') {
      throw new Error('Known attempts must bypass Google writes');
    }
    const writeName = workflow.nodes.find(n=>/googleDocs|gmail/.test(n.type)).name;
    if (edges['Record attempt before write'].main[0][0].node !== writeName ||
        workflow.nodes.find(n=>n.name==='Record attempt before write').parameters.operation !== 'upsert') {
      throw new Error('Attempt must be persisted before the Google write');
    }
  }
  if (filename.startsWith('03') && workflow.nodes.some(n => /gmail|googleDocs/.test(n.type) || (n.type.endsWith('dataTable') && n.parameters.operation !== 'get'))) {
    throw new Error('Receipt lookup must remain read only');
  }
  checks++;
}
console.log(`PASS: ${checks} workflow graphs, Code-node syntax, approval rejection, ledger retry guards, attempt-before-write ordering, and draft-only Gmail.`);
