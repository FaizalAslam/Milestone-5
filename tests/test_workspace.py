"""Wireframe interaction controller tests. Model and MCP calls are offline fixtures only."""
import base64
import csv
from datetime import date, timedelta
import hashlib
import io
import json
from pathlib import Path

import pytest

from groww.data import DataError, load_csv
from groww.models import ClassificationBatch
from groww.outputs import fingerprint
from groww.workspace import Task, Workspace, recover_workspace, register_workspace
from test_engine import FixtureEngine
from test_outputs_approval import ACTIONS, DOC, FakeTransport


def csv_bytes(reviews):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=['platform', 'review_id', 'date', 'rating', 'review_text', 'source_url'])
    writer.writeheader()
    for review in reviews:
        writer.writerow({key: getattr(review, key) for key in writer.fieldnames})
    return stream.getvalue().encode()


def configured(tmp_path, dataset, sources, engine_type=FixtureEngine):
    raw = csv_bytes(dataset.reviews)
    parsed = load_csv(raw, date(2026, 10, 16), 12)
    engine = engine_type(tmp_path / 'model-cache', parsed, sources)
    workspace = Workspace(tmp_path, {'OPENAI_API_KEY':'offline-test-key', 'N8N_MCP_URL':'https://test.n8n.cloud/mcp/test',
        'N8N_MCP_TOKEN':'offline-test-token', 'GOOGLE_DOC_URL':DOC}, today=date(2026,10,16),
        engine_factory=lambda *_: engine, source_fetcher=lambda: sources, start_threads=False)
    workspace.upload(raw, 'reviews.csv')
    return workspace, engine


def finish(workspace):
    workspace.run_analysis(workspace.task, workspace.dataset)
    assert workspace.task.status == 'ready', workspace.task.error
    return workspace.view()


def test_valid_upload_schedules_automatic_pipeline_once(dataset, sources, tmp_path):
    workspace, engine = configured(tmp_path, dataset, sources)
    assert workspace.task.status == 'processing'
    assert not engine.calls  # queued; a presentation refresh cannot submit another job
    for _ in range(3):
        workspace.view()
    assert not engine.calls
    view = finish(workspace)
    before = dict(engine.calls)
    workspace.view()
    workspace.handle({'id':'audit-tab','type':'audit_filter','payload':{'filter':'all','page':1}})
    workspace.handle({'id':'export','type':'download','payload':{'kind':'weekly_product_pulse.md'}})
    assert dict(engine.calls) == before
    assert view['outputs']['valid'] and not workspace.journal.find(workspace.task.bundle.run_id)
    assert hashlib.sha256(workspace.raw).hexdigest() == workspace.dataset.digest


def test_invalid_and_out_of_coverage_uploads_do_not_schedule_model(tmp_path):
    calls = []
    workspace = Workspace(tmp_path, {}, today=date(2026,10,16), engine_factory=lambda *_: calls.append('model'), start_threads=False)
    workspace.upload(b'review_text\ngood\n', 'invalid.csv')
    assert workspace.task is None and workspace.view()['error_kind'] == 'csv'
    valid_header = b'platform,review_id,date,rating,review_text,source_url\nTest,1,2020-01-01,5,good,https://example.com/1\n'
    workspace.upload(valid_header, 'old.csv')
    assert workspace.task is None and workspace.view()['error_kind'] == 'coverage'
    assert workspace.view()['audit']['excluded_count'] == 1
    assert not calls and not workspace.view()['execution']['can_approve']


def test_exclusion_reasons_reconcile_and_preserve_short_specific_feedback():
    raw = b'platform,review_id,date,rating,review_text,source_url\nTest,a,2026-10-14,1,hidden charges,https://example.com/1\nTest,a,2026-10-14,1,hidden charges,https://example.com/1\nTest,a,invalid,1,bad,https://example.com/1\nTest,b,2026-01-01,1,app crashes,https://example.com/2\nTest,c,2026-10-17,1,withdrawal stuck,https://example.com/3\n'
    dataset = load_csv(raw, date(2026,10,16))
    assert dataset.reviews[0].review_text == 'hidden charges'
    assert [r['category'] for r in dataset.exclusions] == ['duplicate','invalid','outside','future']
    assert len(dataset.reviews) + len(dataset.exclusions) == dataset.original_count
    assert dataset.exclusions[1]['review_text'] == 'bad'
    assert hashlib.sha256(raw).hexdigest() == dataset.digest


