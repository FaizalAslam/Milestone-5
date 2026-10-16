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


def test_legacy_example_link_starts_empty_live_upload(monkeypatch):
    import groww.workspace
    def forbidden(*args, **kwargs):
        raise AssertionError('Opening the app must not analyze reviews or write externally')
    monkeypatch.setattr(groww.workspace, 'execute_approved', forbidden)
    monkeypatch.setattr(groww.workspace, 'Engine', forbidden)
    app = AppTest.from_file(ROOT / 'app.py')
    app.query_params['example'] = '1'
    app.run(timeout=40)
    assert not app.exception
    view = app.session_state['workspace_view']
    assert view['mode'] == 'Live' and view['status'] == 'empty'
    assert view['analysis'] is None and view['outputs'] is None
    assert 'example' not in app.query_params
    assert not view['execution']['can_approve'] and not view['execution']['states']


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
