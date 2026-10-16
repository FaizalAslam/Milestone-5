# Phase 4 — Approval, MCP, and destination writes

**Current UI:** Upload & Processing automatically runs the review and output stages. Results Workspace contains insights, output tabs and the final approval panel. Data Quality & Audit contains filtering and evidence details. Demo opens the saved example read only. No sidebar/operator password is required; older phase names below describe backend milestones and CLI operations. See [UI redesign](UI_REDESIGN.md).
All four workflows are published in n8n Cloud, with actual child workflow bindings, a receipt ledger, and connected Google credentials. **Live production MCP authentication, strict tool-schema discovery, and read-only receipt lookup passed on 2026-10-16.** No write tools were called. Human approval, one matching Google Docs entry, and one unsent Gmail draft remain required for end-to-end acceptance. Connection evidence is recorded in `outputs/phase4_mcp_connection_checkpoint.json`. Public workflow templates retain account placeholders.

## 1. Connect the fixed destinations in n8n

1. Open your n8n Cloud workspace. Create or select the Google Doc that will hold the weekly log, and copy its full URL. Do not change its sharing permissions.
2. Create an n8n Data Table named `groww_action_ledger`. Add four **String** columns: `ledger_key`, `payload_hash`, `status`, `receipt_json`.
3. Import `n8n/01_append_product_update.json`, `02_create_support_draft.json`, and `03_get_run_receipts.json` separately. The supplied exports are inactive and contain placeholders.
4. In every Data Table node, choose the table from step 2. In both **Validate approval** Code nodes, set `EXPECTED_DOC_URL` to the exact Doc URL. Keep that destination fixed in n8n.
5. Connect your Google Docs credential to **Append approved entry**. Connect your Gmail credential to **Create approved Gmail draft**. Complete account sign-in and Google consent yourself. Retain Gmail **Draft → Create**, plain text, with recipient options empty.
6. Save/publish the child workflows as required by your workspace. Their Execute Workflow triggers accept string inputs: `envelope` for the write workflows, and `run_id` + `payload_hash` for lookup.
7. Import `n8n/04_mcp_server.json`. Select the correct child workflow in each of its three workflow tools. Refresh the inputs and retain each `$fromAI(...)` mapping. All inputs are required strings. Expose exactly `append_product_update`, `create_support_draft`, and read-only `get_run_receipts`.
8. On **Groww MCP Server**, select your Bearer Auth credential and publish the workflow. Copy its **production MCP URL**. This Python client uses Streamable HTTP, rather than the older SSE endpoint. Keep Google credentials and the destination configuration inside n8n.

These steps follow n8n's [MCP Server Trigger documentation](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-langchain.mcptrigger/), [Data Tables guide](https://docs.n8n.io/data/data-tables/), and [Gmail draft operations](https://docs.n8n.io/integrations/builtin/app-nodes/n8n-nodes-base.gmail/draft-operations/). The exports target MCP Trigger v2, Workflow Tool v2.2, Data Table v1, Google Docs v2, and Gmail v2.1. Verify imported node settings in your actual workspace version.

## 2. Configure the app locally

Edit `.streamlit/secrets.toml`. Preserve your existing OpenAI key. Populate the following locally; do not paste passwords or tokens into chat:

```toml
N8N_MCP_URL = "https://YOUR-WORKSPACE.app.n8n.cloud/mcp/YOUR-PRODUCTION-PATH"
N8N_MCP_TOKEN = "the token from your n8n Bearer Auth credential"
GOOGLE_DOC_URL = "the exact EXPECTED_DOC_URL configured in both write workflows"
```

Restart Streamlit after changing secrets. Run the read-only readiness check:

```powershell
.\.venv312\Scripts\python.exe scripts/preflight.py --mcp
```

It checks the authenticated MCP handshake and all three tool input schemas. It never invokes a write tool and reports only whether secrets are configured.

## 3. Review the exact snapshot

