from pathlib import Path
import csv
import io
import json
from .data import Dataset
from .intelligence import intelligence_markdown, validate_intelligence
from .models import Bundle, ReviewIntelligence
from .outputs import document_text, email_content, explainer_markdown, validate_bundle


def classifications_csv(result: ReviewIntelligence, dataset: Dataset) -> str:
    validate_intelligence(result, dataset)
    assignments = {a.review_key: a for a in result.assignments}
    stream = io.StringIO(newline='')
    fields = ['platform', 'review_id', 'date', 'rating', 'review_text', 'source_url',
              'review_key', 'text_key', 'sentiment', 'substantive', 'theme_id', 'fee_issue']
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for r in dataset.reviews:
        writer.writerow(dict(platform=r.platform, review_id=r.review_id, date=str(r.date), rating=r.rating,
                              review_text=r.review_text, source_url=r.source_url, **assignments[r.key].model_dump()))
    return stream.getvalue()


def save_intelligence(result: ReviewIntelligence, dataset: Dataset, directory: Path):
    result.checks = validate_intelligence(result, dataset)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'review_intelligence.json').write_text(result.model_dump_json(indent=2), encoding='utf-8')
    (directory / 'review_intelligence.md').write_text(intelligence_markdown(result), encoding='utf-8')
    (directory / 'review_classifications.csv').write_text(classifications_csv(result, dataset), encoding='utf-8-sig', newline='')


def bundle_artifacts(bundle: Bundle) -> dict[str, str]:
    """All Phase 3 previews are rendered from the same validated snapshot."""
    validate_bundle(bundle)
    email = email_content(bundle)
    evidence = ['# Fee claim evidence', '', f'Last checked: {bundle.last_checked}', '',
                'Automated source review: passed. Review these passages before approving internal sharing.', '']
    source_map = {s.id: s for s in bundle.sources}
    for index, claim in enumerate(bundle.fee_grounding, 1):
        evidence += [f'## Bullet {index}', '', claim['text'], '',
                     'Sources: ' + ', '.join(f'[{source_map[sid].title}]({source_map[sid].url})' for sid in claim['source_ids']), '']
        for passage in claim['supporting_passages']:
            evidence += ['> ' + passage, '']
    return {
        'weekly_product_pulse.md': bundle.weekly_pulse,
        'fee_explainer.md': explainer_markdown(bundle),
        'document_entry_preview.txt': document_text(bundle),
        'document_entry.json': json.dumps(bundle.entry(), ensure_ascii=False, indent=2),
        'email_draft_preview.txt': 'Subject: ' + email['subject'] + '\n\n' + email['body'],
        'fee_claim_evidence.md': '\n'.join(evidence),
        'official_fee_sources.json': json.dumps([s.model_dump() for s in bundle.sources], ensure_ascii=False, indent=2),
        'latest.json': bundle.model_dump_json(indent=2),
    }


def save_bundle(bundle: Bundle, directory: Path):
    artifacts = bundle_artifacts(bundle)
    directory.mkdir(parents=True, exist_ok=True)
    # Write the loadable snapshot last, after all its previews have been saved.
    for name, content in artifacts.items():
        (directory / name).write_text(content, encoding='utf-8')
