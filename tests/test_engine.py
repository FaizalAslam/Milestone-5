from collections import Counter
import pytest
from groww.analysis import AnalysisError, Engine
from groww.models import (Classification, ClassificationBatch, EvidenceChoice, ExplainerDraft,
                         FeeBullet, FeeChoice, FeeFactCheck, PulseDraft, QuoteChoice, ReviewIntelligence, Taxonomy, Theme)
from groww.data import Review
from groww.export import save_intelligence
from groww.intelligence import validate_intelligence
from datetime import timedelta
import csv
import json


class FixtureEngine(Engine):
    """Offline model fixture: exercises data flow, not actual OpenAI quality."""
    def __init__(self, root, dataset, sources, bad_quote=False):
        self.cache_root, self.model = root, 'offline-test-fixture'
        self.dataset, self.sources, self.bad_quote = dataset, sources, bad_quote
        self.calls = Counter()

    def ask(self, schema, instruction, data):
        self.calls[schema.__name__] += 1
        if schema is Taxonomy:
            return Taxonomy(themes=[Theme(id=f'T{i+1}', name=n, description=n) for i, n in enumerate(['Fees', 'Support', 'Orders'])])
        if schema is ClassificationBatch:
            items = []
            for item in data['reviews']:
                text = item['text']
                theme = 'T1' if 'Hidden' in text else 'T2' if 'Support' in text else 'T3'
                generic = text == 'good'
                items.append(Classification(text_key=item['text_key'], sentiment='positive' if generic else 'negative',
                    substantive=not generic, theme_id=None if generic else theme,
                    fee_issue=None if generic else 'Brokerage versus total', fee_confusion_quote=None if generic else text))
            return ClassificationBatch(items=items)
        if schema is QuoteChoice:
            candidate = data['candidates'][0]
            return QuoteChoice(review_key=candidate['review_key'], text='invented' if self.bad_quote else candidate['text'])
        if schema is FeeChoice:
            rows = self.dataset.reviews[:3]
            return FeeChoice(issue='Brokerage versus total', fee_name='brokerage', supporting_review_keys=[r.key for r in rows],
                             supporting_excerpts=[QuoteChoice(review_key=r.key, text=r.review_text) for r in rows], rationale='Test fixture')
        if schema is PulseDraft:
            return PulseDraft(summary='Test fixture summary.', observation='Test fixture observation.', actions=['Show fee details.', 'Explain charges clearly.', 'Improve order reliability.'])
        if schema is ExplainerDraft:
            return ExplainerDraft(bullets=[FeeBullet(text=s.text, source_ids=[s.id], supporting_passages=[s.text]) for s in self.sources])
        if schema is FeeFactCheck:
            return FeeFactCheck(supported=True, concerns=[])
        raise AssertionError(schema)


def test_full_pipeline_counts_and_caching(dataset, sources, tmp_path):
    dataset.reviews += [Review('Test', str(i), dataset.report_date, 5, 'good', 'https://example.com') for i in (3, 4)]
    dataset.original_count = 5
    engine = FixtureEngine(tmp_path, dataset, sources)
    bundle = engine.run(dataset, sources)
    assert sum(t['count'] for t in bundle.themes) == 3
    assert bundle.non_substantive_count == 2
    assert bundle.sentiment_counts == {'negative': 3, 'positive': 2}
    assert engine.calls['ClassificationBatch'] == 1
    engine.run(dataset, sources)
    assert engine.calls['ClassificationBatch'] == 1  # exact completed batch reused


def test_invented_model_quote_never_reaches_outputs(dataset, sources, tmp_path):
    engine = FixtureEngine(tmp_path, dataset, sources, bad_quote=True)
    with pytest.raises(AnalysisError, match='exact'):
        engine.run(dataset, sources)
    assert engine.calls['QuoteChoice'] == 2  # one bounded semantic repair, then stop
    assert not list(tmp_path.rglob('evidence.json'))


