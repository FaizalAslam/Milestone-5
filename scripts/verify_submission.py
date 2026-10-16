"""Independently verify the generated Phase 6 ZIP without calling external services."""
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import sys
import tomllib
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from groww.submission import audit_materials, validate_links


def verify(root: Path):
    archive = root / 'outputs/groww-milestone-submission.zip'
    _, _, bundle, artifacts, checks = audit_materials(root)
    secret_file = root / '.streamlit/secrets.toml'
    config = tomllib.loads(secret_file.read_text(encoding='utf-8')) if secret_file.exists() else {}
    secret_values = [str(config[k]).encode() for k in ['OPENAI_API_KEY', 'DEMO_ACCESS_PASSWORD', 'N8N_MCP_TOKEN'] if config.get(k)]

    def scan(data):
        with ZipFile(io.BytesIO(data)) as zipped:
            for name in zipped.namelist():
                parts = PurePosixPath(name.replace('\\', '/')).parts
                if name.startswith(('/', '\\')) or '..' in parts or any(p in {'.cache', '.git', 'private', '.env', 'secrets.toml'} or p.startswith('.venv') for p in parts):
                    raise ValueError('A private or unsafe file is present in the packet.')
                content = zipped.read(name)
                if any(value in content for value in secret_values):
                    raise ValueError('A configured credential occurs in the packet. Do not share it.')
                if name.endswith('.zip'):
                    scan(content)
    scan(archive.read_bytes())
    with ZipFile(archive) as zipped:
        manifest = json.loads(zipped.read('manifest.json'))
        if set(zipped.namelist()) != set(manifest['files']) | {'manifest.json'}:
            raise ValueError('The archive contains files missing from its manifest.')
        for name, digest in manifest['files'].items():
            data = zipped.read(name)
            if hashlib.sha256(data).hexdigest() != digest or data != (root / 'submission' / name).read_bytes():
                raise ValueError(f'{name} does not match its manifest or unpacked preview.')
        for name, value in artifacts.items():
            if zipped.read('deliverables/' + name).decode('utf-8') != value:
                raise ValueError(f'Packaged {name} differs from the verified analysis.')
        if zipped.read('data/reviews_sample.csv') != (root / 'data/reviews_sample.csv').read_bytes():
            raise ValueError('The packaged review sample changed.')
        links = json.loads(zipped.read('links.json'))
        validate_links(links)
        if manifest['remote_writes_claimed'] is not False or manifest['checks'] != checks:
            raise ValueError('Packaged counts or live-evidence status are incorrect.')
        for row in manifest['deliverables']:
            if row['file'] not in zipped.namelist():
                raise ValueError('A deliverable points to a missing file.')
        if 'demo/groww_workflow_demo.mp4' in zipped.namelist():
            meta = json.loads(zipped.read('demo/metadata.json'))
            if (not 0 < meta['duration_seconds'] <= 180
                    or meta['sha256'] != hashlib.sha256(zipped.read('demo/groww_workflow_demo.mp4')).hexdigest()
                    or meta.get('full_decode_passed') is not True
                    or meta.get('poster_sha256') != hashlib.sha256(zipped.read('demo/poster.jpg')).hexdigest()):
                raise ValueError('The demo does not match its verified duration/decode receipt.')
    return {'status': 'PASS', 'files_verified': len(manifest['files']) + 1, **checks,
            'demo_duration_seconds': manifest['demo_duration_seconds'], 'credentials_found': False,
            'remote_writes_claimed': False, 'final_submission_status': manifest['final_submission_status']}


if __name__ == '__main__':
    print(json.dumps(verify(ROOT), indent=2))
