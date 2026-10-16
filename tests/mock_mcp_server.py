"""Loopback-only MCP server for protocol tests. Does not access Google or email."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mcp.server.fastmcp import FastMCP
from groww.approval import approval_valid
from groww.outputs import fingerprint

server = FastMCP('Test-only product pulse tools', host='127.0.0.1', port=int(sys.argv[1]),
                 stateless_http=True, json_response=True)
receipts = {}


def action(envelope, expected):
    e = json.loads(envelope)
    p = json.loads(e['payload_json'])
    if not approval_valid(p, e) or e['action'] != expected:
        raise ValueError('Approval required')
    key = (p['run_id'], expected)
    if key not in receipts:
        receipts[key] = dict(run_id=p['run_id'], action=expected, payload_hash=fingerprint(p), status='succeeded',
                            **({'document_url': p['destination_doc_url']} if expected == 'append_product_update' else {'draft_id': 'mock-draft-only'}))
    return receipts[key]


@server.tool()
def append_product_update(envelope: str) -> dict:
    return action(envelope, 'append_product_update')


@server.tool()
def create_support_draft(envelope: str) -> dict:
    return action(envelope, 'create_support_draft')


@server.tool()
def get_run_receipts(run_id: str, payload_hash: str) -> dict:
    return dict(run_id=run_id, payload_hash=payload_hash,
                receipts=[r for (rid, _), r in receipts.items() if rid == run_id and r['payload_hash'] == payload_hash])


if __name__ == '__main__':
    server.run(transport='streamable-http')
