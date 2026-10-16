"""Wireframe UI controller. All model credentials, approval and MCP access stay in Python."""
from __future__ import annotations

import asyncio
import base64
import csv
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import threading
import time
import uuid
from zoneinfo import ZoneInfo

from .analysis import Engine
from .approval import ACTIONS, N8nMCP, approve, execute_approved, prepare_payload
from .data import DataError, Dataset, load_csv
from .execution import ExecutionJournal
from .export import bundle_artifacts, classifications_csv
from .intelligence import intelligence_markdown
from .models import Bundle, ReviewIntelligence
from .outputs import email_content, fee_faq_markdown, fee_question, fingerprint, validate_bundle
from .runstore import LiveRunStore
from .sources import fetch_sources


@dataclass
class Task:
    status: str = 'processing'
    stage: int = 1
    progress: float = 0.02
    message: str = 'Checking the uploaded reviews…'
    intelligence: ReviewIntelligence | None = None
    bundle: Bundle | None = None
    partial: dict | None = None
    error: str = ''
    error_kind: str = ''
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    cancelled: threading.Event = field(default_factory=threading.Event)
    lock: threading.RLock = field(default_factory=threading.RLock)


class Cancelled(Exception):
    pass


class Workspace:
    def __init__(self, root: Path, settings: dict, *, today: date | None = None,
                 engine_factory=Engine, source_fetcher=fetch_sources, start_threads=True):
        self.root = Path(root)
        self.settings = settings
        self.today = today or datetime.now(ZoneInfo('Asia/Kolkata')).date()
        self.id = uuid.uuid4().hex
        self.start_date = self.today - timedelta(days=83)
        self.end_date = self.today
        self.mode = 'Live'
        self.filename = ''
        self.raw: bytes | None = None
        self.dataset: Dataset | None = None
        self.task: Task | None = None
        self.rejected = False
        self.edited = False
        self.notice = ''
        self.error = ''
        self.error_kind = ''
        self.connection = 'Configured' if all(settings.get(k) for k in ('N8N_MCP_URL', 'N8N_MCP_TOKEN', 'GOOGLE_DOC_URL')) else 'Setup needed'
        self.saving = False
        self.save_error = ''
        self.audit_filter = 'all'
        self.audit_search = ''
        self.audit_page = 1
        self.download = None
        self.engine_factory = engine_factory
        self.source_fetcher = source_fetcher
        self.start_threads = start_threads
        self.journal = ExecutionJournal(self.root / '.cache/approval_runs.sqlite3')
        self.store = LiveRunStore(self.root / 'outputs/private/runs')
        self._lock = threading.RLock()
        self._events: set[str] = set()
        self._audit_cache = None
        self.last_seen = time.time()

    @property
    def busy(self):
        return self.saving or bool(self.task and self.task.status == 'processing')

    def update_settings(self, settings):
        self.settings = settings

    def _spawn(self, fn, *args):
        if self.start_threads:
            threading.Thread(target=fn, args=args, daemon=True).start()

    def _cancel_analysis(self):
        if self.task and self.task.status == 'processing':
            self.task.cancelled.set()
            self.task.status = 'cancelled'
            self.task.finished_at = time.time()

    def set_period(self, start, end):
        start, end = date.fromisoformat(start), date.fromisoformat(end)
        if end > self.today or not 56 <= (end - start).days + 1 <= 84:
            raise ValueError('Choose an 8–12 week reporting window ending today or earlier.')
        self.start_date, self.end_date = start, end

    def upload(self, raw: bytes, filename: str, *, start=None, end=None):
        if self.saving:
            raise ValueError('Wait until the current save result is confirmed before replacing this dataset.')
        if self.mode != 'Live':
            raise ValueError('Start a new analysis before uploading another CSV.')
        if start is not None or end is not None:
            self.set_period(start or self.start_date.isoformat(), end or self.end_date.isoformat())
        # Validate before submitting any model request. Replacing an invalid upload clears its old preview.
        self._cancel_analysis()
        self.raw, self.filename = raw, filename.replace('\\', '/').split('/')[-1][:180]
        self.task = None
        self.dataset = None
        self._audit_cache = None
        self.audit_filter, self.audit_search, self.audit_page = 'all', '', 1
        self.save_error = ''
        self.rejected = self.edited = False
        self.notice = self.error = self.error_kind = ''
        try:
            self.dataset = load_csv(raw, self.end_date, 12, start_date=self.start_date)
        except DataError as exc:
            self.error, self.error_kind = str(exc), 'csv'
            return
        if len(self.dataset.reviews) < 3:
            self.error = 'There are fewer than three valid reviews in this reporting window. Adjust the period or upload another CSV.'
            self.error_kind = 'coverage'
            return
        self.task = Task()
        self._spawn(self.run_analysis, self.task, self.dataset)

    def _cached_result(self, dataset):
        for run_id in self.store.available(dataset):
            intelligence, bundle = self.store.load(run_id, dataset)
            if bundle.last_checked == self.today.isoformat():
                return intelligence, bundle
        return None

    def run_analysis(self, task: Task, dataset: Dataset):
        def progress(stage, value, label):
            if task.cancelled.is_set():
                raise Cancelled()
            with task.lock:
                task.stage, task.progress, task.message = stage, max(0, min(value, 1)), label

        engine = None
        try:
            cached = None if task.intelligence else self._cached_result(dataset)
            if cached:
                task.intelligence, task.bundle = cached
                progress(3, 1, 'Verified saved analysis restored for this exact CSV and reporting period.')
            else:
                key = self.settings.get('OPENAI_API_KEY', '')
                if not key:
                    raise ValueError('Analysis is not configured on this server. The app owner must configure the OpenAI API key.')
                engine = self.engine_factory(key, self.settings.get('OPENAI_MODEL', 'gpt-5-mini'),
                                             self.root / '.cache', int(self.settings.get('OPENAI_MAX_WORKERS', '4')))
                intelligence = task.intelligence
                if intelligence is None:
                    progress(2, .04, 'Identifying recurring customer themes…')
                    intelligence = engine.analyze_reviews(dataset,
                        lambda value, label: progress(2, .05 + value * .68, label))
                    task.intelligence = intelligence
                    self.store.save_intelligence(intelligence, dataset)
                progress(3, .75, 'Checking official fee information…')
                sources = self.source_fetcher()
                task.bundle = engine.generate_outputs(dataset, intelligence, sources,
                    lambda value, label: progress(3, .76 + value * .23, label))
                self.store.save_bundle(task.bundle, intelligence)
            if task.cancelled.is_set():
                raise Cancelled()
            task.status, task.progress, task.stage = 'ready', 1, 3
            task.message = 'Analysis and output checks passed. Ready for your review.'
        except Cancelled:
            task.status, task.message = 'cancelled', 'Processing cancelled. No document or Gmail action was taken.'
        except Exception as exc:
            task.status = 'blocked'
            task.partial = getattr(engine, 'partial_insights', None)
            message = str(exc) if isinstance(exc, ValueError) else ''
            if 'fee' in message.lower() and task.intelligence is None:
                task.error_kind = 'fee_evidence'
                task.error = 'We couldn’t establish a recurring fee-related issue from at least three distinct review texts.'
            elif 'populated' in message or 'three valid' in message:
                task.error_kind = 'feedback'
                task.error = 'There isn’t enough useful feedback to establish three supported themes in this reporting window.'
            elif task.stage == 3 and task.bundle is None:
                task.error_kind = 'sources' if task.progress < .8 else 'outputs'
                task.error = message or 'The fee sources or generated outputs could not be verified. Existing review insights are retained.'
            else:
                task.error_kind = 'analysis'
                task.error = message or f'Analysis stopped ({type(exc).__name__}). Retry to resume validated cached work.'
        finally:
            task.finished_at = time.time()

    def new_live(self):
        if self.saving:
            raise ValueError('Wait for the current save result before starting another analysis.')
        self._cancel_analysis()
        self.mode, self.filename, self.raw, self.dataset, self.task = 'Live', '', None, None, None
        self.start_date, self.end_date = self.today - timedelta(days=83), self.today
        self.error = self.error_kind = self.notice = ''
        self.rejected = self.edited = False
        self._audit_cache = None
        self.audit_filter, self.audit_search, self.audit_page = 'all', '', 1
        self.save_error = ''

    def _payload(self):
        if not self.task or not self.task.bundle or not self.dataset:
            raise ValueError('Generate and validate both outputs before approval.')
        validate_bundle(self.task.bundle, self.dataset, self.task.intelligence)
        return prepare_payload(self.task.bundle, self.settings.get('GOOGLE_DOC_URL', ''))

    def _states(self):
        if self.mode != 'Live' or not self.task or not self.task.bundle:
            return {}
        # Successful receipts remain visible even when destination configuration is later changed.
        record = self.journal.find(self.task.bundle.run_id)
        return record.get('states', {})

    def _assert_snapshot(self, expected):
        if self.mode != 'Live':
            raise ValueError('An active uploaded-review workspace is required before external writes.')
        if not self.task or self.task.status != 'ready':
            raise ValueError('Wait until analysis and output verification have finished before approving.')
        payload = self._payload()
        if expected != fingerprint(payload):
            raise ValueError('This preview changed. Review the current content before approving it.')
        return payload

    def save(self, expected, *, retry=False):
        with self._lock:
            if self.saving:
                return
            payload = self._assert_snapshot(expected)
            states = self.journal.load(payload)
            if any(r.get('status') in ('unknown', 'in_progress') for r in states.values()):
                raise ValueError('The previous outcome must be reconciled before another write attempt.')
            if all(states.get(a, {}).get('status') == 'succeeded' for a in ACTIONS):
                return
            if states and not retry:
                raise ValueError('Use the reviewed retry action for a confirmed safe failure.')
            if any(r.get('status') == 'failed' and r.get('safe_to_retry') is not True for r in states.values()):
                raise ValueError('This outcome is not confirmed safe to retry.')
            transport = N8nMCP(self.settings.get('N8N_MCP_URL', ''), self.settings.get('N8N_MCP_TOKEN', ''))
            # Only this explicit UI action creates approval. No model can invoke this controller.
            approval = approve(payload)
            self.saving, self.rejected, self.save_error = True, False, ''
            self._spawn(self._run_save, payload, approval, transport)

    def _run_save(self, payload, approval, transport):
        try:
            execute_approved(payload, approval, {}, transport, self.journal)
        except Exception as exc:
            self.save_error = str(exc) if isinstance(exc, ValueError) else 'The save result needs checking. Completed actions are retained.'
        finally:
            self.saving = False

    def reconcile(self):
        if self.mode != 'Live' or self.saving:
            return
        payload = self._payload()
        self.saving = True
        self._spawn(self._run_reconcile, payload)

    def _run_reconcile(self, payload):
        try:
            transport = N8nMCP(self.settings.get('N8N_MCP_URL', ''), self.settings.get('N8N_MCP_TOKEN', ''))
            found = asyncio.run(transport.receipts(payload))
            self.journal.reconcile(payload, found)
            self.notice = 'Remote results checked.' if found else 'No confirmed remote receipt was found. Uncertain writes remain paused for inspection.'
            self.save_error = ''
        except Exception:
            self.save_error = 'Could not confirm the remote result. Writes remain paused; check n8n and the destination.'
        finally:
            self.saving = False

    def edit_pulse(self, text, expected):
        if self.mode != 'Live' or not self.task or not self.task.bundle:
            raise ValueError('Only a live output can be edited.')
        if expected != fingerprint(self.task.bundle.model_dump()):
            raise ValueError('This draft changed. Reopen the current editor before saving your changes.')
        if self._states() or self.saving:
            raise ValueError('A snapshot with recorded save attempts cannot be edited. Start another analysis instead.')
        candidate = self.task.bundle.model_copy(update={'weekly_pulse': text, 'run_id': uuid.uuid4().hex, 'pulse_edited': True})
        # Keep an invalid edit visible so the user can correct it; approval stays disabled.
        self.task.bundle = candidate
        self.edited, self.rejected = True, False
        try:
            validate_bundle(candidate, self.dataset, self.task.intelligence)
            self.store.save_bundle(candidate, self.task.intelligence)
            self.notice = 'Changes saved. Fresh approval is required.'
        except ValueError as exc:
            self.notice = str(exc)

    def audit_rows(self):
        if not self.dataset:
            return []
        source = self.task.intelligence if self.task and self.task.intelligence else None
        signature = (self.dataset.digest, id(source), id(self.task.partial) if self.task else 0)
        if self._audit_cache and self._audit_cache[0] == signature:
            return self._audit_cache[1]
        rows = list(self.dataset.exclusions)
        assignments = source.assignments if source else (self.task.partial or {}).get('assignments', []) if self.task else []
        nonspecific = {a['review_key'] if isinstance(a, dict) else a.review_key for a in assignments
                       if not (a['substantive'] if isinstance(a, dict) else a.substantive)}
        for r in self.dataset.reviews:
            if r.key in nonspecific:
                rows.append(dict(row='', review_id=r.review_id, platform=r.platform, date=str(r.date),
                    review_text=r.review_text, source_url=r.source_url, category='nonspecific',
                    reason='Nonspecific feedback: retained for sentiment/counts, excluded from themes and quotes.', text_hash=r.text_key))
        self._audit_cache = signature, rows
        return rows

    def _download(self, kind):
        rows = self.audit_rows()
        bundle = self.task.bundle if self.task else None
        intelligence = self.task.intelligence if self.task else None
        if kind == 'excluded':
            output = io.StringIO(newline='')
            fields = ['row', 'review_id', 'platform', 'date', 'category', 'reason', 'review_text', 'source_url', 'text_hash']
            writer = csv.DictWriter(output, fieldnames=fields)
            writer.writeheader()
            writer.writerows(r for r in rows if r['category'] != 'nonspecific')
            name, content, mime = 'review_exclusions.csv', output.getvalue(), 'text/csv'
        elif kind == 'classifications' and intelligence:
            name, content, mime = 'review_classifications.csv', classifications_csv(intelligence, self.dataset), 'text/csv'
        elif kind == 'intelligence' and intelligence:
            name, content, mime = 'review_intelligence.md', intelligence_markdown(intelligence), 'text/markdown'
        elif kind == 'audit' and self.dataset:
            name, content, mime = 'dataset_audit.json', json.dumps(self.dataset.audit(), indent=2), 'application/json'
        elif kind == 'receipts' and self.mode == 'Live' and bundle:
            name, content, mime = 'approval_execution_record.json', json.dumps(self.journal.find(bundle.run_id), indent=2), 'application/json'
        elif bundle and kind in bundle_artifacts(bundle):
            name, content, mime = kind, bundle_artifacts(bundle)[kind], 'text/plain'
        else:
            raise ValueError('This download is not available for the current result.')
        self.download = {'id': uuid.uuid4().hex, 'name': name, 'content': content, 'mime': mime}

    def handle(self, event):
        if not isinstance(event, dict) or not isinstance(event.get('id'), str) or not isinstance(event.get('type'), str):
            return
        if event['id'] in self._events:
            return
        self._events.add(event['id'])
        args, action = event.get('payload') or {}, event['type']
        self.error = '' if not self.error_kind else self.error
        try:
            if action == 'upload':
                encoded = args.get('content', '')
                if not isinstance(encoded, str) or len(encoded) > 21 * 1024 * 1024:
                    raise ValueError('Upload a CSV of at most 15 MB.')
                self.upload(base64.b64decode(encoded, validate=True), str(args.get('name', 'reviews.csv')),
                            start=args.get('start'), end=args.get('end'))
            elif action == 'example':
                raise ValueError('Saved Demo mode has been removed. Upload a reviews CSV to start an analysis.')
            elif action == 'new':
                self.new_live()
            elif action == 'period':
                if self.saving:
                    raise ValueError('Wait for the current save to finish before changing the period.')
                self.set_period(args['start'], args['end'])
                if self.raw:
                    self.upload(self.raw, self.filename)
            elif action == 'cancel':
                self._cancel_analysis()
            elif action == 'retry_analysis':
                if self.mode == 'Live' and self.raw:
                    self.upload(self.raw, self.filename)
            elif action == 'regenerate':
                if self.mode != 'Live' or self.busy or not self.task or not self.task.intelligence or self._states():
                    raise ValueError('Only an unsaved live result with verified review insights can be regenerated.')
                intelligence = self.task.intelligence
                self.task = Task(stage=3, progress=.75, intelligence=intelligence,
                                 message='Checking official sources and regenerating outputs…')
                self.rejected = self.edited = False
                self.notice = 'Outputs are being regenerated. Fresh approval will be required.'
                self._spawn(self.run_analysis, self.task, self.dataset)
            elif action in ('approve', 'retry_save'):
                self.save(args.get('fingerprint'), retry=action == 'retry_save')
            elif action == 'reject':
                if self.mode != 'Live' or self.saving or self._states():
                    raise ValueError('Only an unsaved live preview can be rejected.')
                self.rejected = True
                self.notice = 'Rejected — no external actions were performed.'
            elif action == 'reconcile':
                self.reconcile()
            elif action == 'edit':
                self.edit_pulse(str(args.get('text', '')), args.get('revision'))
            elif action == 'audit_filter':
                self.audit_filter = str(args.get('filter', 'all'))
                self.audit_search = str(args.get('search', ''))[:300]
                self.audit_page = max(1, int(args.get('page', 1)))
            elif action == 'download':
                self._download(str(args.get('kind', '')))
            elif action == 'verify_hash':
                self.notice = ('Original upload fingerprint verified. The file has not been altered.'
                               if self.raw and self.dataset and hashlib.sha256(self.raw).hexdigest() == self.dataset.digest
                               else 'Upload a valid CSV before checking its original fingerprint.')
        except (ValueError, KeyError, TypeError) as exc:
            self.notice = str(exc) if not isinstance(exc, KeyError) else 'This action is missing required data. Reload the current preview.'

    def view(self):
        self.last_seen = time.time()
        task, dataset = self.task, self.dataset
        intelligence = task.intelligence if task else None
        bundle = task.bundle if task else None
        partial = task.partial or {} if task else {}
        audit = dataset.audit() if dataset else {}
        themes = intelligence.themes if intelligence else partial.get('themes', [])
        quotes = intelligence.quotes if intelligence else partial.get('quotes', [])
        nonspecific = intelligence.non_substantive_count if intelligence else partial.get('non_substantive_count')
        rows = self.audit_rows()
        category_counts = {key: sum(r['category'] == key for r in rows) for key in ('duplicate', 'invalid', 'outside', 'future', 'nonspecific')}
        filtered = [r for r in rows if (r['category'] != 'nonspecific' if self.audit_filter == 'all'
                                       else r['category'] == self.audit_filter)]
        if self.audit_search:
            term = self.audit_search.casefold()
            filtered = [r for r in filtered if term in ' '.join(str(v) for v in r.values()).casefold()]
        pages = max(1, (len(filtered) + 7) // 8)
        page = min(self.audit_page, pages)
        states = self._states()
        snapshot = ''
        valid, validation_error, destination_error = False, '', ''
        if bundle:
            try:
                validate_bundle(bundle, dataset, intelligence)
                valid = True
            except ValueError as exc:
                validation_error = str(exc)
            try:
                snapshot = fingerprint(self._payload())
                N8nMCP(self.settings.get('N8N_MCP_URL', ''), self.settings.get('N8N_MCP_TOKEN', ''))
            except ValueError as exc:
                destination_error = str(exc)
        snapshot_matches = bool(snapshot) and all(r.get('payload_hash') == snapshot for r in states.values())
        completed = snapshot_matches and all(states.get(a, {}).get('status') == 'succeeded' for a in ACTIONS)
        uncertain = any(r.get('status') in ('unknown', 'in_progress') for r in states.values())
        retryable = bool(states) and snapshot_matches and any(r.get('status') == 'failed' for r in states.values()) and not completed and not uncertain and all(
            r.get('status') == 'succeeded' or (r.get('status') == 'failed' and r.get('safe_to_retry') is True) for r in states.values())
        analysis = None
        if themes or intelligence:
            assignments = intelligence.assignments if intelligence else partial.get('assignments', [])
            by_key = {r.key: r for r in dataset.reviews}
            theme_views = []
            for theme in themes:
                members = [a for a in assignments if (a.get('theme_id') if isinstance(a, dict) else a.theme_id) == theme['id']]
                sentiment = {}
                supporting = []
                for member in members:
                    key = member.get('review_key') if isinstance(member, dict) else member.review_key
                    mood = member.get('sentiment') if isinstance(member, dict) else member.sentiment
                    sentiment[mood] = sentiment.get(mood, 0) + 1
                    if len(supporting) < 20:
                        r = by_key[key]
                        supporting.append(dict(review_key=r.key, text=r.review_text, date=str(r.date), source_url=r.source_url))
                theme_views.append(dict(theme, sentiment=sentiment, supporting=supporting))
            fee_evidence = intelligence.fee_evidence if intelligence else []
            analysis = {'themes': theme_views, 'quotes': quotes,
                'fee_name': intelligence.fee_name if intelligence else '',
                'fee_issue': intelligence.identified_fee_issue if intelligence else '',
                'fee_rationale': intelligence.fee_rationale if intelligence else '', 'fee_evidence': fee_evidence,
                'sentiment': intelligence.sentiment_counts if intelligence else partial.get('sentiment_counts', {})}
        outputs = None
        if bundle:
            email = email_content(bundle)
            outputs = {'weekly_pulse': bundle.weekly_pulse, 'word_count': len(bundle.weekly_pulse.split()),
                       'fee_question': fee_question(bundle), 'fee_faq_markdown': fee_faq_markdown(bundle),
                       'fee_bullets': bundle.explanation_bullets, 'sources': [
                           {'title': s.title, 'url': s.url, 'checked_at': s.checked_at} for s in bundle.sources],
                       'last_checked': bundle.last_checked, 'email': email, 'valid': valid,
                       'grounding': bundle.fee_grounding,
                       'validation_error': validation_error, 'edited': self.edited or bundle.pulse_edited,
                       'downloads': {k: v for k, v in bundle_artifacts(bundle).items()
                                     if k not in ('latest.json', 'official_fee_sources.json')} if valid else {},
                       'edit_revision': fingerprint(bundle.model_dump()),
                       'can_edit': self.mode == 'Live' and not states and not self.saving,
                       'entry': bundle.entry()}
        sample = self.root / 'data/reviews_sample.csv'
        return {'workspace_id': self.id, 'mode': self.mode, 'connection': self.connection, 'today': str(self.today),
                'period': {'start': str(self.start_date), 'end': str(self.end_date),
                           'weeks': round(((self.end_date - self.start_date).days + 1) / 7, 1)},
                'file': {'name': self.filename, 'bytes': len(self.raw) if self.raw else 0},
                'status': task.status if task else ('invalid' if self.error else 'empty'), 'busy': self.busy,
                'processing': {'stage': task.stage, 'progress': task.progress, 'message': task.message,
                               'elapsed': round((time.time() if task.status == 'processing'
                                                 else task.finished_at or task.started_at) - task.started_at)} if task else None,
                'error': self.error or (task.error if task else ''),
                'error_kind': self.error_kind or (task.error_kind if task else ''), 'notice': self.notice,
                'metrics': dict(audit, useful_count=len(dataset.reviews) - nonspecific if dataset and nonspecific is not None else None,
                                nonspecific_count=nonspecific,
                                coverage_start=str(min(r.date for r in dataset.reviews)) if dataset and dataset.reviews else None),
                'audit': {'counts': category_counts, 'rows': filtered[(page - 1) * 8:page * 8],
                          'filter': self.audit_filter, 'search': self.audit_search, 'page': page, 'pages': pages,
                          'filtered_count': len(filtered), 'excluded_count': len(dataset.exclusions) if dataset else 0,
                          'precedence': 'Schema & timestamp → Duplicate review ID → Reporting window'},
                'analysis': analysis, 'outputs': outputs,
                'execution': {'states': states, 'completed': completed, 'uncertain': uncertain, 'saving': self.saving,
                    'snapshot_matches_receipts': snapshot_matches,
                    'retryable': retryable, 'rejected': self.rejected, 'fingerprint': snapshot,
                    'can_approve': bool(self.mode == 'Live' and task and task.status == 'ready'
                                        and valid and snapshot and not destination_error and not states and not self.saving),
                    'doc_url': self.settings.get('GOOGLE_DOC_URL', '') if self.mode == 'Live' else '',
                    'destination_error': destination_error if self.mode == 'Live' and bundle else '', 'error': self.save_error},
                'download': self.download, 'sample_csv': sample.read_text(encoding='utf-8-sig') if sample.exists() else ''}


_registry: dict[str, Workspace] = {}
_registry_lock = threading.Lock()


def register_workspace(workspace):
    with _registry_lock:
        for key, old in list(_registry.items()):
            if time.time() - old.last_seen > 86400 and not old.busy:
                del _registry[key]
        _registry[workspace.id] = workspace
    return workspace


def recover_workspace(key):
    if not isinstance(key, str) or len(key) != 32:
        return None
    with _registry_lock:
        return _registry.get(key)
