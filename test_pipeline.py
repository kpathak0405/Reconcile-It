from reconciliation import run_reconciliation
from agentic import diagnose_exceptions

print("1. Running deterministic reconciliation...")
reconciled, exceptions = run_reconciliation()
print(f"   -> Clean Records : {len(reconciled)}")
print(f"   -> Exceptions    : {len(exceptions)}")

print("\n2. Passing exceptions to AI Diagnostic Agent...")
diagnosed_memos = diagnose_exceptions(exceptions)
print(f"   -> Diagnosed Memos Generated: {len(diagnosed_memos)}")

# Preview the first diagnosed memo
if diagnosed_memos:
    sample = diagnosed_memos[0]
    print("\nSample Audit Memo:")
    print(f"Order ID  : {sample['order_id']}")
    print(f"Category  : {sample['variance_category']}")
    print(f"Risk      : {sample['risk_level']}")
    print(f"Diagnosis : {sample['root_cause_diagnosis']}")
    print(f"Action    : {sample['accounting_action']}")