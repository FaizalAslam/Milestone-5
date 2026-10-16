from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import pytest
from groww.approval import ACTIONS, approve, execute_approved, parse_receipt, prepare_payload
from groww.outputs import fingerprint, validate_bundle

DOC = 'https://docs.google.com/document/d/test-document-id/edit'


class FakeTransport:
    def __init__(self, fail_action=None, safe=False):
        self.calls = []
        self.fail_action, self.safe = fail_action, safe

    async def call(self, action, payload, approval):
        self.calls.append(action)
        if self.fail_action == action and not self.safe:
            raise TimeoutError('Outcome uncertain')
        if self.fail_action == action:
            return dict(action=action, run_id=payload['run_id'], payload_hash=fingerprint(payload), status='failed', safe_to_retry=True)
        return dict(action=action, run_id=payload['run_id'], payload_hash=fingerprint(payload), status='succeeded',
                    **({'document_url': DOC} if action == ACTIONS[0] else {'draft_id': 'test-draft'}))


def test_bundle_passes_with_real_source_matching(bundle, dataset):
    assert len(validate_bundle(bundle, dataset)) == 6


@pytest.mark.parametrize('change', [
    {'weekly_pulse': 'Too short and missing required structure'},
    {'weekly_pulse': 'word ' * 251},
    {'explanation_bullets': ['x'] * 7},
    {'sentiment_counts': {'negative': 4}},
    {'source_links': ['https://evil.example/pricing']},
    {'mode': 'reference_preview'},
    {'fee_evidence': []},
])
def test_invalid_outputs_block_saving(bundle, change):
    with pytest.raises(ValueError):
        prepare_payload(bundle.model_copy(update=change), DOC)


def test_nonverbatim_quote_rejected(bundle, dataset):
    changed = [dict(q) for q in bundle.quotes]
    changed[0]['text'] = 'Invented quote'
    with pytest.raises(ValueError):
        validate_bundle(bundle.model_copy(update={'quotes': changed}), dataset)


def test_no_approval_rejection_and_edit_produce_no_actions(bundle):
    payload = prepare_payload(bundle, DOC)
    transport = FakeTransport()
    for approval in [None, {'approved': False}, approve(dict(payload, document_text='old'))]:
        with pytest.raises(ValueError, match='Approval'):
            execute_approved(payload, approval, {}, transport)
    assert transport.calls == []


def test_expired_approval_is_blocked(bundle):
    payload = prepare_payload(bundle, DOC)
    permission = approve(payload)
    permission['approved_at'] = (datetime.now(timezone.utc) - timedelta(minutes=31)).isoformat()
    with pytest.raises(ValueError):
        execute_approved(payload, permission, {}, FakeTransport())


def test_success_and_repeated_click_are_idempotent(bundle):
    payload = prepare_payload(bundle, DOC)
    permission, states, transport = approve(payload), {}, FakeTransport()
    execute_approved(payload, permission, states, transport)
    execute_approved(payload, permission, states, transport)
    assert transport.calls == list(ACTIONS)
    assert all(v['status'] == 'succeeded' for v in states.values())


def test_unknown_append_never_drafts_or_blindly_retries(bundle):
    payload = prepare_payload(bundle, DOC)
    permission, states, transport = approve(payload), {}, FakeTransport(ACTIONS[0])
    execute_approved(payload, permission, states, transport)
    execute_approved(payload, permission, states, transport)
    assert transport.calls == [ACTIONS[0]]
    assert states[ACTIONS[0]]['status'] == 'unknown'
    assert ACTIONS[1] not in states


def test_partial_failure_retries_only_confirmed_safe_action(bundle):
    payload = prepare_payload(bundle, DOC)
    permission, states = approve(payload), {}
    transport = FakeTransport(ACTIONS[1], safe=True)
    execute_approved(payload, permission, states, transport)
    transport.fail_action = None
    execute_approved(payload, permission, states, transport)
    assert transport.calls == [ACTIONS[0], ACTIONS[1], ACTIONS[1]]


def test_receipt_requires_matching_remote_identifiers(bundle):
    payload = prepare_payload(bundle, DOC)
    receipt = dict(action=ACTIONS[0], run_id=payload['run_id'], payload_hash=fingerprint(payload), status='succeeded', document_url=DOC)
    assert parse_receipt(SimpleNamespace(structuredContent=receipt), ACTIONS[0], payload)['document_url'] == DOC
    for changed in [dict(receipt, payload_hash='bad'), dict(receipt, document_url='https://example.com'), dict(receipt, document_url='')]:
        with pytest.raises(ValueError):
            parse_receipt(SimpleNamespace(structuredContent=changed), ACTIONS[0], payload)
    with pytest.raises(ValueError):
        parse_receipt(SimpleNamespace(isError=True, structuredContent=receipt), ACTIONS[0], payload)


def test_exported_document_and_email_match_edited_snapshot(bundle, tmp_path):
    import json
    from groww.export import save_bundle
    edited = bundle.model_copy(update={'weekly_pulse': bundle.weekly_pulse.replace('Test fixture:', 'Operator edit:'), 'pulse_edited': True})
    save_bundle(edited, tmp_path)
    assert edited.weekly_pulse in (tmp_path / 'email_draft_preview.txt').read_text(encoding='utf-8')
    assert edited.weekly_pulse in (tmp_path / 'document_entry_preview.txt').read_text(encoding='utf-8')
    assert json.loads((tmp_path / 'document_entry.json').read_text(encoding='utf-8'))['weekly_pulse'] == edited.weekly_pulse
    assert json.loads((tmp_path / 'latest.json').read_text(encoding='utf-8'))['pulse_edited'] is True
