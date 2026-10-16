"""Verify the approval implementation using test-only MCP tools; never write to Google."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
from groww.approval import N8nMCP


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--save', action='store_true', help='Save public checkpoint and verification notes.')
    parser.add_argument('--mcp', action='store_true', help='Also discover the configured real MCP tools, read only.')
    args = parser.parse_args()
    load_dotenv(ROOT / '.env')
    secrets = ROOT / '.streamlit/secrets.toml'
    config = tomllib.loads(secrets.read_text(encoding='utf-8')) if secrets.exists() else {}
    get = lambda k: config.get(k) or os.getenv(k, '')
    names = ['DEMO_ACCESS_PASSWORD', 'N8N_MCP_URL', 'N8N_MCP_TOKEN', 'GOOGLE_DOC_URL']
    cache = ROOT / '.cache/phase4'
    cache.mkdir(parents=True, exist_ok=True)
    junit = cache / 'tests.xml'
    test = subprocess.run([sys.executable, '-m', 'pytest', '-q', 'tests/test_phase4.py',
                           'tests/test_mcp_protocol.py', 'tests/test_outputs_approval.py',
                           f'--junitxml={junit}'], cwd=ROOT, capture_output=True, text=True)
    if test.returncode:
        print(test.stdout + test.stderr)
        raise SystemExit('Phase 4 local tests failed; no checkpoint saved.')
    suites = ET.parse(junit).getroot().findall('testsuite')
    count = sum(int(s.attrib['tests']) for s in suites)
    node = shutil.which('node')
    if not node:
        raise SystemExit('Node.js is required to verify the actual n8n Code nodes.')
    workflows = subprocess.run([node, 'scripts/check_workflows.cjs'], cwd=ROOT, capture_output=True, text=True)
    if workflows.returncode:
        raise SystemExit(workflows.stdout + workflows.stderr)
    remote = {'status': 'not_configured' if not all(get(k) for k in names) else 'not_checked', 'write_tools_called': 0}
    if args.mcp and get('N8N_MCP_URL') and get('N8N_MCP_TOKEN'):
        try:
            available = asyncio.run(N8nMCP(get('N8N_MCP_URL'), get('N8N_MCP_TOKEN')).inspect())
            remote.update(status='discovery_passed', tool_names=sorted(available))
        except Exception as exc:
            remote.update(status='discovery_failed', error_type=type(exc).__name__)
    checkpoint = {'checked_at': datetime.now(timezone.utc).isoformat(), 'local_status': 'PASS',
                  'local_tests': {'passed': count, 'failed': 0, 'mcp_destination': 'loopback test server only'},
                  'n8n_exports': {'status': 'PASS', 'count': 4, 'details': workflows.stdout.strip()},
                  'configuration': {k: bool(get(k)) for k in names}, 'real_mcp': remote,
                  'live_acceptance': 'PENDING: verify one actual Google Docs append and one Gmail draft after human approval',
                  'external_document_or_email_writes_performed': 0}
    report = f'''# Phase 4 verification

Checked: {checkpoint['checked_at']}

- PASS: {count} local approval, durable-journal, UI, and MCP protocol tests; no failures.
- PASS: four exported n8n graphs, approval rejection, ledger guards, attempt-before-write ordering, and draft-only Gmail operations.
- PASS: content changes invalidate approval; rejection calls no write tools.
- PASS: successful actions survive a new session; uncertain attempts stay paused; safe partial retries skip completed actions.
- Real n8n MCP discovery: **{remote['status']}**. The check invokes no write tools.
- Live Google Docs + Gmail acceptance: **PENDING**. No actual document entry or email draft was created by this verification.

The local MCP test exchanges actual protocol messages over HTTP with test-only destination tools. It does not prove Google account access or workflow import compatibility. Follow [the Phase 4 guide](../docs/PHASE4.md) for the remaining account and human-approval checks.
'''
    if args.save:
        (ROOT / 'outputs').mkdir(exist_ok=True)
        (ROOT / 'outputs/phase4_checkpoint.json').write_text(json.dumps(checkpoint, indent=2) + '\n', encoding='utf-8')
        (ROOT / 'outputs/phase4_verification.md').write_text(report, encoding='utf-8')
    print(json.dumps(checkpoint, indent=2))


if __name__ == '__main__':
    main()
