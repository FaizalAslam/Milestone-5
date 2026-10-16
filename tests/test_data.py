import csv
import io
from datetime import date
from pathlib import Path
import pytest
from groww.data import DataError, load_csv


def raw_rows(rows, headers=None):
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(headers or ['platform', 'review_id', 'date', 'rating', 'review_text', 'source_url'])
    writer.writerows(rows)
    return output.getvalue().encode('utf-8-sig')


def row(rid='a', d='2026-10-14', rating='5', text='good'):
    return ['Test', rid, d, rating, text, 'https://example.com/review']


def test_real_dataset_audit_and_preservation():
    path = Path('groww_reviews_all_platforms_updated.csv')
    original = path.read_bytes()
    data = load_csv(original, date(2026, 10, 16))
    assert data.original_count == 13268
    assert len(data.reviews) == 13034
    assert data.outside_count == 234
    assert not data.invalid_rows and not data.duplicate_count and not data.future_count
    assert data.audit()['platform_counts'] == {'Google Play': 12534, 'App Store': 500}
    assert data.audit()['unique_texts'] == 6130
    assert path.read_bytes() == original


def test_boundaries_future_invalid_duplicate_and_short_complaints():
    rows = [row('start', '2026-07-25'), row('old', '2026-07-24'), row('end', '2026-10-16'),
            row('future', '2026-10-17'), row('invalid', 'bad'), row('bad-rating', rating='6'),
            row('start'), row('different-id', text='good'), row('fee', text='hidden charges')]
    data = load_csv(raw_rows(rows), date(2026, 10, 16))
    assert len(data.reviews) == 4
    assert (data.outside_count, data.future_count, data.duplicate_count, len(data.invalid_rows)) == (1, 1, 1, 2)
    assert any(r.review_text == 'hidden charges' for r in data.reviews)
    assert data.original_count == len(data.reviews) + data.outside_count + data.future_count + data.duplicate_count + len(data.invalid_rows)


@pytest.mark.parametrize('rating', ['0', '5.0', '-1', 'six', ''])
def test_invalid_ratings(rating):
    data = load_csv(raw_rows([row(rating=rating)]), date(2026, 10, 16))
    assert len(data.invalid_rows) == 1


def test_missing_and_duplicate_headers():
    with pytest.raises(DataError, match='Missing required columns'):
        load_csv(b'text\nhello\n', date(2026, 10, 16))
    headers = ['platform', 'review_id', 'date', 'rating', 'review_text', 'source_url', 'source_url']
    with pytest.raises(DataError, match='duplicate column'):
        load_csv(raw_rows([row() + ['x']], headers), date(2026, 10, 16))


def test_wrong_encoding_malformed_csv_and_size():
    for data in (b'\xff\xfe', b''):
        with pytest.raises(DataError):
            load_csv(data, date(2026, 10, 16))
    raw = raw_rows([row()]).decode('utf-8-sig').splitlines()[0] + '\n"unterminated'
    with pytest.raises(DataError, match='Malformed CSV'):
        load_csv(raw.encode(), date(2026, 10, 16))
    with pytest.raises(DataError, match='8 and 12'):
        load_csv(raw_rows([row()]), date(2026, 10, 16), 7)


def test_different_ids_with_identical_text_keep_weight():
    data = load_csv(raw_rows([row('a'), row('b')]), date(2026, 10, 16))
    assert len(data.reviews) == 2 and data.audit()['unique_texts'] == 1
