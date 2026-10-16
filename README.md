# Groww Review Intelligence

Streamlit review workspace with OpenAI analysis, checked fee sources, explicit approval, and real MCP calls to n8n Cloud. n8n appends a Google Docs entry and creates a Gmail **draft**. There is no send operation.

## Current implementation and verification

- Dataset audit and Streamlit startup: verified locally against the supplied CSV.
- Phase 2 runs independently and has passed a live OpenAI run on both the sample and all 13,034 included reviews. It produces five themes, three source-matched quotes, named brokerage evidence, and downloadable per-review assignments.
- Phase 3 has passed live generation from that exact saved input: a 149-word pulse with three quotes/actions, four source-grounded fee bullets, and matching document/email previews. All 99 automated tests pass in the clean source bundle, including the Phase 4/5/6 checks.
- Phase 5 preparation: the default saved demo loads without secrets, live output storage is separate, and the clean GitHub deployment bundle passes a fresh-process smoke test. Actual hosted deployment remains pending account sign-in.
- MCP initialization, discovery, both action calls, and receipt lookup: verified against a loopback test MCP server using the actual Python SDK and Streamable HTTP.
- n8n JSON exports: graph references, Code-node syntax, approval rejection, and draft-only Gmail configuration checked locally. Import and Google-account execution require your n8n workspace and credentials.
- Hosted URL and real Google Docs/Gmail evidence: pending account configuration and deployment. No remote writes have been claimed as completed.
- Phase 6: an organized review packet, 2:04 captioned local demo, sample/source audit, deliverable checklist, file hashes, and editable link references are ready. Real account evidence and links remain explicitly pending.

Run the checks below for the latest results. `outputs/verification.md` records what was actually checked.

## 1. Run locally

Python 3.12 is the target. A working `.venv312` has been created in this workspace; the original `.venv` is preserved. The original launcher reported access denied; the new environment was verified independently without changing Windows security settings.

On a fresh machine with Python 3.12 installed:

```powershell
py -3.12 -m venv .venv312
.\.venv312\Scripts\python.exe -m pip install -r requirements.txt
```

In this prepared workspace, launch directly:

```powershell
.\.venv312\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8502
```

Open `http://127.0.0.1:8502`. `start.ps1` runs the same command. Port 8501 was already occupied during setup.

The app defaults to **Saved CSV demo**, with the original report window and real saved analysis loaded automatically. Select **Live upload and analysis** in the sidebar before uploading, generating, editing, or approving. The app saves live files in `outputs/private/runs/`; CLI pipeline exports retain the `outputs/` paths documented below.

`requirements-lock.txt` records the verified Windows environment; use `requirements.txt` on Streamlit Cloud. Do not upload either virtual environment.

## 2. Configure live analysis

