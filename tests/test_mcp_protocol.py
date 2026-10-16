import asyncio
import socket
import subprocess
import sys
import time
from pathlib import Path
from groww.approval import ACTIONS, N8nMCP, approve, execute_approved, prepare_payload


def test_real_mcp_initialize_discover_call_and_recover(bundle):
    # Real MCP messages over streamable HTTP, with test-only destination tools.
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    process = subprocess.Popen([sys.executable, str(Path(__file__).with_name('mock_mcp_server.py')), str(port)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            if process.poll() is not None:
                raise AssertionError('Test MCP server exited unexpectedly')
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=0.2):
                    break
            except OSError:
                time.sleep(0.1)
        else:
            raise AssertionError('Test MCP server did not start')
        transport = N8nMCP(f'http://127.0.0.1:{port}/mcp', 'test-token-not-a-real-secret', allow_local=True)
        available = asyncio.run(transport.inspect())
        assert set(ACTIONS) <= available.keys()
        assert available[ACTIONS[0]]['properties']['envelope']['type'] == 'string'
        payload = prepare_payload(bundle, 'https://docs.google.com/document/d/test-document-id/edit')
        states = execute_approved(payload, approve(payload), {}, transport)
        assert all(states.get(a, {}).get('status') == 'succeeded' for a in ACTIONS)
        recovered = asyncio.run(transport.receipts(payload))
        assert recovered.keys() == states.keys()
        assert recovered[ACTIONS[1]]['draft_id'] == 'mock-draft-only'
    finally:
        process.terminate()
        process.wait(timeout=5)