def test_custom_periods_match_existing_presets_and_reject_invalid_ranges(dataset):
    raw = csv_bytes(dataset.reviews)
    end = date(2026,10,16)
    for weeks in (8,10,12):
        assert load_csv(raw,end,weeks).audit() == load_csv(raw,end,12,start_date=end-timedelta(days=weeks*7-1)).audit()
    custom = load_csv(raw,end,start_date=end-timedelta(days=60))
    assert custom.start_date == end-timedelta(days=60)
    with pytest.raises(DataError,match='8 to 12 weeks'):
        load_csv(raw,end,start_date=end-timedelta(days=20))


def test_fee_failure_keeps_verified_general_findings_without_approvable_outputs(dataset, sources, tmp_path):
    class NoFeeEngine(FixtureEngine):
        def ask(self, schema, instruction, data):
            result = super().ask(schema,instruction,data)
            if schema is ClassificationBatch:
                for item in result.items:
                    item.fee_issue = item.fee_confusion_quote = None
            return result
    workspace, _ = configured(tmp_path,dataset,sources,NoFeeEngine)
    workspace.run_analysis(workspace.task,workspace.dataset)
    view = workspace.view()
    assert view['status'] == 'blocked' and view['error_kind'] == 'fee_evidence'
    assert len(view['analysis']['themes']) == 3 and view['metrics']['useful_count'] == 3
    assert view['outputs'] is None and not view['execution']['can_approve']


def test_no_useful_feedback_is_distinct_from_invalid_csv(dataset, sources, tmp_path):
    from dataclasses import replace
    dataset.reviews = [replace(r,review_text='good') for r in dataset.reviews]
    workspace, _ = configured(tmp_path,dataset,sources)
    workspace.run_analysis(workspace.task,workspace.dataset)
    view = workspace.view()
    assert view['error_kind'] == 'feedback' and view['metrics']['useful_count'] == 0
    assert view['metrics']['nonspecific_count'] == 3 and view['metrics']['invalid_count'] == 0
    assert view['outputs'] is None


def test_source_failure_retains_insights_and_blocks_approval(dataset, sources, tmp_path):
    workspace, _ = configured(tmp_path,dataset,sources)
    def fail():
        raise OSError('fixture source unavailable')
    workspace.source_fetcher = fail
    workspace.run_analysis(workspace.task,workspace.dataset)
    view = workspace.view()
    assert view['error_kind'] == 'sources' and view['analysis']['themes']
    assert not view['outputs'] and not view['execution']['can_approve']


def test_bad_edits_can_be_corrected_and_stale_approval_is_rejected(dataset, sources, tmp_path):
    workspace, _ = configured(tmp_path,dataset,sources)
    original = finish(workspace)
    text = original['outputs']['weekly_pulse']
    workspace.edit_pulse('word '*251,original['outputs']['edit_revision'])
    invalid = workspace.view()
    assert not invalid['outputs']['valid'] and not invalid['execution']['can_approve']
    workspace.edit_pulse(text.replace('Test fixture summary.','Edited fixture summary.'),invalid['outputs']['edit_revision'])
    corrected = workspace.view()
    assert corrected['outputs']['valid'] and corrected['outputs']['edited']
    assert corrected['outputs']['email']['body'].startswith(workspace.task.bundle.weekly_pulse)
    assert original['execution']['fingerprint'] != corrected['execution']['fingerprint']
    workspace.handle({'id':'stale','type':'approve','payload':{'fingerprint':original['execution']['fingerprint']}})
    assert not workspace.journal.find(workspace.task.bundle.run_id) and 'changed' in workspace.notice


def test_regeneration_keeps_insights_and_creates_a_new_approval_snapshot(dataset, sources, tmp_path):
    workspace, engine = configured(tmp_path,dataset,sources)
    before = finish(workspace)
    classification_calls = engine.calls['ClassificationBatch']
    workspace.handle({'id':'regenerate','type':'regenerate'})
    assert workspace.task.status == 'processing' and workspace.task.bundle is None
    after = finish(workspace)
    assert engine.calls['ClassificationBatch'] == classification_calls
    assert before['execution']['fingerprint'] != after['execution']['fingerprint']


