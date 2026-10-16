from __future__ import annotations

import asyncio
import json
import re
import threading
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from types import SimpleNamespace

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from .models import Bundle
from .outputs import document_text, email_content, fingerprint, validate_bundle

ACTIONS = ('append_product_update', 'create_support_draft')
TOOL_FIELDS = {**{a: {'envelope'} for a in ACTIONS}, 'get_run_receipts': {'run_id', 'payload_hash'}}
_locks_guard = threading.Lock()
_locks: dict[str, threading.Lock] = {}


def lock_for(key):
    with _locks_guard:
        return _locks.setdefault(key, threading.Lock())


def prepare_payload(bundle: Bundle, document_url: str) -> dict:
    validate_bundle(bundle)
    parsed = urlparse(document_url)
    if (parsed.scheme != 'https' or parsed.netloc != 'docs.google.com'
            or not re.fullmatch(r'/document/d/[A-Za-z0-9_-]+(?:/(?:edit|view))?/?', parsed.path)):
        raise ValueError('Configure the destination Google Docs document URL first.')
    return {'run_id': bundle.run_id, 'destination_doc_url': document_url,
            'entry': bundle.entry(), 'document_text': document_text(bundle),
            'email': email_content(bundle), 'last_checked': bundle.last_checked}


def approve(payload: dict) -> dict:
    # Only call from an authenticated operator's explicit button callback.
    return {'approved': True, 'payload_hash': fingerprint(payload),
            'approved_at': datetime.now(timezone.utc).isoformat()}


def approval_valid(payload: dict, approval: dict | None) -> bool:
    if not approval or approval.get('approved') is not True or approval.get('payload_hash') != fingerprint(payload):
        return False
    try:
        age = datetime.now(timezone.utc) - datetime.fromisoformat(approval['approved_at'])
        return timedelta(0) <= age <= timedelta(minutes=30)
    except (ValueError, KeyError, TypeError, OverflowError):
        return False


def validate_tool_schemas(schemas: dict) -> None:
    if set(schemas) != set(TOOL_FIELDS):
        raise ValueError('Expose only the two approved write tools and get_run_receipts.')
    for name, fields in TOOL_FIELDS.items():
        schema = schemas[name]
        props = schema.get('properties', {})
        if (schema.get('type') != 'object' or set(props) != fields
                or set(schema.get('required', [])) != fields
                or any(props[f].get('type') != 'string' for f in fields)):
            raise ValueError(f'Unexpected input schema for {name}. All listed inputs must be required strings.')


def result_data(result):
    if getattr(result, 'isError', False):
        raise ValueError('The MCP tool reported an error; the remote outcome needs checking.')
    raw = getattr(result, 'structuredContent', None)
    if raw is None:
        texts = [c.text for c in getattr(result, 'content', []) if getattr(c, 'type', None) == 'text']
        if len(texts) != 1:
            raise ValueError('MCP did not return one structured receipt.')
        raw = json.loads(texts[0])
    # n8n workflow tools commonly wrap one result item in an array.
    if isinstance(raw, list) and len(raw) == 1:
        raw = raw[0]
    if isinstance(raw, dict) and set(raw) == {'result'}:
        raw = raw['result']
        if isinstance(raw, list) and len(raw) == 1:
            raw = raw[0]
    return raw


def parse_receipt(result, action: str, payload: dict) -> dict:
    raw = result_data(result)
    if action not in ACTIONS:
        raise ValueError('Unrecognized receipt action.')
    if not isinstance(raw, dict) or raw.get('run_id') != payload['run_id'] or raw.get('action') != action or raw.get('payload_hash') != fingerprint(payload):
        raise ValueError('MCP receipt does not match the approved action and content.')
    if raw.get('status') not in ('succeeded', 'failed', 'unknown'):
        raise ValueError('MCP returned an unrecognized execution status.')
    if raw['status'] == 'failed' and raw.get('safe_to_retry') is not True:
        raw = dict(raw, status='unknown')
    if raw['status'] == 'succeeded':
        field = 'document_url' if action == ACTIONS[0] else 'draft_id'
        if not isinstance(raw.get(field), str) or not raw[field].strip():
            raise ValueError('MCP reported success without the remote output identifier.')
        if action == ACTIONS[0] and raw['document_url'] != payload['destination_doc_url']:
            raise ValueError('The document receipt points to a different destination.')
    return raw


