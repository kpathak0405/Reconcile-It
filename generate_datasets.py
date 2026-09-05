"""
generate_datasets.py — Script to generate 5 distinct pairs of ERP and Razorpay settlement CSV datasets
with different batch dates, order IDs, amounts, fees, and exception types.
"""

import os
import csv
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

DATASETS_DIR = Path(__file__).parent / "datasets"
DATASETS_DIR.mkdir(parents=True, exist_ok=True)

def to_dec_str(val):
    return f"{Decimal(str(val)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}"

def create_batch_dataset(batch_tag, start_ord_num, count, erp_filename, rzp_filename, settle_date_str):
    erp_rows = []
    rzp_rows = []

    for i in range(count):
        ord_num = start_ord_num + i
        ord_id = f"ORD_{ord_num}"
        pay_id = f"pay_{ord_num + 4000}"
        cust_name = f"Distributor_{ord_num % 80 + 1}"
        
        # Varied amounts between 1500 and 18000
        gross_val = 1500.0 + (i * 145.50) + ((i % 7) * 82.25)
        gross_str = to_dec_str(gross_val)
        gross_dec = Decimal(gross_str)

        # Default values
        created_date = f"2026-09-0{min(i % 5 + 1, 9)}T10:00:00"
        delivered_date = f"2026-09-0{min(i % 5 + 2, 9)}T10:00:00"
        pm = "AMEX" if (i % 9 == 0) else ("NETBANKING" if i % 2 == 0 else "UPI")
        erp_status = "SUCCESS"
        ret_days = "0"

        gateway_status = "CAPTURED"
        fee_rate = Decimal("0.03") if pm == "AMEX" else Decimal("0.02")
        refund_str = "0.00"
        is_eligible = "True"

        # Inject different exceptions based on batch_tag and index
        # -------------------------------------------------------------
        # Exception 1: Midnight Cutoff (Missing in Gateway for this batch)
        if i in (0, 1):
            created_date = f"{settle_date_str[:10]}T23:52:00"
            delivered_date = ""
            # Don't add to Gateway report (Missing in Gateway)
            erp_rows.append({
                "order_id": ord_id, "created_at": created_date, "delivered_at": delivered_date,
                "customer_name": cust_name, "gross_amount": gross_str, "payment_method": pm,
                "erp_status": erp_status, "return_policy_days": ret_days
            })
            continue

        # Exception 2: Ghost Payment (Missing in ERP)
        if i == count - 1:
            fee_dec = (gross_dec * fee_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            tax_dec = (fee_dec * Decimal("0.18")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            net_dec = gross_dec - fee_dec - tax_dec
            rzp_rows.append({
                "payment_id": pay_id, "order_id": ord_id, "settled_at": f"{settle_date_str}T06:00:00",
                "gateway_status": "CAPTURED", "captured_amount": gross_str, "fee": to_dec_str(fee_dec),
                "tax": to_dec_str(tax_dec), "refund_amount": "0.00", "is_settlement_eligible": "True",
                "net_settlement": to_dec_str(net_dec)
            })
            continue

        # Exception 3: Critical Bank Drop
        if i == 12:
            gateway_status = "FAILED_BANK_DEBIT"
            is_eligible = "False"

        # Exception 4: Dispute / Chargeback Hold
        if i == 25:
            gateway_status = "DISPUTED"
            is_eligible = "False"

        # Exception 5: Escrow Hold (Return Window Active)
        if i in (7, 8):
            ret_days = "14"
            is_eligible = "False"

        # Exception 6: Late Authorization Desync
        if i == 18:
            erp_status = "PENDING_VERIFICATION"
            delivered_date = ""

        # Exception 7: Partial Refund
        if i in (14, 15):
            refund_str = "450.00"

        # Exception 8: Mathematical Variance
        variance_extra = Decimal("0.00")
        if i == 22:
            variance_extra = Decimal("150.00") # Discrepancy

        # Build ERP Row
        erp_rows.append({
            "order_id": ord_id, "created_at": created_date, "delivered_at": delivered_date,
            "customer_name": cust_name, "gross_amount": gross_str, "payment_method": pm,
            "erp_status": erp_status, "return_policy_days": ret_days
        })

        # Calculate Gateway Amounts
        if gateway_status in ("FAILED_BANK_DEBIT", "DISPUTED"):
            captured_str = "0.00" if gateway_status == "FAILED_BANK_DEBIT" else gross_str
            fee_str = "0.00" if gateway_status == "FAILED_BANK_DEBIT" else to_dec_str((gross_dec * fee_rate).quantize(Decimal("0.01")))
            tax_str = "0.00" if gateway_status == "FAILED_BANK_DEBIT" else to_dec_str((Decimal(fee_str) * Decimal("0.18")).quantize(Decimal("0.01")))
            net_str = "0.00"
        elif is_eligible == "False":
            captured_str = gross_str
            fee_dec = (gross_dec * fee_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            tax_dec = (fee_dec * Decimal("0.18")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            fee_str = to_dec_str(fee_dec)
            tax_str = to_dec_str(tax_dec)
            net_str = "0.00"
        else:
            captured_str = gross_str
            fee_dec = (gross_dec * fee_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            tax_dec = (fee_dec * Decimal("0.18")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            refund_dec = Decimal(refund_str)
            net_dec = gross_dec - fee_dec - tax_dec - refund_dec - variance_extra
            fee_str = to_dec_str(fee_dec)
            tax_str = to_dec_str(tax_dec)
            net_str = to_dec_str(net_dec)

        # Build Razorpay Row
        rzp_rows.append({
            "payment_id": pay_id, "order_id": ord_id, "settled_at": f"{settle_date_str}T06:00:00",
            "gateway_status": gateway_status, "captured_amount": captured_str, "fee": fee_str,
            "tax": tax_str, "refund_amount": refund_str, "is_settlement_eligible": is_eligible,
            "net_settlement": net_str
        })

    # Write ERP CSV
    erp_path = DATASETS_DIR / erp_filename
    with open(erp_path, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "order_id","created_at","delivered_at","customer_name",
            "gross_amount","payment_method","erp_status","return_policy_days"
        ])
        writer.writeheader()
        writer.writerows(erp_rows)

    # Write Razorpay CSV
    rzp_path = DATASETS_DIR / rzp_filename
    with open(rzp_path, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "payment_id","order_id","settled_at","gateway_status",
            "captured_amount","fee","tax","refund_amount",
            "is_settlement_eligible","net_settlement"
        ])
        writer.writeheader()
        writer.writerows(rzp_rows)

    print(f"Generated Batch {batch_tag}: {erp_filename} ({len(erp_rows)} rows) & {rzp_filename} ({len(rzp_rows)} rows)")

# Generate 5 Sets of Batch CSV Files in datasets/
batches_config = [
    ("SETTLE_20260904", 2001, 45, "erp_sales_orders_20260904.csv", "razorpay_settlement_20260904.csv", "2026-09-04"),
    ("SETTLE_20260905", 3001, 50, "erp_sales_orders_20260905.csv", "razorpay_settlement_20260905.csv", "2026-09-05"),
    ("SETTLE_20260906", 4001, 40, "erp_sales_orders_20260906.csv", "razorpay_settlement_20260906.csv", "2026-09-06"),
    ("SETTLE_20260907", 5001, 55, "erp_sales_orders_20260907.csv", "razorpay_settlement_20260907.csv", "2026-09-07"),
    ("SETTLE_20260908", 6001, 50, "erp_sales_orders_20260908.csv", "razorpay_settlement_20260908.csv", "2026-09-08"),
]

for btag, start_ord, count, erp_name, rzp_name, date_str in batches_config:
    create_batch_dataset(btag, start_ord, count, erp_name, rzp_name, date_str)
