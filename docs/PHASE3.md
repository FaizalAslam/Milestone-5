# Phase 3 — Weekly pulse and fee explanation

**Current UI:** Upload & Processing automatically runs the review and output stages. Results Workspace contains insights, output tabs and the final approval panel. Data Quality & Audit contains filtering and evidence details. Demo opens the saved example read only. No sidebar/operator password is required; older phase names below describe backend milestones and CLI operations. See [UI redesign](UI_REDESIGN.md).
Phase 3 consumes the verified Phase 2 result. It generates the internal note, reusable support snippet, and complete document/email previews. Google Docs and Gmail writes belong to the later explicit approval step.

## 1. Load the verified insights

**Demo** loads the verified outputs read only. **Live** uploads automatically run review intelligence followed by output generation.

Use **25 July–16 October 2026** for the supplied CSV. The Results Workspace exposes three output tabs. Matching saved results are revalidated against the CSV, period, counts and source records before reuse.

For fresh generation, configure the server API key and upload the CSV in Live mode. **More exports and output options → Regenerate outputs** reuses verified review insights and rechecks official sources. The CLI can run this independently:

```powershell
.\.venv312\Scripts\python.exe scripts/run_pipeline.py --report-date 2026-10-16 --live --phase3
```

The saved Phase 2 JSON/assignments are not rewritten. Phase 3 records its exact parent run ID and content fingerprint so outputs cannot silently switch to a different fee issue, quote set or theme ranking.

## 2. Retrieve the official fee facts

The app fetches the current [Groww pricing page](https://groww.in/pricing) and [brokerage FAQ](https://groww.in/help/stocks%2C-f%26o-%26-ipo/searchable/how-much-is-the-brokerage). Redirects stay on official HTTPS Groww pages. Recognized fee content and a common actual check date are required; a failed retrieval stops generation.

The identified question is brokerage confusion, derived from five distinct review texts. Review allegations establish what needs explaining; published official text establishes the fee facts.

## 3. Write and validate the pulse

OpenAI produces a short summary, key observation and exactly three product action ideas. Code inserts the verified top-three counts, original quotes, report window, data cutoff and review totals. The **entire rendered note**, including headings and quotes, must stay within 250 whitespace-separated words. Failed output gets one bounded repair attempt.

The completed pulse is **149 words**. It reports customer experiences without asserting verified billing faults or financial-loss causation. Full-window counts are distinguished from the data cutoff; raw seven-day count changes are not presented as a trend.

## 4. Write and check the fee explanation

OpenAI writes at most six neutral bullets. It selects labelled spans from a catalog of the two retrieved sources; software inserts the exact original passages. Every cited source must support its bullet, and both pages must be used across the explanation.

A separate AI source review checks only the actual customer bullets against the full official text. It looks for unsupported rates/claims, missing minimum/cap context, conflated stock/F&O/account rules and explanations of individual disputes that the sources cannot establish. A failed assessment triggers one rewrite attempt. The writer and checker remain aids to human review, not proof of correctness.

The finished explainer has **four bullets**, two official links and **Last checked: 2026-10-16**. It distinguishes brokerage from total charges, includes the small-trade minimum rule, and identifies special MTF, NRI and equity UPI Mandate balance contexts. It does not adjudicate customer allegations or treat each partial fill as another order.

## 5. Inspect all previews

The page shows:

- Editable pulse for unsaved Live results, word/bullet counters and a rendered preview.
- Customer fee explanation with its source links/check date.
- Expandable official passages and the source check.
- Document preview, including the required six-field JSON entry.
- Exact email subject and complete body containing the pulse and reusable fee snippet.
- Six checkpoint checks and downloads for both Markdown outputs, document JSON, email text and complete analysis.

The subject is `Weekly Product Pulse + Customer Clarification — Groww — 2026-10-16`. The email remains a local preview until Phase 4 creates an unsent Gmail draft after approval.

Pulse edits invalidate approval and update every export only if validation passes. Invalid edits show the failed check and disable downloads; the last valid export is retained. Regeneration creates a new review snapshot and invalidates prior approval. Editing/regenerating is disabled after remote execution has started.

## 6. Verify the saved artifacts

```powershell
.\.venv312\Scripts\python.exe scripts/verify_phase3.py --save outputs/phase3_checkpoint.json
```

This uses no model or MCP calls. It reloads the original CSV, Phase 2 input and Phase 3 snapshot; checks lineage, counts, quotes, lengths, actions, source grounding and dates; and compares every saved output/preview with a fresh rendering of that snapshot. A missing, changed or mismatched preview fails verification.

See `outputs/phase3_verification.md` for the actual execution record. Review the official evidence before approving Phase 4 sharing.
