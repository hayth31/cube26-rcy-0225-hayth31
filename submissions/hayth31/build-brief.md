# Build Brief · Recovery Manager

**Author:** `hayth31`  
**System:** Recovery Manager (Step 5 of 5)  
**Target:** Sydon AI Cube Buildathon · Commerce Context Stream · Round 2  

---

## 1. System Overview

Recovery Manager is an autonomous, evidence-driven fee dispute engine. It reconciles financial charges deducted by ecommerce channels (specifically Amazon FBA) against physical operational records captured by upstream warehouse managers:
- **01. Receiving Manager:** Dock arrival condition, PO verification, carton damage, unit damage.
- **02. Prep Manager:** Unit compliance, polybagging, suffocation warnings, FNSKU label placement, barcode masking.
- **03. Pack Manager:** Outbound carton contents, certified scale weights, physical dimensions, box sealing.
- **04. Returns Manager:** Customer return intake, LPN matching, physical condition grading, disposition.

Recovery Manager has **no vision system**. It operates purely on structured digital records, image hashes, and timestamps to assemble audit-proof dispute packages.

```text
 ┌──────────────────────┐
 │ Channel Fee Reports  │
 └──────────┬───────────┘
            │ Ingest & Parse
            ▼
 ┌─────────────────────────────────────────────────────────────┐
 │                Tenancy Isolation Boundary                   │
 │                (Scoped to TenantContext)                    │
 └──────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
 ┌─────────────────────────────────────────────────────────────┐
 │               Cross-Pod Evidence Matcher                    │
 │               Joins on unit_id, sku, shipment_id            │
 └──────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
 ┌─────────────────────────────────────────────────────────────┐
 │               Authoritative Rules Engine                    │
 │  Evaluates official Amazon dispute policies:                │
 │  - Inbound Defect Policy (30-day window)                    │
 │  - Cubiscan Weight Tier Discrepancies (90-day window)       │
 │  - Lost Inventory Reimbursements (180-day window)           │
 │  - Customer Return 45-Day Restitution (60-day window)       │
 └──────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
 ┌─────────────────────────────────────────────────────────────┐
 │                4-Way Classification Engine                  │
 │   CONTRADICTED · SUPPORTED · SILENT · UNCERTAIN             │
 └──────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
 ┌─────────────────────────────────────────────────────────────┐
 │            Batched Claim Synthesizer (Fail-Open)            │
 │   Free-Tier Gemini 2.0 Flash / Local Legal Template Engine  │
 └──────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
 ┌─────────────────────────────────────────────────────────────┐
 │           Dispute Package & Evidence Record Page            │
 └─────────────────────────────────────────────────────────────┘
```

---

## 2. Core Data Flow & Joining Logic

### 2.1 Universal Joining Keys
Every product is tracked by its universal `unit_id` (`UNIT-0001` through `UNIT-0100`). Secondary matching indexes join records via:
- `fba_shipment_id` (Inbound shipments from Receiving and Prep)
- `order_id` (Outbound orders from Pack and customer returns from Returns)
- `sku` / `fnsku` (Catalog identity and product tier specifications)

### 2.2 Charge Resolution Pathways

1. **Inbound Defect Fees (`inbound_defect_fee`):**
   - *Query:* Match `unit_id` against `PrepRecord` and `ReceivingRecord`.
   - *Logic:* If prep verifies `fnsku_label_placement == "flat"`, `original_barcode_covered == "yes"`, and `polybag_present_sealed == "yes"`, with no receiving defect flag $\rightarrow$ **CONTRADICTED**.
   - *Ambiguity:* If `original_barcode_covered == "uncertain"` $\rightarrow$ **UNCERTAIN**.
   - *True Defect:* If `polybag_present_sealed == "no"` or receiving flags `obvious_defect` $\rightarrow$ **SUPPORTED** (No claim).

2. **Weight Tier Overcharges (`fulfilment_fee_weight_tier`):**
   - *Query:* Lookup SKU in `AUTHORITATIVE_SKU_BENCHMARKS`.
   - *Logic:* If `amount_usd > expected_fee_usd` $\rightarrow$ **CONTRADICTED** (Overcharge amount calculated as `amount_usd - expected_fee_usd`).

3. **Lost Inbound Inventory (`lost_inbound`):**
   - *Query:* Verify dock intake in `ReceivingRecord` (`qty_received >= 1`) and verify no existing `reimbursement_report` credit exists.
   - *Logic:* If dock confirmed intake but Amazon adjusted inventory to lost without payment $\rightarrow$ **CONTRADICTED**.

4. **Unreturned Customer Refunds (`refund_issued_item_not_returned`):**
   - *Query:* Match order in `ReturnsRecord`.
   - *Logic:* If warehouse return scan verifies item was physically received back into facility $\rightarrow$ **CONTRADICTED**.

---

## 3. Engineering Decisions & Trade-Offs

- **Deterministic Rules vs LLM:** We chose a **hybrid architecture**. 100% of data matching and verdict classification is performed deterministically. This guarantees mathematical repeatability, microsecond execution, and zero hallucination. External LLMs are utilized solely for drafting polite, persuasive dispute prose.
- **Fail-Open Resilience:** If the LLM API is rate-limited or unavailable, the system automatically falls back to an offline deterministic template. Operations are never blocked.
- **Strict Row-Level Tenancy:** Implemented via explicit `TenantContext` validation at the query and storage boundary, completely eliminating cross-tenant leakage.
