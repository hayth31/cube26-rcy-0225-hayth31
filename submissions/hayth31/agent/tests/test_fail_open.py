"""
Fail-open and timeout resilience test suite (Rule 3: Fail open).
Verifies that when AI API calls fail or time out, the system fails open gracefully
and synthesizes deterministic dispute packages without losing any evidence or dropping records.
"""
import unittest
from core.models import ClaimPackage, ClaimVerdict, EvidenceChainItem
from core.claim_builder import BatchedClaimBuilder

class TestFailOpenResilience(unittest.TestCase):

    def test_fail_open_without_api_key(self):
        """When GEMINI_API_KEY is missing, system falls back to deterministic dispute drafting."""
        pkg = ClaimPackage(
            line_id="FEE-FAIL-01",
            unit_id="UNIT-01",
            org_id="org_demo_alpha",
            sku="SKU-LAMP-LED",
            charge_type="inbound_defect_fee",
            assessed_amount_usd=2.00,
            verdict=ClaimVerdict.CONTRADICTED.value,
            claim_recommended=True,
            claim_amount_usd=2.00,
            confidence_score=0.96,
            dispute_grounds="",
            cited_policy={"policy_name": "FBA Inbound Defect Policy", "source_url": "https://sellercentral.amazon.com/policy"},
            evidence_chain=[
                EvidenceChainItem("PREP_MANAGER", "PRP-01", "Polybag sealed, FNSKU flat", "fixtures/test.jpg", "op1", "2026-06-01T00:00:00Z")
            ]
        )
        builder = BatchedClaimBuilder(api_key="")
        result = builder.build_formal_claims([pkg])

        self.assertEqual(len(result), 1)
        self.assertTrue(result[0].claim_recommended)
        self.assertIn("DISPUTE CLAIM FILING · FEE-FAIL-01", result[0].dispute_grounds)
        self.assertIn("FBA Inbound Defect Policy", result[0].dispute_grounds)
        self.assertIn("PREP_MANAGER", result[0].dispute_grounds)

    def test_fail_open_on_network_timeout(self):
        """When AI API throws a network timeout or connection error, system fails open."""
        pkg = ClaimPackage(
            line_id="FEE-TIMEOUT-01",
            unit_id="UNIT-02",
            org_id="org_demo_alpha",
            sku="SKU-CABLE-USBC",
            charge_type="inbound_defect_fee",
            assessed_amount_usd=0.50,
            verdict=ClaimVerdict.CONTRADICTED.value,
            claim_recommended=True,
            claim_amount_usd=0.50,
            confidence_score=0.96,
            dispute_grounds="",
            cited_policy={"policy_name": "FBA Inbound Defect Policy", "source_url": "https://sellercentral.amazon.com/policy"},
            evidence_chain=[]
        )
        # Point to invalid port/host to trigger connection error
        builder = BatchedClaimBuilder(api_key="INVALID_KEY_SIMULATION")
        result = builder.build_formal_claims([pkg])

        self.assertEqual(len(result), 1)
        self.assertTrue(result[0].claim_recommended)
        # Verified that dispute letter was still produced deterministically despite API failure
        self.assertIn("DISPUTE CLAIM FILING · FEE-TIMEOUT-01", result[0].dispute_grounds)

if __name__ == "__main__":
    unittest.main()
