from __future__ import annotations

import argparse
import json
import os
import sys
import tomllib
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from groww.data import load_csv
from groww.export import save_bundle, save_intelligence
from groww.models import ReviewIntelligence
from groww.intelligence import validate_intelligence

parser = argparse.ArgumentParser(description='Audit Groww reviews or run the live AI pipeline. Never calls MCP write tools.')
parser.add_argument('--csv', type=Path, default=ROOT / 'groww_reviews_all_platforms_updated.csv')
parser.add_argument('--report-date', type=date.fromisoformat, default=datetime.now(ZoneInfo('Asia/Kolkata')).date())
parser.add_argument('--weeks', type=int, default=12)
parser.add_argument('--live', action='store_true', help='Call OpenAI; uses your API quota.')
phase_args = parser.add_mutually_exclusive_group()
phase_args.add_argument('--phase2', action='store_true', help='Stop after review intelligence; no fee-source fetch or prose generation. Requires --live.')
phase_args.add_argument('--phase3', action='store_true', help='Generate outputs from saved Phase 2; never reclassify reviews. Requires --live.')
parser.add_argument('--intelligence', type=Path, default=ROOT / 'outputs/review_intelligence.json', help='Validated saved Phase 2 input for --phase3.')
parser.add_argument('--workers', type=int, choices=range(1, 9), help='Override concurrent classification requests (default: configured value or 4).')
parser.add_argument('--output-dir', type=Path, default=ROOT / 'outputs', help='Separate sample and full-data results when needed.')
args = parser.parse_args()
if (args.phase2 or args.phase3) and not args.live:
    parser.error('--phase2 and --phase3 require --live. Omit both for a dataset-only audit.')
raw = args.csv.read_bytes()
dataset = load_csv(raw, args.report_date, args.weeks)
out = args.output_dir
out.mkdir(parents=True, exist_ok=True)
(out / 'dataset_audit.json').write_text(json.dumps(dataset.audit(), indent=2), encoding='utf-8')
print(json.dumps(dataset.audit(), indent=2))
if args.live:
    from dotenv import load_dotenv
    from groww.analysis import Engine
    from groww.sources import fetch_sources
    from openai import OpenAIError
    load_dotenv(ROOT / '.env')
    secrets_path = ROOT / '.streamlit' / 'secrets.toml'
    secrets = tomllib.loads(secrets_path.read_text(encoding='utf-8')) if secrets_path.exists() else {}
    key = secrets.get('OPENAI_API_KEY') or os.getenv('OPENAI_API_KEY', '')
    if not key:
        parser.exit(2, 'Configure OPENAI_API_KEY locally before using --live. Never paste it into chat.\n')
    try:
        engine = Engine(key, secrets.get('OPENAI_MODEL') or os.getenv('OPENAI_MODEL', 'gpt-5-mini'), ROOT / '.cache',
                        args.workers or int(secrets.get('OPENAI_MAX_WORKERS') or os.getenv('OPENAI_MAX_WORKERS', '4')))
        progress = lambda progress, label: print(f'{progress:.0%} {label}', flush=True)
        if args.phase3:
            intelligence = ReviewIntelligence.model_validate_json(args.intelligence.read_text(encoding='utf-8'))
            validate_intelligence(intelligence, dataset)
            print('Verified saved Phase 2 input. Classification is unchanged.', flush=True)
        else:
            intelligence = engine.analyze_reviews(dataset, progress)
            save_intelligence(intelligence, dataset, out)
            print('Phase 2 generated, validated, and saved. No MCP write actions were called.')
        if args.phase2:
            parser.exit(0)
        bundle = engine.generate_outputs(dataset, intelligence, fetch_sources(), progress)
        save_bundle(bundle, out)
        print('Outputs generated and validated. No MCP write actions were called.')
    except OpenAIError as exc:
        # API error bodies can include credential fragments; never print them.
        parser.exit(2, f'Live analysis stopped ({type(exc).__name__}). Check API key, model access, quota/rate limits, and connectivity. '
                    'Valid completed batches remain cached. No MCP actions were called.\n')
    except ValueError as exc:
        parser.exit(1, f'Validation stopped the run: {exc}. Valid completed batches remain cached. No MCP actions were called.\n')
