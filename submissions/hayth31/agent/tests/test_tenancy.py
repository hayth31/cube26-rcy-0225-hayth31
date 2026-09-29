"""
Tenancy isolation test suite (Rule 1: Tenancy isolation before any feature).
Verifies that Tenant Alpha cannot see, query, or forge image keys belonging to Tenant Bravo.
"""
import unittest
from core.tenancy import TenantContext, TenancyViolationError, TenantScopedStore
from core.models import FeeChargeRecord, PrepRecord
from core.matcher import CrossPodMatcher

class TestTenancyIsolation(unittest.TestCase):

    def setUp(self):
        self.tenant_alpha = TenantContext("org_demo_alpha")
        self.tenant_bravo = TenantContext("org_demo_bravo")

    def test_cross_tenant_record_validation(self):
        """Tenant Alpha must reject records belonging to Tenant Bravo."""
        with self.assertRaises(TenancyViolationError):
            self.tenant_alpha.validate_record("org_demo_bravo")

    def test_cross_tenant_matcher_leakage(self):
        """CrossPodMatcher for Alpha must raise TenancyViolationError if Bravo record is passed."""
        prep_bravo = PrepRecord(
            record_id="PRP-BRAVO-01",
            unit_id="UNIT-BRAVO-01",
            org_id="org_demo_bravo",
            work_order_id="WO-01",
            fba_shipment_id="FBA-01",
            sku="SKU-BOTTLE",
            asin=None,
            fnsku="X00B",
            prep_price_usd=0.50,
            wo_polybag=False,
            wo_suffocation_warning=False,
            wo_expiry_date=False,
            wo_handling_marks=None,
            polybag_present_sealed="not_required",
            suffocation_warning="not_required",
            fnsku_label_placement="flat",
            original_barcode_covered="yes",
            expiry_date="not_required",
            handling_marks="not_required",
            photo_refs="",
            operator_id="op1",
            captured_at="2026-06-01T00:00:00Z"
        )
        with self.assertRaises(TenancyViolationError):
            CrossPodMatcher(self.tenant_alpha, [], [prep_bravo], [], [])

    def test_tenant_isolated_store(self):
        """Tenant Alpha sees zero rows in Bravo's partition."""
        store = TenantScopedStore()
        store.insert(self.tenant_alpha, "fees", "FEE-01", {"amt": 10}, "org_demo_alpha")
        store.insert(self.tenant_bravo, "fees", "FEE-02", {"amt": 20}, "org_demo_bravo")

        alpha_records = store.list_all(self.tenant_alpha, "fees")
        bravo_records = store.list_all(self.tenant_bravo, "fees")

        self.assertEqual(len(alpha_records), 1)
        self.assertEqual(len(bravo_records), 1)
        self.assertEqual(alpha_records[0]["amt"], 10)
        self.assertEqual(bravo_records[0]["amt"], 20)

    def test_image_token_tampering_prevention(self):
        """Image reference paths cannot be accessed across tenants with guessable tokens."""
        img_path = "fixtures/prep/UNIT-0001_front.jpg"
        alpha_token = self.tenant_alpha.secure_asset_token(img_path)
        bravo_token = self.tenant_bravo.secure_asset_token(img_path)

        self.assertNotEqual(alpha_token, bravo_token)
        self.assertFalse(self.tenant_alpha.verify_asset_token(img_path, bravo_token))
        self.assertTrue(self.tenant_alpha.verify_asset_token(img_path, alpha_token))

if __name__ == "__main__":
    unittest.main()