Start the app with `start.ps1`. In **Live**, use **25 July–16 October 2026** and upload the supplied CSV. Review the validated results and output tabs, then inspect **Save Approved Outputs**. The **Demo** example is read only. A matching already-completed run restores its receipts rather than offering duplicate writes.

Review the visible document destination, complete weekly pulse, brokerage explanation, structured document entry, and complete email subject/body. The six entry fields are `date`, `top_themes`, `weekly_pulse`, `identified_fee_issue`, `explanation_bullets`, and `source_links`. The email recipient stays blank in the Gmail account connected to n8n. No send operation is configured.

The app displays the run ID and content fingerprint. Changing content, regenerating, or changing the dataset invalidates approval. A changed destination produces a different fingerprint. After an attempt starts, the snapshot stays locked for reconciliation.

## 4. Perform the human approval check

1. Optionally run `scripts/preflight.py --mcp` for read-only discovery. Confirm no Google operation appears in n8n.
2. Click **Reject**. Confirm the rejection message, no document entry, no draft, and no write workflow execution. Inspect the destinations before proceeding.
3. Review the same snapshot again and personally click **Approve and save**. This explicit approval authorizes the current fingerprint for 30 minutes.
4. Confirm one new Doc entry and one unsent Gmail draft. Compare their contents to the approved previews. The receipts must report the expected Doc URL, an actual draft ID, matching run ID/hash, and separate successful action statuses.
5. Rerun/reload and load the same saved outputs. Confirm completed actions stay completed and do not create duplicates. Download the receipts and approval/execution record. Store account screenshots in `outputs/private/`.

Only the approval controller can invoke write tools. The LLM receives no write-tool access. The bearer credential authenticates the trusted application; the `approved` flag is an application contract, rather than independent proof of human consent for any arbitrary bearer-token holder.

## 5. Understand partial failures and recovery

The app's SQLite journal at `.cache/approval_runs.sqlite3` records approval metadata and marks each action **before** calling MCP. It restores action states after a browser reload without restoring approval. It never stores the bearer token. Browser refresh recovers the same in-memory workspace while the server is running. After a server restart, upload the same CSV and reporting window to restore a matching verified result from `outputs/private/runs/`. n8n separately records its attempt before Google access and persists successful receipts afterward.

- **Succeeded:** keep the remote identifier; subsequent attempts skip this action.
- **Failed, `safe_to_retry: true`:** a remote operator has confirmed no write occurred. Review the same preview, then click **Approve and retry remaining actions** to give fresh approval. Successful actions are skipped.
- **Unknown / in progress:** a timeout could have happened after the write. The next action stays paused. Inspect the n8n execution and actual Doc/Gmail destination, then use **Check save result**. An empty lookup does not unlock a retry.

If a remote write occurred but receipt persistence failed, reconcile the existing n8n row's `receipt_json` to `succeeded` with its actual `document_url` or `draft_id`. If you confirm that the write did not occur, reconcile it to `failed` with `safe_to_retry: true`. Preserve `run_id`, `action`, and `payload_hash`, update the row's status, then refresh the app's receipts. Never erase an attempt merely to force a retry.

The local journal serializes claims across processes sharing that file. The remote Data Table is not a distributed transaction lock. This is a single-operator prototype; independent deployed clients must not approve the same run concurrently. Google writes and receipt persistence are separate operations, so unresolved outcomes require reconciliation.

## 6. Reproduce the local checkpoint

```powershell
.\.venv312\Scripts\python.exe -m pytest -q
node scripts/check_workflows.cjs
.\.venv312\Scripts\python.exe scripts/verify_phase4.py --save
```

The last command uses test-only tools and writes `outputs/phase4_checkpoint.json` plus `outputs/phase4_verification.md`. Add `--mcp` for real authenticated discovery only. These tests do not append to Google Docs or create Gmail drafts. The live acceptance steps above remain required.
