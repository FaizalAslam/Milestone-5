from streamlit.testing.v1 import AppTest
from pathlib import Path
from datetime import date


def test_app_dataset_and_unconfigured_flow():
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / 'app.py').run(timeout=30)
    app.selectbox[0].set_value('Live upload and analysis').run(timeout=30)
    app.date_input[0].set_value(date(2026, 10, 16)).run(timeout=30)
    assert not app.exception
    assert [m.value for m in app.metric] == ['13,268', '13,034', '234', '6,130']
    for section in ['2 · Review intelligence', '3 · Product + support outputs', '4 · Approve + save']:
        app.radio[0].set_value(section).run(timeout=30)
        assert not app.exception
    assert not any(b.label == 'Approve and save' and not b.disabled for b in app.button)


def test_phase2_ui_saves_independently_and_keeps_phase3_separate(dataset, sources, tmp_path, monkeypatch):
    """Use an explicitly mocked model; no live requests or real output files."""
    import groww.analysis
    import groww.data
    import groww.export
    import groww.sources
    import groww.runstore
    from test_engine import FixtureEngine

    engine = FixtureEngine(tmp_path / 'cache', dataset, sources)
    store_class = groww.runstore.LiveRunStore
    monkeypatch.setattr(groww.runstore, 'LiveRunStore', lambda *_: store_class(tmp_path / 'live'))
    monkeypatch.setattr(groww.data, 'load_csv', lambda *_: dataset)
    monkeypatch.setattr(groww.analysis, 'Engine', lambda *_: engine)
    save = groww.export.save_intelligence
    monkeypatch.setattr(groww.export, 'save_intelligence', lambda result, data, _: save(result, data, tmp_path / 'out'))
    def forbidden_source_fetch():
        raise AssertionError('Phase 2 must not fetch Phase 3 fee sources')
    monkeypatch.setattr(groww.sources, 'fetch_sources', forbidden_source_fetch)
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / 'app.py')
    app.secrets['OPENAI_API_KEY'] = 'offline-fixture'
    app.secrets['DEMO_ACCESS_PASSWORD'] = 'fixture-password'
    app.run(timeout=30)
    app.selectbox[0].set_value('Live upload and analysis').run(timeout=30)
    app.text_input[0].set_value('fixture-password')
    next(b for b in app.button if b.label == 'Unlock live workflow').click().run()
    app.radio[0].set_value('2 · Review intelligence').run()
    next(b for b in app.button if b.label == 'Analyze reviews (Phase 2)').click().run(timeout=30)
    assert not app.exception
    assert any('Phase 2 saved' in success.value for success in app.success)
    assert engine.calls == {'Taxonomy': 1, 'ClassificationBatch': 1, 'QuoteChoice': 3, 'FeeChoice': 1}
    assert (tmp_path / 'out/review_classifications.csv').exists()
    assert app.session_state['intelligence'].identified_fee_issue == 'Brokerage versus total'
    assert 'bundle' not in app.session_state
    app.radio[0].set_value('3 · Product + support outputs').run()
    assert not app.exception
    assert any(b.label == 'Generate outputs from Phase 2' and not b.disabled for b in app.button)
    assert engine.calls['PulseDraft'] == 0
    app.radio[0].set_value('4 · Approve + save').run()
    assert not app.exception
    assert not any(b.label == 'Approve and save' for b in app.button)
    app.slider[0].set_value(8).run()
    assert 'intelligence' not in app.session_state


def test_phase3_ui_generates_previews_and_invalidates_approval_on_edits(dataset, sources, tmp_path, monkeypatch):
    """Exercise the real Streamlit flow with test-only sources and a mocked model."""
    import groww.analysis
    import groww.approval
    import groww.data
    import groww.export
    import groww.sources
    import groww.runstore
    from test_engine import FixtureEngine

    engine = FixtureEngine(tmp_path / 'cache', dataset, sources)
    store_class = groww.runstore.LiveRunStore
    monkeypatch.setattr(groww.runstore, 'LiveRunStore', lambda *_: store_class(tmp_path / 'live'))
    insights = engine.analyze_reviews(dataset)
    monkeypatch.setattr(groww.data, 'load_csv', lambda *_: dataset)
    monkeypatch.setattr(groww.analysis, 'Engine', lambda *_: engine)
    monkeypatch.setattr(groww.sources, 'fetch_sources', lambda: sources)
    remote_calls = []
    monkeypatch.setattr(groww.approval, 'execute_approved', lambda *args: remote_calls.append(args))
    save = groww.export.save_bundle
    monkeypatch.setattr(groww.export, 'save_bundle', lambda result, _: save(result, tmp_path / 'out'))
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / 'app.py')
    app.secrets['OPENAI_API_KEY'] = 'offline-fixture'
    app.secrets['DEMO_ACCESS_PASSWORD'] = 'fixture-password'
    app.run(timeout=30)
    app.selectbox[0].set_value('Live upload and analysis').run(timeout=30)
    app.session_state['operator_authenticated'] = True
    app.session_state['intelligence'] = insights
    app.radio[0].set_value('3 · Product + support outputs').run()
    next(b for b in app.button if b.label == 'Generate outputs from Phase 2').click().run(timeout=30)
    assert not app.exception
    assert {'Weekly pulse preview', 'Document entry preview', 'Email draft preview', 'Phase 3 checkpoint'} <= {e.label for e in app.expander}
    assert not remote_calls
    assert engine.calls['ClassificationBatch'] == 1
    bundle = app.session_state['bundle']
    assert bundle.intelligence_run_id == insights.run_id
    assert bundle.weekly_pulse in next(t for t in app.text_area if t.label == 'Email body preview').value
    app.session_state['approval'] = {'approved': True, 'payload_hash': 'old-snapshot'}
    edited = bundle.weekly_pulse.replace('Test fixture summary.', 'Operator summary.')
    next(t for t in app.text_area if t.label == 'Weekly product pulse').set_value(edited).run()
    assert not app.exception and 'approval' not in app.session_state
    assert app.session_state['bundle'].pulse_edited
    assert edited in (tmp_path / 'out/email_draft_preview.txt').read_text(encoding='utf-8')
    next(t for t in app.text_area if t.label == 'Weekly product pulse').set_value('word ' * 251).run()
    assert not app.exception
    assert any('250 words' in w.value for w in app.warning)
    assert 'Phase 3 checkpoint' not in {e.label for e in app.expander}
    assert (tmp_path / 'out/weekly_product_pulse.md').read_text(encoding='utf-8') == edited
    next(b for b in app.button if b.label == 'Regenerate outputs from Phase 2').click().run(timeout=30)
    assert not app.exception and not app.session_state['bundle'].pulse_edited
    assert app.session_state['bundle'].run_id != bundle.run_id
    assert not remote_calls
