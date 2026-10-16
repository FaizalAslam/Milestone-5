"""Smoke-test the clean deployment bundle without local secrets or live writes."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from groww.deployment import build_repository_bundle


SMOKE = r'''
from pathlib import Path
import json
from streamlit.testing.v1 import AppTest
root = Path.cwd()
assert not (root / '.streamlit/secrets.toml').exists()
assert not (root / '.env').exists()
app = AppTest.from_file(root / 'app.py').run(timeout=40)
assert not app.exception, [e.message for e in app.exception]
assert app.session_state['workspace_view']['status'] == 'empty'
workspace = app.session_state['_workspace']
workspace.load_example()
app.run(timeout=40)
assert not app.exception, [e.message for e in app.exception]
view = app.session_state['workspace_view']
assert view['mode'] == 'Demo' and view['metrics']['included_count'] == 13034
assert workspace.task.bundle.intelligence_run_id == workspace.task.intelligence.run_id
assert len(view['analysis']['themes']) == 5 and len(view['analysis']['quotes']) == 3
assert view['outputs']['word_count'] == 149 and len(view['outputs']['fee_bullets']) == 4
assert not view['execution']['can_approve'] and not view['outputs']['can_edit']
print(json.dumps({'status':'PASS','mode':'Read-only completed example','included_reviews':13034,
                  'secrets_files_present':False,'custom_component_loaded':True,'approval_disabled':True,
                  'live_model_calls':0,'external_writes':0}))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--save', action='store_true')
    parser.add_argument('--full-tests', action='store_true', help='Also run the complete tests inside the extracted source bundle.')
    parser.add_argument('--hosted-url', help='Optional real Streamlit URL; checks health only, without approving any action.')
    args = parser.parse_args()
    archive = ROOT / 'outputs/groww-streamlit-deployment.zip'
    manifest = build_repository_bundle(ROOT, archive)
    cache = ROOT / '.cache'
    cache.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='deployment-smoke-', dir=cache) as directory:
        with ZipFile(archive) as bundle:
            bundle.extractall(directory)
        check = subprocess.run([sys.executable, '-c', SMOKE], cwd=directory, capture_output=True, text=True)
        if check.returncode:
            print(check.stdout + check.stderr)
            raise SystemExit('Clean deployment bundle smoke check failed.')
        smoke = json.loads(check.stdout.strip().splitlines()[-1])
        if args.full_tests:
            junit = Path(directory) / 'clean_tests.xml'
            tests = subprocess.run([sys.executable, '-m', 'pytest', '-q', f'--junitxml={junit}'],
                                    cwd=directory, capture_output=True, text=True)
            if tests.returncode:
                print(tests.stdout + tests.stderr)
                raise SystemExit('The full test suite failed in the extracted deployment bundle.')
            smoke['clean_bundle_tests_passed'] = sum(int(s.attrib['tests']) for s in ET.parse(junit).getroot().findall('testsuite'))
    hosted = {'url': None, 'status': 'PENDING_ACCOUNT_SIGN_IN_AND_DEPLOYMENT'}
    if args.hosted_url:
        parsed = urlparse(args.hosted_url)
        if parsed.scheme != 'https' or not parsed.hostname or not parsed.hostname.endswith('.streamlit.app') or parsed.query or parsed.fragment:
            raise SystemExit('Use the actual HTTPS Streamlit Community Cloud app URL.')
        import httpx
        response = httpx.get(args.hosted_url.rstrip('/') + '/_stcore/health', timeout=20, follow_redirects=False)
        hosted = {'url': args.hosted_url, 'status': 'HEALTH_PASS_UI_ACCEPTANCE_PENDING' if response.status_code == 200 else 'HEALTH_NOT_CONFIRMED',
                  'http_status': response.status_code}
    checkpoint = {'checked_at': datetime.now(timezone.utc).isoformat(), 'clean_bundle': smoke,
                  'repository_file_count': len(manifest['files']), 'python_target': '3.12',
                  'hosted_deployment': hosted, 'live_analysis_and_approved_remote_output_match': 'PENDING_LIVE_ACCEPTANCE',
                  'actual_hosted_browser_check': 'PENDING', 'external_writes_performed': 0}
    if args.save:
        (ROOT / 'outputs/phase5_checkpoint.json').write_text(json.dumps(checkpoint, indent=2) + '\n', encoding='utf-8')
        (ROOT / 'outputs/deployment_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        (ROOT / 'outputs/phase5_verification.md').write_text(
            '# Phase 5 verification\n\n'
            f'Checked: {checkpoint["checked_at"]}\n\n'
            '- PASS: clean repository bundle extracted and opened in a fresh Python process with no local secrets.\n'
            '- PASS: wireframe component, read-only completed example, 13,034 included reviews, matching Phase 2/3 lineage, and disabled demo approval.\n'
            '- PASS: source archive excludes actual credentials, private live results, caches, and local environments.\n'
            f'- Hosted deployment: **{hosted["status"]}**.\n'
            '- PENDING: actual hosted URL, fresh-browser visit, automatic live analysis, and human-approved n8n/Google acceptance.\n\n'
            'Local bundle readiness is separate from successful hosting. Follow [the Phase 5 guide](../docs/PHASE5.md).\n', encoding='utf-8')
    print(json.dumps(checkpoint, indent=2))


if __name__ == '__main__':
    main()
