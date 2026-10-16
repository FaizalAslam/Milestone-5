from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from zoneinfo import ZoneInfo
from urllib.parse import urlparse

from .models import Bundle, ExplainerDraft, FeeBullet, FeeFactCheck, Source


def render_pulse(report_date, themes, quotes, draft, audit=None) -> str:
    context = (f"Context: {audit['window_start']}–{audit['window_end']}; data through {audit['data_cutoff']}."
               if audit else 'Counts cover the selected review context.')
    if audit:
        context += f" {audit['included_count']:,} reviews; {sum(t['count'] for t in themes):,} substantive."
    lines = [f'# Weekly Product Pulse — Groww — {report_date}', '', '## Top themes', context,
             '; '.join(f"{t['name']} ({t['count']})" for t in themes[:3]) + '.', draft.summary,
             '', '## Supporting user quotes']
    for quote in quotes:
        lines += ['', f'> “{quote["text"]}”']
    lines += ['', '## Key observation', draft.observation, '', '## Product action ideas']
    lines += [f'{i}. {text}' for i, text in enumerate(draft.actions, 1)]
    return '\n'.join(lines)


def explainer_markdown(bundle: Bundle) -> str:
    title = f'Understanding {bundle.fee_name}' if bundle.fee_name else bundle.identified_fee_issue
    return '\n'.join([f'# Customer clarification — {title}', '',
                      *[f'- {b}' for b in bundle.explanation_bullets], '',
                      *[f'Source {i}: {url}' for i, url in enumerate(bundle.source_links, 1)], '',
                      f'Last checked: {bundle.last_checked}'])


def fee_question(bundle: Bundle) -> str:
    """Frame the selected review issue as a question, without adding fee claims."""
    name = bundle.fee_name.strip()
    if name.casefold() == 'brokerage' or (not name and 'brokerage' in bundle.identified_fee_issue.casefold()):
        return 'How is brokerage calculated, and why can my total trade charges be higher?'
    return f'What is {name}, and how is it calculated?' if name else 'What does this fee cover, and how is it calculated?'


def fee_faq_markdown(bundle: Bundle) -> str:
    """Q&A presentation for the workspace; preserve previously approved exports."""
    return '\n'.join(['# Frequently Asked Fee Question', '', '## Question', fee_question(bundle),
                      '', '## Answer', *[f'- {b}' for b in bundle.explanation_bullets], '',
                      *[f'Source {i}: {url}' for i, url in enumerate(bundle.source_links, 1)], '',
                      f'Last checked: {bundle.last_checked}'])


def email_content(bundle: Bundle) -> dict:
    return {'subject': f'Weekly Product Pulse + Customer Clarification — Groww — {bundle.date}',
            'body': bundle.weekly_pulse + '\n\n---\n\nReusable support snippet\n\n' + explainer_markdown(bundle)}


def document_text(bundle: Bundle) -> str:
    return '\n\n'.join([f'Groww Product + Support Update | {bundle.date} | Run {bundle.run_id}',
                           'Top themes: ' + ', '.join(t['name'] for t in bundle.themes[:3]),
                           bundle.weekly_pulse,
                           'Identified fee issue: ' + bundle.identified_fee_issue,
                           explainer_markdown(bundle)]) + '\n\n'