class N8nMCP:
    def __init__(self, url: str, token: str, *, allow_local=False):
        parsed = urlparse(url)
        allowed = parsed.scheme == 'https' and parsed.hostname and parsed.hostname.endswith('.n8n.cloud')
        if allow_local:
            allowed |= parsed.scheme == 'http' and parsed.hostname in ('127.0.0.1', 'localhost')
        if not allowed or parsed.username or parsed.password or parsed.query or parsed.fragment or not token:
            raise ValueError('Configure an HTTPS n8n Cloud MCP URL and bearer token.')
        self.url, self.token = url, token

    async def inspect(self):
        async with httpx.AsyncClient(headers={'Authorization': f'Bearer {self.token}'}, timeout=60) as client:
            async with streamable_http_client(self.url, http_client=client) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    available = await session.list_tools()
                    schemas = {t.name: t.inputSchema for t in available.tools}
                    validate_tool_schemas(schemas)
                    return schemas

    async def call(self, action, payload, approval):
        if action not in ACTIONS or not approval_valid(payload, approval):
            raise ValueError('Explicit approval of the current content is required.')
        envelope = dict(approval, action=action,
                        payload_json=json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':')))
        async with httpx.AsyncClient(headers={'Authorization': f'Bearer {self.token}'}, timeout=90) as client:
            async with streamable_http_client(self.url, http_client=client) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    validate_tool_schemas({t.name: t.inputSchema for t in tools.tools})
                    found = next((t for t in tools.tools if t.name == action), None)
                    if not found or set(found.inputSchema.get('properties', {})) != {'envelope'}:
                        raise ValueError(f'n8n must expose {action} with one string input named envelope.')
                    result = await session.call_tool(action, {'envelope': json.dumps(envelope, ensure_ascii=False)},
                                                     read_timeout_seconds=timedelta(seconds=90))
                    return parse_receipt(result, action, payload)

    async def receipts(self, payload):
        async with httpx.AsyncClient(headers={'Authorization': f'Bearer {self.token}'}, timeout=60) as client:
            async with streamable_http_client(self.url, http_client=client) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool('get_run_receipts', {
                        'run_id': payload['run_id'], 'payload_hash': fingerprint(payload)})
                    raw = result_data(result)
                    if not isinstance(raw, dict) or raw.get('run_id') != payload['run_id'] or raw.get('payload_hash') != fingerprint(payload):
                        raise ValueError('Receipt lookup returned a different run.')
                    if not isinstance(raw.get('receipts'), list) or len({r.get('action') for r in raw['receipts']}) != len(raw['receipts']):
                        raise ValueError('Receipt lookup returned malformed or duplicate actions.')
                    return {r['action']: parse_receipt(SimpleNamespace(structuredContent=r), r['action'], payload)
                            for r in raw['receipts']}


def execute_approved(payload: dict, approval: dict | None, states: dict, transport, journal=None) -> dict:
    if not approval_valid(payload, approval):
        raise ValueError('Approval is missing, expired, rejected, or invalidated by an edit.')
    key = fingerprint(payload)
    run_lock = lock_for(payload['run_id'])
    if not run_lock.acquire(blocking=False):
        raise ValueError('This approved run is already executing.')
    try:
        if journal:
            states.update(journal.load(payload))
        for action in ACTIONS:
            previous = states.get(action, {})
            if previous and (previous.get('payload_hash') != key or previous.get('run_id') != payload['run_id']):
                raise ValueError('Execution receipts belong to different content; reconcile that run first.')
            if previous.get('status') == 'succeeded':
                continue
            if previous.get('status') in ('in_progress', 'unknown'):
                break
            if previous.get('status') == 'failed' and previous.get('safe_to_retry') is not True:
                break
            if journal:
                claimed, saved = journal.claim(payload, action, approval)
                states.update(saved)
                if not claimed:
                    if states.get(action, {}).get('status') == 'succeeded':
                        continue
                    break
            states[action] = {'status': 'in_progress', 'run_id': payload['run_id'], 'action': action,
                              'payload_hash': key}
            try:
                receipt = parse_receipt(SimpleNamespace(structuredContent=asyncio.run(transport.call(action, payload, approval))), action, payload)
                states[action] = receipt
            except Exception:
                # A timeout/error might occur after the remote write. Do not blindly retry.
                states[action] = {'status': 'unknown', 'run_id': payload['run_id'], 'action': action,
                                  'payload_hash': key,
                                  'message': 'Remote outcome unconfirmed. Inspect n8n and the destination before retrying.'}
            if journal:
                states.update(journal.reconcile(payload, {action: states[action]}))
            if states[action]['status'] != 'succeeded':
                break
        return states
    finally:
        run_lock.release()
