from datetime import date
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from groww.data import Dataset, Review
from groww.models import Bundle, PulseDraft, Source
from groww.outputs import render_pulse


@pytest.fixture
def dataset():
    texts = ['Hidden brokerage charges make the total unclear.',
             'Support never explains why taxes and brokerage differ.',
             'The order screen froze and I cannot understand its brokerage fees.']
    rows = [Review('Test', str(i), date(2026, 10, 14), 1, t, 'https://example.com/review/' + str(i)) for i, t in enumerate(texts)]
    return Dataset(rows, 3, 0, [], 0, 0, date(2026, 10, 16), date(2026, 7, 25), 'a' * 64)


@pytest.fixture
def sources():
    return [Source(id='pricing', title='Test fixture pricing', url='https://groww.in/pricing',
                   checked_at='2026-10-16', text='Brokerage is a separate fee.'),
            Source(id='brokerage', title='Test fixture help', url='https://groww.in/help/test',
                   checked_at='2026-10-16', text='Other charges may apply.')]


@pytest.fixture
def bundle(dataset, sources):
    themes = [dict(id=f'T{i+1}', name=n, description=n, count=1, current_week=1, previous_week=0)
              for i, n in enumerate(['Fees', 'Support', 'Order reliability'])]
    quotes = [dict(review_key=r.key, text=r.review_text, date=str(r.date), source_url=r.source_url,
                   theme_id=f'T{i+1}') for i, r in enumerate(dataset.reviews)]
    pulse = render_pulse('2026-10-16', themes, quotes, PulseDraft(summary='Test fixture: feedback concerns fees, support, and orders.',
        observation='Customers report unclear totals.', actions=['Explain the fee breakdown.', 'Improve support guidance.', 'Fix the order screen.']))
    return Bundle(run_id='b' * 32, date='2026-10-16', dataset_sha256=dataset.digest, mode='openai_live', model='test-fixture',
                  audit=dataset.audit(), themes=themes, sentiment_counts={'negative': 3}, non_substantive_count=0,
                  quotes=quotes, fee_evidence=quotes, identified_fee_issue='Brokerage versus total trade cost',
                  weekly_pulse=pulse, explanation_bullets=['Brokerage is a separate fee.', 'Other charges may apply.'],
                  fee_grounding=[dict(text=s.text, source_ids=[s.id], supporting_passages=[s.text]) for s in sources],
                  fee_fact_check=dict(supported=True, concerns=[]),
                  source_links=[s.url for s in sources], sources=sources, last_checked='2026-10-16')
