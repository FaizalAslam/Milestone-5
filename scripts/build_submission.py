"""Build the Phase 6 review packet, with honest pending live-evidence status."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from groww.deployment import build_repository_bundle
from groww.submission import build_submission, load_links


def main():
    source = ROOT / 'outputs/groww-streamlit-deployment.zip'
    deployment = build_repository_bundle(ROOT, source)
    (ROOT / 'outputs/deployment_manifest.json').write_text(json.dumps(deployment, indent=2) + '\n', encoding='utf-8')
    manifest = build_submission(ROOT, ROOT / 'submission', source)
    links = load_links(ROOT)
    remaining = []
    if not links['github_repository']:
        remaining.append('GitHub repository URL')
    remaining.extend(['Publish source and verify GitHub CI', 'Hosted deployment and browser verification',
                      'Actual approved Google Doc entry evidence',
                      'Actual Gmail draft ID/screenshot and matching execution receipts'])
    checkpoint = {'checked_at': datetime.now(timezone.utc).isoformat(),
                  'local_package_status': manifest['local_package_status'],
                  'final_submission_status': manifest['final_submission_status'],
                  'checks': manifest['checks'], 'demo_duration_seconds': manifest['demo_duration_seconds'],
                  'packaged_files': len(manifest['files']) + 1, 'archive_sha256': manifest['archive_sha256'],
                  'archive_bytes': manifest['archive_bytes'], 'remote_writes_claimed': False,
                  'remaining': remaining}
    (ROOT / 'outputs/phase6_checkpoint.json').write_text(json.dumps(checkpoint, indent=2) + '\n', encoding='utf-8')
    (ROOT / 'outputs/phase6_verification.md').write_text(
        '# Phase 6 verification\n\n'
        f'Local package: **{manifest["local_package_status"]}**. Final live submission: **{manifest["final_submission_status"]}**.\n\n'
        f'- {manifest["checks"]["included_reviews"]:,} included reviews; original CSV fingerprint preserved.\n'
        f'- {manifest["checks"]["sample_rows"]} sample records match every original CSV field; no duplicate sample IDs.\n'
        f'- Pulse: {manifest["checks"]["pulse_words"]} words; three verified quotes; exactly three actions.\n'
        f'- Fee explanation: {manifest["checks"]["fee_bullets"]} bullets, two official links, dated source check.\n'
        f'- Source list: {manifest["checks"]["source_urls"]} distinct HTTPS URLs.\n'
        f'- Captioned screen walkthrough: {manifest["demo_duration_seconds"]} seconds, if present.\n'
        '- Public source archive, README, n8n templates, document/email previews and evidence checklist included.\n'
        '- File hashes are recorded in submission/manifest.json. Supplied links are recorded in links.json; unavailable links remain null.\n'
        '- No remote Google Docs entry or Gmail draft is claimed; their real receipts/screenshots remain pending.\n', encoding='utf-8')
    print(json.dumps(checkpoint, indent=2))


if __name__ == '__main__':
    main()
