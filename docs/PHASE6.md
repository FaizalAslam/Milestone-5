# Phase 6 — Submission packet

Phase 6 assembles the completed local work into a reviewable packet. GitHub/hosted links and real Google Docs/Gmail evidence are intentionally deferred until accounts are connected. Previews remain labelled as previews.

## What is included

`outputs/groww-milestone-submission.zip` extracts to a self-contained review packet:

| File/folder | Purpose |
| --- | --- |
| `index.html` | Review page with the demo, pulse, fee snippet, previews, and requirement checklist |
| `README.md` | How to run, where approval happens, the identified fee issue, and verification status |
| `demo/groww_workflow_demo.mp4` | 2 minute 4 second captioned walkthrough of actual local app screenshots |
| `demo/metadata.json`, `STORYBOARD.md` | Duration, full-decode verification, screen hashes, captions, and timing |
| `deliverables/` | Weekly pulse, fee explainer, structured entry, document/email previews, complete analysis, review evidence, and official source passages |
| `data/reviews_sample.csv` | 53 unchanged original reviews, including original text, dates, IDs and source URLs |
| `SOURCES.md` | Six source URLs, including two official Groww fee sources |
| `workflows/` | Four credential-free n8n workflow imports |
| `source/groww-streamlit-deployment.zip` | App source, dependencies, tests, and verified saved demo for a fresh setup |
| `guides/`, `verification/`, `evidence/` | Phase walkthroughs, actual recorded local checkpoints, and app screenshots |
| `links.json` | Intentionally empty references to add later |
| `pending/LIVE_EVIDENCE_CHECKLIST.md` | Actual account evidence still required |
| `manifest.json` | Requirement statuses, analysis run, counts, and file hashes |

The walkthrough is a captioned sequence of actual app screens, not a continuous recording of fresh model calls or remote writes. It shows the saved analysis, source-linked fee evidence, both outputs, and rejection leaving both actions unstarted. It explicitly labels account connections and live evidence as pending.

## Build and verify

```powershell
.\.venv312\Scripts\python.exe scripts/build_submission.py
.\.venv312\Scripts\python.exe scripts/verify_submission.py
```

The builder verifies the original CSV fingerprint, frozen Phase 2/3 lineage, all existing output exports, every sample CSV field, the six-source list, controlled workflow files, and the video duration/hash. It rebuilds the credential-free source ZIP and writes both `submission/` and the final ZIP. The separate verifier checks the packaged files, copied content, nested source archive, file hashes, requirement paths, and configured credential exclusion. Neither command calls OpenAI, MCP write tools, Google Docs, or Gmail.

Open `submission/index.html` directly, or serve the packet locally:

```powershell
.\.venv312\Scripts\python.exe -m http.server 8766 --bind 127.0.0.1 --directory submission
```

Then open http://127.0.0.1:8766/. Only the generated public packet is served.

## Add links later

`submission_links.json` in the workspace is the editable source of truth. It is excluded from Git and the public deployment source bundle. Rebuilding preserves it. Missing values are JSON `null`; no invented links or draft IDs are inserted.

After the real references exist, use the relevant options:

```powershell
.\.venv312\Scripts\python.exe scripts/update_submission_links.py --github-repository https://github.com/OWNER/REPOSITORY --hosted-prototype https://ACTUAL-APP.streamlit.app
.\.venv312\Scripts\python.exe scripts/update_submission_links.py --google-doc https://docs.google.com/document/d/ACTUAL-DOCUMENT-ID/edit --gmail-draft-id ACTUAL-DRAFT-ID
.\.venv312\Scripts\python.exe scripts/build_submission.py
.\.venv312\Scripts\python.exe scripts/verify_submission.py
```

Replace example references with actual values; do not run the examples with placeholder IDs. An optional `--demo-video-url` can record an uploaded video URL. `--clear FIELD_NAME` clears only a requested field. These commands record references locally and make no external calls.

Adding links does not change pending remote actions into successful evidence. After connecting accounts, personally approve the exact snapshot in the app, verify the actual Google Doc and unsent Gmail draft, then attach the matching real receipts and account screenshots after reviewing them. Keep those account files under `outputs/private/` until ready for submission. The current public packet excludes that directory.

## Rebuild the video, if needed

The current video is already included and decoded successfully. Rebuilding requires optional tooling:

```powershell
.\.venv312\Scripts\python.exe -m pip install -r requirements-demo.txt
.\.venv312\Scripts\python.exe scripts/build_demo_video.py
```

The encoder uses the actual captured screens in `outputs/demo/frames/`, keeps the video below three minutes, writes a shot-by-shot storyboard, and fully decodes the final MP4 to verify it. Capture updated screens before regenerating if the app's content changes. The optional encoder packages are not required to run or deploy Streamlit.