If it does not already exist, copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`. Populate:

- `OPENAI_API_KEY`: your OpenAI API key.
- `OPENAI_MODEL`: defaults to `gpt-5-mini`; use an account-accessible Responses model supporting structured outputs.
- `OPENAI_MAX_WORKERS`: optional, defaults to `4` concurrent classification requests (range 1–8). Use `1` for accounts with tight rate limits. Completed requests remain cached if rate limits stop the run.
- `DEMO_ACCESS_PASSWORD`: a strong shared password for the operator/reviewer.

Keep the populated file out of Git. Restart the app after configuration. Unlock the workflow in the sidebar. API keys are never requested in the public app UI. Do not paste keys into chat or screenshots.

Choose **Review intelligence → Analyze reviews (Phase 2)**. This runs review analysis only; it does not retrieve fee facts, generate Phase 3 prose, or call MCP. First check it on `data/reviews_sample.csv`, then run the complete supplied CSV. The full CSV contains 6,130 distinct texts in the checked window, so the first full run makes approximately 154 classification calls plus theme discovery and evidence selection. This uses your API quota and may take several minutes. Progress is visible; completed batches resume from `.cache/` after interruption.

The cache is keyed by CSV fingerprint, report dates, model, and prompt version. It is excluded from Git. No API key is stored in it. Cached taxonomy, batches, and evidence are validated before reuse. An invalid cache file is preserved with an `.invalid-...json` name and replaced by a validated response. A fresh response that fails semantic checks gets one repair attempt before the run stops. API/network failures leave completed batches reusable.

Command-line audit, with no model or MCP calls:

```powershell
.\.venv312\Scripts\python.exe scripts/run_pipeline.py --report-date 2026-10-16
```

Run Phase 2 on the sample, saving its artifacts separately, then run the full CSV:

```powershell
.\.venv312\Scripts\python.exe scripts/run_pipeline.py --csv data/reviews_sample.csv --report-date 2026-10-16 --live --phase2 --output-dir outputs/private/sample
.\.venv312\Scripts\python.exe scripts/run_pipeline.py --report-date 2026-10-16 --live --phase2
```

Successful Phase 2 runs produce:

- `outputs/review_intelligence.md`: ranked themes, sentiment, three verbatim quotes, fee confusion, evidence, comparison coverage, and checkpoint results.
- `outputs/review_intelligence.json`: validated result, including every included review's classification and the input fingerprint.
- `outputs/review_classifications.csv`: original included review text, IDs, dates, ratings, URLs, sentiment, substantive flag, primary theme, and fee-confusion label. Repeated wording maps back to every original review.

In the app, inspect the top-three cards, theme table, sentiment chart, three quote cards, and expandable fee evidence. All six checkpoint checks must show PASS. Download the report, JSON, or classifications. **Load saved Phase 2 analysis** verifies the dataset fingerprint, complete audit, window, counts, and evidence again before displaying it. Changing the CSV or reporting window clears the current analysis and any approval. [Phase 2 walkthrough](docs/PHASE2.md) explains each step and its pass criteria.

Recheck a saved full-data Phase 2 result without making model or MCP requests:

```powershell
.\.venv312\Scripts\python.exe scripts/verify_phase2.py --save outputs/phase2_checkpoint.json
```

This compares the JSON to the original CSV, recomputes the counts, validates all evidence, and checks that the classifications export matches. It exits with an error if any check fails.

For Phase 3, open **Product + support outputs → Load saved Phase 3 outputs** to inspect the completed result. To generate fresh outputs, load the Phase 2 insights on that page, unlock the sidebar, and choose **Generate outputs from Phase 2**. Only this step fetches current official Groww pages and writes the pulse/fee explanation. If it fails, the saved Phase 2 result remains available. The [Phase 3 walkthrough](docs/PHASE3.md) explains the checks, previews, and approval handoff.

Generate Phase 3 from the existing verified insights, without reclassifying reviews:

```powershell
.\.venv312\Scripts\python.exe scripts/run_pipeline.py --report-date 2026-10-16 --live --phase3
.\.venv312\Scripts\python.exe scripts/verify_phase3.py --save outputs/phase3_checkpoint.json
```

The second command uses no API or MCP calls. It compares the output to the exact Phase 2 input, rechecks limits/grounding, and verifies every saved preview. For a different saved input, pass `--intelligence path/to/review_intelligence.json` and its matching CSV/date/window to the generation command.

To run both phases from the command line without invoking any write tools:

```powershell
.\.venv312\Scripts\python.exe scripts/run_pipeline.py --report-date 2026-10-16 --live
```

Successful Phase 3 runs produce `outputs/latest.json`, `weekly_product_pulse.md`, `fee_explainer.md`, `document_entry.json`, `document_entry_preview.txt`, `email_draft_preview.txt`, `fee_claim_evidence.md`, and `official_fee_sources.json`. The app exposes Markdown, JSON, and email-preview downloads plus document/email previews. Pulse edits require password access, must remain valid, and invalidate approval; valid edits update all previews/exports together. Fee bullets remain tied to their source evidence. A saved result loads only with its matching Phase 2 input, dataset fingerprint, reporting window, and original evidence. Reference evidence stays separate.

## 3. Dataset and analysis behavior

Required CSV columns: `platform`, `review_id`, `date`, `rating`, `review_text`, `source_url`. Dates use `YYYY-MM-DD`; ratings are integers 1–5; source URLs use HTTPS. `title`, `app_version`, and `country` are retained in the sample but optional to analysis.

The window is inclusive: `report_date - (weeks*7 - 1)` through `report_date`. Invalid rows, duplicate `(platform, review_id)` records, future dates, and out-of-window reviews are reported separately. The original file is never overwritten.

For 16 October 2026 and 12 weeks:

| Check | Result |
| --- | ---: |
| Uploaded | 13,268 |
| Included, 25 July–16 October | 13,034 |
| Outside window | 234 |
| Invalid / duplicate / future | 0 / 0 / 0 |
| Google Play / App Store included | 12,534 / 500 |
| Data cutoff | 14 October 2026 |

The user confirmed original public review text and dates. Public source links and review IDs are retained. Individual review authenticity has not been independently re-scraped.

Theme discovery uses a platform/rating/week-stratified sample, then a frozen taxonomy classifies **every** distinct text in batches. At most five themes are allowed. Each substantive review has one primary theme; nonspecific praise contributes to overall sentiment separately. Short concrete complaints are retained. Different review IDs with identical text still count separately; classification is reused to avoid paying to classify the same wording repeatedly.

Top-three themes are ranked by substantive-review count. Meaningful 4–25-word excerpts must match source records and cover all three themes. Fee confusion requires one named fee with an exact matching passage in each of at least three distinct review texts; generic deductions or merely mentioning an expensive fee is insufficient. The pulse uses full-window themes and latest-observed seven-day counts versus the preceding seven days. This is an observational review sample, not a representative survey of Groww customers.

## 4. Fee issue identified from reviews

The completed full-data AI run identifies **brokerage confusion and unexpected Groww brokerage deductions**, supported by five distinct original review texts with exact passages naming brokerage. Reviewers ask for clarity on brokerage/taxes, compare a quoted per-order fee with larger deductions, and question brokerage line items or application. These are customer reports; Phase 3 must check official facts and distinguish commodities, equity, and order contexts before explaining them.

The leading full-window themes are customer support/account operations (550 reviews), app stability/performance/UI (470), and missing features/product gaps (457). Pricing/charges (349) is a separate fourth-ranked theme. The counts cover 2,001 substantive reviews; 11,033 nonspecific reviews remain in overall sentiment. See `outputs/review_intelligence.md` for the actual quotes and fee evidence, and `outputs/phase2_checkpoint.json` for the independent verification receipt.

`data/reference_evidence.json` retains three preliminary original review examples. `data/reviews_sample.csv` contains 53 unchanged original records spanning both platforms and ratings. The preliminary preview stays separate from the completed AI result and cannot be approved as AI output.

Fee explanations are generated from the two official Groww sources fetched at run time. The writer selects fixed source-passage labels; the app inserts their exact original text and checks every cited source. A separate AI check compares the customer bullets with the full official texts for unsupported claims, rates, minima, caps and scope. These checks assist review; they do not prove semantic correctness. Inspect the matched passages before Phase 4 approval. Equity, F&O, MTF, NRI, and UPI Mandate balance contexts must not be conflated. The UPI guard requires explicit equity/Mandate/balance scope. The current snippet addresses brokerage confusion without deciding whether any reviewer's disputed deduction was correct.

## 5. Configure n8n Cloud

See [the Phase 4 walkthrough](docs/PHASE4.md) for account setup, the exact approval demonstration, and recovery. Local approval/MCP checks pass; real Google Docs and Gmail acceptance remains pending account configuration and human approval. Verification is recorded separately in `outputs/phase4_checkpoint.json`.

All four JSON exports are inactive and contain placeholders rather than credentials. You can regenerate them with `python scripts/build_n8n_workflows.py`.

1. Create a Google Doc for the weekly log. Copy its full URL.
2. In your n8n project, create a Data Table named `groww_action_ledger` with **string** columns: `ledger_key`, `payload_hash`, `status`, `receipt_json`. Copy its table ID.
3. Import `n8n/01_append_product_update.json`, `02_create_support_draft.json`, and `03_get_run_receipts.json` as separate workflows.
4. In **every Data Table node**, select your ledger table. In the **Validate approval** Code node in both write workflows, replace `REPLACE_WITH_GOOGLE_DOC_URL` with the exact fixed Doc URL. The app's Doc URL must match it.
5. Connect your Google Docs credential to **Append approved entry**, and your Gmail credential to **Create approved Gmail draft**. Use your own account connection screens. The Gmail resource must remain **Draft**, operation **Create**; leave recipient options empty.
6. Save/publish those workflows as required by your n8n version. Their input triggers accept the specified fields from the MCP tool wrappers.
7. Import `n8n/04_mcp_server.json`. In its three workflow tools, select the matching imported child workflow, refresh the input schema, and retain the mappings:
   - `append_product_update`: one string `envelope`.
   - `create_support_draft`: one string `envelope`.
   - `get_run_receipts`: strings `run_id` and `payload_hash`.
8. On **Groww MCP Server**, retain **Bearer Auth**, create/select your bearer credential, and publish. Copy the displayed **production MCP URL**. Use the v2 Streamable HTTP endpoint, not an older `/sse` URL.
9. Add `N8N_MCP_URL`, `N8N_MCP_TOKEN`, and `GOOGLE_DOC_URL` to the local or hosted Streamlit secrets. The token must match the n8n bearer credential. The prototype accepts n8n Cloud HTTPS hosts; arbitrary URLs are rejected.
10. Load a validated live AI run, open **Approve + save**, and click **Check MCP connection (read only)**. This initializes MCP and discovers tools; it does not invoke write tools.

The workflow exports target MCP Trigger v2, Workflow Tool v2.2, and Data Table v1. Their public node schemas were checked against n8n source; imported node configuration and credentials still need verification in your actual n8n version.

## 6. Where approval happens

The **Approve + save** page previews the destination Doc URL, complete note, fee explanation, structured entry, and exact email subject/body. Click **Approve and save** only after reviewing them. **Reject** performs no remote action.

The backend binds approval to the exact serialized payload fingerprint and a 30-minute approval window. Editing the pulse, changing the CSV/window, or regenerating invalidates approval. Fee bullets are read-only because they are tied to checked source evidence. Once a write starts, editing is disabled.

Only the approval controller calls the two MCP write tools; the LLM does not have direct access to those tools. n8n checks approval metadata, content hash, output limits, and the fixed Doc destination. The bearer token authenticates this trusted client. The `approved` flag is an application gate, not independent cryptographic proof of a human decision for arbitrary clients holding that token.

Each n8n action records an attempt **before** its Google write and persists the result afterward. Completed operations return stored receipts on retry. A private SQLite journal at `.cache/approval_runs.sqlite3` also claims each action before MCP access and restores states after browser reloads. It stores approval metadata and receipts, without credentials; approval is never automatically restored into a new session. This is a single-operator prototype; Data Tables are not a transactional distributed lock for multiple independently deployed clients.

An error after a write starts leaves an **unknown** outcome. The second action stops, and no blind retry occurs. Inspect the n8n execution and remote destination. Then use **Refresh remote receipts (read only)**. If a write definitely did not occur, an operator may reconcile its ledger `receipt_json` to `status: "failed", safe_to_retry: true`, preserving `run_id`, `action`, and `payload_hash`; refresh receipts and retry the confirmed-safe incomplete action. If it did occur, reconcile to `succeeded` with its actual `document_url` or `draft_id`. Never delete an attempt record merely to force a retry.

After reconciliation, review and click **Approve and retry remaining actions** for a fresh approval of the same snapshot. Confirmed successful actions are skipped. Download the execution receipts and approval/execution record, capture the appended Doc entry and Gmail Drafts screen, and place evidence in `outputs/private/` so account details are not accidentally committed. There is no auto-send step.

## 7. Deploy the hosted prototype

The default app opens **Saved CSV demo** from the frozen, hash-checked `data/demo/` snapshot. Choose **Live upload and analysis** for uploads, generation, editing, or approval. A generated local access password is stored only in `.streamlit/secrets.toml`. Live results use `outputs/private/runs/` and can be resumed by an authenticated operator with the matching dataset/window.

Use [the Phase 5 guide](docs/PHASE5.md) and `outputs/groww-streamlit-deployment.zip` for the clean GitHub source bundle. `scripts/verify_phase5.py --save` verifies that this bundle opens without local secrets. Actual hosting and Google acceptance remain pending account sign-in/configuration; no hosted URL is claimed.

1. Connect GitHub and create a repository containing the source, CSV, `data/`, n8n exports, and requirements. Exclude `.venv*`, `.cache`, `.env`, and populated `secrets.toml`.
2. In Streamlit Community Cloud, create an app from that repository, branch, entrypoint `app.py`, and Python **3.12**.
3. Paste the configured secrets into the app's **Advanced settings → Secrets**. Google OAuth credentials remain inside n8n, not in this repository.
4. Deploy and retain the actual returned `*.streamlit.app` URL. If access is restricted, grant the intended reviewer access using Streamlit's normal sharing settings.
5. Test in a fresh browser session: dataset metrics, password unlock, live or matching saved AI analysis, source review, rejection with no writes, approval, document link, and draft receipt.
6. For a fast demonstration, keep the complete `data/demo/` folder and original CSV in the repository. Saved CSV demo fixes the original report date/window and loads the real Phase 2/3 results automatically. Live analysis never rewrites that public snapshot.

Account sign-in, permission grants, and app publication require your connected accounts. A hosted URL must not be claimed until the deployment actually succeeds.

## 8. Verification commands

```powershell
.\.venv312\Scripts\python.exe -m pytest -q
node scripts/check_workflows.cjs
.\.venv312\Scripts\python.exe scripts/preflight.py
# After n8n setup, initialize/discover without calling write tools:
.\.venv312\Scripts\python.exe scripts/preflight.py --mcp
```

Tests cover the supplied dataset, malformed inputs, date boundaries, duplicate weighting, model-output traceability, count reconciliation, word/bullet limits, no-approval/rejection/edit/expiry, repeated clicks, partial failures, uncertain writes, and real MCP message exchange against test-only tools. The workflow checker exercises the actual exported approval Code nodes. These do not substitute for a live OpenAI run or Google/n8n account acceptance checks.

`tests/mock_mcp_server.py` is a loopback-only test service. It never accesses Google or sends email. Do not deploy it as the production server.

## Deliverable checklist

Open `submission/index.html`, or extract `outputs/groww-milestone-submission.zip`. The packet includes the actual 2:04 captioned video and all local deliverables. See [the Phase 6 guide](docs/PHASE6.md). To rebuild and independently verify it:

```powershell
.\.venv312\Scripts\python.exe scripts/build_submission.py
.\.venv312\Scripts\python.exe scripts/verify_submission.py
```

Add account links later through `submission_links.json` / `scripts/update_submission_links.py`. Rebuilding preserves those references; adding a link never substitutes for real execution evidence.

| Deliverable | Location / completion condition |
| --- | --- |
| Hosted prototype | Actual Streamlit URL, after deployment |
| Weekly pulse | `outputs/weekly_product_pulse.md`, after live analysis |
| Fee explanation | `outputs/fee_explainer.md`, after live analysis |
| Phase 3 verification | `outputs/phase3_checkpoint.json`, `outputs/phase3_verification.md` |
| Document/email previews | `outputs/document_entry_preview.txt`, `outputs/email_draft_preview.txt` |
| Appended entry | Real Google Doc plus execution receipt after approval |
| Email draft evidence | Real Gmail draft screenshot/text plus draft ID after approval |
| Reviews sample | `data/reviews_sample.csv` |
| Source list | `SOURCES.md` — six URLs |
| Setup and approval guide | This README |
| Importable workflows | `n8n/01_*.json` through `04_*.json` |
