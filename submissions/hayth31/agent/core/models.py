"""
Data models and typed contracts for Recovery Manager.
Enforces validation, serialization, and cross-pod evidence definitions.
"""
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from enum import Enum
import json

class ReportType(str, Enum):
    FEE_REPORT = "fee_report"
    INVENTORY_ADJUSTMENT = "inventory_adjustment"
    REIMBURSEMENT_REPORT = "reimbursement_report"

class ChargeType(str, Enum):
    INBOUND_DEFECT_FEE = "inbound_defect_fee"
    FULFILMENT_FEE_WEIGHT_TIER = "fulfilment_fee_weight_tier"
    LOST_INBOUND = "lost_inbound"
    DAMAGED_IN_WAREHOUSE = "damaged_in_warehouse"
    REFUND_ISSUED_ITEM_NOT_RETURNED = "refund_issued_item_not_returned"
    UNPLANNED_PREP_FEE = "unplanned_prep_fee"
    BARCODE_MISSING = "barcode_missing_or_unreadable"

class ClaimVerdict(str, Enum):
    CONTRADICTED = "CONTRADICTED"     # Evidence proves accusation false -> Claim eligible
    SUPPORTED = "SUPPORTED"           # Evidence proves defect occurred -> No claim (valid fee)
    SILENT = "SILENT"                 # Insufficient or no evidence -> Cannot claim
    UNCERTAIN = "UNCERTAIN"           # Evidence is ambiguous / conflicting -> Flag for human review
    ALREADY_REIMBURSED = "ALREADY_REIMBURSED"  # Credit already received -> Prevent duplicate claim
    DUPLICATE = "DUPLICATE"           # Duplicate fee assessed on same shipment/unit -> Claim refund

@dataclass
class FeeChargeRecord:
    line_id: str
    report_type: str
    unit_id: Optional[str]
    org_id: str
    sku: Optional[str]
    fnsku: Optional[str]
    fba_shipment_id: Optional[str]
    order_id: Optional[str]
    charge_type: str
    quantity: int
    amount_usd: float
    posted_date: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FeeChargeRecord":
        return cls(
            line_id=data.get("line_id", ""),
            report_type=data.get("report_type", "fee_report"),
            unit_id=data.get("unit_id") or None,
            org_id=data.get("org_id", ""),
            sku=data.get("sku") or None,
            fnsku=data.get("fnsku") or None,
            fba_shipment_id=data.get("fba_shipment_id") or None,
            order_id=data.get("order_id") or None,
            charge_type=data.get("charge_type", ""),
            quantity=int(data.get("quantity") or 1),
            amount_usd=float(data.get("amount_usd") or 0.0),
            posted_date=data.get("posted_date", "")
        )

@dataclass
class ReceivingRecord:
    record_id: str
    unit_id: str
    org_id: str
    po_number: str
    po_line: Optional[str]
    supplier: str
    sku: str
    asin: Optional[str]
    product_title: str
    spec_colour: Optional[str]
    spec_variant: Optional[str]
    spec_components: Optional[str]
    cartons_ordered: int
    cartons_received: int
    units_per_carton_ordered: int
    units_per_carton_counted: int
    qty_ordered: int
    qty_received: int
    identity_match: str
    carton_damage: str
    unit_damage: str
    quality_flags: Optional[str]
    photo_refs: str
    operator_id: str
    captured_at: str

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ReceivingRecord":
        return cls(
            record_id=d.get("record_id", ""),
            unit_id=d.get("unit_id", ""),
            org_id=d.get("org_id", ""),
            po_number=d.get("po_number", ""),
            po_line=d.get("po_line"),
            supplier=d.get("supplier", ""),
            sku=d.get("sku", ""),
            asin=d.get("asin"),
            product_title=d.get("product_title", ""),
            spec_colour=d.get("spec_colour"),
            spec_variant=d.get("spec_variant"),
            spec_components=d.get("spec_components"),
            cartons_ordered=int(d.get("cartons_ordered") or 0),
            cartons_received=int(d.get("cartons_received") or 0),
            units_per_carton_ordered=int(d.get("units_per_carton_ordered") or 0),
            units_per_carton_counted=int(d.get("units_per_carton_counted") or 0),
            qty_ordered=int(d.get("qty_ordered") or 0),
            qty_received=int(d.get("qty_received") or 0),
            identity_match=d.get("identity_match", "uncertain"),
            carton_damage=d.get("carton_damage", "none"),
            unit_damage=d.get("unit_damage", "none"),
            quality_flags=d.get("quality_flags") or None,
            photo_refs=d.get("photo_refs", ""),
            operator_id=d.get("operator_id", ""),
            captured_at=d.get("captured_at", "")
        )

