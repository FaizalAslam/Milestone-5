from __future__ import annotations

import csv
import hashlib
import io
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from urllib.parse import urlparse

REQUIRED = {'platform', 'review_id', 'date', 'rating', 'review_text', 'source_url'}


class DataError(ValueError):
    pass


@dataclass(frozen=True)
class Review:
    platform: str
    review_id: str
    date: date
    rating: int
    review_text: str
    source_url: str
    title: str = ''

    @property
    def key(self) -> str:
        return f'{self.platform}:{self.review_id}'

    @property
    def text_key(self) -> str:
        # Case folding is for grouping only. Never change the original quote.
        return hashlib.sha256(' '.join(self.review_text.split()).casefold().encode()).hexdigest()


@dataclass
class Dataset:
    reviews: list[Review]
    original_count: int
    duplicate_count: int
    invalid_rows: list[dict]
    outside_count: int
    future_count: int
    report_date: date
    start_date: date
    digest: str

    def audit(self) -> dict:
        cutoff = max((r.date for r in self.reviews), default=None)
        periods = {}
        if cutoff:
            for name, end in [('latest', cutoff), ('preceding', cutoff - timedelta(days=7))]:
                start = end - timedelta(days=6)
                rows = [r for r in self.reviews if start <= r.date <= end]
                observed = {r.date for r in rows}
                periods[name] = {'start': str(start), 'end': str(end), 'reviews': len(rows),
                                 'missing_observed_dates': [str(start + timedelta(days=i)) for i in range(7)
                                                            if start + timedelta(days=i) not in observed]}
        return {
            'original_count': self.original_count,
            'included_count': len(self.reviews),
            'duplicate_count': self.duplicate_count,
            'invalid_count': len(self.invalid_rows),
            'outside_window_count': self.outside_count,
            'future_count': self.future_count,
            'window_start': self.start_date.isoformat(),
            'window_end': self.report_date.isoformat(),
            'data_cutoff': cutoff.isoformat() if cutoff else None,
            'days_between_cutoff_and_report': (self.report_date - cutoff).days if cutoff else None,
            'comparison_periods': periods,
            'platform_counts': dict(Counter(r.platform for r in self.reviews)),
            'rating_counts': dict(sorted(Counter(r.rating for r in self.reviews).items())),
            'unique_texts': len({r.text_key for r in self.reviews}),
            'dataset_sha256': self.digest,
        }


def load_csv(raw: bytes, report_date: date, weeks: int = 12) -> Dataset:
    if not 8 <= weeks <= 12:
        raise DataError('Choose a review window between 8 and 12 weeks.')
    if not raw or len(raw) > 15 * 1024 * 1024:
        raise DataError('Upload a nonempty CSV of at most 15 MB.')
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise DataError('Save the CSV using UTF-8 encoding and upload it again.') from exc
    reader = csv.DictReader(io.StringIO(text, newline=''), strict=True)
    try:
        headers = reader.fieldnames or []
        missing = REQUIRED - set(headers)
        if missing:
            raise DataError('Missing required columns: ' + ', '.join(sorted(missing)))
        if len(headers) != len(set(headers)):
            raise DataError('The CSV has duplicate column headings.')
        rows = list(reader)
    except csv.Error as exc:
        raise DataError(f'Malformed CSV: {exc}') from exc
    if not rows or len(rows) > 50000:
        raise DataError('The CSV must contain between 1 and 50,000 reviews.')
    start = report_date - timedelta(days=weeks * 7 - 1)
    valid, invalid, seen = [], [], set()
    duplicates = outside = future = 0
    for line, row in enumerate(rows, 2):
        try:
            if None in row or any(row.get(c) is None for c in headers):
                raise ValueError('Row has a different number of fields than the header.')
            if any(not row[c].strip() for c in REQUIRED):
                raise ValueError('A required value is blank.')
            d = date.fromisoformat(row['date'].strip())
            if d.isoformat() != row['date'].strip():
                raise ValueError('Date must use YYYY-MM-DD format.')
            rating = int(row['rating'].strip())
            if str(rating) != row['rating'].strip() or rating not in range(1, 6):
                raise ValueError('Rating must be a whole number from 1 to 5.')
            url = urlparse(row['source_url'].strip())
            if url.scheme != 'https' or not url.hostname:
                raise ValueError('source_url must be a public HTTPS URL.')
            review = Review(row['platform'].strip(), row['review_id'].strip(), d, rating,
                            row['review_text'], row['source_url'].strip(), row.get('title', ''))
            if review.key in seen:
                duplicates += 1
                continue
            seen.add(review.key)
            if d > report_date:
                future += 1
            elif d < start:
                outside += 1
            else:
                valid.append(review)
        except (ValueError, TypeError) as exc:
            invalid.append({'row': line, 'reason': str(exc)})
    return Dataset(valid, len(rows), duplicates, invalid, outside, future, report_date, start,
                   hashlib.sha256(raw).hexdigest())
