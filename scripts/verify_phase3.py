"""Verify saved Phase 3 outputs against their Phase 2 input and exported previews. No API/MCP calls."""
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
from groww.export import bundle_artifacts
from groww.models import Bundle, ReviewIntelligence
from groww.outputs import validate_bundle


def verify(csv_path: Path, intelligence_path: Path, analysis_path: Path) -> dict:
    intelligence = ReviewIntelligence.model_validate_json(intelligence_path.read_text(encoding='utf-8'))
    bundle = Bundle.model_validate_json(analysis_path.read_text(encoding='utf-8'))
    report_date = date.fromisoformat(intelligence.date)
    days = (report_date - date.fromisoformat(intelligence.audit['window_start'])).days + 1
    if days % 7:
        raise ValueError('The saved input window must cover a whole number of weeks.')
    dataset = load_csv(csv_path.read_bytes(), report_date, days // 7)
    checks = validate_bundle(bundle, dataset, intelligence)
    artifacts = bundle_artifacts(bundle)
    for name, expected in artifacts.items():
        actual = analysis_path if name == 'latest.json' else analysis_path.parent / name
        if actual.read_text(encoding='utf-8') != expected:
            raise ValueError(f'{name} differs from the verified Phase 3 snapshot.')
    return {'status': 'PASS', 'run_id': bundle.run_id, 'phase2_run_id': intelligence.run_id,
            'phase2_fingerprint': bundle.intelligence_fingerprint,
            'input_sha256': dataset.digest, 'analysis_sha256': hashlib.sha256(analysis_path.read_bytes()).hexdigest(),
            'included_reviews': len(dataset.reviews), 'weekly_pulse_words': len(bundle.weekly_pulse.split()),
            'product_actions': 3, 'verified_quotes': len(bundle.quotes),
            'fee_bullets': len(bundle.explanation_bullets), 'official_source_links': bundle.source_links,
            'last_checked': bundle.last_checked, 'fee_fact_check': bundle.fee_fact_check,
            'checks': checks, 'matching_exports': list(artifacts), 'remote_actions_executed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv', type=Path, default=ROOT / 'groww_reviews_all_platforms_updated.csv')
    parser.add_argument('--intelligence', type=Path, default=ROOT / 'outputs/review_intelligence.json')
    parser.add_argument('--analysis', type=Path, default=ROOT / 'outputs/latest.json')
    parser.add_argument('--save', type=Path, help='Optional verification receipt path.')
    args = parser.parse_args()
    try:
        receipt = verify(args.csv, args.intelligence, args.analysis)
    except (ValueError, KeyError, OSError) as exc:
        parser.exit(1, f'FAIL: {exc}\n')
    if args.save:
        args.save.parent.mkdir(parents=True, exist_ok=True)
        args.save.write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps(receipt, indent=2))
