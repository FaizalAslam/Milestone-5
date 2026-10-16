"""Generate credential-free n8n workflow imports. Run after changing this builder."""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / 'n8n'
OUT.mkdir(exist_ok=True)


def node(name, kind, params, x=0, y=0, version=1, **extra):
    return dict(id=name.lower().replace(' ', '-'), name=name, type=kind,
                typeVersion=version, position=[x, y], parameters=params, **extra)


def code(name, js, x=0, y=0):
    return node(name, 'n8n-nodes-base.code', {'jsCode': js}, x, y, 2)


def trigger(fields=('envelope',)):
    return node('Workflow input', 'n8n-nodes-base.executeWorkflowTrigger',
                {'workflowInputs': {'values': [{'name': f, 'type': 'string'} for f in fields]}}, version=1.1)


def link(connections, source, target, branch=0, connection='main'):
    outputs = connections.setdefault(source, {}).setdefault(connection, [])
    while len(outputs) <= branch:
        outputs.append([])
    outputs[branch].append({'node': target, 'type': connection, 'index': 0})


def write(filename, name, nodes, connections):
    (OUT / filename).write_text(json.dumps({'name': name, 'nodes': nodes, 'connections': connections,
                                           'settings': {'executionOrder': 'v1'}, 'active': False,
                                           'pinData': {}, 'tags': []}, indent=2), encoding='utf-8')


def table(name, operation, values=None, x=0):
    params = {'resource': 'row', 'operation': operation,
              'dataTableId': {'__rl': True, 'mode': 'id', 'value': 'REPLACE_LEDGER_TABLE_ID'}}
    if operation in ('get', 'upsert'):
        params.update(matchType='allConditions', filters={'conditions': [
            {'keyName': 'ledger_key', 'condition': 'eq', 'keyValue': "={{ $('Validate approval').first().json.ledger_key }}"}]})
    if operation == 'get':
        params.update(returnAll=False, limit=1)
    if values:
        params['columns'] = {'mappingMode': 'defineBelow', 'value': values,
                             'matchingColumns': [], 'schema': [
                                 {'id': k, 'displayName': k, 'type': 'string', 'required': False,
                                  'defaultMatch': False, 'display': True, 'canBeUsedToMatch': True}
                                 for k in values], 'attemptToConvertTypes': False, 'convertFieldsToString': False}
    return node(name, 'n8n-nodes-base.dataTable', params, x, 0, 1, alwaysOutputData=operation == 'get')


VALIDATE = r'''
const crypto = require('crypto');
const EXPECTED_DOC_URL = 'REPLACE_WITH_GOOGLE_DOC_URL';
const ACTION = '__ACTION__';
const envelope = JSON.parse($input.first().json.envelope);
if (envelope.approved !== true || envelope.action !== ACTION) throw new Error('Approval required for this action');
const age = Date.now() - Date.parse(envelope.approved_at);
if (!Number.isFinite(age) || age < -10000 || age > 30 * 60 * 1000) throw new Error('Approval expired');
if (typeof envelope.payload_json !== 'string') throw new Error('Missing approved snapshot');
const hash = crypto.createHash('sha256').update(envelope.payload_json, 'utf8').digest('hex');
if (hash !== envelope.payload_hash) throw new Error('Approved content changed');
const p = JSON.parse(envelope.payload_json);
if (!/^[a-f0-9]{32}$/.test(p.run_id)) throw new Error('Invalid run ID');
if (EXPECTED_DOC_URL.startsWith('REPLACE_') || p.destination_doc_url !== EXPECTED_DOC_URL) throw new Error('Configure and verify the fixed document destination');
const docMatch = EXPECTED_DOC_URL.match(/^https:\/\/docs\.google\.com\/document\/d\/([A-Za-z0-9_-]+)/);
if (!docMatch) throw new Error('Invalid document destination');
const e = p.entry;
const fields = ['date','top_themes','weekly_pulse','identified_fee_issue','explanation_bullets','source_links'];
if (!e || Object.keys(e).sort().join() !== fields.sort().join()) throw new Error('Invalid document entry schema');
if (!Array.isArray(e.top_themes) || e.top_themes.length !== 3 || !Array.isArray(e.explanation_bullets) || e.explanation_bullets.length < 1 || e.explanation_bullets.length > 6) throw new Error('Output structure invalid');
if (e.weekly_pulse.trim().split(/\s+/u).length > 250) throw new Error('Pulse exceeds word limit');
if (!Array.isArray(e.source_links) || e.source_links.length !== 2 || e.source_links.some(u => !u.startsWith('https://groww.in/'))) throw new Error('Official source links required');
const actions = e.weekly_pulse.split('## Product action ideas')[1]?.trim().split('\n');
if (!actions || actions.length !== 3 || actions.some((a,i) => !a.startsWith(`${i+1}. `))) throw new Error('Exactly three action ideas required');
if (!p.email || Object.keys(p.email).sort().join() !== 'body,subject' || !p.email.body.includes(e.weekly_pulse) || !p.email.subject.startsWith('Weekly Product Pulse + Customer Clarification — Groww — ')) throw new Error('Invalid draft');
if (!p.document_text?.includes(e.weekly_pulse) || e.explanation_bullets.some(b => !p.document_text.includes(b) || !p.email.body.includes(b))) throw new Error('Preview and action contents differ');
const receipt = {run_id:p.run_id, action:ACTION, payload_hash:hash, approved_at:envelope.approved_at};
return [{json:{payload:p, receipt, ledger_key:p.run_id+':'+ACTION, document_id:docMatch[1]}}];
'''


