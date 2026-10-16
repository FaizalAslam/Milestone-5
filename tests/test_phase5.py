"""Hosted-demo, credential-boundary, and live-run recovery checks; no external writes."""
from datetime import date
import json
from pathlib import Path
from zipfile import ZipFile

import pytest
from streamlit.testing.v1 import AppTest

from groww.data import load_csv
from groww.demo import demo_manifest, load_demo
from groww.deployment import ROOT_FILES, build_repository_bundle
from groww.runstore import LiveRunStore
from scripts.configure_access import ensure_access_password

ROOT = Path(__file__).resolve().parents[1]


def test_frozen_demo_is_real_traceable_and_detects_tampering(tmp_path):
    import shutil
    manifest = demo_manifest(ROOT)
    dataset = load_csv((ROOT / 'groww_reviews_all_platforms_updated.csv').read_bytes(), date.fromisoformat(manifest['report_date']), 12)
    insights, bundle = load_demo(ROOT, dataset)
    assert len(dataset.reviews) == manifest['included_reviews'] == 13034
    assert insights.run_id == bundle.intelligence_run_id == manifest['intelligence_run_id']
    assert [t['count'] for t in insights.themes[:3]] == [550, 470, 457]
    shutil.copytree(ROOT / 'data/demo', tmp_path / 'data/demo')
    with (tmp_path / 'data/demo/latest.json').open('a', encoding='utf-8') as file:
        file.write(' ')
    with pytest.raises(ValueError, match='demo files changed'):
        load_demo(tmp_path, dataset)


def test_repository_archive_excludes_secrets_caches_and_live_runs(tmp_path):
    for name in ROOT_FILES:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('public fixture', encoding='utf-8')
    for name in ['.streamlit/secrets.toml', '.env', '.cache/token', 'outputs/private/live.json',
                 'data/private/token.txt', 'groww/__pycache__/private.pyc', 'scripts/.env']:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('SECRET MUST NOT SHIP', encoding='utf-8')
    manifest_path = tmp_path / 'data/demo/manifest.json'
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text('{}', encoding='utf-8')
    archive = tmp_path / 'deployment.zip'
    build_repository_bundle(tmp_path, archive)
    with ZipFile(archive) as bundle:
        assert '.streamlit/secrets.toml.example' in bundle.namelist()
        assert '.streamlit/secrets.toml' not in bundle.namelist()
        assert all(b'SECRET MUST NOT SHIP' not in bundle.read(n) for n in bundle.namelist())


def test_password_generation_preserves_existing_credentials(tmp_path):
    import tomllib
    path = tmp_path / 'secrets.toml'
    path.write_text('OPENAI_API_KEY = "test-key-preserve"\nDEMO_ACCESS_PASSWORD = ""\n', encoding='utf-8')
    assert ensure_access_password(path)
    saved = path.read_text(encoding='utf-8')
    config = tomllib.loads(saved)
    assert config['OPENAI_API_KEY'] == 'test-key-preserve'
    assert len(config['DEMO_ACCESS_PASSWORD']) >= 40
    assert not ensure_access_password(path)
    assert path.read_text(encoding='utf-8') == saved
    absent = tmp_path / 'environment-only.toml'
    assert not ensure_access_password(absent, 'already-in-environment')
    assert not absent.exists()


def test_live_run_can_resume_with_verified_parent_and_matching_dataset(dataset, sources, tmp_path):
    from dataclasses import replace
    from datetime import timedelta
    from test_engine import FixtureEngine
    engine = FixtureEngine(tmp_path / 'cache', dataset, sources)
    intelligence = engine.analyze_reviews(dataset)
    bundle = engine.generate_outputs(dataset, intelligence, sources)
    store = LiveRunStore(tmp_path / 'private/runs')
    store.save_bundle(bundle, intelligence)
    assert store.available(dataset) == [bundle.run_id]
    restored_input, restored_output = store.load(bundle.run_id, dataset)
    assert restored_input.model_dump(mode='json') == intelligence.model_dump(mode='json')
    assert restored_output.model_dump(mode='json') == bundle.model_dump(mode='json')
    other_window = replace(dataset, start_date=dataset.start_date + timedelta(days=7))
    assert store.available(other_window) == []
    with pytest.raises(ValueError):
        store.load(bundle.run_id, other_window)
    with pytest.raises(ValueError, match='Invalid saved run ID'):
        store.load('../other', dataset)


def test_public_saved_demo_opens_and_cannot_analyze_or_approve_even_when_unlocked(monkeypatch):
    import groww.analysis
    import groww.approval
    calls = []
    def no_engine(*_):
        raise AssertionError('Saved demo must not instantiate a live model client')
    monkeypatch.setattr(groww.analysis, 'Engine', no_engine)
    monkeypatch.setattr(groww.approval, 'execute_approved', lambda *a: calls.append(a))
    app = AppTest.from_file(ROOT / 'app.py')
    app.secrets.update(DEMO_ACCESS_PASSWORD='test-only', OPENAI_API_KEY='test-only',
                       N8N_MCP_URL='https://test.n8n.cloud/mcp/test', N8N_MCP_TOKEN='test-only',
                       GOOGLE_DOC_URL='https://docs.google.com/document/d/test-document-id/edit')
    app.run(timeout=30)
    assert not app.exception
    assert app.selectbox[0].value == 'Saved CSV demo'
    assert app.date_input[0].value == date(2026, 10, 16) and app.date_input[0].disabled
    assert app.session_state['bundle'].run_id == demo_manifest(ROOT)['output_run_id']
    app.session_state['operator_authenticated'] = True
    app.radio[0].set_value('2 · Review intelligence').run(timeout=30)
    assert next(b for b in app.button if b.label == 'Analyze reviews (Phase 2)').disabled
    app.radio[0].set_value('3 · Product + support outputs').run(timeout=30)
    assert next(b for b in app.button if b.label == 'Regenerate outputs from Phase 2').disabled
    app.radio[0].set_value('4 · Approve + save').run(timeout=30)
    assert not app.exception
    assert next(b for b in app.button if b.label == 'Approve and save').disabled
    assert not calls
    app.session_state['approval'] = {'approved': True}
    app.selectbox[0].set_value('Live upload and analysis').run(timeout=30)
    assert 'approval' not in app.session_state and 'bundle' not in app.session_state
    assert not calls
