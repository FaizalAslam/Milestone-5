
from __future__ import annotations

import asyncio
import hmac
import json
import os
import uuid
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from groww.analysis import Engine
from groww.approval import ACTIONS, N8nMCP, approve, execute_approved, prepare_payload
from groww.execution import ExecutionJournal
from groww.data import DataError, load_csv
from groww.export import classifications_csv
from groww.demo import demo_manifest, load_demo
from groww.runstore import LiveRunStore
from groww.intelligence import intelligence_markdown, validate_intelligence
from groww.models import Bundle, ReviewIntelligence
from groww.outputs import document_text, email_content, explainer_markdown, fingerprint, validate_bundle
from groww.sources import fetch_sources

ROOT = Path(__file__).parent
journal = ExecutionJournal(ROOT / '.cache' / 'approval_runs.sqlite3')
run_store = LiveRunStore(ROOT / 'outputs/private/runs')
load_dotenv(ROOT / '.env')
st.set_page_config(page_title='Groww · Product Pulse', page_icon='📊', layout='wide')
st.markdown('''<style>
.block-container {max-width:1200px;padding-top:2rem;} h1 {letter-spacing:-.045em;}
[data-testid="stMetric"] {background:white;border:1px solid #deebe4;border-radius:12px;padding:16px;}
[data-testid="stSidebar"] {border-right:1px solid #deebe4;}
div.stButton>button {border-radius:8px;} a {color:#07836b;}
</style>''', unsafe_allow_html=True)


def setting(name, default=''):
    try:
        return str(st.secrets.get(name) or os.getenv(name, default))
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return os.getenv(name, default)


def reset_run(include_intelligence=True):
    keys = ['bundle', 'approval', 'receipts', 'pulse_editor', 'rejected']
    if include_intelligence:
        keys.append('intelligence')
    for key in keys:
        st.session_state.pop(key, None)


def install_bundle(bundle):
    reset_run(include_intelligence=False)
    st.session_state.bundle = bundle
    st.session_state.pulse_editor = bundle.weekly_pulse


def install_intelligence(result):
    reset_run()
    st.session_state.intelligence = result


def evidence_cards(quotes):
    for quote in quotes:
        with st.container(border=True):
            st.text(quote['text'])
            st.caption(f"{quote['date']} · {quote['review_key']}")
            st.link_button('Public review source', quote['source_url'])


today = datetime.now(ZoneInfo('Asia/Kolkata')).date()
try:
    demo = demo_manifest(ROOT)
except (ValueError, OSError):
    st.error('The saved demo is missing or invalid. Restore data/demo from the deployment bundle.')
    st.stop()
password = setting('DEMO_ACCESS_PASSWORD')
operator = bool(password) and st.session_state.get('operator_authenticated', False)
with st.sidebar:
    st.markdown('### Groww Product Pulse')
    st.caption('Customer feedback → product action')
    mode = st.selectbox('Run mode', ['Saved CSV demo', 'Live upload and analysis'])
    demo_mode = mode == 'Saved CSV demo'
    phase = st.radio('Workspace', ['1 · Dataset', '2 · Review intelligence', '3 · Product + support outputs', '4 · Approve + save'])
    st.divider()
    st.markdown('**Reporting window**')
    report_date = st.date_input('Report date', value=date.fromisoformat(demo['report_date']) if demo_mode else today,
                                max_value=today, disabled=demo_mode, key='report_date_demo' if demo_mode else 'report_date_live')
    weeks = st.slider('Weeks of review context', min_value=8, max_value=12, value=12, disabled=demo_mode,
                      key='weeks_demo' if demo_mode else 'weeks_live')
    st.divider()
    if password and not operator:
        with st.form('operator_login'):
            entered = st.text_input('Demo access password', type='password')
            if st.form_submit_button('Unlock live workflow'):
                if hmac.compare_digest(entered.encode(), password.encode()):
                    st.session_state.operator_authenticated = True
                    st.rerun()
                st.error('Incorrect access password.')
    elif operator:
        st.success('Live workflow unlocked')
        if st.button('Lock live workflow'):
            st.session_state.operator_authenticated = False
            st.session_state.pop('approval', None)
            st.session_state.pop('receipts', None)
            st.rerun()
    else:
        st.info('Dataset preview is available. Configure a demo access password to unlock live analysis and saving.')
    st.caption('Google Docs and Gmail are changed only after approval. Email is saved as a draft.')
