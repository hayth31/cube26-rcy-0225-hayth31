# CLAUDE.md · Recovery Manager Durable Constraints & Hard Rules

This document establishes the binding engineering guidelines, behavioral invariants, and forbidden patterns for the **Recovery Manager** agent (`hayth31`).

---

## 1. Durable Constraints

1. **Step 5 of 5 — No Camera:** Recovery Manager operates at the end of the chain. It has no vision pipeline, no camera stream, and no image capture interface. It consumes structured operational records produced by Receiving, Prep, Pack, and Returns Managers.
2. **Never Invent Evidence:** If upstream records are missing, incomplete, or ambiguous, the only acceptable outputs are `SILENT` or `UNCERTAIN`. Fabricating evidence or extrapolating assumptions to force a claim is strictly forbidden.
3. **Precision Over Recall:** In fee recovery, an unfiled claim costs the seller a few dollars; a false claim submitted to Amazon Seller Support damages seller reputation and risks account suspension. Maintain $\ge 95\%$ Claim Precision at all times.
4. **Free-Tier Models Only:** All external AI dependencies must operate within zero-cost free tiers (e.g. Gemini 2.0 Flash on Google AI Studio). The core matching and classification engine must run 100% locally and deterministically.

---

## 2. The 5 Non-Negotiable Engineering Rules (`RULES.md`)

1. **Rule 1: Tenancy Isolation Before Any Feature:**
   - Every database query, record ingestion, and evidence join must enforce row-level security scoped to the tenant organization (`TenantContext`).
   - Tenant Alpha (`org_demo_alpha`) must never see or access Tenant Bravo (`org_demo_bravo`) rows.
   - All image reference paths must be signed with tenant-salted HMAC tokens to prevent cross-tenant key guessing.
2. **Rule 2: Batch Model Calls:**
   - Always batch claim generation calls into a single prompt carrying all units in a batch. Never make one model call per unit or per check.
3. **Rule 3: Fail Open:**
   - If an AI model fails, times out, or encounters missing API credentials, the system must never drop records or block operators. It must degrade gracefully to the deterministic legal template engine and preserve the capture.
4. **Rule 4: `UNCERTAIN` is a Valid First-Class Verdict:**
   - Ambiguous, unreadable, or conflicting evidence must output `UNCERTAIN`. It is not a low-confidence PASS. Show it prominently in the interface for human review.
5. **Rule 5: Look Authoritative Rules Up:**
   - Ground every dispute directly in published Amazon Seller Central policies (Inbound Performance Feedback, Cubiscan Discrepancies, 45-Day Return Restitution, Lost Inventory Reimbursements). Do not allow LLMs to hallucinate policy clauses.

---

## 3. Forbidden Language & Anti-Patterns

| Forbidden Phrase / Claim | Why It Is Forbidden | Acceptable Alternative |
| :--- | :--- | :--- |
| *"Tamper-evident, immutable, or anchored records"* | We do not have a public blockchain or external timestamp authority. We have internal content hashes and database timestamps. | *"Signed content hashes and timestamped operational logs."* |
| *"Low-confidence PASS"* | Blurs the line between acceptable proof and guesswork. | *"UNCERTAIN — flagged for operator review."* |
| *"It works well"* | Vague, unscientific marketing claim. | Report explicit numerical precision, recall, false positive, and false negative rates. |
| *"Auto-dispute all charges"* | Reckless strategy that causes seller account termination. | *"Conservative, evidence-backed dispute generation."* |
| Discarding operator overrides | Hides human disagreement data from evaluators. | Log original verdict, new verdict, reason, and operator ID. |
