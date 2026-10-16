# Phase 2 — Review intelligence walkthrough

Phase 2 transforms the included CSV reviews into auditable insights. It uses OpenAI structured outputs and ends before pulse generation, official fee fact retrieval, or MCP actions.

## 1. Confirm the input

The default Saved CSV demo already contains the completed analysis. Choose **Live upload and analysis** in the sidebar to upload, change dates, or call the model.

Select report date **2026-10-16** and **12 weeks**. The supplied CSV must show 13,268 uploaded reviews, 13,034 included reviews, and 6,130 distinct texts. The window is 25 July–16 October, with actual data through 14 October. The source CSV stays unchanged.

Set `OPENAI_API_KEY` and `DEMO_ACCESS_PASSWORD` in `.streamlit/secrets.toml`, restart the app, and unlock the sidebar. Keep credentials local. For a first live check, upload `data/reviews_sample.csv`; it contains 53 unchanged original reviews. Select **Review intelligence → Analyze reviews (Phase 2)**.

## 2. Discover themes

The engine groups case/whitespace variants of repeated text and selects up to 400 distinct texts, stratified by platform, star rating, and week. OpenAI proposes three to five substantive themes. Theme IDs, distinct names, descriptions, and the maximum theme count are checked before classification begins. Discovery samples do not determine final counts.

## 3. Classify all included feedback

Every distinct text is sent to OpenAI in batches of up to 40 texts or 40,000 characters, with four concurrent requests by default. Set `OPENAI_MAX_WORKERS` to 1–8 to suit the account's rate limits. Structured output records sentiment, whether feedback is substantive, one primary theme if substantive, and any fee confusion with an exact supporting passage. Generic praise is counted in sentiment separately. Short concrete complaints such as “hidden charges” remain substantive. Price dissatisfaction alone does not establish a misunderstanding.

Each batch must return exactly the supplied text keys. API requests use short batch-local labels, which the engine maps back to full original text fingerprints before validating or caching; this avoids long-ID transcription mistakes. Theme assignments and exact fee passages are checked. Completed, valid batches are cached privately. Invalid model output gets one bounded repair attempt; a run stops if it still fails. Rejected parsed responses are preserved privately for diagnosis. Restarting reuses valid completed work.

## 4. Reconcile and rank

Classifications map back to every original review ID. Two different IDs containing the same text remain two observations. The validator recomputes sentiment, substantive and nonspecific totals, full-window theme counts, and latest/preceding seven-day theme counts from those assignments. The top three themes are ranked by full-window review count, with theme ID breaking ties.

The app displays the three leading themes, all themes, sentiment, and comparison coverage. Different review volumes or an incomplete cutoff day do not by themselves establish a trend.

## 5. Select evidence

OpenAI selects three meaningful verbatim excerpts, 4–25 words each, one from each top theme. Each excerpt must match an original included review and convey the reviewer's experience or request. Isolated status labels lose their context and are rejected. The app shows each original ID, date, and public source link. Candidates are explicitly grouped by theme and use short API labels that map back to the original records.

The model also selects a specific recurring fee confusion from the classified fee candidates, supported by three to eight distinct review texts, and explains their connection. The selected fee must be named explicitly in the issue title and in an exact supporting passage from every selected review. Generic “hidden charges” cannot serve as the final fee name, and unrelated DDPI, brokerage, and disputed-position charges cannot be grouped into one explanation. IDs with repeated wording cannot inflate the evidence requirement. The full original reviews, classification passages, and selected fee passages remain visible. These are customer reports; official fee facts are checked in Phase 3.

“Brokerage versus total trade charges” is a preliminary candidate from manual inspection. It becomes a confirmed analysis result only if the full live model run selects and supports it. Keyword matches alone do not complete this step.

## 6. Inspect the checkpoint and save

The app reports PASS only after:

1. Every included review has one classification and weighted totals reconcile.
2. There are three to five distinct themes and three populated leading themes.
3. Sentiment includes all reviews, with nonspecific feedback separated.
4. All three exact quotes cover the top themes and match source metadata.
5. Fee confusion has at least three distinct original supporting texts.
6. Seven-day counts reconcile and the available date coverage is disclosed.

The JSON, Markdown report, and per-review CSV are saved to `outputs/` and available as downloads. Saved Phase 2 results can be loaded independently and are revalidated against the selected CSV/window. Phase 3 failures do not discard these files. Do not use a sample run as the full-dataset result.

## Verification limits

Automated tests use clearly marked offline model fixtures, including the Streamlit button flow. They establish pipeline behavior, traceability, count correctness, cache recovery, and phase separation. The live OpenAI sample and full-data acceptance checks have also passed for 2026-10-16. The full result has 13,034 classifications, five themes, three verified quotes, and five distinct brokerage evidence reviews. `outputs/phase2_checkpoint.json` records the independent input/export checks; `outputs/phase2_verification.md` records the detailed results and live failures resolved during implementation. Model classifications remain reviewable judgements. No synthetic completed Groww analysis is supplied.
