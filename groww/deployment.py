"""Select public repository files with explicit boundaries; credentials and live runs stay local."""
from pathlib import Path
import hashlib
import json
from zipfile import ZIP_DEFLATED, ZipFile


ROOT_FILES = ['app.py', 'README.md', 'SOURCES.md', 'requirements.txt', 'requirements-lock.txt',
              'start.ps1', '.gitignore', '.gitattributes', '.streamlit/config.toml', 'requirements-demo.txt',
              'submission_links.example.json',
              '.streamlit/secrets.toml.example', '.github/workflows/tests.yml', 'groww_reviews_all_platforms_updated.csv']
SOURCE_DIRS = ['groww', 'scripts', 'tests', 'data', 'docs', 'n8n']
FORBIDDEN = {'.git', '.cache', '__pycache__', '.pytest_cache', 'private', 'node_modules'}


def repository_files(root: Path):
    files = [root / name for name in ROOT_FILES]
    for name in SOURCE_DIRS:
        files.extend(p for p in (root / name).rglob('*') if p.is_file()
                     and not any(part in FORBIDDEN for part in p.relative_to(root).parts)
                     and p.suffix not in {'.pyc', '.log', '.sqlite3', '.db'}
                     and p.name not in {'.env', 'secrets.toml'} and not p.is_symlink())
    missing = [p.relative_to(root).as_posix() for p in files if not p.is_file()]
    if missing:
        raise ValueError('Required deployment files missing: ' + ', '.join(missing))
    if not (root / 'data/demo/manifest.json').is_file():
        raise ValueError('Prepare the verified saved demo before deployment.')
    return sorted(set(files))


def build_repository_bundle(root: Path, archive: Path) -> dict:
    files = repository_files(root)
    manifest = {'entrypoint': 'app.py', 'python': '3.12', 'secret_files_included': False,
                'live_runs_included': False, 'files': {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    archive.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(archive, 'w', ZIP_DEFLATED) as bundle:
        for path in files:
            bundle.write(path, path.relative_to(root).as_posix())
        bundle.writestr('DEPLOYMENT_MANIFEST.json', json.dumps(manifest, indent=2) + '\n')
    return manifest
