"""
Cross-Pod Evidence Matcher.
Joins channel fee report entries with upstream operational records (Receiving, Prep, Pack, Returns)
under strict tenant boundary enforcement.
"""
from typing import Dict, List, Optional, Tuple, Set
from .models import (
    FeeChargeRecord,
    ReceivingRecord,
    PrepRecord,
    PackRecord,
    ReturnsRecord,
    EvidenceChainItem
)
from .tenancy import TenantContext

class CrossPodMatcher:
    """Joins charges against cross-pod evidence records for a single tenant."""

    def __init__(
        self,
        tenant: TenantContext,
        receiving_records: List[ReceivingRecord],
        prep_records: List[PrepRecord],
        pack_records: List[PackRecord],
        returns_records: List[ReturnsRecord]
    ):
        self.tenant = tenant
        # Verify and index records strictly for this tenant
        self.receiving_by_unit: Dict[str, ReceivingRecord] = {}
        for r in receiving_records:
            self.tenant.validate_record(r.org_id)
            self.receiving_by_unit[r.unit_id] = r

        self.prep_by_unit: Dict[str, PrepRecord] = {}
        for p in prep_records:
            self.tenant.validate_record(p.org_id)
            self.prep_by_unit[p.unit_id] = p

        self.pack_by_unit: Dict[str, PackRecord] = {}
        self.pack_by_order: Dict[str, PackRecord] = {}
        for pk in pack_records:
            self.tenant.validate_record(pk.org_id)
            self.pack_by_unit[pk.unit_id] = pk
            if pk.order_id:
                self.pack_by_order[pk.order_id] = pk

        self.returns_by_unit: Dict[str, ReturnsRecord] = {}
        self.returns_by_order: Dict[str, ReturnsRecord] = {}
        for ret in returns_records:
            self.tenant.validate_record(ret.org_id)
            self.returns_by_unit[ret.unit_id] = ret
            if ret.order_id:
                self.returns_by_order[ret.order_id] = ret

        # Reimbursement tracking set (unit_id, charge_type)
        self.reimbursed_units: Set[Tuple[str, str]] = set()

    def register_reimbursement(self, unit_id: str, charge_type: str) -> None:
        self.reimbursed_units.add((unit_id, charge_type))

    def is_already_reimbursed(self, unit_id: Optional[str], charge_type: str) -> bool:
        if not unit_id:
            return False
        return (unit_id, charge_type) in self.reimbursed_units

    def match_charge(
        self, charge: FeeChargeRecord
    ) -> Tuple[
        Optional[ReceivingRecord],
        Optional[PrepRecord],
        Optional[PackRecord],
        Optional[ReturnsRecord],
        List[EvidenceChainItem]
    ]:
        self.tenant.validate_record(charge.org_id)

        rec = self.receiving_by_unit.get(charge.unit_id) if charge.unit_id else None
        prep = self.prep_by_unit.get(charge.unit_id) if charge.unit_id else None
        
        pack = None
        if charge.unit_id and charge.unit_id in self.pack_by_unit:
            pack = self.pack_by_unit[charge.unit_id]
        elif charge.order_id and charge.order_id in self.pack_by_order:
            pack = self.pack_by_order[charge.order_id]

        ret = None
        if charge.unit_id and charge.unit_id in self.returns_by_unit:
            ret = self.returns_by_unit[charge.unit_id]
        elif charge.order_id and charge.order_id in self.returns_by_order:
            ret = self.returns_by_order[charge.order_id]

        # Build evidence chain
        chain: List[EvidenceChainItem] = []
        if rec:
            chain.append(EvidenceChainItem(
                manager="RECEIVING_MANAGER",
                record_id=rec.record_id,
                observed_findings=f"Intake qty={rec.qty_received}, carton_dmg={rec.carton_damage}, unit_dmg={rec.unit_damage}, flags={rec.quality_flags or 'none'}",
                photo_refs=rec.photo_refs,
                operator_id=rec.operator_id,
                timestamp=rec.captured_at
            ))

        if prep:
            chain.append(EvidenceChainItem(
                manager="PREP_MANAGER",
                record_id=prep.record_id,
                observed_findings=f"FNSKU={prep.fnsku_label_placement}, barcode_covered={prep.original_barcode_covered}, polybag={prep.polybag_present_sealed}, suffocation={prep.suffocation_warning}",
                photo_refs=prep.photo_refs,
                operator_id=prep.operator_id,
                timestamp=prep.captured_at
            ))

        if pack:
            chain.append(EvidenceChainItem(
                manager="PACK_MANAGER",
                record_id=pack.record_id,
                observed_findings=f"Observed in box: {pack.observed_in_box}, operator verdict: {pack.operator_verdict}",
                photo_refs=pack.photo_refs,
                operator_id=pack.operator_id,
                timestamp=pack.captured_at
            ))

        if ret:
            chain.append(EvidenceChainItem(
                manager="RETURNS_MANAGER",
                record_id=ret.record_id,
                observed_findings=f"Observed state: {ret.observed_state}, disposition: {ret.operator_disposition}, identity match: {ret.identity_match}",
                photo_refs=ret.photo_refs,
                operator_id=ret.operator_id,
                timestamp=ret.captured_at
            ))

        return rec, prep, pack, ret, chain
