"""Keep authenticated live results separate from the public saved demo."""
from pathlib import Path
import re

from . import export
from .models import Bundle, ReviewIntelligence
from .outputs import validate_bundle


class LiveRunStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    def save_intelligence(self, result, dataset):
        export.save_intelligence(result, dataset, self.root / result.run_id)

    def save_bundle(self, bundle, intelligence):
        directory = self.root / bundle.run_id
        export.save_bundle(bundle, directory)
        if intelligence:
            directory.mkdir(parents=True, exist_ok=True)
            (directory / 'review_intelligence.json').write_text(intelligence.model_dump_json(indent=2), encoding='utf-8')

    def available(self, dataset):
        if not self.root.exists():
            return []
        matches = []
        for path in sorted(self.root.glob('*/latest.json'), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                bundle = Bundle.model_validate_json(path.read_text(encoding='utf-8'))
                if (bundle.dataset_sha256 == dataset.digest and bundle.date == str(dataset.report_date)
                        and bundle.audit.get('window_start') == str(dataset.start_date)):
                    matches.append(bundle.run_id)
            except (ValueError, OSError):
                continue
        return matches[:10]

    def load(self, run_id, dataset):
        if not re.fullmatch('[a-f0-9]{32}', run_id):
            raise ValueError('Invalid saved run ID.')
        directory = self.root / run_id
        result = ReviewIntelligence.model_validate_json((directory / 'review_intelligence.json').read_text(encoding='utf-8'))
        bundle = Bundle.model_validate_json((directory / 'latest.json').read_text(encoding='utf-8'))
        validate_bundle(bundle, dataset, result)
        return result, bundle
