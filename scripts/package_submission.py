"""Package deployable source and public evidence, explicitly excluding live secrets."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).resolve().parents[1]
files = [root / p for p in ['app.py', 'README.md', 'SOURCES.md', 'requirements.txt', 'requirements-lock.txt',
    'start.ps1', '.gitignore', '.gitattributes', '.streamlit/config.toml', '.streamlit/secrets.toml.example',
    'requirements-demo.txt', 'submission_links.example.json',
    '.github/workflows/tests.yml', 'groww_reviews_all_platforms_updated.csv', 'outputs/dataset_audit.json',
    'outputs/verification.md', 'outputs/phase2_verification.md', 'outputs/phase2_checkpoint.json',
    'outputs/review_intelligence.md', 'outputs/review_intelligence.json', 'outputs/review_classifications.csv',
    'outputs/latest.json', 'outputs/weekly_product_pulse.md', 'outputs/fee_explainer.md',
    'outputs/document_entry.json', 'outputs/document_entry_preview.txt', 'outputs/email_draft_preview.txt',
    'outputs/fee_claim_evidence.md', 'outputs/official_fee_sources.json',
    'outputs/phase3_checkpoint.json', 'outputs/phase3_verification.md',
    'outputs/phase4_checkpoint.json', 'outputs/phase4_verification.md',
    'outputs/phase5_checkpoint.json', 'outputs/phase5_verification.md', 'outputs/deployment_manifest.json',
    'outputs/phase6_checkpoint.json', 'outputs/phase6_verification.md',
    'outputs/demo/groww_workflow_demo.mp4', 'outputs/demo/metadata.json', 'outputs/demo/STORYBOARD.md', 'outputs/demo/poster.jpg']]
for directory in ['groww', 'scripts', 'tests', 'data', 'docs', 'n8n']:
    files += [p for p in (root / directory).rglob('*') if p.is_file() and not p.is_symlink()
              and not any(part in {'__pycache__', '.cache', '.git', 'private', 'node_modules'} for part in p.relative_to(root).parts)
              and p.suffix not in {'.pyc', '.log', '.sqlite3', '.db'} and p.name not in {'secrets.toml', '.env'}]
files += list((root / 'outputs').glob('preview_*.jpg'))
files += list((root / 'outputs/demo/frames').glob('*.jpg'))
archive = root / 'outputs' / 'groww-review-intelligence.zip'
with ZipFile(archive, 'w', ZIP_DEFLATED) as z:
    for p in sorted(set(files)):
        if p.exists():
            if p.name in ('secrets.toml', '.env'):
                raise ValueError('Refusing to package live secrets.')
            z.write(p, p.relative_to(root).as_posix())
with ZipFile(archive) as z:
    assert not any('.venv' in n or '__pycache__' in n or n.endswith('/secrets.toml') or n == '.env' for n in z.namelist())
    print(f'Packaged {len(z.namelist())} files; live secrets and environments excluded. Archive: {archive.name}')
