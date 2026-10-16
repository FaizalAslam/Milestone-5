"""Audit the model's Phase 2 output against original, included CSV records."""
from collections import Counter
from datetime import timedelta
import json

from .data import Dataset
from .models import ReviewIntelligence


def validate_named_fee(fee_name: str, issue: str):
    name = fee_name.casefold().strip()
    if len(name) < 2 or name in {'fee', 'fees', 'charge', 'charges', 'deduction', 'deductions', 'hidden charges',
                                'unclear charges', 'unexpected deductions', 'other charges', 'taxes'}:
        raise ValueError('Choose one named fee, not a generic category of unexplained deductions.')
    if name not in issue.casefold():
        raise ValueError('The fee issue title must explicitly identify the selected named fee.')
    if '_' in issue:
        raise ValueError('Write the fee issue as a readable English phrase with spaces, not a code identifier.')


def validate_intelligence(result: ReviewIntelligence, dataset: Dataset) -> list[str]:
    def require(condition, message):
        if not condition:
            raise ValueError(message)

    audit = dataset.audit()
    require(result.dataset_sha256 == dataset.digest and result.date == str(dataset.report_date),
            'Analysis belongs to a different dataset or report date.')
    # JSON object keys (such as rating counts) become strings when saved.
    require(json.dumps(result.audit, sort_keys=True) == json.dumps(audit, sort_keys=True, default=str),
            'Analysis uses a different reporting window or dataset audit.')
    require(bool(result.run_id.strip()) and bool(result.model.strip()), 'Analysis metadata is missing.')
    ids = [t.get('id') for t in result.themes]
    require(3 <= len(ids) <= 5 and len(set(ids)) == len(ids) and
            all(i in ('T1', 'T2', 'T3', 'T4', 'T5') for i in ids),
            'Expected three to five distinct substantive themes with IDs T1–T5.')
    require(all(isinstance(t.get(field), str) and t[field].strip()
                for t in result.themes for field in ('name', 'description')),
            'Every theme needs a name and description.')
    require(len({t['name'].strip().casefold() for t in result.themes}) == len(ids), 'Theme names must be distinct.')
    original = {r.key: r for r in dataset.reviews}
    assignments = {a.review_key: a for a in result.assignments}
    require(len(assignments) == len(result.assignments) and set(assignments) == set(original),
            'Every included review must have exactly one classification.')
    sentiments, counts, current, previous = Counter(), Counter(), Counter(), Counter()
    nonspecific = 0
    cutoff = max(r.date for r in dataset.reviews)
    latest_start = cutoff - timedelta(days=6)
    previous_start = latest_start - timedelta(days=7)
    by_text = {}
    for key, assignment in assignments.items():
        r = original[key]
        require(assignment.text_key == r.text_key, 'Classification text fingerprint does not match its source.')
        require((assignment.substantive and assignment.theme_id in ids) or
                (not assignment.substantive and assignment.theme_id is None), 'Invalid primary theme assignment.')
        require(assignment.fee_issue is None or (assignment.substantive and bool(assignment.fee_issue.strip())),
                'A fee confusion flag must refer to substantive feedback.')
        signature = (assignment.sentiment, assignment.substantive, assignment.theme_id, assignment.fee_issue)
        require(by_text.setdefault(r.text_key, signature) == signature, 'Repeated text has inconsistent classifications.')
        sentiments[assignment.sentiment] += 1
        if assignment.substantive:
            counts[assignment.theme_id] += 1
            if latest_start <= r.date <= cutoff:
                current[assignment.theme_id] += 1
            elif previous_start <= r.date < latest_start:
                previous[assignment.theme_id] += 1
        else:
            nonspecific += 1
    require(dict(sentiments) == result.sentiment_counts, 'Sentiment counts do not reconcile with review classifications.')
    require(nonspecific == result.non_substantive_count, 'Nonspecific feedback count does not reconcile.')
    for theme in result.themes:
        for field, expected in [('count', counts[theme['id']]), ('current_week', current[theme['id']]),
                                ('previous_week', previous[theme['id']])]:
            require(type(theme.get(field)) is int and theme[field] == expected,
                    f'Theme {theme["id"]} {field} does not reconcile with source reviews.')
    require(result.themes == sorted(result.themes, key=lambda t: (-t['count'], t['id'])),
            'Themes must be ranked by review count.')
    require(all(t['count'] > 0 for t in result.themes[:3]), 'Three populated top themes are required.')

    def verify_evidence(item, full_text=False):
        key = item.get('review_key')
        require(key in original, 'Evidence refers to an excluded or unknown review.')
        r = original[key]
        text = item.get('text', '')
        require(isinstance(text, str) and bool(text.strip()) and (text == r.review_text if full_text else text in r.review_text),
                'Evidence is not an exact original review excerpt.')
        require(item.get('date') == str(r.date) and item.get('source_url') == r.source_url,
                'Evidence date or source URL does not match the original review.')
        return r, assignments[key]

    require(len(result.quotes) == 3 and len({q.get('review_key') for q in result.quotes}) == 3,
            'Exactly three distinct user quotes are required.')
    quote_themes = set()
    for quote in result.quotes:
        r, assignment = verify_evidence(quote)
        require(4 <= len(quote['text'].split()) <= 25, 'Use a meaningful 4–25-word user excerpt, not an isolated UI label.')
        require(quote.get('theme_id') == assignment.theme_id, 'Quote theme does not match its review classification.')
        quote_themes.add(assignment.theme_id)
    require(quote_themes == {t['id'] for t in result.themes[:3]}, 'Quotes must represent all three top themes.')
    require(bool(result.identified_fee_issue.strip()) and bool(result.fee_rationale.strip()),
            'The recurring fee issue needs a specific label and evidence rationale.')
    validate_named_fee(result.fee_name, result.identified_fee_issue)
    require(3 <= len(result.fee_evidence) <= 8, 'Select three to eight supporting fee review texts.')
    fee_texts = set()
    for evidence in result.fee_evidence:
        r, assignment = verify_evidence(evidence, full_text=True)
        require(bool(assignment.fee_issue), 'Fee evidence must come from a review classified as fee confusion.')
        passage = evidence.get('confusion_passage', '')
        require(isinstance(passage, str) and bool(passage.strip()) and passage in r.review_text,
                'Fee confusion passage must match the original text.')
        selected = evidence.get('selected_fee_passage', '')
        require(isinstance(selected, str) and bool(selected.strip()) and selected in r.review_text
                and result.fee_name.casefold().strip() in selected.casefold(),
                'Each supporting review must have an exact passage naming the selected fee.')
        fee_texts.add(r.text_key)
    require(len(fee_texts) == len(result.fee_evidence), 'Repeated text cannot establish independent fee confusion.')
    return ['One classification per included review; weighted counts reconcile',
            'Three to five themes; top three ranked by substantive review count',
            'All-review sentiment separated from nonspecific feedback',
            'Three exact quotes cover the top three themes with original IDs, dates, and URLs',
            'One named fee supported by exact passages in at least three distinct original review texts',
            'Latest and preceding seven-day counts reconcile; coverage disclosed']