def test_phase2_stands_alone_and_exports_auditable_originals(dataset, sources, tmp_path):
    first = dataset.reviews[0]
    dataset.reviews += [Review('Other platform', 'duplicate-text', first.date - timedelta(days=7), 2,
                               first.review_text.upper(), 'https://example.com/duplicate')]
    dataset.reviews += [Review('Test', str(i), dataset.report_date, 5, text, 'https://example.com')
                        for i, text in [(4, 'good'), (5, '  GOOD\n')]]
    dataset.original_count = len(dataset.reviews)
    engine = FixtureEngine(tmp_path / 'cache', dataset, sources)
    result = engine.analyze_reviews(dataset)
    assert engine.calls == {'Taxonomy': 1, 'ClassificationBatch': 1, 'QuoteChoice': 3, 'FeeChoice': 1}
    assert result.themes[0]['count'] == 2
    assert result.themes[0]['current_week'] == result.themes[0]['previous_week'] == 1
    assert result.non_substantive_count == 2
    assert result.sentiment_counts == {'negative': 4, 'positive': 2}
    assert len(result.assignments) == 6 and result.audit['unique_texts'] == 4
    save_intelligence(result, dataset, tmp_path / 'out')
    saved = ReviewIntelligence.model_validate_json((tmp_path / 'out/review_intelligence.json').read_text(encoding='utf-8'))
    assert validate_intelligence(saved, dataset)
    with (tmp_path / 'out/review_classifications.csv').open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == len(dataset.reviews)
    assert [r['review_text'] for r in rows] == [r.review_text for r in dataset.reviews]
    assert [r['source_url'] for r in rows] == [r.source_url for r in dataset.reviews]
    assert 'Recurring fee confusion' in (tmp_path / 'out/review_intelligence.md').read_text(encoding='utf-8')
    assert not (tmp_path / 'out/latest.json').exists()  # Phase 3 not generated


def test_semantically_corrupt_cache_is_quarantined_and_repaired(dataset, sources, tmp_path):
    engine = FixtureEngine(tmp_path, dataset, sources)
    engine.analyze_reviews(dataset)
    cached = next(tmp_path.rglob('batch-0000.json'))
    cached.write_text(json.dumps({'items': []}), encoding='utf-8')
    engine.analyze_reviews(dataset)
    assert engine.calls['ClassificationBatch'] == 2
    assert list(tmp_path.rglob('batch-0000.invalid-*.json'))
    engine.analyze_reviews(dataset)
    assert engine.calls['ClassificationBatch'] == 2  # repaired result resumes without another call


@pytest.mark.parametrize('failure', ['missing_review', 'null_theme'])
def test_invalid_fresh_classification_is_retried_before_caching(dataset, sources, tmp_path, failure):
    class IncompleteOnce(FixtureEngine):
        def ask(self, schema, instruction, data):
            result = super().ask(schema, instruction, data)
            if schema is ClassificationBatch and self.calls['ClassificationBatch'] == 1:
                if failure == 'missing_review':
                    return ClassificationBatch(items=result.items[:-1])
                result.items[0].theme_id = None
            return result
    engine = IncompleteOnce(tmp_path, dataset, sources)
    result = engine.analyze_reviews(dataset)
    assert len(result.assignments) == 3
    assert all(a.substantive and a.theme_id is not None for a in result.assignments)
    assert engine.calls['ClassificationBatch'] == 2


def test_insufficient_distinct_fee_evidence_stops_phase2(dataset, sources, tmp_path):
    class InsufficientEvidence(FixtureEngine):
        def ask(self, schema, instruction, data):
            result = super().ask(schema, instruction, data)
            if schema is ClassificationBatch:
                result.items[-1].fee_issue = None
                result.items[-1].fee_confusion_quote = None
            return result
    engine = InsufficientEvidence(tmp_path, dataset, sources)
    with pytest.raises(AnalysisError, match='Fewer than three distinct'):
        engine.analyze_reviews(dataset)
    assert engine.calls['FeeChoice'] == 0


