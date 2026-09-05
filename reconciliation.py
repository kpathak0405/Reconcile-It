import csv
from decimal import Decimal, ROUND_HALF_UP

def to_dec(val):
    if not val:
        return Decimal("0.00")
    return Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def run_reconciliation(erp_file="datasets/internal_sales_orders.csv", gateway_file="datasets/razorpay_settlement_report.csv"):
    # 1. Ingest ERP data
    erp_records = {}
    with open(erp_file, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            erp_records[row["order_id"]] = row

    # 2. Ingest Gateway data
    gateway_records = {}
    with open(gateway_file, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            gateway_records[row["order_id"]] = row

    reconciled = []
    exceptions = []

    # Financial ledger accumulators
    total_gross = Decimal("0.00")
    total_fee = Decimal("0.00")
    total_tax_itc = Decimal("0.00")
    total_net_settled = Decimal("0.00")

    all_order_ids = sorted(list(set(erp_records.keys()).union(set(gateway_records.keys()))))

    for oid in all_order_ids:
        erp = erp_records.get(oid)
        gtw = gateway_records.get(oid)

        # Failure Case 1: Missing in Gateway (Timing / Midnight Cutoff)
        if not gtw:
            exceptions.append({
                "order_id": oid,
                "type": "MISSING_IN_GATEWAY",
                "discrepancy_amount": erp["gross_amount"],
                "context": f"ERP recorded order on {erp['created_at']}, but not settled in this batch.",
                "erp_status": erp["erp_status"],
                "gateway_status": "NONE"
            })
            continue

        # Failure Case 2: Missing in ERP (Ghost Payment / Webhook Drop)
        if not erp:
            exceptions.append({
                "order_id": oid,
                "type": "GHOST_PAYMENT_IN_GATEWAY",
                "discrepancy_amount": gtw["net_settlement"],
                "context": f"Gateway collected ₹{gtw['captured_amount']} (Pay ID: {gtw['payment_id']}), but missing from merchant ERP.",
                "erp_status": "NONE",
                "gateway_status": gtw["gateway_status"]
            })
            continue

        # Convert to Decimal for exact math
        gross = to_dec(erp["gross_amount"])
        captured = to_dec(gtw["captured_amount"])
        fee = to_dec(gtw["fee"])
        tax = to_dec(gtw["tax"])
        refund = to_dec(gtw["refund_amount"])
        net = to_dec(gtw["net_settlement"])
        is_eligible = gtw["is_settlement_eligible"].strip().lower() == "true"

        # Failure Case 3: Upstream Bank Drop / Critical Leak
        if gtw["gateway_status"] == "FAILED_BANK_DEBIT":
            exceptions.append({
                "order_id": oid,
                "type": "CRITICAL_BANK_DROP",
                "discrepancy_amount": str(gross),
                "context": f"ERP marked as {erp['erp_status']}, but gateway captured ₹0.00 (Customer debit failed upstream).",
                "erp_status": erp["erp_status"],
                "gateway_status": gtw["gateway_status"]
            })
            continue

        # Failure Case 4: Dispute / Chargeback Hold
        if gtw["gateway_status"] == "DISPUTED":
            exceptions.append({
                "order_id": oid,
                "type": "DISPUTE_CHARGEBACK_HOLD",
                "discrepancy_amount": str(gross),
                "context": "Chargeback active. Payout held back by gateway.",
                "erp_status": erp["erp_status"],
                "gateway_status": gtw["gateway_status"]
            })
            continue

        # Failure Case 5: Escrow Hold (Active 14-day return window)
        if not is_eligible:
            exceptions.append({
                "order_id": oid,
                "type": "ESCROW_RETURN_WINDOW_ACTIVE",
                "discrepancy_amount": str(captured),
                "context": f"Active return policy ({erp['return_policy_days']} days). Funds held in escrow until window expires.",
                "erp_status": erp["erp_status"],
                "gateway_status": gtw["gateway_status"]
            })
            continue

        # Failure Case 6: Late Authorization / Webhook Sync Issue
        if erp["erp_status"] == "PENDING_VERIFICATION" and gtw["gateway_status"] == "CAPTURED":
            exceptions.append({
                "order_id": oid,
                "type": "LATE_AUTHORIZATION_DESYNC",
                "discrepancy_amount": str(net),
                "context": "Customer funds captured by Razorpay, but ERP status is still PENDING_VERIFICATION.",
                "erp_status": erp["erp_status"],
                "gateway_status": gtw["gateway_status"]
            })
            continue

        # Standard Mathematical Validation
        expected_net = captured - fee - tax - refund
        variance = abs(net - expected_net)

        if variance <= Decimal("0.05"):
            # Clean Match
            reconciled.append({
                "order_id": oid,
                "payment_id": gtw["payment_id"],
                "gross_amount": str(gross),
                "fee": str(fee),
                "tax": str(tax),
                "refund_amount": str(refund),
                "net_settlement": str(net)
            })
            total_gross += gross
            total_fee += fee
            total_tax_itc += tax
            total_net_settled += net
        else:
            exceptions.append({
                "order_id": oid,
                "type": "MATHEMATICAL_VARIANCE",
                "discrepancy_amount": str(variance),
                "context": f"Net settlement (₹{net}) does not equal captured minus deductions (₹{expected_net}).",
                "erp_status": erp["erp_status"],
                "gateway_status": gtw["gateway_status"]
            })

    # Summary Report
    total_processed = len(all_order_ids)
    match_rate = (len(reconciled) / total_processed) * 100 if total_processed > 0 else 0

    print("=" * 60)
    print("FINANCE CONTROLLER RECONCILIATION SUMMARY")
    print("=" * 60)
    print(f"Total Transactions Processed : {total_processed}")
    print(f"Cleanly Reconciled           : {len(reconciled)} ({match_rate:.1f}%)")
    print(f"Exceptions Requiring AI      : {len(exceptions)}")
    print("-" * 60)
    print(f"Total Gross Sales Verified   : ₹{total_gross:,.2f}")
    print(f"Gateway Processing Fees      : ₹{total_fee:,.2f}")
    print(f"Eligible Input Tax Credit    : ₹{total_tax_itc:,.2f}")
    print(f"Net Deposited in Bank        : ₹{total_net_settled:,.2f}")
    print("=" * 60)

    return reconciled, exceptions

if __name__ == "__main__":
    reconciled, exceptions = run_reconciliation()