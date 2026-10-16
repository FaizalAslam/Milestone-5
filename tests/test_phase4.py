"""Approval and interruption regression checks. All destinations and credentials are test-only."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

from groww.approval import (ACTIONS, TOOL_FIELDS, approve, execute_approved,
                            prepare_payload, result_data, validate_tool_schemas)
from groww.execution import ExecutionJournal
from test_outputs_approval import DOC, FakeTransport


def schemas():
    return {n: {'type': 'object', 'properties': {f: {'type': 'string'} for f in fields}, 'required': sorted(fields)}
            for n, fields in TOOL_FIELDS.items()}


@pytest.mark.parametrize('change', ['extra_send_tool', 'missing_lookup', 'wrong_type', 'optional_envelope'])
def test_tool_discovery_rejects_unsafe_or_incomplete_contract(change):
    tools = schemas()
    validate_tool_schemas(tools)
    if change == 'extra_send_tool':
        tools['send_email'] = tools[ACTIONS[1]]
    elif change == 'missing_lookup':
        del tools['get_run_receipts']
    elif change == 'wrong_type':
        tools[ACTIONS[0]]['properties']['envelope']['type'] = 'object'
    else:
        tools[ACTIONS[0]]['required'] = []
    with pytest.raises(ValueError):
        validate_tool_schemas(tools)


def test_durable_receipts_prevent_repeated_writes_after_new_session(bundle, tmp_path):
    payload, transport = prepare_payload(bundle, DOC), FakeTransport()
    path = tmp_path / 'execution.sqlite3'
    execute_approved(payload, approve(payload), {}, transport, ExecutionJournal(path))
    fresh = {}
    execute_approved(payload, approve(payload), fresh, transport, ExecutionJournal(path))
    assert transport.calls == list(ACTIONS)
    assert all(fresh[a]['status'] == 'succeeded' for a in ACTIONS)
    assert ExecutionJournal(path).find(bundle.run_id)['approval']['approved_at']


def test_crash_after_attempt_record_stays_paused_after_restart(bundle, tmp_path):
    payload, transport = prepare_payload(bundle, DOC), FakeTransport()
    path = tmp_path / 'execution.sqlite3'
    assert ExecutionJournal(path).claim(payload, ACTIONS[0], approve(payload))[0]
    states = execute_approved(payload, approve(payload), {}, transport, ExecutionJournal(path))
    assert states[ACTIONS[0]]['status'] == 'in_progress'
    assert transport.calls == []
    # Empty read-only lookup cannot erase the uncertain attempt.
    assert ExecutionJournal(path).reconcile(payload, {}) == states


def test_journal_claim_is_atomic_across_instances(bundle, tmp_path):
    payload, path = prepare_payload(bundle, DOC), tmp_path / 'execution.sqlite3'
    journals = [ExecutionJournal(path), ExecutionJournal(path)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda j: j.claim(payload, ACTIONS[0], approve(payload))[0], journals))
    assert sorted(results) == [False, True]


def test_partial_failure_survives_reload_and_retries_only_draft(bundle, tmp_path):
    payload, transport = prepare_payload(bundle, DOC), FakeTransport(ACTIONS[1], safe=True)
    path = tmp_path / 'execution.sqlite3'
    execute_approved(payload, approve(payload), {}, transport, ExecutionJournal(path))
    transport.fail_action = None
    execute_approved(payload, approve(payload), {}, transport, ExecutionJournal(path))
    assert transport.calls == [ACTIONS[0], ACTIONS[1], ACTIONS[1]]


def test_unknown_receipt_needs_confirmation_before_remaining_action(bundle, tmp_path):
    payload, transport = prepare_payload(bundle, DOC), FakeTransport(ACTIONS[0])
    journal = ExecutionJournal(tmp_path / 'execution.sqlite3')
    execute_approved(payload, approve(payload), {}, transport, journal)
    transport.fail_action = None
    execute_approved(payload, approve(payload), {}, transport, journal)
    assert transport.calls == [ACTIONS[0]]
    evidence_transport = FakeTransport()
    confirmed = asyncio.run(evidence_transport.call(ACTIONS[0], payload, approve(payload)))
    journal.reconcile(payload, {ACTIONS[0]: confirmed})
    execute_approved(payload, approve(payload), {}, transport, journal)
    assert transport.calls == [ACTIONS[0], ACTIONS[1]]
    with pytest.raises(ValueError, match='downgraded'):
        journal.reconcile(payload, {ACTIONS[0]: dict(confirmed, status='unknown')})


def test_existing_run_cannot_change_destination_or_content(bundle, tmp_path):
    payload = prepare_payload(bundle, DOC)
    journal = ExecutionJournal(tmp_path / 'execution.sqlite3')
    journal.claim(payload, ACTIONS[0], approve(payload))
    changed = dict(payload, document_text='changed')
    with pytest.raises(ValueError, match='different content'):
        execute_approved(changed, approve(changed), {}, FakeTransport(), journal)


def test_receipt_wrappers_and_error_response():
    assert result_data(SimpleNamespace(structuredContent={'result': [{'receipts': []}]})) == {'receipts': []}
    with pytest.raises(ValueError, match='reported an error'):
        result_data(SimpleNamespace(isError=True, structuredContent={'receipts': []}))


def test_unsafely_failed_state_never_retries(bundle):
    payload, transport = prepare_payload(bundle, DOC), FakeTransport()
    state = dict(run_id=bundle.run_id, action=ACTIONS[0], payload_hash=approve(payload)['payload_hash'], status='failed')
    execute_approved(payload, approve(payload), {ACTIONS[0]: state}, transport)
    assert not transport.calls


def test_phase4_ui_reject_approve_and_reload(bundle, dataset, tmp_path, monkeypatch):
    """The custom UI bridge uses this same server controller; fake MCP has no Google access."""
    import groww.workspace
    from groww.workspace import Workspace, Task
    transport = FakeTransport()
    monkeypatch.setattr(groww.workspace, 'N8nMCP', lambda *_: transport)
    workspace = Workspace(tmp_path, {'N8N_MCP_URL':'https://test.n8n.cloud/mcp/test',
        'N8N_MCP_TOKEN':'test-only', 'GOOGLE_DOC_URL':DOC}, start_threads=False)
    workspace.dataset = dataset
    workspace.task = Task(status='ready', bundle=bundle)
    workspace._spawn = lambda fn, *args: fn(*args)
    view = workspace.view()
    assert view['outputs']['email']['body'].startswith(bundle.weekly_pulse)
    assert view['execution']['can_approve'] and not transport.calls
    workspace.handle({'id':'reject-1','type':'reject'})
    assert workspace.rejected and not transport.calls
    assert not workspace.journal.find(bundle.run_id)
    event = {'id':'approve-1','type':'approve','payload':{'fingerprint':view['execution']['fingerprint']}}
    workspace.handle(event)
    assert transport.calls == list(ACTIONS)
    assert workspace.view()['execution']['completed']
    workspace.handle(event)
    assert transport.calls == list(ACTIONS)
    # A fresh controller restores durable receipts for the same result without reapproval/writes.
    restored = Workspace(tmp_path, workspace.settings, start_threads=False)
    restored.dataset, restored.task = dataset, workspace.task
    assert restored.view()['execution']['completed']
    assert not restored.view()['execution']['can_approve']
    assert transport.calls == list(ACTIONS)