@pytest.mark.parametrize('tamper,match', [
    ('assignment', 'exactly one'), ('sentiment', 'Sentiment counts'), ('count', 'does not reconcile'),
    ('quote_text', 'exact original'), ('quote_source', 'source URL'), ('duplicate_fee', 'Repeated text'),
    ('fee_passage', 'confusion passage'), ('window', 'different reporting window'),
    ('unrelated_fee', 'naming the selected fee'), ('generic_fee', 'one named fee'),
])
def test_phase2_checkpoint_rejects_tampered_evidence_and_counts(dataset, sources, tmp_path, tamper, match):
    result = FixtureEngine(tmp_path, dataset, sources).analyze_reviews(dataset)
    if tamper == 'assignment':
        result.assignments.append(result.assignments[0])
    elif tamper == 'sentiment':
        result.sentiment_counts['positive'] = 1
    elif tamper == 'count':
        result.themes[0]['count'] += 1
    elif tamper == 'quote_text':
        result.quotes[0]['text'] = 'invented review'
    elif tamper == 'quote_source':
        result.quotes[0]['source_url'] = 'https://example.com/wrong'
    elif tamper == 'duplicate_fee':
        result.fee_evidence[-1] = result.fee_evidence[0]
    elif tamper == 'fee_passage':
        result.fee_evidence[0]['confusion_passage'] = 'invented passage'
    elif tamper == 'window':
        result.audit['window_start'] = '2026-08-01'
    elif tamper == 'unrelated_fee':
        result.fee_evidence[0]['selected_fee_passage'] = 'Hidden'
    elif tamper == 'generic_fee':
        result.fee_name = 'charges'
    with pytest.raises(ValueError, match=match):
        validate_intelligence(result, dataset)


def test_phase3_reuses_phase2_without_reclassification(dataset, sources, tmp_path):
    engine = FixtureEngine(tmp_path, dataset, sources)
    result = engine.analyze_reviews(dataset)
    original_calls = engine.calls.copy()
    bundle = engine.generate_outputs(dataset, result, sources)
    assert all(engine.calls[name] == count for name, count in original_calls.items())
    assert engine.calls['PulseDraft'] == engine.calls['ExplainerDraft'] == 1
    assert bundle.quotes == result.quotes and bundle.identified_fee_issue == result.identified_fee_issue


def test_multiple_batches_reconcile_every_original_review(dataset, sources, tmp_path):
    dataset.reviews += [Review('Test', str(i), dataset.reviews[0].date, 1, f'Support problem {i}',
                               f'https://example.com/{i}') for i in range(3, 85)]
    dataset.original_count = len(dataset.reviews)
    engine = FixtureEngine(tmp_path, dataset, sources)
    result = engine.analyze_reviews(dataset)
    assert engine.calls['ClassificationBatch'] == 3
    assert len(result.assignments) == sum(t['count'] for t in result.themes) == 85
    assert result.themes[0]['id'] == 'T2' and result.themes[0]['count'] == 83


def test_independent_verifier_checks_json_and_export_against_input(dataset, sources, tmp_path):
    import io
    from groww.data import load_csv
    from scripts.verify_phase2 import verify
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(['platform', 'review_id', 'date', 'rating', 'review_text', 'source_url'])
    writer.writerows([[r.platform, r.review_id, r.date, r.rating, r.review_text, r.source_url] for r in dataset.reviews])
    csv_path = tmp_path / 'input.csv'
    csv_path.write_bytes(stream.getvalue().encode('utf-8'))
    parsed = load_csv(csv_path.read_bytes(), dataset.report_date)
    result = FixtureEngine(tmp_path / 'cache', parsed, sources).analyze_reviews(parsed)
    save_intelligence(result, parsed, tmp_path / 'out')
    receipt = verify(csv_path, tmp_path / 'out/review_intelligence.json')
    assert receipt['status'] == 'PASS' and receipt['classification_export_matches']
    assert receipt['classified_reviews'] == 3
    export = tmp_path / 'out/review_classifications.csv'
    with export.open('a', encoding='utf-8') as stream:
        stream.write('an extra corrupt row\n')
    with pytest.raises(ValueError, match='CSV differs'):
        verify(csv_path, tmp_path / 'out/review_intelligence.json')