live_operator = operator and not demo_mode

st.caption('PRODUCT + SUPPORT / CUSTOMER INTELLIGENCE')
st.title('Groww Review Intelligence')
st.write('Turn customer reviews into a weekly product pulse and a source-backed fee explanation.')
uploaded = st.file_uploader('Upload public customer reviews', type=['csv'], disabled=demo_mode,
                            help='Choose Live upload and analysis to upload. UTF-8 CSV, up to 15 MB. Required: platform, review_id, date, rating, review_text, source_url.')
sample = ROOT / 'groww_reviews_all_platforms_updated.csv'
use_sample = st.checkbox('Use the supplied Groww reviews CSV', value=True, disabled=uploaded is not None or demo_mode)
raw = sample.read_bytes() if demo_mode and sample.exists() else uploaded.getvalue() if uploaded else sample.read_bytes() if use_sample and sample.exists() else None
if raw is None:
    st.info('Upload a CSV to begin. Your original file will not be changed.')
    st.stop()
try:
    dataset = load_csv(raw, report_date, weeks)
except DataError as exc:
    st.error(str(exc))
    st.stop()
audit = dataset.audit()
dataset_key = f'{dataset.digest}:{report_date}:{weeks}:{mode}'
if st.session_state.get('dataset_key') != dataset_key:
    reset_run()
    st.session_state.dataset_key = dataset_key
if demo_mode:
    st.info(f"Saved CSV demo · Captured {demo['report_date']} · {demo['included_reviews']:,} reviews · Fee sources checked {demo['source_last_checked']}")
    st.caption('Select Live upload and analysis in the sidebar to use current feedback. Live analysis and saving require the access password.')
    if 'bundle' not in st.session_state:
        try:
            demo_intelligence, demo_bundle = load_demo(ROOT, dataset)
            install_intelligence(demo_intelligence)
            install_bundle(demo_bundle)
        except (ValueError, OSError) as exc:
            st.error(str(exc))
            st.stop()
cols = st.columns(4)
for col, title, value in zip(cols, ['Reviews uploaded', 'Reviews in window', 'Excluded reviews', 'Unique texts'],
                             [audit['original_count'], audit['included_count'], audit['original_count'] - audit['included_count'], audit['unique_texts']]):
    col.metric(title, f'{value:,}')
st.caption(f"Context: {audit['window_start']} to {audit['window_end']} · Data through {audit['data_cutoff'] or 'no included dates'} · Report date in India time")
if audit['days_between_cutoff_and_report']:
    st.caption(f"Coverage note: the latest review is {audit['days_between_cutoff_and_report']} day(s) before the report date. Comparisons end on the data cutoff, whose final day may be partial.")
if not dataset.reviews:
    st.warning('No valid reviews fall inside this reporting window. Choose a matching report date or upload recent reviews.')
    st.stop()

if phase.startswith('1'):
    st.subheader('Dataset checkpoint')
    if not dataset.invalid_rows:
        st.success('PASS · Required columns, dates, ratings, and source URLs are valid.')
    else:
        st.warning(f"{len(dataset.invalid_rows)} invalid rows excluded. Inspect the reasons before analyzing.")
        st.dataframe(pd.DataFrame(dataset.invalid_rows), hide_index=True)
    st.write(f"Excluded: {dataset.outside_count} outside the window, {dataset.future_count} future-dated, {dataset.duplicate_count} duplicate IDs, {len(dataset.invalid_rows)} invalid rows.")
    left, right = st.columns(2)
    with left:
        st.markdown('**Reviews by platform**')
        st.bar_chart(pd.Series(audit['platform_counts'], name='Reviews'), color='#07836b')
    with right:
        st.markdown('**Star ratings**')
        st.bar_chart(pd.Series(audit['rating_counts'], name='Reviews'), color='#07836b')
    st.caption('Different reviews with the same text remain separate observations. AI classifies repeated text once and maps it back to those reviews.')
    with st.expander('Preview original review records'):
        st.dataframe(pd.DataFrame([{'platform': r.platform, 'review_id': r.review_id, 'date': r.date,
                                   'rating': r.rating, 'review_text': r.review_text, 'source_url': r.source_url}
                                  for r in dataset.reviews[:30]]), hide_index=True)
    st.download_button('Download validation report', json.dumps(audit, indent=2), 'dataset_audit.json', 'application/json')

