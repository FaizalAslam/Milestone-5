"""Build a credential-free GitHub repository bundle for Streamlit Community Cloud."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from groww.deployment import build_repository_bundle


if __name__ == '__main__':
    archive = ROOT / 'outputs/groww-streamlit-deployment.zip'
    manifest = build_repository_bundle(ROOT, archive)
    (ROOT / 'outputs/deployment_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(f'Repository bundle ready: {archive.name}; {len(manifest["files"])} public source/data files; no live secrets or private outputs.')