def action_workflow(action, filename):
    nodes = [trigger(), code('Validate approval', VALIDATE.replace('__ACTION__', action), 240)]
    nodes.append(table('Look up receipt', 'get', x=480))
    nodes.append(code('Inspect previous', r'''
const prior = $input.first().json;
const ctx = $('Validate approval').first().json;
if (prior.ledger_key && prior.payload_hash !== ctx.receipt.payload_hash) throw new Error('Run ID reused for different content');
const receipt = prior.ledger_key ? JSON.parse(prior.receipt_json) : null;
const safeRetry = receipt?.status === 'failed' && receipt.safe_to_retry === true;
return [{json:{has_previous:!!prior.ledger_key && !safeRetry, receipt}}];
''', 720))
    nodes.append(node('Already attempted', 'n8n-nodes-base.if', {
        'conditions': {'options': {'caseSensitive': True, 'typeValidation': 'strict', 'version': 2},
                       'conditions': [{'id': 'has-prior', 'leftValue': '={{ $json.has_previous }}', 'rightValue': True,
                                       'operator': {'type': 'boolean', 'operation': 'true', 'singleValue': True}}],
                       'combinator': 'and'}, 'options': {}}, 960, 0, 2.2))
    nodes.append(code('Return previous receipt', 'return [{json:$input.first().json.receipt}];', 1200, -220))
    nodes.append(table('Record attempt before write', 'upsert', {
        'ledger_key': "={{ $('Validate approval').first().json.ledger_key }}",
        'payload_hash': "={{ $('Validate approval').first().json.receipt.payload_hash }}",
        'status': 'in_progress',
        'receipt_json': "={{ JSON.stringify({...$('Validate approval').first().json.receipt,status:'unknown',message:'Write started; inspect destination before retrying.'}) }}"}, x=1200))
    if action == 'append_product_update':
        nodes.append(node('Append approved entry', 'n8n-nodes-base.googleDocs', {
            'operation': 'update', 'documentURL': "={{ $('Validate approval').first().json.payload.destination_doc_url }}",
            'simple': True, 'actionsUi': {'actionFields': [{'object': 'text', 'action': 'insert',
                'text': "={{ $('Validate approval').first().json.payload.document_text }}",
                'insertSegment': 'body', 'locationChoice': 'endOfSegmentLocation'}]}, 'updateFields': {}},
            1440, 0, 2, credentials={'googleDocsOAuth2Api': {'id': 'REPLACE_DOCS_CREDENTIAL_ID', 'name': 'Groww Google Docs'}}))
        output = "const remote={document_url:ctx.payload.destination_doc_url};"
        perform = 'Append approved entry'
    else:
        nodes.append(node('Create approved Gmail draft', 'n8n-nodes-base.gmail', {
            'resource': 'draft', 'operation': 'create',
            'subject': "={{ $('Validate approval').first().json.payload.email.subject }}",
            'emailType': 'text', 'message': "={{ $('Validate approval').first().json.payload.email.body }}",
            'options': {}}, 1440, 0, 2.1,
            credentials={'gmailOAuth2': {'id': 'REPLACE_GMAIL_CREDENTIAL_ID', 'name': 'Groww Gmail Drafts'}}))
        output = "const id=$input.first().json.id; if (!id) throw new Error('Gmail did not return a draft ID'); const remote={draft_id:id};"
        perform = 'Create approved Gmail draft'
    nodes.append(code('Build success receipt', "const ctx=$('Validate approval').first().json;\n" + output +
                      "\nreturn [{json:{...ctx.receipt,status:'succeeded',...remote,completed_at:new Date().toISOString(),execution_id:String($execution.id)}}];", 1680))
    nodes.append(table('Persist success receipt', 'upsert', {
        'ledger_key': "={{ $('Validate approval').first().json.ledger_key }}",
        'payload_hash': '={{ $json.payload_hash }}', 'status': 'succeeded',
        'receipt_json': '={{ JSON.stringify($json) }}'}, x=1920))
    nodes.append(code('Return success receipt', "return [{json:$('Build success receipt').first().json}];", 2160))
    connections = {}
    chain = ['Workflow input', 'Validate approval', 'Look up receipt', 'Inspect previous', 'Already attempted']
    for a, b in zip(chain, chain[1:]):
        link(connections, a, b)
    link(connections, 'Already attempted', 'Return previous receipt', 0)
    link(connections, 'Already attempted', 'Record attempt before write', 1)
    chain = ['Record attempt before write', perform, 'Build success receipt', 'Persist success receipt', 'Return success receipt']
    for a, b in zip(chain, chain[1:]):
        link(connections, a, b)
    write(filename, 'Groww — ' + action, nodes, connections)