if phase.startswith('2'):
    st.subheader('Review intelligence')
    st.write('Discover up to five themes, classify all included feedback, and find evidence of recurring fee confusion.')
    st.caption('General praise contributes to sentiment. Top themes use substantive feedback, including short concrete complaints. Model calls use your OpenAI API account.')
    api_key = setting('OPENAI_API_KEY')
    if not api_key:
        st.info('Live analysis is not configured. Add OPENAI_API_KEY to Streamlit secrets; instructions are in the README. No AI results are fabricated in preview mode.')
    st.caption('Phase 2 ends with review insights and an audit export. Generate the weekly pulse and official fee explanation in Phase 3.')
    if st.button('Analyze reviews (Phase 2)', type='primary', disabled=not (live_operator and api_key)):
        reset_run()
        bar = st.progress(0, 'Starting review intelligence')
        try:
            result = Engine(api_key, setting('OPENAI_MODEL', 'gpt-5-mini'), ROOT / '.cache',
                            int(setting('OPENAI_MAX_WORKERS', '4'))).analyze_reviews(
                dataset, lambda value, label: bar.progress(value, label))
            run_store.save_intelligence(result, dataset)
            install_intelligence(result)
            st.success('PASS · Phase 2 saved: counts reconcile, three quotes match, and fee confusion has distinct review evidence.')
        except Exception as exc:
            bar.empty()
            st.error(f'Analysis stopped ({type(exc).__name__}). No document or email action was taken.')
            if isinstance(exc, ValueError):
                st.error(str(exc))
            else:
                st.info('Check your model access, API quota, and network connection. Completed classification batches resume from the private cache.')
    saved_intelligence = ROOT / 'data/demo/review_intelligence.json'
    if saved_intelligence.exists() and st.button('Load saved Phase 2 analysis'):
        try:
            result = ReviewIntelligence.model_validate_json(saved_intelligence.read_text(encoding='utf-8'))
            result.checks = validate_intelligence(result, dataset)
            install_intelligence(result)
        except ValueError as exc:
            st.error(str(exc))
    saved = ROOT / 'data/demo/latest.json'
    if saved.exists() and st.button('Load saved AI analysis of this dataset'):
        try:
            bundle = Bundle.model_validate_json(saved.read_text(encoding='utf-8'))
            validate_bundle(bundle, dataset)
            if bundle.date != str(report_date) or bundle.audit['window_start'] != str(dataset.start_date):
                raise ValueError('Saved analysis uses a different reporting window.')
            install_bundle(bundle)
        except ValueError as exc:
            st.error(str(exc))
    reference = ROOT / 'data' / 'reference_evidence.json'
    if 'intelligence' not in st.session_state and 'bundle' not in st.session_state and reference.exists():
        with st.expander('Inspect preliminary fee evidence from the supplied CSV'):
            evidence = json.loads(reference.read_text(encoding='utf-8'))
            st.warning('Reference preview · Manually selected review excerpts. This is not a completed AI clustering run and cannot be approved or saved to internal tools.')
            st.write(evidence['identified_fee_issue'])
            evidence_cards(evidence['quotes'])

