# Phase 5 — Streamlit Community Cloud deployment

**Current UI:** Upload & Processing automatically runs the review and output stages. Results Workspace contains insights, output tabs and the final approval panel. Data Quality & Audit contains filtering and evidence details. The app opens directly to CSV upload; Demo mode is removed. No sidebar/operator password is required; older phase names below describe backend milestones and CLI operations. See [UI redesign](UI_REDESIGN.md).
The application source is published to [FaizalAslam/Milestone-5](https://github.com/FaizalAslam/Milestone-5), on branch `main`, and [GitHub checks passed](https://github.com/FaizalAslam/Milestone-5/actions/runs/38893135873). **No hosted URL exists yet.** Streamlit sign-in, deployment, and the hosted acceptance checks remain to be completed. All four n8n workflows are published; production MCP authentication, tool-schema discovery, and read-only receipt lookup passed. Human-approved Google writes still need verification. Local readiness is recorded separately from live acceptance.

## 1. What is prepared

- `outputs/groww-streamlit-deployment.zip` contains the GitHub source, public CSV, archived verification fixtures, tests, n8n templates, and dependency configuration. Actual secrets, private live runs, local environments, and caches are excluded. A file hash manifest is included.
- The app accepts a CSV and reporting window, then runs analysis automatically. It has no operator-password step, Live/Demo switch, saved-example button or public example route.
- `data/demo/` is an archived public analysis fixture used only by offline verification and submission tooling; the app never falls back to it. Live files are saved under `outputs/private/runs/<run_id>/`, and the approval journal is in `.cache/approval_runs.sqlite3`. Neither location is shipped to GitHub.
- Reuploading the same CSV and reporting window resumes a matching verified private run from the current deployment, when one exists. The restored parent analysis is validated again. Saving still requires fresh approval; uncertain attempts stay paused.

## 2. Sign in and choose the repository

Open [GitHub](https://github.com/new) and [Streamlit Community Cloud](https://share.streamlit.io/). Complete sign-in, any account terms, and requested permission/consent steps yourself. Choose a GitHub repository you own; a private repository is suitable when your Streamlit account has access to it.

Use the deployment ZIP as the repository contents, with `app.py` at the repository root. Commit the supplied `.gitignore`, `.gitattributes`, `.streamlit/config.toml`, and `.github/workflows/tests.yml`, including those dot folders. The byte-preservation attributes keep the raw CSV and demo JSON hashes stable across Windows/Linux checkouts. Do not upload your working directory wholesale or the populated local secrets file.

The GitHub checks run Python 3.12 tests and the actual n8n workflow Code-node checks. A successful local run is recorded in the verification notes; a remote CI pass is only established after the repository exists and GitHub Actions finishes.

## 3. Add deployment secrets and publish

1. In Streamlit, choose **Create app → Yup, I have an app**.
2. Select the repository, its actual branch, and `app.py` as the entrypoint. Choose an available app subdomain.
3. In **Advanced settings**, select **Python 3.12** and enter these secrets:

```toml
OPENAI_API_KEY = "your existing OpenAI API key"
OPENAI_MODEL = "gpt-5-mini"
OPENAI_MAX_WORKERS = 4
N8N_MCP_URL = "your authenticated n8n production MCP URL"
N8N_MCP_TOKEN = "your matching n8n bearer token"
GOOGLE_DOC_URL = "the exact fixed Doc URL from both n8n write workflows"
```

Model and MCP credentials remain in `.streamlit/secrets.toml` or deployment secrets. The former `DEMO_ACCESS_PASSWORD` setting is no longer used by the UI. Read/copy secret values locally into Streamlit's Secrets field. Do not paste them into chat, GitHub files, issues, screenshots, or the public app. Google OAuth credentials stay in n8n.

4. Deploy and inspect build logs until the app finishes opening. Record the **actual** `https://…streamlit.app` URL. Do not treat a requested subdomain as a successful deployment.

This follows Streamlit's official [deployment instructions](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy) and [Community Cloud secrets management](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management).

## 4. Check the actual hosted app

Use a fresh browser session with no app login:

1. Open the real URL. Confirm the empty upload workspace and all three header tabs, with no Demo controls or saved-example links. A legacy `?example=1` URL must also open the empty upload screen.
2. Before upload, confirm no generated results or approval controls are available.
3. Confirm the app requires no extra operator-login step. Model/MCP credentials stay in deployment secrets.
4. Upload `data/reviews_sample.csv` with its matching reporting period. Validation, review intelligence and output generation must run automatically. This verifies the hosted OpenAI and official-source paths with the original 53-row public sample. Inspect the results and all constraint checks.
5. Complete the [Phase 4 live acceptance procedure](PHASE4.md): read-only MCP discovery, Reject with no writes, then review the exact previews and personally approve. Check one actual Doc entry and one unsent Gmail draft; compare both with their approved preview and fingerprint.
6. Refresh/load the same run and verify no duplicates. Save the actual hosted URL, execution receipts, and account evidence under `outputs/private/`.

Cloud local storage may be replaced on reboot/redeploy. Download live outputs and receipts before redeploying. If a local journal disappears, n8n's attempt ledger remains the remote record; check it before retrying an uncertain action. The app does not claim distributed exactly-once behavior across independently deployed clients.

## 5. Reproduce local deployment readiness

```powershell
.\.venv312\Scripts\python.exe -m pytest -q
node scripts/check_workflows.cjs
.\.venv312\Scripts\python.exe scripts/prepare_deployment.py
.\.venv312\Scripts\python.exe scripts/verify_phase5.py --save
```

The smoke checker extracts the repository bundle into a clean directory and opens the upload-only wireframe component in a fresh Python process with no local secrets. It verifies empty upload, removal of the legacy example route, and locked approval; it makes no model calls or external writes. A live app health check can be added with `--hosted-url https://ACTUAL-SUBDOMAIN.streamlit.app`, but a health response alone does not replace the hosted browser and account checks above.

Archived fixtures in `data/demo/` are retained for offline evidence verification. They are not an app feature and are never substituted for uploaded review analysis.
