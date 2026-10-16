"""Load an immutable, verified public demo independently of live output files."""
import hashlib
import json
from pathlib import Path

from .intelligence import validate_intelligence
from .models import Bundle, ReviewIntelligence
from .outputs import validate_bundle


def demo_manifest(root: Path) -> dict:
    return json.loads((root / 'data/demo/manifest.json').read_text(encoding='utf-8'))


def load_demo(root: Path, dataset):
    manifest = demo_manifest(root)
    if dataset.digest != manifest['dataset_sha256']:
        raise ValueError('The saved demo requires its original public CSV.')
    for name, digest in manifest['files'].items():
        if hashlib.sha256((root / 'data/demo' / name).read_bytes()).hexdigest() != digest:
            raise ValueError('The saved demo files changed. Restore the verified snapshot.')
    result = ReviewIntelligence.model_validate_json((root / 'data/demo/review_intelligence.json').read_text(encoding='utf-8'))
    bundle = Bundle.model_validate_json((root / 'data/demo/latest.json').read_text(encoding='utf-8'))
    validate_intelligence(result, dataset)
    validate_bundle(bundle, dataset, result)
    return result, bundle
