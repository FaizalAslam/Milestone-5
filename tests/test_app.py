from datetime import date
from pathlib import Path
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def test_app_starts_at_empty_upload_without_operator_controls():
    app = AppTest.from_file(ROOT / 'app.py').run(timeout=40)
    assert not app.exception
    view = app.session_state['workspace_view']
    assert view['status'] == 'empty' and view['mode'] == 'Live'
    assert not app.text_input and not app.radio and not app.selectbox
    assert not view['execution']['can_approve']


def test_completed_example_uses_real_lineage_and_is_read_only(monkeypatch):
    import groww.workspace
    def forbidden(*args, **kwargs):
        raise AssertionError('Example must not instantiate a model or run external writes')
    monkeypatch.setattr(groww.workspace, 'execute_approved', forbidden)
    app = AppTest.from_file(ROOT / 'app.py').run(timeout=40)
    workspace = app.session_state['_workspace']
    workspace.load_example()
    app.run(timeout=40)
    assert not app.exception
    view = app.session_state['workspace_view']
    assert view['mode'] == 'Demo' and view['status'] == 'ready'
    assert view['metrics']['included_count'] == 13034
    assert view['metrics']['useful_count'] == 2001
    assert view['metrics']['nonspecific_count'] == 11033
    assert len(view['analysis']['themes']) == 5 and len(view['analysis']['quotes']) == 3
    assert workspace.task.bundle.intelligence_run_id == workspace.task.intelligence.run_id
    assert not view['execution']['can_approve'] and not view['outputs']['can_edit']
    assert not view['execution']['states'] and view['execution']['doc_url'] == ''


def test_server_credentials_are_not_in_component_data():
    app = AppTest.from_file(ROOT / 'app.py')
    app.secrets.update(OPENAI_API_KEY='private-openai-fixture-value', N8N_MCP_TOKEN='private-mcp-fixture-value',
                       DEMO_ACCESS_PASSWORD='unused-password-fixture-value')
    app.run(timeout=40)
    import json
    wire = json.dumps(app.session_state['workspace_view'])
    assert 'private-openai-fixture-value' not in wire
    assert 'private-mcp-fixture-value' not in wire
    assert 'unused-password-fixture-value' not in wire