@pytest.mark.parametrize('safe',[True,False])
def test_partial_and_uncertain_writes_keep_document_success_and_safe_retry_rules(dataset,sources,tmp_path,monkeypatch,safe):
    import groww.workspace as module
    workspace, _ = configured(tmp_path,dataset,sources)
    before = finish(workspace)
    transport = FakeTransport(ACTIONS[1],safe=safe)
    monkeypatch.setattr(module,'N8nMCP',lambda *_:transport)
    workspace._spawn = lambda fn,*args:fn(*args)
    workspace.handle({'id':'approve','type':'approve','payload':{'fingerprint':before['execution']['fingerprint']}})
    view = workspace.view()
    assert view['execution']['states'][ACTIONS[0]]['status'] == 'succeeded'
    assert view['execution']['retryable'] == safe
    transport.fail_action = None
    workspace.handle({'id':'retry','type':'retry_save','payload':{'fingerprint':before['execution']['fingerprint']}})
    if safe:
        assert workspace.view()['execution']['completed']
        assert transport.calls == [ACTIONS[0],ACTIONS[1],ACTIONS[1]]
    else:
        assert workspace.view()['execution']['uncertain']
        assert transport.calls == [ACTIONS[0],ACTIONS[1]]


def test_browser_recovery_reuses_same_task_and_settings_stay_server_side(dataset,sources,tmp_path):
    workspace, _ = configured(tmp_path,dataset,sources)
    register_workspace(workspace)
    restored = recover_workspace(workspace.id)
    assert restored is workspace and restored.task is workspace.task
    wire = json.dumps(workspace.view())
    assert 'offline-test-key' not in wire and 'offline-test-token' not in wire
    assert 'N8N_MCP_URL' not in wire and 'N8N_MCP_TOKEN' not in wire


def test_changed_destination_preserves_receipts_without_claiming_current_snapshot_was_saved(dataset,sources,tmp_path,monkeypatch):
    import groww.workspace as module
    workspace, _ = configured(tmp_path,dataset,sources)
    before=finish(workspace)
    transport=FakeTransport()
    monkeypatch.setattr(module,'N8nMCP',lambda *_:transport)
    workspace._spawn=lambda fn,*args:fn(*args)
    workspace.save(before['execution']['fingerprint'])
    workspace.settings['GOOGLE_DOC_URL']='https://docs.google.com/document/d/another-document/edit'
    after=workspace.view()['execution']
    assert len(after['states']) == 2 and not after['snapshot_matches_receipts']
    assert not after['completed'] and not after['retryable'] and not after['can_approve']
    assert transport.calls == list(ACTIONS)


def test_excluded_export_does_not_mislabel_valid_nonspecific_reviews(dataset,sources,tmp_path):
    from dataclasses import replace
    dataset.reviews.append(replace(dataset.reviews[0],review_id='generic',review_text='good'))
    workspace, _ = configured(tmp_path,dataset,sources)
    finish(workspace)
    assert workspace.view()['audit']['counts']['nonspecific'] == 1
    workspace._download('excluded')
    rows=list(csv.DictReader(io.StringIO(workspace.download['content'])))
    assert rows == []  # This CSV has no invalid/duplicate/out-of-window rows.
    workspace._download('classifications')
    assert len(list(csv.DictReader(io.StringIO(workspace.download['content'])))) == 4


def test_mode_and_period_changes_do_not_modify_a_running_save(dataset,sources,tmp_path):
    workspace, _ = configured(tmp_path,dataset,sources)
    finish(workspace)
    workspace.saving = True
    period = (workspace.start_date,workspace.end_date)
    workspace.handle({'id':'period','type':'period','payload':{'start':'2026-08-08','end':'2026-10-16'}})
    workspace.handle({'id':'mode','type':'example'})
    assert workspace.mode == 'Live' and (workspace.start_date,workspace.end_date) == period
    assert 'Wait' in workspace.notice


def test_approval_waits_for_background_output_verification(dataset,sources,tmp_path):
    workspace,_=configured(tmp_path,dataset,sources)
    ready=finish(workspace)
    workspace.task.status='processing'
    assert not workspace.view()['execution']['can_approve']
    workspace.handle({'id':'early-approve','type':'approve','payload':{'fingerprint':ready['execution']['fingerprint']}})
    assert 'verification' in workspace.notice
    assert not workspace.journal.find(workspace.task.bundle.run_id)


def test_unchanged_file_restores_verified_completed_run_without_new_model_or_write_calls(tmp_path):
    root=Path(__file__).resolve().parents[1]
    # Copy only the immutable public demo references, with an isolated test journal/store.
    import shutil
    shutil.copytree(root/'data/demo',tmp_path/'data/demo')
    workspace=Workspace(tmp_path,{},today=date(2026,10,16),start_threads=False,
        engine_factory=lambda *_:pytest.fail('Exact current saved analysis should be reused'))
    workspace.upload((root/'groww_reviews_all_platforms_updated.csv').read_bytes(),'original.csv')
    finish(workspace)
    assert workspace.task.bundle.run_id == '76326aa28fff423394c24cbbfa0d8c0a'
    assert not workspace.journal.find(workspace.task.bundle.run_id)
