import os
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

# 1. Define Strict Pydantic Schema for Guaranteed Output Format
class AuditMemo(BaseModel):
    order_id: str
    variance_category: str = Field(
        description="One of: TIMING_CUTOFF, ESCROW_HOLD, GHOST_WEBHOOK, BANK_DROP, DISPUTE, FEE_SURCHARGE, UNKNOWN"
    )
    root_cause_diagnosis: str = Field(
        description="Concise 1-2 sentence technical financial diagnosis of why this record deviated."
    )
    accounting_action: str = Field(
        description="Specific journal entry, API trigger, or manual workflow step the finance team must execute."
    )
    risk_level: str = Field(
        description="One of: LOW, MEDIUM, CRITICAL"
    )

class BatchAuditReport(BaseModel):
    memos: list[AuditMemo]

# 2. System Instructions Grounded in Corporate Gateway Accounting
SYSTEM_PROMPT = """
You are the AI Finance Controller, having an experience of 15+ years in various fintech companies and currently working for an enterprise merchant integrated with Razorpay.
Your sole job is to analyze an Unresolved Discrepancy Queue produced by our deterministic matching engine.

Accounting & Policy Context:
1. Midnight Cutoff (T+2): Orders logged after 23:50 IST roll into the subsequent settlement batch. This is an expected timing variance, not a financial leakage.
2. Escrow Holdback: For goods with active return/replacement windows (e.g., 14 days), gateway holds net payout in nodal escrow to avoid clawbacks. Funds release automatically upon window expiry.
3. Ghost Payment: Razorpay captured customer funds, but merchant ERP missed the webhook callback. The merchant has received unearned revenue; ERP order must be backfilled/marked SUCCESS.
4. Upstream Bank Drop: Customer debited, but gateway status is FAILED_BANK_DEBIT. Money reverses automatically via RBI T+5 guidelines. Merchant MUST NOT fulfill or dispatch.
5. Dispute / Chargeback: Funds are frozen by card networks. Merchant must upload proof of delivery (POD) within 72 hours.

Output strict JSON adhering to the BatchAuditReport schema.
"""

def diagnose_exceptions(exceptions_list: list[dict]) -> list[dict]:
    """
    Accepts the raw in-memory exceptions list from reconcile.py.
    Returns a list of structured audit memos.
    """
    if not exceptions_list:
        return []

    client = genai.Client()

    # Pass the raw exceptions batch directly in the prompt
    prompt = f"Analyze these {len(exceptions_list)} reconciliation exceptions:\n\n{exceptions_list}"

    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=BatchAuditReport,
            temperature=0.1
        )
    )

    # Parse and validate the response
    parsed_report = BatchAuditReport.model_validate_json(response.text)
    return [memo.model_dump() for memo in parsed_report.memos]