intelligence = st.session_state.get('intelligence')
bundle = st.session_state.get('bundle')
if intelligence and phase.startswith('2'):
    st.caption(f'Phase 2 AI analysis · {intelligence.model} · Run {intelligence.run_id[:10]} · Report {intelligence.date}')
    st.markdown('**Top three themes**')
    for col, theme in zip(st.columns(3), intelligence.themes[:3]):
        col.metric(theme['name'], f"{theme['count']:,}")
    st.dataframe(pd.DataFrame(intelligence.themes)[['id', 'name', 'count', 'current_week', 'previous_week']].rename(
        columns={'count': 'Reviews', 'name': 'Theme', 'current_week': 'Latest 7 days', 'previous_week': 'Preceding 7 days'}), hide_index=True)
    with st.expander('Theme definitions'):
        st.caption('Model summaries of customer reports and requests; reported problems and losses are not independently verified.')
        for theme in intelligence.themes:
            st.markdown('**' + theme['name'] + '**')
            st.text(theme['description'])
    st.caption(f"Substantive feedback: {sum(t['count'] for t in intelligence.themes):,}; nonspecific feedback: {intelligence.non_substantive_count:,}. Each included review counts once. Theme ranking covers the full window.")
    with st.expander('Latest seven days compared with the preceding seven days'):
        st.json(audit['comparison_periods'])
        st.caption('These periods end at the data cutoff. Dates without reviews do not prove missing collection. The final day may be partial. Volume changes alone do not establish a trend.')
    st.markdown('**Text sentiment across all included reviews**')
    st.bar_chart(pd.Series(intelligence.sentiment_counts, name='Reviews'), color='#07836b')
    st.markdown('**Three verified user quotes**')
    evidence_cards(intelligence.quotes)
    st.markdown('**Recurring fee confusion**')
    st.caption('Named fee: ' + intelligence.fee_name)
    st.write(intelligence.identified_fee_issue)
    st.write(intelligence.fee_rationale)
    st.caption('These are customer reports. Official fee facts are checked in Phase 3.')
    with st.expander(f'Inspect {len(intelligence.fee_evidence)} distinct supporting review texts'):
        for evidence in intelligence.fee_evidence:
            evidence_cards([evidence])
            st.caption('Exact confusion passage: ' + evidence['confusion_passage'])
            st.caption('Selected fee passage: ' + evidence['selected_fee_passage'])
    with st.expander('Phase 2 checkpoint', expanded=True):
        for check in intelligence.checks:
            st.success('PASS · ' + check)
    st.download_button('Download Phase 2 report', intelligence_markdown(intelligence), 'review_intelligence.md', 'text/markdown')
    st.download_button('Download review classifications', classifications_csv(intelligence, dataset), 'review_classifications.csv', 'text/csv')
    st.download_button('Download Phase 2 JSON', intelligence.model_dump_json(indent=2), 'review_intelligence.json', 'application/json')

if bundle and not phase.startswith('1'):
    st.caption(f'AI analysis · {bundle.model} · Run {bundle.run_id[:10]} · Report {bundle.date}')
    if bundle.pulse_edited:
        st.caption('The weekly pulse was edited by the operator after AI generation.')
    if phase.startswith('2') and not intelligence:
        st.markdown('**Top themes**')
        st.dataframe(pd.DataFrame(bundle.themes).rename(columns={'count': 'Reviews', 'name': 'Theme'}), hide_index=True)
        st.caption(f"Substantive feedback: {sum(t['count'] for t in bundle.themes):,}; nonspecific feedback: {bundle.non_substantive_count:,}. Week counts are the latest seven observed days versus the preceding seven days.")
        st.markdown('**Text sentiment across all included reviews**')
        st.bar_chart(pd.Series(bundle.sentiment_counts, name='Reviews'), color='#07836b')
        st.markdown('**Three verified user quotes**')
        evidence_cards(bundle.quotes)
        st.markdown('**Recurring fee issue**')
        st.write(bundle.identified_fee_issue)
        with st.expander(f'Inspect {len(bundle.fee_evidence)} supporting review texts'):
            evidence_cards(bundle.fee_evidence)