@dataclass
class PrepRecord:
    record_id: str
    unit_id: str
    org_id: str
    work_order_id: str
    fba_shipment_id: str
    sku: str
    asin: Optional[str]
    fnsku: str
    prep_price_usd: float
    wo_polybag: bool
    wo_suffocation_warning: bool
    wo_expiry_date: bool
    wo_handling_marks: Optional[str]
    polybag_present_sealed: str
    suffocation_warning: str
    fnsku_label_placement: str
    original_barcode_covered: str
    expiry_date: str
    handling_marks: str
    photo_refs: str
    operator_id: str
    captured_at: str

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PrepRecord":
        return cls(
            record_id=d.get("record_id", ""),
            unit_id=d.get("unit_id", ""),
            org_id=d.get("org_id", ""),
            work_order_id=d.get("work_order_id", ""),
            fba_shipment_id=d.get("fba_shipment_id", ""),
            sku=d.get("sku", ""),
            asin=d.get("asin"),
            fnsku=d.get("fnsku", ""),
            prep_price_usd=float(d.get("prep_price_usd") or 0.0),
            wo_polybag=str(d.get("wo_polybag", "")).lower() == "true",
            wo_suffocation_warning=str(d.get("wo_suffocation_warning", "")).lower() == "true",
            wo_expiry_date=str(d.get("wo_expiry_date", "")).lower() == "true",
            wo_handling_marks=d.get("wo_handling_marks") or None,
            polybag_present_sealed=d.get("polybag_present_sealed", "not_required"),
            suffocation_warning=d.get("suffocation_warning", "not_required"),
            fnsku_label_placement=d.get("fnsku_label_placement", "missing"),
            original_barcode_covered=d.get("original_barcode_covered", "not_required"),
            expiry_date=d.get("expiry_date", "not_required"),
            handling_marks=d.get("handling_marks", "not_required"),
            photo_refs=d.get("photo_refs", ""),
            operator_id=d.get("operator_id", ""),
            captured_at=d.get("captured_at", "")
        )

@dataclass
class PackRecord:
    record_id: str
    unit_id: str
    org_id: str
    order_id: str
    channel: str
    order_lines: str
    observed_in_box: str
    operator_verdict: str
    photo_refs: str
    operator_id: str
    captured_at: str

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PackRecord":
        return cls(
            record_id=d.get("record_id", ""),
            unit_id=d.get("unit_id", ""),
            org_id=d.get("org_id", ""),
            order_id=d.get("order_id", ""),
            channel=d.get("channel", ""),
            order_lines=d.get("order_lines", ""),
            observed_in_box=d.get("observed_in_box", ""),
            operator_verdict=d.get("operator_verdict", "uncertain"),
            photo_refs=d.get("photo_refs", ""),
            operator_id=d.get("operator_id", ""),
            captured_at=d.get("captured_at", "")
        )

@dataclass
class ReturnsRecord:
    record_id: str
    unit_id: str
    org_id: str
    order_id: str
    ordered_sku: str
    ordered_asin: Optional[str]
    identity_match: str
    parts_list: Optional[str]
    parts_missing: Optional[str]
    observed_state: str
    amazon_condition: Optional[str]
    operator_disposition: str
    photo_refs: str
    operator_id: str
    captured_at: str

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ReturnsRecord":
        return cls(
            record_id=d.get("record_id", ""),
            unit_id=d.get("unit_id", ""),
            org_id=d.get("org_id", ""),
            order_id=d.get("order_id", ""),
            ordered_sku=d.get("ordered_sku", ""),
            ordered_asin=d.get("ordered_asin"),
            identity_match=d.get("identity_match", "uncertain"),
            parts_list=d.get("parts_list"),
            parts_missing=d.get("parts_missing"),
            observed_state=d.get("observed_state", "uncertain"),
            amazon_condition=d.get("amazon_condition"),
            operator_disposition=d.get("operator_disposition", "uncertain"),
            photo_refs=d.get("photo_refs", ""),
            operator_id=d.get("operator_id", ""),
            captured_at=d.get("captured_at", "")
        )

@dataclass
class EvidenceChainItem:
    manager: str
    record_id: str
    observed_findings: str
    photo_refs: Optional[str] = None
    operator_id: Optional[str] = None
    timestamp: Optional[str] = None

@dataclass
class HumanOverride:
    is_overridden: bool = False
    original_verdict: Optional[str] = None
    new_verdict: Optional[str] = None
    override_reason: Optional[str] = None
    operator_id: Optional[str] = None
    overridden_at: Optional[str] = None

@dataclass
class ClaimPackage:
    line_id: str
    unit_id: Optional[str]
    org_id: str
    sku: Optional[str]
    charge_type: str
    assessed_amount_usd: float
    verdict: str
    claim_recommended: bool
    claim_amount_usd: float
    confidence_score: float
    dispute_grounds: str
    cited_policy: Dict[str, str]
    evidence_chain: List[EvidenceChainItem] = field(default_factory=list)
    explanation_if_unsupported: Optional[str] = None
    human_override: HumanOverride = field(default_factory=HumanOverride)
    evaluation_timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
