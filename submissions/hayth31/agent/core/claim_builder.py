"""
Batched Claim Synthesizer powered by Free-Tier Gemini API with Fail-Open Architecture.
(Rule 2: Batch your model calls; Rule 3: Fail open; Free-tier models only).
"""
import os
import json
import logging
from typing import List, Dict, Any, Optional
import urllib.request
import urllib.error
from .models import ClaimPackage, ClaimVerdict

logger = logging.getLogger(__name__)

class BatchedClaimBuilder:
    """
    Synthesizes formal dispute packages for contradictory claims.
    Uses free-tier Gemini API (gemini-2.0-flash / gemini-1.5-flash) in batched mode.
    If the API key is not provided or the network request fails, it fails open
    with high-fidelity deterministic dispute drafting.
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.0-flash"):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.model = model

    def build_formal_claims(self, claim_packages: List[ClaimPackage]) -> List[ClaimPackage]:
        """
        Takes a list of ClaimPackages. For packages with verdict CONTRADICTED,
        synthesizes official dispute claim letters in a SINGLE batched model call.
        """
        claimable = [pkg for pkg in claim_packages if pkg.claim_recommended]
        if not claimable:
            return claim_packages

        # If API key is present, attempt batched LLM synthesis
        if self.api_key:
            try:
                self._synthesize_batch_with_gemini(claimable)
                return claim_packages
            except Exception as e:
                logger.warning(f"Batched Gemini model call failed open: {e}. Falling back to deterministic synthesis.")

        # Fail Open / Default Deterministic Synthesis (Rule 3)
        for pkg in claimable:
            pkg.dispute_grounds = self._deterministic_dispute_letter(pkg)

        return claim_packages

    def _synthesize_batch_with_gemini(self, packages: List[ClaimPackage]) -> None:
        """
        Batches multiple claims into a SINGLE prompt to adhere to Rule 2 (Batch model calls).
        """
        items_payload = []
        for p in packages:
            evid_summaries = [f"[{e.manager}] Record {e.record_id}: {e.observed_findings} (Operator: {e.operator_id or 'N/A'})" for e in p.evidence_chain]
            items_payload.append({
                "line_id": p.line_id,
                "unit_id": p.unit_id,
                "sku": p.sku,
                "charge_type": p.charge_type,
                "amount_usd": p.claim_amount_usd,
                "policy_name": p.cited_policy.get("policy_name", ""),
                "evidence": evid_summaries
            })

        prompt = (
            "You are the Recovery Manager agent for an ecommerce brand disputing improper charges with Amazon Seller Support.\n"
            "Review the following batch of substantiated disputes. For each item, write a professional, firm, and evidence-backed dispute statement citing the official policy and the attached operational records.\n"
            "Return a JSON object with a single key 'claims' which is a list of objects containing 'line_id' and 'formal_dispute_letter'.\n\n"
            f"Claims to dispute:\n{json.dumps(items_payload, indent=2)}"
        )

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "response_mime_type": "application/json"
            }
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(content)
            claims_map = {c["line_id"]: c["formal_dispute_letter"] for c in parsed.get("claims", [])}
            for p in packages:
                if p.line_id in claims_map:
                    p.dispute_grounds = claims_map[p.line_id]

    def _deterministic_dispute_letter(self, pkg: ClaimPackage) -> str:
        """Deterministic dispute letter template ensuring 100% precision and zero hallucination."""
        policy_title = pkg.cited_policy.get("policy_name", "Amazon Marketplace Dispute Policy")
        policy_url = pkg.cited_policy.get("source_url", "")
        
        evidence_lines = []
        for e in pkg.evidence_chain:
            photo_info = f" [Photos: {e.photo_refs}]" if e.photo_refs else ""
            evidence_lines.append(f"  - {e.manager} ({e.record_id}, {e.timestamp or 'N/A'}): {e.observed_findings}{photo_info}")

        evidence_block = "\n".join(evidence_lines) if evidence_lines else "  - Automated system audit comparison."

        return (
            f"DISPUTE CLAIM FILING · {pkg.line_id}\n"
            f"Target: Amazon Seller Support / FBA Reimbursements Team\n"
            f"Subject: Formal Dispute of Improper Fee: {pkg.charge_type} (${pkg.assessed_amount_usd:.2f}) for Unit {pkg.unit_id or 'N/A'}\n"
            f"Governing Policy: {policy_title} ({policy_url})\n\n"
            f"Case Summary:\n"
            f"The fee of ${pkg.assessed_amount_usd:.2f} assessed against unit {pkg.unit_id or 'N/A'} (SKU: {pkg.sku or 'N/A'}) "
            f"is contradicted by verified warehouse operational evidence. Under {policy_title}, we request a reimbursement credit of ${pkg.claim_amount_usd:.2f}.\n\n"
            f"Operational Evidence Audit Trail:\n{evidence_block}\n\n"
            f"Action Requested:\n"
            f"Reimburse ${pkg.claim_amount_usd:.2f} to seller balance and reverse the associated defect rate notation."
        )
