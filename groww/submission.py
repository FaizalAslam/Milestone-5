"""Build a reviewable milestone packet from verified public outputs, without external writes."""
from __future__ import annotations

import csv
from datetime import date, datetime, timezone
import hashlib
from html import escape
import io
import json
from pathlib import Path, PurePosixPath
import re
from urllib.parse import urlparse
from zipfile import ZIP_DEFLATED, ZipFile

from .data import load_csv
from .demo import demo_manifest, load_demo
from .export import bundle_artifacts
from .intelligence import intelligence_markdown
from .outputs import email_content

LINK_FIELDS = {'github_repository', 'hosted_prototype', 'demo_video_url', 'google_doc', 'gmail_draft_id'}


def validate_links(links: dict):
    if set(links) != LINK_FIELDS:
        raise ValueError('Submission links must contain exactly the five template fields.')
    for name, value in links.items():
        if value is None:
            continue
        if not isinstance(value, str) or not value.strip():
            raise ValueError('Use null for links or IDs that are not available yet.')
        if name == 'gmail_draft_id':
            if not re.fullmatch(r'[A-Za-z0-9_-]+', value):
                raise ValueError('Invalid Gmail draft identifier.')
            continue
        url = urlparse(value)
        if url.scheme != 'https' or not url.hostname or url.username or url.password:
            raise ValueError('Submission links must use HTTPS without embedded credentials.')
        if name == 'github_repository' and (url.hostname != 'github.com' or len(url.path.strip('/').split('/')) != 2):
            raise ValueError('Use the actual GitHub owner/repository URL.')
        if name == 'hosted_prototype' and not url.hostname.endswith('.streamlit.app'):
            raise ValueError('Use the actual Streamlit Community Cloud URL.')
        if name == 'google_doc' and (url.hostname != 'docs.google.com' or not re.fullmatch(r'/document/d/[A-Za-z0-9_-]+(?:/(?:edit|view))?/?', url.path)):
            raise ValueError('Use the actual Google Docs document URL.')


def load_links(root: Path) -> dict:
    path = root / 'submission_links.json'
    links = json.loads(path.read_text(encoding='utf-8')) if path.exists() else dict.fromkeys(sorted(LINK_FIELDS))
    validate_links(links)
    return links


def audit_materials(root: Path):
    manifest = demo_manifest(root)
    raw = (root / 'groww_reviews_all_platforms_updated.csv').read_bytes()
    dataset = load_csv(raw, date.fromisoformat(manifest['report_date']), manifest['weeks'])
    insights, bundle = load_demo(root, dataset)
    artifacts = bundle_artifacts(bundle)
    for name, expected in artifacts.items():
        saved = root / 'outputs' / name
        if saved.exists() and saved.read_text(encoding='utf-8') != expected:
            raise ValueError(f'{name} has changed from the verified public snapshot. Resolve the mismatch before packaging.')
    original = list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
    lookup = {(r['platform'], r['review_id']): r for r in original}
    sample = list(csv.DictReader(io.StringIO((root / 'data/reviews_sample.csv').read_text(encoding='utf-8-sig'))))
    seen = set()
    for row in sample:
        key = (row.get('platform'), row.get('review_id'))
        if key in seen or row != lookup.get(key):
            raise ValueError('The reviews sample must retain unique, unchanged original records, text, dates and source URLs.')
        seen.add(key)
    if not sample:
        raise ValueError('The public reviews sample is empty.')
    sources = (root / 'SOURCES.md').read_text(encoding='utf-8')
    urls = re.findall(r'\]\((https://[^\s)]+)\)', sources)
    if not 4 <= len(urls) <= 6 or len(set(urls)) != len(urls) or not set(bundle.source_links) <= set(urls):
        raise ValueError('The source list needs 4–6 distinct HTTPS URLs, including both fee sources.')
    required_workflows = {'01_append_product_update.json', '02_create_support_draft.json',
                          '03_get_run_receipts.json', '04_mcp_server.json'}
    if {p.name for p in (root / 'n8n').glob('*.json')} != required_workflows:
        raise ValueError('All four controlled n8n workflow imports are required.')
    for path in (root / 'n8n').glob('*.json'):
        workflow = json.loads(path.read_text(encoding='utf-8'))
        for node in workflow['nodes']:
            if node['type'] == 'n8n-nodes-base.gmail' and (node['parameters'].get('resource'), node['parameters'].get('operation')) != ('draft', 'create'):
                raise ValueError('Only draft creation may be configured for Gmail.')
    return dataset, insights, bundle, artifacts, {'sample_rows': len(sample), 'source_urls': len(urls),
        'included_reviews': len(dataset.reviews), 'pulse_words': len(bundle.weekly_pulse.split()),
        'fee_bullets': len(bundle.explanation_bullets), 'original_csv_sha256': dataset.digest}


