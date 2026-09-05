"""
database.py — Supabase database integration layer for ReconcileIt.

Provides persistent storage and retrieval for:
  - Batches & cut-off schedules
  - Staged feed files
  - Reconciliation results, KPI metrics & Gemini diagnostics
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")

supabase_client = None

if SUPABASE_URL and SUPABASE_ANON_KEY:
    try:
        from supabase import create_client
        supabase_client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        print(f"[INFO] Supabase client initialized for {SUPABASE_URL}")
    except Exception as err:
        print(f"[WARN] Failed to initialize Supabase client: {err}")


def save_staged_file_to_db(batch_id: str, feed_type: str, filename: str, file_size: int = 0):
    """Save staged file metadata to Supabase staged_files table."""
    if not supabase_client:
        return
    try:
        # Ensure batch row exists
        supabase_client.table("batches").upsert({"batch_id": batch_id}).execute()
        # Insert staged file record
        supabase_client.table("staged_files").insert({
            "batch_id": batch_id,
            "feed_type": feed_type,
            "filename": filename,
            "file_size": file_size
        }).execute()
        print(f"[INFO] Saved staged file '{filename}' for batch '{batch_id}' to Supabase")
    except Exception as e:
        print(f"[WARN] Supabase save_staged_file failed: {e}")


def save_reconciliation_to_db(batch_id: str, kpi: dict, verified_count: int, total_count: int, exceptions: list, diagnostics: list):
    """Save reconciliation execution KPIs and AI diagnostics to Supabase."""
    if not supabase_client:
        return
    try:
        # Mark batch as reconciled
        supabase_client.table("batches").upsert({
            "batch_id": batch_id,
            "reconciled": True,
            "kpi": kpi
        }).execute()

        # Upsert reconciliation_results
        supabase_client.table("reconciliation_results").upsert({
            "batch_id": batch_id,
            "verified_count": verified_count,
            "total_count": total_count,
            "kpi": kpi,
            "exceptions": exceptions,
            "diagnostics": diagnostics
        }, on_conflict="batch_id").execute()
        print(f"[INFO] Successfully saved reconciliation results for '{batch_id}' to Supabase")
    except Exception as e:
        print(f"[WARN] Supabase save_reconciliation failed: {e}")


def get_batch_data_from_db(batch_id: str):
    """
    Retrieve batch state, staged file listings, KPI metrics and diagnostics from Supabase.
    Returns dict if found, or None if not present/error.
    """
    if not supabase_client:
        return None

    try:
        # Query batches table
        batch_res = supabase_client.table("batches").select("*").eq("batch_id", batch_id).execute()
        if not batch_res.data:
            return None

        batch_info = batch_res.data[0]

        # Query staged_files table
        files_res = supabase_client.table("staged_files").select("*").eq("batch_id", batch_id).execute()
        erp_files = [f["filename"] for f in files_res.data if f.get("feed_type") == "erp"]
        rzp_files = [f["filename"] for f in files_res.data if f.get("feed_type") == "razorpay"]

        # Query reconciliation_results table
        rec_res = supabase_client.table("reconciliation_results").select("*").eq("batch_id", batch_id).execute()
        rec_data = rec_res.data[0] if rec_res.data else None

        return {
            "batch_id": batch_id,
            "cutoff_time": batch_info.get("cutoff_time", "23:50:00 IST"),
            "reconciled": batch_info.get("reconciled", False) or (rec_data is not None),
            "files": {
                "erp": erp_files,
                "razorpay": rzp_files
            },
            "kpi": rec_data.get("kpi") if rec_data else batch_info.get("kpi"),
            "diagnostics": rec_data.get("diagnostics", []) if rec_data else [],
            "exceptions": rec_data.get("exceptions", []) if rec_data else []
        }
    except Exception as e:
        print(f"[WARN] Supabase get_batch_data failed for '{batch_id}': {e}")
        return None
