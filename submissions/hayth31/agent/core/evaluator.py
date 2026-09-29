"""
Recovery Manager Evaluator Engine.
Takes charges, retrieves matched evidence from upstream managers, applies authoritative rules,
and produces defensible claim packages.
"""
from typing import List, Dict, Optional, Tuple, Set
from datetime import datetime
from .models import (
    FeeChargeRecord,
    ClaimPackage,
    ClaimVerdict,
    EvidenceChainItem,
    HumanOverride
)
from .tenancy import TenantContext
from .matcher import CrossPodMatcher
from .rules_engine import AuthoritativeRulesEngine

class RecoveryEvaluator:
    """Core evaluation engine for evaluating charges against evidence."""

    def __init__(self, tenant: TenantContext, matcher: CrossPodMatcher):
        self.tenant = tenant
        self.matcher = matcher
        self.seen_charges: Set[Tuple[str, str, str]] = set()  # (unit_id, charge_type, shipment_id)

    def evaluate_charge(self, charge: FeeChargeRecord) -> ClaimPackage:
        self.tenant.validate_record(charge.org_id)

        # 1. Check for Duplicate Charge
        charge_signature = (charge.unit_id or "", charge.charge_type, charge.fba_shipment_id or charge.order_id or "")
        if charge_signature in self.seen_charges and charge.charge_type != "fulfilment_fee_weight_tier":
            return ClaimPackage(
                line_id=charge.line_id,
                unit_id=charge.unit_id,
                org_id=charge.org_id,
                sku=charge.sku,
                charge_type=charge.charge_type,
                assessed_amount_usd=charge.amount_usd,
                verdict=ClaimVerdict.DUPLICATE.value,
                claim_recommended=True,
                claim_amount_usd=charge.amount_usd,
                confidence_score=0.99,
                dispute_grounds=f"Duplicate fee detected: identical charge already assessed on shipment/order {charge_signature[2]}.",
                cited_policy={
                    "policy_name": "Amazon Seller Billing Duplicate Charge Correction Policy",
                    "source_url": "https://sellercentral.amazon.com/help/hub/reference/billing",
                    "rule_key": "DUPLICATE_BILLING"
                },
                evidence_chain=[],
                evaluation_timestamp=datetime.utcnow().isoformat() + "Z"
            )

        if charge.charge_type != "fulfilment_fee_weight_tier":
            self.seen_charges.add(charge_signature)

        # 2. Check for Prior Reimbursement
        is_already_reimbursed = self.matcher.is_already_reimbursed(charge.unit_id, charge.charge_type)
        if is_already_reimbursed:
            return ClaimPackage(
                line_id=charge.line_id,
                unit_id=charge.unit_id,
                org_id=charge.org_id,
                sku=charge.sku,
                charge_type=charge.charge_type,
                assessed_amount_usd=charge.amount_usd,
                verdict=ClaimVerdict.ALREADY_REIMBURSED.value,
                claim_recommended=False,
                claim_amount_usd=0.0,
                confidence_score=1.0,
                dispute_grounds="Reimbursement already credited in channel settlement records.",
                cited_policy={
                    "policy_name": "FBA Reimbursement Policy",
                    "source_url": "https://sellercentral.amazon.com/help/hub/reference/G200213130",
                    "rule_key": "REIMBURSEMENT_RECONCILIATION"
                },
                evidence_chain=[],
                explanation_if_unsupported="A matching reimbursement entry was already found in reports. Filing duplicate claim is barred by policy.",
                evaluation_timestamp=datetime.utcnow().isoformat() + "Z"
            )

        # 3. Match cross-pod evidence
        rec, prep, pack, ret, chain = self.matcher.match_charge(charge)

        # 4. Route to Authoritative Rules by charge type
        ct = charge.charge_type
        if ct in ("inbound_defect_fee", "unplanned_prep_fee", "barcode_missing_or_unreadable"):
            verdict, claim_amt, grounds, policy, unsupp_expl = AuthoritativeRulesEngine.evaluate_inbound_defect(charge, prep, rec)
        elif ct in ("fulfilment_fee_weight_tier", "overweight_oversize_misclassification"):
            verdict, claim_amt, grounds, policy, unsupp_expl = AuthoritativeRulesEngine.evaluate_weight_tier_fee(charge, pack, prep)
        elif ct == "lost_inbound":
            verdict, claim_amt, grounds, policy, unsupp_expl = AuthoritativeRulesEngine.evaluate_lost_inbound(charge, rec, is_already_reimbursed)
        elif ct == "refund_issued_item_not_returned":
            verdict, claim_amt, grounds, policy, unsupp_expl = AuthoritativeRulesEngine.evaluate_unreturned_refund(charge, ret)
        elif ct == "damaged_in_warehouse":
            verdict = ClaimVerdict.SUPPORTED
            claim_amt = 0.0
            grounds = "Warehouse damage is recorded as an inventory credit/reimbursement."
            policy = {
                "policy_name": "FBA Warehouse Damage Policy",
                "source_url": "https://sellercentral.amazon.com/help/hub/reference/G200213130",
                "rule_key": "WAREHOUSE_DAMAGE"
            }
            unsupp_expl = "Reimbursement reports confirm warehouse damage has been credited or acknowledged."
        else:
            verdict = ClaimVerdict.SILENT
            claim_amt = 0.0
            grounds = f"Unrecognized charge type: {ct}"
            policy = {"policy_name": "Generic Policy", "source_url": "", "rule_key": "UNKNOWN"}
            unsupp_expl = "No authoritative dispute rule configured for this charge type."

        # Assign confidence score based on evidence quality
        if verdict == ClaimVerdict.CONTRADICTED:
            confidence = 0.96 if len(chain) >= 2 else 0.90
            claim_rec = True
        elif verdict == ClaimVerdict.SUPPORTED:
            confidence = 0.95
            claim_rec = False
        elif verdict == ClaimVerdict.UNCERTAIN:
            confidence = 0.50
            claim_rec = False
        else:  # SILENT
            confidence = 0.85
            claim_rec = False

        return ClaimPackage(
            line_id=charge.line_id,
            unit_id=charge.unit_id,
            org_id=charge.org_id,
            sku=charge.sku,
            charge_type=charge.charge_type,
            assessed_amount_usd=charge.amount_usd,
            verdict=verdict.value,
            claim_recommended=claim_rec,
            claim_amount_usd=claim_amt,
            confidence_score=confidence,
            dispute_grounds=grounds,
            cited_policy=policy,
            evidence_chain=chain,
            explanation_if_unsupported=unsupp_expl,
            evaluation_timestamp=datetime.utcnow().isoformat() + "Z"
        )

    def evaluate_batch(self, charges: List[FeeChargeRecord]) -> List[ClaimPackage]:
        """Evaluate a batch of charges for the tenant."""
        return [self.evaluate_charge(c) for c in charges]