def fingerprint(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def validate_sources(sources: list[Source]):
    if len(sources) != 2 or len({s.id for s in sources}) != 2 or len({s.url for s in sources}) != 2:
        raise ValueError('Exactly two distinct official fee sources are required.')
    if any(urlparse(s.url).hostname != 'groww.in' or urlparse(s.url).scheme != 'https' or not s.text.strip() for s in sources):
        raise ValueError('Fee explanations require retrieved official HTTPS Groww source text.')
    checked = {s.checked_at for s in sources}
    if len(checked) != 1 or any(date.fromisoformat(d) > datetime.now(ZoneInfo('Asia/Kolkata')).date() for d in checked):
        raise ValueError('Both official sources must share a valid, nonfuture check date.')


def validate_explainer(explainer: ExplainerDraft, sources: list[Source]):
    validate_sources(sources)
    if not 1 <= len(explainer.bullets) <= 6:
        raise ValueError('The fee explanation must contain one to six bullets.')
    if len({b.text.strip().casefold() for b in explainer.bullets}) != len(explainer.bullets):
        raise ValueError('Fee explanation bullets must not repeat.')
    source_map = {s.id: s for s in sources}
    used = set()
    for bullet in explainer.bullets:
        if not bullet.text.strip() or '\n' in bullet.text or '\r' in bullet.text:
            raise ValueError('Each fee bullet must be a nonempty paragraph on one line.')
        if 'upi' in bullet.text.casefold() and not all(term in bullet.text.casefold() for term in ('equity', 'mandate', 'balance')):
            raise ValueError('A UPI pricing bullet must explicitly refer to equity orders using UPI Mandate balance, not generic UPI funding.')
        if not bullet.source_ids or len(set(bullet.source_ids)) != len(bullet.source_ids) or not set(bullet.source_ids) <= source_map.keys():
            raise ValueError('A fee bullet is missing valid official source IDs.')
        if not 1 <= len(bullet.supporting_passages) <= 3:
            raise ValueError('Each fee bullet needs one to three exact supporting source passages.')
        for passage in bullet.supporting_passages:
            if not passage.strip() or not any(passage in source_map[sid].text for sid in bullet.source_ids):
                raise ValueError(f'A fee source passage did not match its cited official text: {passage!r}. Select an exact catalog passage.')
        for sid in bullet.source_ids:
            if not any(passage in source_map[sid].text for passage in bullet.supporting_passages):
                raise ValueError('Every cited source must supply a matching passage for that bullet.')
        used.update(bullet.source_ids)
    if used != set(source_map):
        raise ValueError('Both official sources must support the explanation.')


def validate_bundle(bundle: Bundle, dataset=None, intelligence=None) -> list[str]:
    if bundle.mode != 'openai_live':
        raise ValueError('Reference previews cannot be approved as a completed AI analysis.')
    if not 3 <= len(bundle.themes) <= 5 or len({t['id'] for t in bundle.themes}) != len(bundle.themes):
        raise ValueError('Expected three to five distinct themes.')
    total = bundle.audit['included_count']
    if sum(bundle.sentiment_counts.values()) != total:
        raise ValueError('Sentiment counts do not reconcile with the included reviews.')
    if any(not isinstance(t['count'], int) or t['count'] < 0 for t in bundle.themes):
        raise ValueError('Theme counts must be nonnegative integers.')
    if sum(t['count'] for t in bundle.themes) + bundle.non_substantive_count != total:
        raise ValueError('Theme and nonspecific-review counts do not reconcile.')
    if [t['count'] for t in bundle.themes] != sorted([t['count'] for t in bundle.themes], reverse=True):
        raise ValueError('Top themes must be ranked by review count.')
    if len(bundle.quotes) != 3 or len({q['review_key'] for q in bundle.quotes}) != 3:
        raise ValueError('Three distinct real quotes are required.')
    if not bundle.identified_fee_issue.strip() or len({q['text'] for q in bundle.fee_evidence}) < 3:
        raise ValueError('At least three distinct review texts must support the fee issue.')
    if not 1 <= len(bundle.weekly_pulse.split()) <= 250:
        raise ValueError('The weekly pulse must contain at most 250 words.')
    for heading in ['## Top themes', '## Supporting user quotes', '## Key observation', '## Product action ideas']:
        if bundle.weekly_pulse.count(heading) != 1:
            raise ValueError('Keep each required weekly-pulse heading exactly once.')
    actions = bundle.weekly_pulse.split('## Product action ideas', 1)[1].strip().splitlines()
    if len(actions) != 3 or any(not line.startswith(f'{i}. ') or not line[3:].strip() for i, line in enumerate(actions, 1)):
        raise ValueError('Keep exactly three numbered action ideas at the end of the pulse.')
    if any(q['text'] not in bundle.weekly_pulse for q in bundle.quotes):
        raise ValueError('The pulse must retain all three verified user quotes.')
    if {q.get('theme_id') for q in bundle.quotes} != {t['id'] for t in bundle.themes[:3]}:
        raise ValueError('The pulse quotes must cover the top three themes.')
    if not 1 <= len(bundle.explanation_bullets) <= 6 or any(not b.strip() for b in bundle.explanation_bullets):
        raise ValueError('Provide one to six nonempty fee explanation bullets.')
    if any('\n' in b or '\r' in b for b in bundle.explanation_bullets):
        raise ValueError('Each explanation bullet must be one paragraph on one line.')
    if len(bundle.fee_grounding) != len(bundle.explanation_bullets):
        raise ValueError('Every fee explanation bullet needs its official source grounding.')
    grounded = ExplainerDraft(bullets=[FeeBullet.model_validate(b) for b in bundle.fee_grounding])
    if [b.text for b in grounded.bullets] != bundle.explanation_bullets:
        raise ValueError('Fee explanation bullets differ from their checked source grounding.')
    validate_explainer(grounded, bundle.sources)
    fee_check = FeeFactCheck.model_validate(bundle.fee_fact_check)
    if not fee_check.supported or fee_check.concerns:
        raise ValueError('The official-source fee fact check must pass before exporting or approval.')
    expected = {s.url for s in bundle.sources}
    if len(expected) != 2 or set(bundle.source_links) != expected:
        raise ValueError('Exactly two verified official source links are required.')
    if any(urlparse(u).hostname != 'groww.in' or urlparse(u).scheme != 'https' for u in expected):
        raise ValueError('Fee explanations must link to official HTTPS Groww pages.')
    checked = date.fromisoformat(bundle.last_checked)
    if checked > datetime.now(ZoneInfo('Asia/Kolkata')).date() or any(s.checked_at != bundle.last_checked for s in bundle.sources):
        raise ValueError('The source-check date is inconsistent with the report or sources.')
    if dataset:
        audit = dataset.audit()
        if dataset.digest != bundle.dataset_sha256 or str(dataset.report_date) != bundle.date or json.dumps(audit, sort_keys=True) != json.dumps(bundle.audit, sort_keys=True):
            raise ValueError('The analysis does not match the uploaded dataset or reporting window.')
        originals = {r.key: r for r in dataset.reviews}
        for q in bundle.quotes + bundle.fee_evidence:
            original = originals.get(q['review_key'])
            if original is None or not q['text'].strip() or q['text'] not in original.review_text:
                raise ValueError('An evidence quote does not match an included review.')
            if q.get('date') != str(original.date) or q.get('source_url') != original.source_url:
                raise ValueError('Evidence dates and source links must match the original reviews.')
    if intelligence is not None:
        from .intelligence import validate_intelligence
        if dataset is not None:
            validate_intelligence(intelligence, dataset)
        if bundle.intelligence_run_id != intelligence.run_id or bundle.intelligence_fingerprint != fingerprint(intelligence.model_dump(exclude={'checks'})):
            raise ValueError('Phase 3 must identify the exact saved Phase 2 input.')
        for field in ('date', 'dataset_sha256', 'themes', 'sentiment_counts', 'non_substantive_count', 'quotes', 'fee_name', 'identified_fee_issue', 'fee_evidence'):
            if getattr(bundle, field) != getattr(intelligence, field):
                raise ValueError(f'Phase 3 changed its verified Phase 2 {field}.')
    return ['Review counts reconcile', 'Three source-matched user quotes',
            'Recurring fee evidence present', 'Pulse ≤250 words and exactly three actions',
            'Fee explanation ≤6 bullets with exact source grounding', 'Two official sources and last-checked date present']
