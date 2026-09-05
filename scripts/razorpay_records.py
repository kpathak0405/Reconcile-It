import csv
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

def round_curr(val):
    return Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

# Gateway settlement batch processed on September 3, 2026 at 06:00 AM
settlement_time = datetime(2026, 9, 3, 6, 0, 0)
settlements = []

for i in range(1, 61):
    # Orders 1, 2, 3 were past cut-off -> pushed to next settlement batch
    if i in [1, 2, 3]:
        continue

    order_id = f"ORD_{1000 + i}"
    payment_id = f"pay_{5000 + i}"
    gross_amount = Decimal(str(round(1500.00 + (i * 120.00), 2)))
    
    # Standard rates: 2% domestic, 3% for Amex
    mdr_rate = Decimal("0.03") if i in [28, 29] else Decimal("0.02")
    gst_rate = Decimal("0.18")
    
    gateway_status = "CAPTURED"
    captured_amount = gross_amount
    fee = round_curr(captured_amount * mdr_rate)
    tax = round_curr(fee * gst_rate)
    refund_amount = Decimal("0.00")
    
    # 14-day policy applies to orders 10, 11, 12, 15, 16
    is_long_return = i in [10, 11, 12, 15, 16]
    
    # Edge Cases & Settlement Flags:
    if i in [10, 11, 12]:
        # Active 14-day return window: Escrow holdback -> Not eligible yet
        is_settlement_eligible = False
        net_settlement = Decimal("0.00")
    elif i in [15, 16]:
        # Return window passed, but partial refund issued for damaged stock
        is_settlement_eligible = True
        refund_amount = Decimal("400.00")
        net_settlement = round_curr(captured_amount - fee - tax - refund_amount)
    elif i in [20, 21]:
        # Late Auth: Razorpay captured successfully (ERP missed webhook)
        is_settlement_eligible = True
        net_settlement = round_curr(captured_amount - fee - tax)
    elif i == 35:
        # Bank drop: Payment failed upstream at the bank
        gateway_status = "FAILED_BANK_DEBIT"
        captured_amount = Decimal("0.00")
        fee = Decimal("0.00")
        tax = Decimal("0.00")
        is_settlement_eligible = False
        net_settlement = Decimal("0.00")
    elif i == 55:
        # Chargeback / Dispute hold
        gateway_status = "DISPUTED"
        is_settlement_eligible = False
        net_settlement = Decimal("0.00")
    else:
        # Clean standard settlement
        is_settlement_eligible = True
        net_settlement = round_curr(captured_amount - fee - tax)

    settlements.append({
        "payment_id": payment_id,
        "order_id": order_id,
        "settled_at": settlement_time.isoformat(),
        "gateway_status": gateway_status,
        "captured_amount": f"{captured_amount:.2f}",
        "fee": f"{fee:.2f}",
        "tax": f"{tax:.2f}",
        "refund_amount": f"{refund_amount:.2f}",
        "is_settlement_eligible": str(is_settlement_eligible),
        "net_settlement": f"{net_settlement:.2f}"
    })

with open("razorpay_settlement_report.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=settlements[0].keys())
    writer.writeheader()
    writer.writerows(settlements)

print(f"Generated razorpay_settlement_report.csv with {len(settlements)} rows.")