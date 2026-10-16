"""Freeze the verified public Phase 2/3 outputs for the hosted saved demo. No API calls."""
import hashlib
import json
from datetime import date
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from groww.data import load_csv
from groww.models import Bundle, ReviewIntelligence
from groww.outputs import validate_bundle


def main():
    raw = (ROOT / 'groww_reviews_all_platforms_updated.csv').read_bytes()
    bundle = Bundle.model_validate_json((ROOT / 'outputs/latest.json').read_text(encoding='utf-8'))
    intelligence = ReviewIntelligence.model_validate_json((ROOT / 'outputs/review_intelligence.json').read_text(encoding='utf-8'))
    dataset = load_csv(raw, date.fromisoformat(bundle.date), 12)
    validate_bundle(bundle, dataset, intelligence)
    dest = ROOT / 'data/demo'
    dest.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for name in ['review_intelligence.json', 'latest.json']:
        data = (ROOT / 'outputs' / name).read_bytes()
        (dest / name).write_bytes(data)
        hashes[name] = hashlib.sha256(data).hexdigest()
    manifest = dict(product='Groww', report_date=bundle.date, weeks=12, dataset_sha256=dataset.digest,
                    included_reviews=len(dataset.reviews), data_cutoff=bundle.audit['data_cutoff'],
                    intelligence_run_id=intelligence.run_id, output_run_id=bundle.run_id,
                    source_last_checked=bundle.last_checked, files=hashes)
    (dest / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(f'Frozen original public demo: {len(dataset.reviews):,} reviews; report {bundle.date}; no live model or MCP calls.')


if __name__ == '__main__':
    main()
