"""
Headless CLI Runner for Recovery Manager.
Cube Buildathon · Commerce Context · Round 2
Processes fee reports, matches cross-pod evidence, evaluates defensible claims, and outputs results.
"""
import os
import csv
import json
import argparse
from typing import List, Dict, Any
from core.models import (
    FeeChargeRecord,
    ReceivingRecord,
    PrepRecord,
    PackRecord,
    ReturnsRecord,
    ClaimPackage,
    ClaimVerdict
)
from core.tenancy import TenantContext
from core.matcher import CrossPodMatcher
from core.evaluator import RecoveryEvaluator
from core.claim_builder import BatchedClaimBuilder

def load_csv(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def run_recovery_for_org(
    org_id: str,
    fee_records: List[FeeChargeRecord],
    receiving_records: List[ReceivingRecord],
    prep_records: List[PrepRecord],
    pack_records: List[PackRecord],
    returns_records: List[ReturnsRecord],
    gemini_key: str = ""
) -> List[ClaimPackage]:
    # 1. Establish strict tenant context (Rule 1)
    tenant = TenantContext(org_id=org_id)

    # Filter all records for this tenant only
    t_fees = [f for f in fee_records if f.org_id == org_id]
    t_rec = [r for r in receiving_records if r.org_id == org_id]
    t_prep = [p for p in prep_records if p.org_id == org_id]
    t_pack = [pk for pk in pack_records if pk.org_id == org_id]
    t_ret = [ret for ret in returns_records if ret.org_id == org_id]

    # 2. Initialize Matcher and register prior reimbursements
    matcher = CrossPodMatcher(
        tenant=tenant,
        receiving_records=t_rec,
        prep_records=t_prep,
        pack_records=t_pack,
        returns_records=t_ret
    )

    for f in t_fees:
        if f.report_type == "reimbursement_report" and f.unit_id:
            matcher.register_reimbursement(f.unit_id, f.charge_type)

    # 3. Evaluate charges
    evaluator = RecoveryEvaluator(tenant=tenant, matcher=matcher)
    evaluated_packages = evaluator.evaluate_batch(t_fees)

    # 4. Synthesize formal dispute claims in batched model call (Rule 2 & 3)
    builder = BatchedClaimBuilder(api_key=gemini_key)
    final_packages = builder.build_formal_claims(evaluated_packages)

    return final_packages

def print_summary(org_id: str, packages: List[ClaimPackage]) -> None:
    print(f"\n{'='*75}")
    print(f"RECOVERY MANAGER SUMMARY REPORT · Tenant: {org_id}")
    print(f"{'='*75}")
    total_charges = len(packages)
    contradicted = [p for p in packages if p.verdict == ClaimVerdict.CONTRADICTED.value]
    supported = [p for p in packages if p.verdict == ClaimVerdict.SUPPORTED.value]
    silent = [p for p in packages if p.verdict == ClaimVerdict.SILENT.value]
    uncertain = [p for p in packages if p.verdict == ClaimVerdict.UNCERTAIN.value]
    already_reimb = [p for p in packages if p.verdict == ClaimVerdict.ALREADY_REIMBURSED.value]
    duplicates = [p for p in packages if p.verdict == ClaimVerdict.DUPLICATE.value]

    total_claim_val = sum(p.claim_amount_usd for p in packages if p.claim_recommended)

    print(f"Total Charges Evaluated: {total_charges}")
    print(f"  - CONTRADICTED (Claims Recommended) : {len(contradicted)}")
    print(f"  - SUPPORTED (Valid Fees / Defect)   : {len(supported)}")
    print(f"  - SILENT (Insufficient Evidence)    : {len(silent)}")
    print(f"  - UNCERTAIN (Flagged for Review)    : {len(uncertain)}")
    print(f"  - ALREADY REIMBURSED (Pre-credited) : {len(already_reimb)}")
    print(f"  - DUPLICATE CHARGES (Overbilled)    : {len(duplicates)}")
    print(f"\nTotal Recoverable Dollars Identified: ${total_claim_val:.2f}")

    print(f"\nSample Recommended Claims:")
    for p in (contradicted + duplicates)[:5]:
        print(f"  [{p.line_id}] {p.charge_type} on {p.unit_id or 'N/A'}: ${p.claim_amount_usd:.2f} (Conf: {p.confidence_score*100:.0f}%)")
        print(f"    Grounds: {p.dispute_grounds.splitlines()[0] if p.dispute_grounds else 'N/A'}")

def main():
    parser = argparse.ArgumentParser(description="Run Recovery Manager headless agent")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_data_dir = os.path.abspath(os.path.join(script_dir, "..", "..", "..", "data"))
    parser.add_argument("--data-dir", default=default_data_dir, help="Path to data directory")
    parser.add_argument("--org", default="all", help="Target org: org_demo_alpha, org_demo_bravo, or all")
    parser.add_argument("--output", default="recovery_output.json", help="Path to save output JSON")
    args = parser.parse_args()

    fee_path = os.path.join(args.data_dir, "fee_report_sample.csv")
    rec_path = os.path.join(args.data_dir, "upstream", "receiving_sample.csv")
    prep_path = os.path.join(args.data_dir, "upstream", "prep_sample.csv")
    pack_path = os.path.join(args.data_dir, "upstream", "pack_sample.csv")
    ret_path = os.path.join(args.data_dir, "upstream", "returns_sample.csv")

    fee_records = [FeeChargeRecord.from_dict(d) for d in load_csv(fee_path)]
    rec_records = [ReceivingRecord.from_dict(d) for d in load_csv(rec_path)]
    prep_records = [PrepRecord.from_dict(d) for d in load_csv(prep_path)]
    pack_records = [PackRecord.from_dict(d) for d in load_csv(pack_path)]
    ret_records = [ReturnsRecord.from_dict(d) for d in load_csv(ret_path)]

    orgs_to_process = ["org_demo_alpha", "org_demo_bravo"] if args.org == "all" else [args.org]
    all_results = {}

    for org in orgs_to_process:
        packages = run_recovery_for_org(
            org_id=org,
            fee_records=fee_records,
            receiving_records=rec_records,
            prep_records=prep_records,
            pack_records=pack_records,
            returns_records=ret_records
        )
        print_summary(org, packages)
        all_results[org] = [p.to_dict() for p in packages]

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nAll results saved successfully to {args.output}")

if __name__ == "__main__":
    main()
