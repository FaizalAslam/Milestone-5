# Supplied wireframe implementation

The reference ZIP contains the Results Workspace, Upload & Processing, and Data Quality & Audit desktop layouts, plus the Fintech Intelligence Engine design tokens. The accompanying screen inventory specifies the upload, progress, output editing, evidence, approval, recovery and responsive states.

## Interface

- Local Streamlit v2 component; no separate frontend server, runtime Tailwind CDN or iframe dashboard. Bundled Inter variable font includes its SIL Open Font License.
- Match the reference header navigation, mint/green palette, lavender panels, metric cards, ranked theme cards, two-column results/upload layouts, three output tabs, audit table and evidence drawers. Layouts stack at tablet/mobile widths; audit rows become readable mobile cards.
- The app opens at an empty upload workspace. The Live/Demo switch, saved-example controls and automatic fallback to bundled analysis have been removed. Legacy example URLs open the upload screen. Operator/password controls are removed from the product UI.
- Runtime customer/model text is separate JSON data, escaped before HTML rendering. Only trusted local component code is executable. URLs are restricted to HTTPS in the renderer and retain backend source validation.

## Processing and data integrity

- A valid upload starts one background job (or restores a matching verified private run from this deployment): validation → review intelligence → official fee-source retrieval and output generation. Tab switches, evidence inspection and downloads do not submit new jobs.
- Reporting presets support 8, 10 and 12 weeks. Explicit start/end dates support inclusive 56–84 day ranges ending today or earlier. Applying a changed period explicitly recalculates; pending date edits disable approval.
- Original bytes remain intact. Schema/timestamp validation precedes duplicate review-ID handling, then date exclusion. Each rejected row has one primary reason; future-dated reviews are separately identifiable. This preserves the existing backend's precedence rather than adopting illustrative wireframe counts.
- Nonspecific reviews remain valid for sentiment and count reconciliation but do not contribute to themes or quotes. Brief concrete complaints are not removed by a word-count cutoff.
- Excluded-row CSV exports contain actual CSV exclusions. Nonspecific feedback is inspected separately and retained in the full classification export.
- Up to five themes, one primary theme per useful review, top three highlighted, and three exact source-matched quotes. The fee component shows the selected named issue and distinct original supporting texts.
- Insufficient useful feedback or fee evidence blocks approval. Already verified general findings remain visible when fee evidence/source checks fail; a speculative fee fallback is never inserted.

## Outputs and external actions

- The original validators, lineage checks, six-field document entry, email subject, n8n tools and action order are preserved.
- Pulse editing is inline, with a live word counter. Saved invalid edits stay correctable and block approval. Valid edits update all previews, create a new content version and require fresh approval.
- The fee output is presented as **Frequently Asked Fee Question**: a question framed from the selected fee issue, followed by the verified answer, review-evidence count, official links and source-check date. Copy and the `fee_faq.md` download retain that Q&A presentation. Historical approved document/email payloads remain unchanged.
- Regeneration reuses verified review intelligence and rechecks official fee sources. Downloads include pulse, explainer, email text, document JSON, complete analysis, fee passages, classification mapping and execution records.
- Only the explicit Approve and Save action generates an approval record. It validates the current server content fingerprint; stale approvals are rejected; no external write can start before validated outputs exist.
- Google Docs append precedes Gmail draft creation. The recipient stays blank; there is no send action.
- Existing SQLite/n8n receipts prevent repeating successful writes. The success panel replaces the approval controls. Confirmed safe partial failures retry only the remaining action. Unknown outcomes require read-only reconciliation; a missing receipt never unlocks a blind retry.
- An opaque same-browser reference restores active work after page refresh while the server is running. After server restart, matching CSV/window uploads can restore verified saved artifacts and durable receipts. Cloud ephemeral-storage limitations remain unchanged.

## Reference content versus actual behavior

Sample 2024 dates, counts, auto-square-off rates, fake credential labels, latency estimates and SOC-2 claims are illustrative design content. They are replaced with actual dataset values and verified execution states. The existing subject remains `Weekly Product Pulse + Customer Clarification — Groww — YYYY-MM-DD`; a design document's open question does not override the user-approved workflow contract.

## Verification

Run `python -m pytest`, `node --input-type=module --check < groww/ui/workspace.js`, `node scripts/check_workflows.cjs`, and `python scripts/verify_phase5.py --save`. Browser checks and screenshots are recorded in `outputs/ui_redesign/` and `outputs/ui_redesign_checkpoint.json`. Live and offline checks are distinguished; the redesign never self-approves a real Google write.

## Lighter interface refinement

The latest interface uses shorter labels (Insights, Upload reviews, Review data), white surfaces, subtle dividers and more space between sections. Upload instructions, pipeline labels and save copy are shorter. Theme descriptions remain in their evidence drawers; long quote IDs are under Review details. Data filtering stays visible, while file-integrity and source/execution information are expandable.

Review counts, original quote text, generated fee facts, export contents, approved payloads and write controls are unchanged. The weekly pulse preview omits its repeated title; downloads and approved communication retain the full title. Saved Demo mode remains removed.