if phase.startswith('3'):
    st.subheader('Product + support outputs')
    st.caption('Generate from verified review insights, inspect both outputs, then review the document and email previews before Phase 4 approval.')
    saved_phase2 = ROOT / 'data/demo/review_intelligence.json'
    saved_outputs = ROOT / 'data/demo/latest.json'
    started = bool(st.session_state.get('receipts')) or bool(bundle and journal.find(bundle.run_id))
    if saved_phase2.exists() and not intelligence and st.button('Load saved Phase 2 insights', disabled=started):
        try:
            result = ReviewIntelligence.model_validate_json(saved_phase2.read_text(encoding='utf-8'))
            validate_intelligence(result, dataset)
            install_intelligence(result)
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
    if saved_outputs.exists() and st.button('Load saved Phase 3 outputs', disabled=started):
        try:
            result = ReviewIntelligence.model_validate_json(saved_phase2.read_text(encoding='utf-8'))
            saved_bundle = Bundle.model_validate_json(saved_outputs.read_text(encoding='utf-8'))
            validate_bundle(saved_bundle, dataset, result)
            install_intelligence(result)
            install_bundle(saved_bundle)
            st.rerun()
        except (ValueError, OSError) as exc:
            st.error(str(exc))
    if intelligence:
        st.caption(f'Verified Phase 2 input: {intelligence.run_id[:10]} · {len(dataset.reviews):,} reviews · Fee: {intelligence.fee_name}')
    api_key = setting('OPENAI_API_KEY')
    label = 'Regenerate outputs from Phase 2' if bundle else 'Generate outputs from Phase 2'
    if st.button(label, type='primary', disabled=not (live_operator and api_key and intelligence) or started):
        reset_run(include_intelligence=False)
        bar = st.progress(0, 'Retrieving current official Groww fee information')
        try:
            sources = fetch_sources()
            bundle = Engine(api_key, setting('OPENAI_MODEL', 'gpt-5-mini'), ROOT / '.cache').generate_outputs(
                dataset, intelligence, sources, lambda value, label: bar.progress(value, label))
            run_store.save_bundle(bundle, intelligence)
            install_bundle(bundle)
            st.rerun()
        except Exception as exc:
            bar.empty()
            st.error(f'Output generation stopped ({type(exc).__name__}). Phase 2 results are retained.')
            if isinstance(exc, ValueError):
                st.error(str(exc))
            else:
                st.info('Check official-source availability, model access, quota, and network connectivity.')
    if not live_operator:
        st.info('Load saved outputs for preview. Unlock the workflow in the sidebar to generate or edit outputs.')
    if not intelligence and not bundle:
        st.info('Load saved Phase 2 insights here, or complete Review intelligence first.')
elif phase.startswith('4') and not bundle:
    st.info('Complete or load Phase 2 in Review intelligence, then generate the outputs in Phase 3 before approval.')

if live_operator and phase.startswith(('3', '4')):
    saved_runs = run_store.available(dataset)
    if saved_runs:
        with st.expander('Resume a saved live run'):
            selected_run = st.selectbox('Saved run for this CSV and report date', saved_runs)
            if st.button('Load saved live run'):
                try:
                    restored_intelligence, restored_bundle = run_store.load(selected_run, dataset)
                    install_intelligence(restored_intelligence)
                    install_bundle(restored_bundle)
                    st.rerun()
                except (ValueError, OSError) as exc:
                    st.error(str(exc))

