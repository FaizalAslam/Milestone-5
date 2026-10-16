"""Submission integrity checks; no publishing or remote evidence is simulated as complete."""
import csv
import hashlib
import json
from pathlib import Path
import shutil
from zipfile import ZipFile

import pytest

from groww.deployment import build_repository_bundle
from groww.submission import LINK_FIELDS, audit_materials, build_submission, load_links, validate_links

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def material_root(tmp_path):
    project = tmp_path / 'project'
    project.mkdir()
    for name in ['groww_reviews_all_platforms_updated.csv', 'SOURCES.md']:
        shutil.copyfile(ROOT / name, project / name)
    shutil.copytree(ROOT / 'data/demo', project / 'data/demo')
    shutil.copyfile(ROOT / 'data/reviews_sample.csv', project / 'data/reviews_sample.csv')
    shutil.copytree(ROOT / 'n8n', project / 'n8n')
    return project


def test_submission_audit_uses_original_rows_and_real_snapshot():
    _, _, bundle, _, checks = audit_materials(ROOT)
    assert checks['sample_rows'] == 53 and checks['source_urls'] == 6
    assert checks['included_reviews'] == 13034 and checks['pulse_words'] == 149
    assert checks['fee_bullets'] == 4 and bundle.intelligence_run_id


@pytest.mark.parametrize('change', ['text', 'date', 'source_url', 'duplicate'])
def test_altered_or_duplicate_sample_cannot_be_packaged(material_root, change):
    path = material_root / 'data/reviews_sample.csv'
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        rows, fields = list(reader), reader.fieldnames
    if change == 'duplicate':
        rows.append(rows[0])
    elif change == 'text':
        rows[0]['review_text'] += ' altered'
    elif change == 'date':
        rows[0]['date'] = '2026-10-01'
    else:
        rows[0]['source_url'] = 'https://example.com/changed'
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError, match='unchanged original records'):
        audit_materials(material_root)


@pytest.mark.parametrize('field,value', [
    ('hosted_prototype', 'http://example.streamlit.app'),
    ('github_repository', 'https://github.com/owner/repo/tree/main'),
    ('github_repository', 'https://evil.example/owner/repo'),
    ('google_doc', 'https://docs.google.com/document/d/'),
    ('demo_video_url', 'https://user:secret@example.com/video'),
])
def test_invalid_link_or_embedded_credentials_are_rejected(field, value):
    links = dict.fromkeys(LINK_FIELDS)
    links[field] = value
    with pytest.raises(ValueError):
        validate_links(links)


def test_link_updates_cannot_claim_remote_evidence_and_packet_hashes_match(material_root, tmp_path):
    links = dict.fromkeys(LINK_FIELDS)
    links.update(github_repository='https://github.com/example/fixture', google_doc='https://docs.google.com/document/d/fixture/edit', gmail_draft_id='fixture-draft')
    path = material_root / 'submission_links.json'
    path.write_text(json.dumps(links), encoding='utf-8')
    archive = tmp_path / 'source.zip'
    build_repository_bundle(ROOT, archive)
    packet = material_root / 'packet'
    manifest = build_submission(material_root, packet, archive)
    assert load_links(material_root) == links
    assert manifest['remote_writes_claimed'] is False
    assert manifest['final_submission_status'] == 'WAITING_FOR_LINKS_AND_LIVE_EVIDENCE'
    assert manifest['local_package_status'] == 'PENDING_DEMO'
    assert all('PENDING_LIVE' in row['status'] for row in manifest['deliverables'] if row['name'] in ['Appended Google Docs entry evidence', 'Gmail draft evidence'])
    with ZipFile(material_root / 'outputs/groww-milestone-submission.zip') as zipped:
        for name, digest in manifest['files'].items():
            assert hashlib.sha256(zipped.read(name)).hexdigest() == digest
        assert json.loads(zipped.read('links.json')) == links
        assert '<script>' not in zipped.read('index.html').decode('utf-8')


def test_private_files_inside_source_archive_are_blocked(material_root, tmp_path):
    archive = tmp_path / 'source.zip'
    build_repository_bundle(ROOT, archive)
    with ZipFile(archive, 'a') as zipped:
        zipped.writestr('.streamlit/secrets.toml', 'DO NOT SHIP')
    with pytest.raises(ValueError, match='private or unsafe path'):
        build_submission(material_root, material_root / 'packet', archive)


def test_video_over_three_minutes_or_changed_hash_is_blocked(material_root, tmp_path):
    archive = tmp_path / 'source.zip'
    build_repository_bundle(ROOT, archive)
    demo = material_root / 'outputs/demo'
    demo.mkdir(parents=True)
    video = b'fixture bytes; not a real demonstration'
    (demo / 'groww_workflow_demo.mp4').write_bytes(video)
    (demo / 'metadata.json').write_text(json.dumps({'duration_seconds': 181, 'sha256': hashlib.sha256(video).hexdigest()}), encoding='utf-8')
    with pytest.raises(ValueError, match='no longer than three minutes'):
        build_submission(material_root, material_root / 'packet', archive)
    (demo / 'metadata.json').write_text(json.dumps({'duration_seconds': 100, 'sha256': 'wrong'}), encoding='utf-8')
    with pytest.raises(ValueError, match='verified hash'):
        build_submission(material_root, material_root / 'packet', archive)


def test_tampered_export_and_send_operation_are_blocked(material_root):
    output = material_root / 'outputs'
    output.mkdir()
    pulse = output / 'weekly_product_pulse.md'
    pulse.write_text('altered report', encoding='utf-8')
    with pytest.raises(ValueError, match='changed from the verified public snapshot'):
        audit_materials(material_root)
    pulse.unlink()
    path = material_root / 'n8n/02_create_support_draft.json'
    workflow = json.loads(path.read_text(encoding='utf-8'))
    next(n for n in workflow['nodes'] if n['type'] == 'n8n-nodes-base.gmail')['parameters'].update(resource='message', operation='send')
    path.write_text(json.dumps(workflow), encoding='utf-8')
    with pytest.raises(ValueError, match='Only draft creation'):
        audit_materials(material_root)


def test_independent_verifier_rejects_changed_packet_bytes(material_root, tmp_path):
    from scripts.verify_submission import verify
    archive = tmp_path / 'source.zip'
    build_repository_bundle(ROOT, archive)
    build_submission(material_root, material_root / 'submission', archive)
    assert verify(material_root)['status'] == 'PASS'
    packet = material_root / 'outputs/groww-milestone-submission.zip'
    with ZipFile(packet) as zipped:
        files = {name: zipped.read(name) for name in zipped.namelist()}
    files['deliverables/weekly_product_pulse.md'] += b'changed after verification'
    with ZipFile(packet, 'w') as zipped:
        for name, data in files.items():
            zipped.writestr(name, data)
    with pytest.raises(ValueError, match='does not match its manifest'):
        verify(material_root)