def pulse_html(text):
    lines = []
    for line in text.splitlines():
        value = escape(line)
        if line.startswith('# '):
            lines.append('<h2>' + escape(line[2:]) + '</h2>')
        elif line.startswith('## '):
            lines.append('<h3>' + escape(line[3:]) + '</h3>')
        elif line.startswith('> '):
            lines.append('<blockquote>' + escape(line[2:]) + '</blockquote>')
        elif line:
            lines.append('<p>' + value + '</p>')
    return '\n'.join(lines)


def review_page(bundle, checks, rows, links, video_ready):
    fee = '<ul>' + ''.join('<li>' + escape(b) + '</li>' for b in bundle.explanation_bullets) + '</ul>'
    sources = ''.join(f'<a href="{escape(u, quote=True)}">Official source {i}</a> ' for i, u in enumerate(bundle.source_links, 1))
    matrix = ''.join(f'<tr><td>{escape(title)}</td><td><span class="status {"pending" if "PENDING" in status or "DEFERRED" in status else "ready"}">{escape(status)}</span></td><td><a href="{path}">Open</a></td></tr>' for title, status, path in rows)
    link_list = ''.join('<li>' + escape(k.replace('_', ' ').title()) + ': ' +
                        (f'<a href="{escape(v, quote=True)}">{escape(v)}</a>' if v and k != 'gmail_draft_id' else escape(v or 'To be added later')) + '</li>' for k, v in links.items())
    video = '<video controls preload="metadata" poster="demo/poster.jpg"><source src="demo/groww_workflow_demo.mp4" type="video/mp4"></video>' if video_ready else '<p>Video capture is pending. Run the Streamlit app using the source bundle.</p>'
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Groww — Milestone submission</title>
<style>body{{margin:0;background:#f5f7f6;color:#17322b;font:16px/1.65 system-ui,sans-serif}}main{{max-width:1100px;margin:auto;padding:44px 28px}}h1{{font-size:44px;line-height:1.1;letter-spacing:-1.5px}}h2{{line-height:1.3}}h3{{margin-top:28px}}a{{color:#087458}}.eyebrow{{font-size:12px;font-weight:700;letter-spacing:2px}}.lead{{max-width:760px;color:#52675e}}.notice{{border-left:4px solid #d1a13a;background:#fff7df;padding:16px 20px}}.metrics{{display:flex;gap:16px;flex-wrap:wrap;margin:28px 0}}.metric{{flex:1;min-width:130px;padding:18px;background:white;border:1px solid #d8e3dd;border-radius:12px}}.metric strong{{font-size:28px;display:block}}nav{{display:flex;gap:18px;flex-wrap:wrap;margin:25px 0}}section{{background:#fff;padding:28px;border:1px solid #d8e3dd;border-radius:14px;margin:24px 0}}blockquote{{margin:14px 0;padding:10px 18px;border-left:3px solid #92b9a9;background:#f4f8f6}}table{{width:100%;border-collapse:collapse}}td,th{{padding:14px 10px;text-align:left;border-bottom:1px solid #e3ebe6}}.status{{font-size:12px;font-weight:650}}.ready{{color:#097758}}.pending{{color:#946719}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f7f5;padding:20px;border-radius:8px;font:14px/1.6 ui-monospace,monospace}}video{{width:100%;border-radius:10px;background:#102a25}}li{{margin-bottom:14px}}footer{{color:#60766b;font-size:13px;margin-top:30px}}@media(max-width:650px){{main{{padding:25px 16px}}h1{{font-size:34px}}section{{padding:18px}}table{{font-size:13px}}}}</style></head>
<body><main><p class="eyebrow">PRODUCT + SUPPORT / MILESTONE 6</p><h1>Groww Review Intelligence</h1><p class="lead">Original customer reviews → traceable product insights → weekly pulse + brokerage explanation → explicit approval → MCP.</p>
<p class="notice"><strong>Local package prepared. Links and live evidence will be added later.</strong><br>Document and email files below are exact previews. Real Google Docs append, Gmail draft evidence, and hosted deployment remain pending.</p>
<div class="metrics"><div class="metric"><strong>{checks['included_reviews']:,}</strong>reviews analyzed</div><div class="metric"><strong>{checks['pulse_words']}/250</strong>pulse words</div><div class="metric"><strong>{checks['fee_bullets']}/6</strong>fee bullets</div><div class="metric"><strong>{checks['sample_rows']}</strong>original sample rows</div></div>
<nav><a href="#demo">Demo</a><a href="#pulse">Weekly pulse</a><a href="#fee">Fee explanation</a><a href="#email">Email preview</a><a href="#checklist">Deliverables</a></nav>
<section id="demo"><h2>Watch the local workflow</h2>{video}<p>Captioned screen walkthrough of the actual local app. Saved analysis is shown; no remote write is represented as completed.</p></section>
<section id="pulse">{pulse_html(bundle.weekly_pulse)}<p><a href="deliverables/weekly_product_pulse.md">Download Markdown</a> · <a href="deliverables/review_intelligence.md">Inspect the review evidence and IDs</a></p></section>
<section id="fee"><h2>Customer clarification — Understanding brokerage</h2>{fee}<p>{sources}</p><p>Last checked: {escape(bundle.last_checked)}</p><p><a href="deliverables/fee_explainer.md">Download reusable support snippet</a></p></section>
<section id="email"><h2>Complete email draft preview</h2><pre>{escape(email_content(bundle)['subject'])}</pre><p><a href="deliverables/email_draft_preview.txt">Open complete email body</a> · <a href="deliverables/document_entry_preview.txt">Open document entry preview</a> · <a href="deliverables/document_entry.json">Structured entry JSON</a></p><p>Recipient is blank. Gmail draft creation requires approval in the connected app.</p></section>
<section id="checklist"><h2>Requirement checklist</h2><table><thead><tr><th>Deliverable</th><th>Status</th><th>File</th></tr></thead><tbody>{matrix}</tbody></table></section>
<section><h2>Project links and pending connections</h2><ul>{link_list}</ul><p>Adding a URL records a link; it does not verify a remote action. See <a href="pending/LIVE_EVIDENCE_CHECKLIST.md">the live-evidence checklist</a>.</p></section>
<footer>Report {escape(bundle.date)} · Data through {escape(bundle.audit['data_cutoff'])} · Run {escape(bundle.run_id)} · <a href="README.md">Setup and approval instructions</a> · <a href="manifest.json">File hashes</a></footer></main></body></html>'''


def build_submission(root: Path, directory: Path, source_archive: Path) -> dict:
    dataset, insights, bundle, artifacts, checks = audit_materials(root)
    links = load_links(root)
    files = {'deliverables/' + name: value.encode('utf-8') for name, value in artifacts.items()}
    files['deliverables/review_intelligence.md'] = intelligence_markdown(insights).encode('utf-8')
    files['data/reviews_sample.csv'] = (root / 'data/reviews_sample.csv').read_bytes()
    files['SOURCES.md'] = (root / 'SOURCES.md').read_bytes()
    files['links.json'] = (json.dumps(links, indent=2) + '\n').encode('utf-8')
    if not source_archive.is_file():
        raise ValueError('Build the credential-free deployment source archive first.')
    with ZipFile(source_archive) as source:
        required_source = {'app.py', 'requirements.txt', '.streamlit/secrets.toml.example',
                           'groww_reviews_all_platforms_updated.csv', 'data/demo/latest.json',
                           'data/demo/review_intelligence.json', 'data/demo/manifest.json'}
        if not required_source <= set(source.namelist()):
            raise ValueError('The source archive is incomplete for a fresh setup.')
        for name in source.namelist():
            parts = PurePosixPath(name.replace('\\', '/')).parts
            if (name.startswith(('/', '\\')) or '..' in parts or any(p in {'.cache', '.git', 'private', 'secrets.toml', '.env'} or p.startswith('.venv') for p in parts)):
                raise ValueError('The source archive contains a private or unsafe path.')
    files['source/groww-streamlit-deployment.zip'] = source_archive.read_bytes()
    for path in sorted((root / 'n8n').glob('*.json')):
        files['workflows/' + path.name] = path.read_bytes()
    for path in sorted((root / 'docs').glob('*.md')):
        files['guides/' + path.name] = path.read_bytes()
    for path in sorted((root / 'outputs').glob('phase*_verification.md')):
        if path.name != 'phase6_verification.md':
            files['verification/' + path.name] = path.read_bytes()
    for path in sorted((root / 'outputs').glob('phase*_checkpoint.json')):
        if path.name != 'phase6_checkpoint.json':
            files['verification/' + path.name] = path.read_bytes()
    for path in sorted((root / 'outputs').glob('preview_*.jpg')):
        files['evidence/' + path.name] = path.read_bytes()
    for name in ['ui_redesign_checkpoint.json', 'ui_redesign_verification.md']:
        path = root / 'outputs' / name
        if path.is_file():
            files['verification/' + name] = path.read_bytes()
    for path in sorted((root / 'outputs/ui_redesign').glob('*.png')):
        files['evidence/ui_redesign/' + path.name] = path.read_bytes()
    video_path, meta_path = root / 'outputs/demo/groww_workflow_demo.mp4', root / 'outputs/demo/metadata.json'
    video_ready = video_path.is_file() and meta_path.is_file()
    video_duration = None
    if video_ready:
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
        video_duration = meta['duration_seconds']
        if not 0 < video_duration <= 180 or meta['sha256'] != hashlib.sha256(video_path.read_bytes()).hexdigest() or meta.get('full_decode_passed') is not True:
            raise ValueError('Demo video must match its verified hash and be no longer than three minutes.')
        files['demo/groww_workflow_demo.mp4'] = video_path.read_bytes()
        files['demo/metadata.json'] = meta_path.read_bytes()
        poster = root / 'outputs/demo/poster.jpg'
        if not poster.is_file() or meta.get('poster_sha256') != hashlib.sha256(poster.read_bytes()).hexdigest():
            raise ValueError('The video poster is missing or differs from the encoded walkthrough.')
        files['demo/poster.jpg'] = poster.read_bytes()
        if (root / 'outputs/demo/STORYBOARD.md').exists():
            files['demo/STORYBOARD.md'] = (root / 'outputs/demo/STORYBOARD.md').read_bytes()
    rows = [
        ('Prototype / ≤3-minute demo', 'READY_LOCAL_VIDEO' if video_ready else 'PENDING_VIDEO_OR_HOSTED_LINK', 'demo/groww_workflow_demo.mp4' if video_ready else 'links.json'),
        ('Weekly product pulse', 'READY', 'deliverables/weekly_product_pulse.md'),
        ('Fee explanation', 'READY', 'deliverables/fee_explainer.md'),
        ('Appended Google Docs entry evidence', 'PENDING_LIVE — preview supplied', 'deliverables/document_entry_preview.txt'),
        ('Gmail draft evidence', 'PENDING_LIVE — complete text preview supplied', 'deliverables/email_draft_preview.txt'),
        ('Original reviews sample', 'READY', 'data/reviews_sample.csv'),
        ('4–6 source URLs', 'READY', 'SOURCES.md'),
        ('Setup, approval, and identified fee README', 'READY', 'README.md'),
        ('Importable n8n workflows', 'READY_TEMPLATES — account import pending', 'workflows/04_mcp_server.json'),
        ('Hosted / GitHub links', 'READY_LINKS — deployment verification pending' if links['github_repository'] and links['hosted_prototype'] else 'PENDING_HOSTED_LINK — supplied links recorded' if links['github_repository'] else 'PENDING_CONNECTION', 'links.json')]
    pending = '''# Live evidence checklist — pending account connection

These files are previews and local verification. No appended Doc entry, actual Gmail draft, or hosted deployment is claimed.

After accounts are connected:

1. Deploy to the chosen GitHub repository and Streamlit Community Cloud; verify the real URL in a fresh browser session.
2. Configure the n8n production MCP URL/token and fixed Google Doc. Run read-only discovery.
3. Review the exact outputs in Live mode. Reject once and verify no writes. Then personally approve the current snapshot in the app.
4. Verify one new Doc entry and one unsent Gmail draft against the approved previews. Save the actual draft ID, Doc URL, matching run/fingerprint, approval timestamp, and separate successful action receipts.
5. Capture the actual appended Doc entry and Gmail draft. Keep account screenshots and receipts under outputs/private/ until reviewed for submission.
6. Add the GitHub, hosted prototype, Google Doc, and draft references to submission_links.json using scripts/update_submission_links.py. Rebuild this package.

Adding links alone does not change pending remote evidence into a pass. Attach and verify the real receipts/screenshots separately. No email-send operation is configured.
'''
    files['pending/LIVE_EVIDENCE_CHECKLIST.md'] = pending.encode('utf-8')
    table = '\n'.join(f'| {title} | {status} | [{Path(path).name}]({path}) |' for title, status, path in rows)
    readme = f'''# Groww Review Intelligence — submission packet

Open **index.html** for the review page and captioned demo. This package contains the completed local workflow. **Supplied project links are recorded in links.json. Hosted deployment and actual Google Docs/Gmail evidence remain pending until verified.**

## What the reviews identified

The original CSV has 13,268 reviews; 13,034 fall in the inclusive 12-week window ending 16 October 2026. The leading themes are support/account operations (550), app stability/UI (470), and missing features (457). Five distinct original review texts support the identified issue: **brokerage confusion and unexpected Groww brokerage deductions**. Customer reports are kept separate from official fee facts.

The pulse contains {checks['pulse_words']} words, three source-matched quotes, and exactly three product actions. The fee explainer has {checks['fee_bullets']} bullets, two official Groww links, and Last checked: {bundle.last_checked}. The sample retains {checks['sample_rows']} complete original review records.

## Deliverable map

| Requirement | Status | File |
| --- | --- | --- |
{table}

## Run the prototype from this packet

1. Extract `source/groww-streamlit-deployment.zip` into a new folder and open a terminal there.
2. Use Python 3.12:

```powershell
py -3.12 -m venv .venv312
.\\.venv312\\Scripts\\python.exe -m pip install -r requirements.txt
.\\.venv312\\Scripts\\python.exe -m streamlit run app.py --server.port 8502
```

3. Open http://127.0.0.1:8502. The upload workspace opens without secrets. Click **Demo** to inspect the read-only completed example without model calls or external writes.
4. For live use, copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and configure it locally. Choose Live, select the reporting period and upload a CSV. Analysis and output generation start automatically. Follow the included Phase 4 and 5 guides for n8n and hosting. Credentials are excluded from this package.

## Where MCP approval happens

In the **Results Workspace → Save Approved Outputs** panel, inspect the fixed document destination, structured entry, pulse, fee snippet, and full email. **Approve and save** authorizes the current content fingerprint for 30 minutes. Reject makes no writes. Edits/regeneration invalidate approval. Completed actions are skipped on retry; unknown outcomes require read-only remote reconciliation. Gmail has a draft-create action only, with no auto-send operation.

## Verification and remaining evidence

`verification/` contains the recorded local checks, separately labelled from live acceptance. `manifest.json` records every included file hash. The source list has {checks['source_urls']} URLs. `links.json` intentionally uses null for missing links; it does not contain invented URLs or draft IDs.

Follow `pending/LIVE_EVIDENCE_CHECKLIST.md` after connecting accounts. Keep actual receipts and account screenshots private until they are reviewed. Rebuilding preserves the separately maintained root `submission_links.json` file.
'''
    files['README.md'] = readme.encode('utf-8')
    files['index.html'] = review_page(bundle, checks, rows, links, video_ready).encode('utf-8')
    manifest = {'schema_version': 1, 'built_at': datetime.now(timezone.utc).isoformat(),
                'local_package_status': 'PASS' if video_ready else 'PENDING_DEMO',
                'final_submission_status': 'WAITING_FOR_LINKS_AND_LIVE_EVIDENCE',
                'run_id': bundle.run_id, 'checks': checks, 'demo_duration_seconds': video_duration,
                'remote_writes_claimed': False, 'deliverables': [{'name': n, 'status': s, 'file': p} for n, s, p in rows],
                'files': {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())}}
    files['manifest.json'] = (json.dumps(manifest, indent=2) + '\n').encode('utf-8')
    directory.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    archive = root / 'outputs/groww-milestone-submission.zip'
    archive.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(archive, 'w', ZIP_DEFLATED) as zipped:
        for name, data in sorted(files.items()):
            zipped.writestr(name, data)
    return dict(manifest, archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(), archive_bytes=archive.stat().st_size)