if bundle and phase.startswith(('3', '4')):
    started = bool(st.session_state.get('receipts')) or bool(journal.find(bundle.run_id))
    if phase.startswith('3'):
        st.caption('You may edit the pulse. Edits must retain its headings, verified quotes, and exactly three action ideas. Fee bullets remain tied to their checked official evidence.')
        edited = st.text_area('Weekly product pulse', key='pulse_editor', height=400, disabled=started or not live_operator)
        changed = edited != bundle.weekly_pulse
        if changed:
            bundle = bundle.model_copy(update={'weekly_pulse': edited, 'run_id': uuid.uuid4().hex, 'pulse_edited': True})
            st.session_state.bundle = bundle
            st.session_state.pop('approval', None)
            st.session_state.pop('receipts', None)
        valid_outputs = False
        try:
            bundle.checks = validate_bundle(bundle, dataset, intelligence)
            if changed:
                run_store.save_bundle(bundle, intelligence)
            valid_outputs = True
        except (ValueError, OSError) as exc:
            st.warning(str(exc))
        st.caption(f'{len(bundle.weekly_pulse.split())}/250 pulse words · {len(bundle.explanation_bullets)}/6 fee bullets · Sources checked {bundle.last_checked}')
        with st.expander('Weekly pulse preview', expanded=True):
            st.markdown(bundle.weekly_pulse)
        st.markdown(explainer_markdown(bundle))
        st.caption('Fee facts passed an automated comparison with the official pages. Inspect the matched passages before approval.')
        with st.expander('Check fee claims against official source passages'):
            for grounded in bundle.fee_grounding:
                st.write(grounded['text'])
                st.caption('Official source IDs: ' + ', '.join(grounded['source_ids']))
                for passage in grounded['supporting_passages']:
                    st.text(passage)
            for source in bundle.sources:
                st.link_button(source.title, source.url)
                st.caption(f'Checked: {source.checked_at}')
        with st.expander('Document entry preview'):
            st.markdown(document_text(bundle))
            st.json(bundle.entry())
        email = email_content(bundle)
        with st.expander('Email draft preview'):
            st.text_input('Email subject preview', value=email['subject'], disabled=True)
            st.text_area('Email body preview', value=email['body'], height=320, disabled=True)
            st.caption('This is the complete draft text for the later approval step.')
        if valid_outputs:
            with st.expander('Phase 3 checkpoint', expanded=True):
                for check in bundle.checks:
                    st.success('PASS · ' + check)
                if bundle.intelligence_run_id:
                    st.caption('Outputs match the exact verified Phase 2 input.')
        st.download_button('Download weekly pulse', bundle.weekly_pulse, 'weekly_product_pulse.md', 'text/markdown', disabled=not valid_outputs)
        st.download_button('Download fee explanation', explainer_markdown(bundle), 'fee_explainer.md', 'text/markdown', disabled=not valid_outputs)
        st.download_button('Download document entry', json.dumps(bundle.entry(), ensure_ascii=False, indent=2), 'document_entry.json', 'application/json', disabled=not valid_outputs)
        st.download_button('Download email preview', 'Subject: ' + email['subject'] + '\n\n' + email['body'], 'email_draft_preview.txt', 'text/plain', disabled=not valid_outputs)
        st.download_button('Download complete analysis', bundle.model_dump_json(indent=2), 'groww_analysis.json', 'application/json', disabled=not valid_outputs)
    if phase.startswith('4'):
        st.subheader('Review, approve, and save')
        st.caption('Review the document entry and complete email below. Approve and save authorizes these two actions for this snapshot only, for 30 minutes.')
        doc_url = setting('GOOGLE_DOC_URL') if operator else ''
        if not operator:
            st.info('Unlock the live workflow to view its document destination and approve saving.')
        st.write('Document destination: ' + (doc_url or 'Not configured'))
        st.caption('Email destination: Drafts in the Gmail account connected in n8n. Recipient is left blank.')
        st.markdown(bundle.weekly_pulse)
        st.markdown(explainer_markdown(bundle))
        email = email_content(bundle)
        with st.expander('Full email draft preview', expanded=True):
            st.text_input('Subject', value=email['subject'], disabled=True)
            st.text_area('Email body', value=email['body'], height=320, disabled=True)
        with st.expander('Structured document entry'):
            st.json(bundle.entry())
        st.download_button('Download email draft text', email['subject'] + '\n\n' + email['body'], 'email_draft.txt')
        with st.expander('Phase 4 setup checkpoint', expanded=True):
            for key, label in [('DEMO_ACCESS_PASSWORD', 'App access password'), ('GOOGLE_DOC_URL', 'Target Google Doc'),
                               ('N8N_MCP_URL', 'Published n8n Cloud MCP URL'), ('N8N_MCP_TOKEN', 'MCP bearer token')]:
                st.write(('✓ Configured · ' if setting(key) else '○ Required · ') + label)
            st.caption('Configure local values in .streamlit/secrets.toml. Keep the bearer token out of chat. Import instructions: docs/PHASE4.md.')
        ready = False
        try:
            validate_bundle(bundle, dataset, intelligence)
            payload = prepare_payload(bundle, doc_url)
            transport = N8nMCP(setting('N8N_MCP_URL'), setting('N8N_MCP_TOKEN'))
            if operator:
                st.session_state.receipts = journal.load(payload)
            started = bool(st.session_state.get('receipts'))
            ready = live_operator
            if demo_mode:
                st.info('Saved demo preview. Switch to Live upload and analysis and review this snapshot again to approve saving.')
            else:
                st.success('Output checks passed. Saving still requires your approval below.')
            st.caption('Run ID: ' + bundle.run_id + ' · Content fingerprint: ' + fingerprint(payload))
        except ValueError as exc:
            st.info(str(exc))
        if st.button('Check MCP connection (read only)', disabled=not (ready and operator)):
            try:
                available = asyncio.run(transport.inspect())
                st.success('MCP initialization and tool discovery passed. No write tools called.')
            except Exception:
                st.error('MCP connection failed. Check the published production URL, bearer authentication, and workflow configuration.')
        left, right = st.columns(2)
        if left.button('Approve and save', type='primary', disabled=not ready or started):
            st.session_state.approval = approve(payload)
            st.session_state.receipts = {}
            st.session_state.pop('rejected', None)
            try:
                with st.spinner('Saving the approved snapshot through MCP…'):
                    execute_approved(payload, st.session_state.approval, st.session_state.receipts, transport, journal)
                st.rerun()
            except (ValueError, OSError) as exc:
                st.error(str(exc))
        if right.button('Reject', disabled=started):
            st.session_state.approval = None
            st.session_state.rejected = bundle.run_id
        if st.session_state.get('rejected') == bundle.run_id:
            st.info('Rejected. No document or Gmail action was taken.')
        if ready and st.button('Refresh remote receipts (read only)'):
            try:
                recovered = asyncio.run(transport.receipts(payload))
                st.session_state.receipts = journal.reconcile(payload, recovered)
                if recovered:
                    st.rerun()
                else:
                    st.info('No remote receipt found. Existing uncertain attempts remain paused; inspect n8n executions and the destination.')
            except Exception:
                st.error('Could not verify remote receipts. Writes remain paused.')
        receipts = st.session_state.get('receipts', {})
        st.dataframe(pd.DataFrame([{'Action': a, 'Status': receipts.get(a, {}).get('status', 'not started')} for a in ACTIONS]), hide_index=True)
        if receipts and operator:
            st.markdown('**Execution receipts**')
            st.json(receipts)
            st.download_button('Download execution receipts', json.dumps(receipts, indent=2), 'execution_receipts.json')
            saved = journal.find(bundle.run_id)
            record = {'run_id': bundle.run_id, 'approved_content_fingerprint': saved.get('payload_hash'),
                      'approval_timestamp': saved.get('approval', {}).get('approved_at'), 'actions': receipts}
            st.download_button('Download approval and execution record', json.dumps(record, indent=2), 'approval_execution_record.json')
            if all(receipts.get(a, {}).get('status') == 'succeeded' for a in ACTIONS):
                if ready:
                    st.success('PASS · The approved document entry and unsent Gmail draft were created.')
                    st.link_button('Open updated Google Doc', receipts[ACTIONS[0]]['document_url'])
                    st.link_button('Open Gmail Drafts', 'https://mail.google.com/mail/u/0/#drafts')
                else:
                    st.warning('Completed receipts are retained, but the current preview or destination could not be verified against this run.')
            elif any(r.get('status') in ('unknown', 'in_progress') for r in receipts.values()):
                st.warning('An outcome is unconfirmed. Inspect n8n executions and the destination. Do not start another run to retry this write.')
            elif ready:
                st.info('Review the same preview again before approving the remaining actions. Confirmed successful actions will be skipped.')
                if st.button('Approve and retry remaining actions'):
                    st.session_state.approval = approve(payload)
                    try:
                        execute_approved(payload, st.session_state.approval, receipts, transport, journal)
                        st.rerun()
                    except (ValueError, OSError) as exc:
                        st.error(str(exc))
