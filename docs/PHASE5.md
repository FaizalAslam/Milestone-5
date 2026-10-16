# Phase 5 — Streamlit Community Cloud deployment

The application source is published to [FaizalAslam/Milestone-5](https://github.com/FaizalAslam/Milestone-5), on branch `main`, and its initial [GitHub checks passed](https://github.com/FaizalAslam/Milestone-5/actions/runs/38888457085). **No hosted URL exists yet.** Streamlit sign-in, deployment, and the hosted acceptance checks remain to be completed. The n8n workflows are imported with actual tool bindings and selected Google credentials; authenticated production discovery and the human-approved Google writes still need verification. Local readiness is recorded separately from live acceptance.

## 1. What is prepared

- `outputs/groww-streamlit-deployment.zip` contains the GitHub source, public CSV, verified saved demo, tests, n8n templates, and dependency configuration. Actual secrets, private live runs, local environments, and caches are excluded. A file hash manifest is included.
- The default **Saved CSV demo** opens the original 16 October 2026 analysis immediately. It uses 13,034 reviews, the fixed original window, and matched Phase 2/3 lineage. Its source dates remain visible even when opened later.
- **Live upload and analysis** accepts another CSV and reporting window. Analysis, editing, and approval require the access password. Demo mode cannot call the model or perform MCP writes, even when the operator is signed in.
- `data/demo/` is a frozen public snapshot with file hashes. Live files are saved under `outputs/private/runs/<run_id>/`, and the approval journal is in `.cache/approval_runs.sqlite3`. Neither location is shipped to GitHub.
- An authenticated operator can use **Resume a saved live run** for a matching CSV/report date. The restored parent analysis is validated again. Saving still requires fresh approval; uncertain attempts stay paused.

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
DEMO_ACCESS_PASSWORD = "your local generated or chosen access password"
N8N_MCP_URL = "your authenticated n8n production MCP URL"
N8N_MCP_TOKEN = "your matching n8n bearer token"
GOOGLE_DOC_URL = "the exact fixed Doc URL from both n8n write workflows"
```

A strong access password has already been generated locally in `.streamlit/secrets.toml`; the existing OpenAI key was preserved. Read/copy secret values locally into Streamlit's Secrets field. Do not paste them into chat, GitHub files, issues, screenshots, or the public app. Google OAuth credentials stay in n8n.

4. Deploy and inspect build logs until the app finishes opening. Record the **actual** `https://…streamlit.app` URL. Do not treat a requested subdomain as a successful deployment.

This follows Streamlit's official [deployment instructions](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy) and [Community Cloud secrets management](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management).

## 4. Check the actual hosted app

Use a fresh browser session with no app login:

1. Open the real URL. Confirm the saved-demo label, 13,034 included reviews, and report date 2026-10-16.
2. Open Review intelligence and Product + support outputs. Confirm the verified themes, three quotes, 149-word pulse, four fee bullets, two official links, and original Last checked date.
3. Confirm demo analysis and **Approve and save** are disabled. Switch to Live mode and confirm the password is required for live analysis and approval.
4. Unlock, upload `data/reviews_sample.csv`, choose its matching report date/window, and run Phase 2 then Phase 3. This verifies the hosted OpenAI and official-source paths with the original 53-row public sample. Inspect the results and all constraint checks.
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

The smoke checker extracts the repository bundle into a clean directory and runs all four pages in a fresh Python process with no local secrets. It validates the real demo and locked approval; it makes no model calls or external writes. A live app health check can be added with `--hosted-url https://ACTUAL-SUBDOMAIN.streamlit.app`, but a health response alone does not replace the hosted browser and account checks above.

Only refresh `data/demo/` deliberately using `scripts/prepare_demo.py` after checking that the source CSV and completed Phase 2/3 outputs are appropriate to publish. Live analysis never overwrites that public snapshot.
