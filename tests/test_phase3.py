import csv
import io
import json

import pytest

from groww.analysis import AnalysisError
from groww.data import load_csv
from groww.export import save_bundle, save_intelligence
from groww.models import ExplainerDraft, FeeFactCheck, PulseDraft
from groww.outputs import validate_bundle, validate_explainer
from groww.sources import passage_catalog
from scripts.verify_phase3 import verify
from test_engine import FixtureEngine


def test_phase3_cache_reuses_outputs_and_invalidates_when_official_text_changes(dataset, sources, tmp_path):
    engine = FixtureEngine(tmp_path, dataset, sources)
    insights = engine.analyze_reviews(dataset)
    first = engine.generate_outputs(dataset, insights, sources)
    second = engine.generate_outputs(dataset, insights, sources)
    assert engine.calls['PulseDraft'] == engine.calls['ExplainerDraft'] == engine.calls['FeeFactCheck'] == 1
    assert first.run_id != second.run_id  # a new review snapshot invalidates old approval
    assert first.intelligence_run_id == insights.run_id
    changed = [s.model_copy(deep=True) for s in sources]
    changed[0].text += ' Test fixture updated official terms.'
    engine.sources = changed
    engine.generate_outputs(dataset, insights, changed)
    assert engine.calls['ExplainerDraft'] == engine.calls['FeeFactCheck'] == 2


def test_overlong_pulse_gets_bounded_repair_before_export(dataset, sources, tmp_path):
    class TooLongOnce(FixtureEngine):
        def ask(self, schema, instruction, data):
            result = super().ask(schema, instruction, data)
            if schema is PulseDraft and self.calls['PulseDraft'] == 1:
                result.summary = 'long ' * 251
            return result
    engine = TooLongOnce(tmp_path, dataset, sources)
    result = engine.generate_outputs(dataset, engine.analyze_reviews(dataset), sources)
    assert engine.calls['PulseDraft'] == 2
    assert len(result.weekly_pulse.split()) <= 250


def test_mismatched_source_passage_is_repaired_before_fact_check(dataset, sources, tmp_path):
    class BadPassageOnce(FixtureEngine):
        def ask(self, schema, instruction, data):
            result = super().ask(schema, instruction, data)
            if schema is ExplainerDraft and self.calls['ExplainerDraft'] == 1:
                result.bullets[0].supporting_passages = ['a made-up official passage']
            return result
    engine = BadPassageOnce(tmp_path, dataset, sources)
    result = engine.generate_outputs(dataset, engine.analyze_reviews(dataset), sources)
    assert result.fee_fact_check['supported']
    assert engine.calls['ExplainerDraft'] == 2 and engine.calls['FeeFactCheck'] == 1


def test_negative_fee_fact_check_stops_generation_without_blindly_flipping_verdict(dataset, sources, tmp_path):
    class UnsupportedClaims(FixtureEngine):
        def ask(self, schema, instruction, data):
            result = super().ask(schema, instruction, data)
            if schema is FeeFactCheck:
                return FeeFactCheck(supported=False, concerns=['Bullet 1 claims an unsupported universal cap.'])
            return result
    engine = UnsupportedClaims(tmp_path, dataset, sources)
    with pytest.raises(AnalysisError, match='unsupported universal cap'):
        engine.generate_outputs(dataset, engine.analyze_reviews(dataset), sources)
    assert engine.calls['ExplainerDraft'] == 2
    assert engine.calls['FeeFactCheck'] == 1  # same rejected claim reuses its negative assessment
    assert not list(tmp_path.rglob('explainer.json'))


def test_every_cited_source_must_actually_support_its_bullet(sources):
    from groww.models import FeeBullet
    draft = ExplainerDraft(bullets=[FeeBullet(text='Test claim', source_ids=['pricing', 'brokerage'],
                                             supporting_passages=[sources[0].text])])
    with pytest.raises(ValueError, match='Every cited source'):
        validate_explainer(draft, sources)


def test_upi_exception_cannot_be_presented_as_a_rule_for_generic_upi_orders(sources):
    from groww.models import FeeBullet
    draft = ExplainerDraft(bullets=[
        FeeBullet(text='UPI-funded orders incur 1% brokerage.', source_ids=['pricing'], supporting_passages=[sources[0].text]),
        FeeBullet(text=sources[1].text, source_ids=['brokerage'], supporting_passages=[sources[1].text])])
    with pytest.raises(ValueError, match='equity orders using UPI Mandate balance'):
        validate_explainer(draft, sources)


@pytest.mark.parametrize('field,value', [
    ('intelligence_run_id', 'wrong-parent'), ('intelligence_fingerprint', '0' * 64),
    ('fee_name', 'unrelated fee'), ('identified_fee_issue', 'a different scenario'),
])
def test_phase3_cannot_silently_replace_its_phase2_input(dataset, sources, tmp_path, field, value):
    engine = FixtureEngine(tmp_path, dataset, sources)
    insights = engine.analyze_reviews(dataset)
    result = engine.generate_outputs(dataset, insights, sources)
    with pytest.raises(ValueError, match='Phase 3'):
        validate_bundle(result.model_copy(update={field: value}), dataset, insights)


def test_source_catalog_uses_exact_original_spans_with_full_coverage(sources):
    sources[0].text = ' '.join(f'word{i}' for i in range(180))
    catalog = passage_catalog(sources)
    spans = [p['text'] for p in catalog.values() if p['source_id'] == sources[0].id]
    assert all(span in sources[0].text for span in spans)
    assert all(f'word{i}' in ' '.join(spans).split() for i in range(180))


def test_independent_phase3_verifier_detects_email_preview_drift(dataset, sources, tmp_path):
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(['platform', 'review_id', 'date', 'rating', 'review_text', 'source_url'])
    writer.writerows([[r.platform, r.review_id, r.date, r.rating, r.review_text, r.source_url] for r in dataset.reviews])
    path = tmp_path / 'input.csv'
    path.write_bytes(stream.getvalue().encode('utf-8'))
    parsed = load_csv(path.read_bytes(), dataset.report_date)
    engine = FixtureEngine(tmp_path / 'cache', parsed, sources)
    insights = engine.analyze_reviews(parsed)
    result = engine.generate_outputs(parsed, insights, sources)
    save_intelligence(insights, parsed, tmp_path / 'out')
    save_bundle(result, tmp_path / 'out')
    receipt = verify(path, tmp_path / 'out/review_intelligence.json', tmp_path / 'out/latest.json')
    assert receipt['status'] == 'PASS' and receipt['weekly_pulse_words'] <= 250
    assert json.loads((tmp_path / 'out/document_entry.json').read_text(encoding='utf-8')) == result.entry()
    assert all(set(t) == {'id', 'name', 'count'} for t in result.entry()['top_themes'])
    (tmp_path / 'out/email_draft_preview.txt').write_text('Different unapproved email text', encoding='utf-8')
    with pytest.raises(ValueError, match='email_draft_preview.txt differs'):
        verify(path, tmp_path / 'out/review_intelligence.json', tmp_path / 'out/latest.json')
