"""Recheck saved AI insights against the original CSV without API or MCP calls."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from groww.data import load_csv
from groww.export import classifications_csv
from groww.intelligence import validate_intelligence
from groww.models import ReviewIntelligence


def verify(csv_path: Path, analysis_path: Path) -> dict:
    result = ReviewIntelligence.model_validate_json(analysis_path.read_text(encoding='utf-8'))
    report_date = date.fromisoformat(result.date)
    days = (report_date - date.fromisoformat(result.audit['window_start'])).days + 1
    if days % 7:
        raise ValueError('The saved review window must cover a whole number of weeks.')
    dataset = load_csv(csv_path.read_bytes(), report_date, days // 7)
    checks = validate_intelligence(result, dataset)
    # Check the exported rows too when the export is present alongside the JSON.
    export = analysis_path.parent / 'review_classifications.csv'
    if export.exists():
        with export.open(encoding='utf-8-sig', newline='') as stream:
            if stream.read() != classifications_csv(result, dataset):
                raise ValueError('The saved classifications CSV differs from the verified JSON and original input.')
    return {'status': 'PASS', 'run_id': result.run_id, 'model': result.model,
            'input_sha256': dataset.digest, 'analysis_sha256': hashlib.sha256(analysis_path.read_bytes()).hexdigest(),
            'included_reviews': len(dataset.reviews), 'classified_reviews': len(result.assignments),
            'unique_texts': dataset.audit()['unique_texts'], 'theme_count': len(result.themes),
            'substantive_reviews': sum(t['count'] for t in result.themes),
            'nonspecific_reviews': result.non_substantive_count, 'quotes': len(result.quotes),
            'distinct_fee_evidence_texts': len(result.fee_evidence), 'checks': checks,
            'classification_export_matches': export.exists()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv', type=Path, default=ROOT / 'groww_reviews_all_platforms_updated.csv')
    parser.add_argument('--analysis', type=Path, default=ROOT / 'outputs/review_intelligence.json')
    parser.add_argument('--save', type=Path, help='Optional path for the verification receipt.')
    args = parser.parse_args()
    try:
        receipt = verify(args.csv, args.analysis)
    except (ValueError, KeyError, OSError) as exc:
        parser.exit(1, f'FAIL: {exc}\n')
    if args.save:
        args.save.parent.mkdir(parents=True, exist_ok=True)
        args.save.write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps(receipt, indent=2))
