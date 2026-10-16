"""Extract traceable reference evidence; never label it as a completed AI run."""
import csv
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from groww.data import load_csv

raw = (ROOT / 'groww_reviews_all_platforms_updated.csv').read_bytes()
dataset = load_csv(raw, date(2026, 10, 16))
ids = ['0196e447-a8c8-4a43-9f8b-7a8868864177', 'e651315f-a8aa-4540-9b8d-dc2468d1fc51',
       '3c7714ea-d6e5-482c-9f18-fc2e573f133b']
by_id = {r.review_id: r for r in dataset.reviews}
quotes = [dict(review_key=by_id[i].key, date=str(by_id[i].date), text=by_id[i].review_text,
               source_url=by_id[i].source_url) for i in ids]
data_dir = ROOT / 'data'
data_dir.mkdir(exist_ok=True)
(data_dir / 'reference_evidence.json').write_text(json.dumps({
    'mode': 'reference_preview', 'dataset_sha256': dataset.digest,
    'identified_fee_issue': 'Understanding brokerage separately from total trade charges and taxes',
    'note': 'Manually selected public-review evidence. Full AI theme ranking and counts remain pending a live model run.',
    'quotes': quotes}, ensure_ascii=False, indent=2), encoding='utf-8')
with (ROOT / 'groww_reviews_all_platforms_updated.csv').open(encoding='utf-8-sig', newline='') as f:
    reader = csv.DictReader(f)
    fields = reader.fieldnames
    rows = list(reader)
# Include fee evidence plus platform/rating examples, retaining every original field.
selected = [r for r in rows if r['review_id'] in ids]
seen = {r['review_id'] for r in selected}
for platform in ('Google Play', 'App Store'):
    for rating in ('1', '2', '3', '4', '5'):
        candidates = [r for r in rows if r['platform'] == platform and r['rating'] == rating and r['review_id'] not in seen]
        for r in candidates[:5]:
            selected.append(r)
            seen.add(r['review_id'])
with (data_dir / 'reviews_sample.csv').open('w', encoding='utf-8-sig', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(selected)
print(f'Prepared {len(quotes)} traceable fee examples and {len(selected)} original sample records; no AI theme claims.')