action_workflow('append_product_update', '01_append_product_update.json')
action_workflow('create_support_draft', '02_create_support_draft.json')

# Read-only recovery tool: no Google or Gmail nodes, no table writes.
nodes = [trigger(('run_id', 'payload_hash')),
         code('Validate lookup', r'''
const p=$input.first().json;
if (!/^[a-f0-9]{32}$/.test(p.run_id) || !/^[a-f0-9]{64}$/.test(p.payload_hash)) throw new Error('Invalid lookup');
return [{json:p}];
''', 240)]
nodes.append(node('Get run receipts', 'n8n-nodes-base.dataTable', {
    'resource': 'row', 'operation': 'get', 'dataTableId': {'__rl': True, 'mode': 'id', 'value': 'REPLACE_LEDGER_TABLE_ID'},
    'matchType': 'allConditions', 'filters': {'conditions': [
        {'keyName': 'payload_hash', 'condition': 'eq', 'keyValue': '={{ $json.payload_hash }}'}]},
    'returnAll': True}, 480, 0, 1, alwaysOutputData=True))
nodes.append(code('Return run receipts', r'''
const p=$('Validate lookup').first().json;
const receipts=$input.all().filter(i=>i.json.ledger_key?.startsWith(p.run_id+':')).map(i=>JSON.parse(i.json.receipt_json));
return [{json:{run_id:p.run_id,payload_hash:p.payload_hash,receipts}}];
''', 720))
connections = {}
for a, b in zip(nodes, nodes[1:]):
    link(connections, a['name'], b['name'])
write('03_get_run_receipts.json', 'Groww — get_run_receipts (read only)', nodes, connections)

nodes = [node('Groww MCP Server', '@n8n/n8n-nodes-langchain.mcpTrigger',
              {'path': 'groww-product-pulse', 'authentication': 'bearerAuth'}, 560, 0, 2,
              credentials={'httpBearerAuth': {'id': 'REPLACE_BEARER_CREDENTIAL_ID', 'name': 'Groww MCP bearer token'}})]
connections = {}
for i, (name, wid, fields) in enumerate([
    ('append_product_update', 'REPLACE_APPEND_WORKFLOW_ID', ['envelope']),
    ('create_support_draft', 'REPLACE_DRAFT_WORKFLOW_ID', ['envelope']),
    ('get_run_receipts', 'REPLACE_LOOKUP_WORKFLOW_ID', ['run_id', 'payload_hash']),
]):
    descriptions = {'envelope': 'Exact approved envelope JSON string supplied by the Streamlit approval controller',
                    'run_id': 'Run ID to inspect, without performing writes', 'payload_hash': 'Approved payload SHA-256'}
    nodes.append(node(name, '@n8n/n8n-nodes-langchain.toolWorkflow', {
        'name': name, 'description': descriptions.get(fields[0], name) + '. ' + name,
        'workflowId': {'__rl': True, 'mode': 'id', 'value': wid},
        'workflowInputs': {'mappingMode': 'defineBelow', 'value': {
            f: "={{ $fromAI('" + f + "', '" + descriptions[f] + "', 'string') }}" for f in fields},
            'matchingColumns': [], 'schema': [{'id': f, 'displayName': f, 'required': True,
                'defaultMatch': False, 'display': True, 'canBeUsedToMatch': True, 'type': 'string'} for f in fields],
            'attemptToConvertTypes': False, 'convertFieldsToString': False}}, 300 + i * 280, 240, 2.2))
    link(connections, name, 'Groww MCP Server', connection='ai_tool')
write('04_mcp_server.json', 'Groww — approved product and support tools', nodes, connections)
print('Generated four credential-free n8n workflow imports.')
