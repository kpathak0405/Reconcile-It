import csv
from datetime import datetime, timedelta

# Settlement calculation run time: September 3, 2026 at 06:00 AM
base_order_time = datetime(2026, 8, 20, 10, 0, 0)
orders = []

for i in range(1, 61):
    order_id = f"ORD_{1000 + i}"
    created_at = base_order_time + timedelta(hours=i * 5)
    delivered_at = created_at + timedelta(days=1)
    customer_name = f"Distributor_{i}"
    gross_amount = round(1500.00 + (i * 120.00), 2)
    payment_method = "AMEX" if i in [28, 29] else ("NETBANKING" if i % 2 == 0 else "UPI")
    
    # Perishable goods (0 days) by default, 14 days for raw materials / equipment
    return_policy_days = 14 if i in [10, 11, 12, 15, 16] else 0
    erp_status = "SUCCESS"

    # Edge Case Injections in ERP:
    if i in [1, 2, 3]:
        # Placed late on Sept 2 - Midnight Cutoff
        created_at = datetime(2026, 9, 2, 23, 50 + i, 0)
        delivered_at = ""
    elif i in [20, 21]:
        # Interrupted Bank Debit: ERP shows Pending Verification
        erp_status = "PENDING_VERIFICATION"
        delivered_at = ""
    elif i == 35:
        # Critical Leak Simulation: ERP marked SUCCESS, but customer bank dropped
        erp_status = "SUCCESS"
        delivered_at = created_at + timedelta(hours=8)
    elif i in [44, 45]:
        # Webhook dropped: Missing completely from ERP (Ghost payment in Gateway)
        continue

    orders.append({
        "order_id": order_id,
        "created_at": created_at.isoformat() if isinstance(created_at, datetime) else created_at,
        "delivered_at": delivered_at.isoformat() if isinstance(delivered_at, datetime) else delivered_at,
        "customer_name": customer_name,
        "gross_amount": f"{gross_amount:.2f}",
        "payment_method": payment_method,
        "erp_status": erp_status,
        "return_policy_days": return_policy_days
    })

with open("internal_sales_orders.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=orders[0].keys())
    writer.writeheader()
    writer.writerows(orders)

print(f"Generated internal_sales_orders.csv with {len(orders)} rows.")