def intelligence_markdown(result: ReviewIntelligence) -> str:
    audit = result.audit
    lines = [f'# Groww Review Intelligence — {result.date}', '',
             f'Model: {result.model} · Run: {result.run_id}', '',
             f'Window: {audit["window_start"]} to {audit["window_end"]}. Data cutoff: {audit["data_cutoff"]}.',
             f'{audit["included_count"]:,} included reviews; {audit["unique_texts"]:,} distinct texts.', '',
             'Theme descriptions summarize customer reports and requests; reported problems and losses are not independently verified.', '',
             '## Top three themes', '']
    for rank, theme in enumerate(result.themes[:3], 1):
        lines.append(f'{rank}. **{theme["name"]}** — {theme["count"]:,} reviews. {theme["description"]}')
    lines += ['', '## All themes and comparison', '',
              '| Theme | Full window | Latest 7 days | Preceding 7 days |', '| --- | ---: | ---: | ---: |']
    for t in result.themes:
        lines.append(f'| {t["name"]} | {t["count"]} | {t["current_week"]} | {t["previous_week"]} |')
    for name, period in audit['comparison_periods'].items():
        lines += ['', f'{name.title()}: {period["start"]} to {period["end"]}; {period["reviews"]} reviews. '
                  f'Dates without observed reviews: {", ".join(period["missing_observed_dates"]) or "none"}.']
    lines += ['', 'Counts reflect the available reviews; a date without reviews does not prove missing collection. '
              'The cutoff day may be partial. Raw count changes alone do not establish a product trend.', '',
              '## Sentiment', '', ', '.join(f'{k}: {v:,}' for k, v in sorted(result.sentiment_counts.items())),
              f'Nonspecific feedback: {result.non_substantive_count:,}. Theme counts cover substantive feedback only.', '',
              '## Three source-matched quotes', '']
    for q in result.quotes:
        lines += [f'> {q["text"]}', '', f'{q["date"]} · {q["review_key"]} · [Review source]({q["source_url"]})', '']
    lines += ['## Recurring fee confusion', '', f'Named fee: **{result.fee_name}**', '', result.identified_fee_issue, '', result.fee_rationale, '',
              'These are customer reports. Phase 3 checks official fee facts before generating an explanation.', '']
    for e in result.fee_evidence:
        lines += [f'> {e["text"]}', '', f'{e["date"]} · {e["review_key"]} · [Review source]({e["source_url"]})', '',
                  f'Confusion passage: {e["confusion_passage"]}', '', f'Selected fee passage: {e["selected_fee_passage"]}', '']
    lines += ['## Automated checkpoint', ''] + [f'- PASS: {check}' for check in result.checks]
    return '\n'.join(lines) + '\n'
