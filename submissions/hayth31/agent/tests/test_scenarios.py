"""
Unit test suite verifying all 8 required test scenarios for Recovery Manager.
"""
import unittest
from core.models import (
    FeeChargeRecord,
    ReceivingRecord,
    PrepRecord,
    PackRecord,
    ReturnsRecord,
    ClaimVerdict
)
from core.tenancy import TenantContext
from core.matcher import CrossPodMatcher
from core.evaluator import RecoveryEvaluator

class TestRecoveryScenarios(unittest.TestCase):

    def setUp(self):
        self.tenant = TenantContext("org_demo_alpha")

    def test_scenario_1_correct_claim_full_evidence(self):
        """Scenario 1: Defect fee contradicted by full prep compliance evidence."""
        charge = FeeChargeRecord(
            line_id="FEE-TEST-01",
            report_type="fee_report",
            unit_id="UNIT-TEST-01",
            org_id="org_demo_alpha",
            sku="SKU-LAMP-LED",
            fnsku="X00TEST01",
            fba_shipment_id="FBA-TEST-100",
            order_id=None,
            charge_type="inbound_defect_fee",
            quantity=1,
            amount_usd=2.00,
            posted_date="2026-07-01"
        )
        prep = PrepRecord(
            record_id="PRP-TEST-01",
            unit_id="UNIT-TEST-01",
            org_id="org_demo_alpha",
            work_order_id="WO-01",
            fba_shipment_id="FBA-TEST-100",
            sku="SKU-LAMP-LED",
            asin=None,
            fnsku="X00TEST01",
            prep_price_usd=0.55,
            wo_polybag=False,
            wo_suffocation_warning=False,
            wo_expiry_date=False,
            wo_handling_marks=None,
            polybag_present_sealed="not_required",
            suffocation_warning="not_required",
            fnsku_label_placement="flat",
            original_barcode_covered="yes",
            expiry_date="not_required",
            handling_marks="all_present",
            photo_refs="fixtures/prep/test.jpg",
            operator_id="op_amira",
            captured_at="2026-06-01T12:00:00Z"
        )
        rec = ReceivingRecord(
            record_id="RCV-TEST-01",
            unit_id="UNIT-TEST-01",
            org_id="org_demo_alpha",
            po_number="PO-100",
            po_line="1",
            supplier="Supplier Alpha",
            sku="SKU-LAMP-LED",
            asin=None,
            product_title="LED Lamp",
            spec_colour=None,
            spec_variant=None,
            spec_components=None,
            cartons_ordered=1,
            cartons_received=1,
            units_per_carton_ordered=10,
            units_per_carton_counted=10,
            qty_ordered=10,
            qty_received=10,
            identity_match="yes",
            carton_damage="none",
            unit_damage="none",
            quality_flags=None,
            photo_refs="",
            operator_id="op_amira",
            captured_at="2026-06-01T10:00:00Z"
        )
        matcher = CrossPodMatcher(self.tenant, [rec], [prep], [], [])
        evaluator = RecoveryEvaluator(self.tenant, matcher)
        result = evaluator.evaluate_charge(charge)

        self.assertEqual(result.verdict, ClaimVerdict.CONTRADICTED.value)
        self.assertTrue(result.claim_recommended)
        self.assertEqual(result.claim_amount_usd, 2.00)
        self.assertIn("contradicted by certified prep audit", result.dispute_grounds)

    def test_scenario_2_claim_with_partial_evidence(self):
        """Scenario 2: Claim supported by dock receiving proof without prep record."""
        charge = FeeChargeRecord(
            line_id="FEE-TEST-02",
            report_type="inventory_adjustment",
            unit_id="UNIT-TEST-02",
            org_id="org_demo_alpha",
            sku="SKU-LAMP-LED",
            fnsku=None,
            fba_shipment_id="FBA-TEST-100",
            order_id=None,
            charge_type="lost_inbound",
            quantity=1,
            amount_usd=0.00,
            posted_date="2026-07-01"
        )
        rec = ReceivingRecord(
            record_id="RCV-TEST-02",
            unit_id="UNIT-TEST-02",
            org_id="org_demo_alpha",
            po_number="PO-100",
            po_line="1",
            supplier="Supplier Alpha",
            sku="SKU-LAMP-LED",
            asin=None,
            product_title="LED Lamp",
            spec_colour=None,
            spec_variant=None,
            spec_components=None,
            cartons_ordered=1,
            cartons_received=1,
            units_per_carton_ordered=10,
            units_per_carton_counted=10,
            qty_ordered=10,
            qty_received=10,
            identity_match="yes",
            carton_damage="none",
            unit_damage="none",
            quality_flags=None,
            photo_refs="",
            operator_id="op_amira",
            captured_at="2026-06-01T10:00:00Z"
        )
        matcher = CrossPodMatcher(self.tenant, [rec], [], [], [])
        evaluator = RecoveryEvaluator(self.tenant, matcher)
        result = evaluator.evaluate_charge(charge)

        self.assertEqual(result.verdict, ClaimVerdict.CONTRADICTED.value)
        self.assertTrue(result.claim_recommended)
        self.assertGreater(result.claim_amount_usd, 0.0)

    def test_scenario_3_claim_with_no_evidence_silent(self):
        """Scenario 3: No records exist -> Verdict must be SILENT (Do not invent evidence)."""
        charge = FeeChargeRecord(
            line_id="FEE-TEST-03",
            report_type="fee_report",
            unit_id="UNIT-NONEXISTENT",
            org_id="org_demo_alpha",
            sku="SKU-UNKNOWN",
            fnsku=None,
            fba_shipment_id="FBA-UNKNOWN",
            order_id=None,
            charge_type="inbound_defect_fee",
            quantity=1,
            amount_usd=5.00,
            posted_date="2026-07-01"
        )
        matcher = CrossPodMatcher(self.tenant, [], [], [], [])
        evaluator = RecoveryEvaluator(self.tenant, matcher)
        result = evaluator.evaluate_charge(charge)

        self.assertEqual(result.verdict, ClaimVerdict.SILENT.value)
        self.assertFalse(result.claim_recommended)
        self.assertEqual(result.claim_amount_usd, 0.0)
        self.assertIsNotNone(result.explanation_if_unsupported)

    def test_scenario_4_multiple_charges_same_shipment(self):
        """Scenario 4: Multiple different charges on the same shipment."""
        c1 = FeeChargeRecord("FEE-14-1", "fee_report", "UNIT-0014", "org_demo_alpha", "SKU-LAMP-LED", None, "FBA-101", None, "inbound_defect_fee", 1, 2.00, "2026-07-18")
        c2 = FeeChargeRecord("FEE-14-3", "fee_report", "UNIT-0014", "org_demo_alpha", "SKU-LAMP-LED", None, "FBA-101", "ORD-50014", "fulfilment_fee_weight_tier", 1, 4.75, "2026-06-20")

        prep = PrepRecord("PRP-14", "UNIT-0014", "org_demo_alpha", "WO-1", "FBA-101", "SKU-LAMP-LED", None, "X0014", 0.55, False, False, False, None, "not_required", "not_required", "flat", "yes", "not_required", "all_present", "", "op1", "2026-06-06T07:36:00Z")
        rec = ReceivingRecord("RCV-14", "UNIT-0014", "org_demo_alpha", "PO-1", None, "Supp", "SKU-LAMP-LED", None, "Lamp", None, None, None, 1, 1, 1, 1, 1, 1, "yes", "none", "none", None, "", "op1", "2026-06-04T14:36:00Z")

        matcher = CrossPodMatcher(self.tenant, [rec], [prep], [], [])
        evaluator = RecoveryEvaluator(self.tenant, matcher)
        res1 = evaluator.evaluate_charge(c1)
        res2 = evaluator.evaluate_charge(c2)

        self.assertEqual(res1.verdict, ClaimVerdict.CONTRADICTED.value)
        self.assertEqual(res2.verdict, ClaimVerdict.CONTRADICTED.value)
        self.assertEqual(res2.claim_amount_usd, 1.25)  # 4.75 - 3.50 expected

    def test_scenario_5_fee_matches_evidence_from_different_manager(self):
        """Scenario 5: Customer return discrepancy fee matched against Returns Manager record."""
        charge = FeeChargeRecord("FEE-RET-01", "fee_report", "UNIT-0014", "org_demo_alpha", "SKU-LAMP-LED", None, None, "ORD-50014", "refund_issued_item_not_returned", 1, 0.00, "2026-07-18")
        ret = ReturnsRecord("RTN-14", "UNIT-0014", "org_demo_alpha", "ORD-50014", "SKU-LAMP-LED", None, "yes", None, None, "signs_of_use", None, "liquidate", "", "op1", "2026-07-18T07:36:00Z")

        matcher = CrossPodMatcher(self.tenant, [], [], [], [ret])
        evaluator = RecoveryEvaluator(self.tenant, matcher)
        res = evaluator.evaluate_charge(charge)

        self.assertEqual(res.verdict, ClaimVerdict.CONTRADICTED.value)
        self.assertEqual(res.evidence_chain[0].manager, "RETURNS_MANAGER")

    def test_scenario_6_ambiguous_evidence_uncertain(self):
        """Scenario 6: Ambiguous/uncertain evidence must yield UNCERTAIN verdict (Rule 4)."""
        charge = FeeChargeRecord("FEE-UNC-01", "fee_report", "UNIT-0035", "org_demo_alpha", "SKU-CABLE-USBC", None, "FBA-103", None, "inbound_defect_fee", 1, 0.50, "2026-07-15")
        prep = PrepRecord("PRP-35", "UNIT-0035", "org_demo_alpha", "WO-1", "FBA-103", "SKU-CABLE-USBC", None, "X0035", 0.40, True, True, False, None, "yes", "legible", "flat", "uncertain", "not_required", "not_required", "", "op1", "2026-06-09T22:21:00Z")

        matcher = CrossPodMatcher(self.tenant, [], [prep], [], [])
        evaluator = RecoveryEvaluator(self.tenant, matcher)
        res = evaluator.evaluate_charge(charge)

        self.assertEqual(res.verdict, ClaimVerdict.UNCERTAIN.value)
        self.assertFalse(res.claim_recommended)

    def test_scenario_7_duplicate_charges(self):
        """Scenario 7: Duplicate identical charges on same unit/shipment."""
        c1 = FeeChargeRecord("FEE-DUP-01", "fee_report", "UNIT-DUP", "org_demo_alpha", "SKU-BOTTLE-750", None, "FBA-DUP", None, "inbound_defect_fee", 1, 1.00, "2026-07-01")
        c2 = FeeChargeRecord("FEE-DUP-02", "fee_report", "UNIT-DUP", "org_demo_alpha", "SKU-BOTTLE-750", None, "FBA-DUP", None, "inbound_defect_fee", 1, 1.00, "2026-07-02")

        matcher = CrossPodMatcher(self.tenant, [], [], [], [])
        evaluator = RecoveryEvaluator(self.tenant, matcher)
        res1 = evaluator.evaluate_charge(c1)
        res2 = evaluator.evaluate_charge(c2)

        self.assertEqual(res2.verdict, ClaimVerdict.DUPLICATE.value)
        self.assertTrue(res2.claim_recommended)
        self.assertEqual(res2.claim_amount_usd, 1.00)

    def test_scenario_8_already_reimbursed_charges(self):
        """Scenario 8: Charge already reimbursed in past reimbursement report."""
        charge = FeeChargeRecord("FEE-REIMB-01", "fee_report", "UNIT-0071", "org_demo_alpha", "SKU-CABLE-USBC", None, "FBA-107", None, "lost_inbound", 1, 0.00, "2026-07-01")
        matcher = CrossPodMatcher(self.tenant, [], [], [], [])
        matcher.register_reimbursement("UNIT-0071", "lost_inbound")

        evaluator = RecoveryEvaluator(self.tenant, matcher)
        res = evaluator.evaluate_charge(charge)

        self.assertEqual(res.verdict, ClaimVerdict.ALREADY_REIMBURSED.value)
        self.assertFalse(res.claim_recommended)
        self.assertEqual(res.claim_amount_usd, 0.0)

if __name__ == "__main__":
    unittest.main()
