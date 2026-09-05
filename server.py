"""
server.py — Flask API serving the Razorpay Autonomous Settlement Auditor.

Endpoints:
  GET  /                        → Render the single-page application
  POST /api/stage-files         → Accept multipart uploads, write to data/staging/
  POST /api/run-reconciliation  → Execute matching engine + Gemini diagnostics
"""

import os
import sys

# Force UTF-8 encoding for stdout and stderr to handle unicode characters like ₹ on Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import csv
import glob
import traceback
from pathlib import Path
from decimal import Decimal

from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

# ── Load environment variables ──────────────────────────────────────────────
# The .env uses `export KEY=VAL` syntax, dotenv handles stripping `export `
load_dotenv(override=True)

# Ensure GEMINI_API_KEY is available (dotenv may have loaded it with `export` prefix)
_gemini_key = os.environ.get("GEMINI_API_KEY")
if not _gemini_key:
    # Try stripping `export ` prefix manually from raw .env read
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith("export "):
                line = line[len("export "):]
            if line.startswith("GEMINI_API_KEY="):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                os.environ["GEMINI_API_KEY"] = val
                break

# ── Import backend modules ──────────────────────────────────────────────────
from reconciliation import run_reconciliation
from agentic import diagnose_exceptions
from database import (
    save_staged_file_to_db,
    save_reconciliation_to_db,
    get_batch_data_from_db
)

# ── Flask Application ───────────────────────────────────────────────────────
app = Flask(
    __name__,
    static_folder="static",
    template_folder="templates"
)

STAGING_ROOT = Path(__file__).parent / "data" / "staging"
STAGING_ROOT.mkdir(parents=True, exist_ok=True)
(STAGING_ROOT / "erp").mkdir(exist_ok=True)
(STAGING_ROOT / "razorpay").mkdir(exist_ok=True)


# ── CORS Middleware ──────────────────────────────────────────────────────────
@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


# In-memory cache for per-batch reconciliation results
BATCH_RESULTS = {}


# ── Routes ──────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the single-page application."""
    return render_template("index.html")


@app.route("/api/stage-files", methods=["POST", "OPTIONS"])
def stage_files():
    """
    Accept multipart FormData with:
      - batch_id: e.g. 'SETTLE_20260903'
      - feed_type: 'erp' | 'razorpay'
      - files[]: one or more uploaded file objects
    Writes them into data/staging/{batch_id}/{feed_type}/.
    """
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    batch_id = request.form.get("batch_id", "SETTLE_20260903").strip()
    feed_type = request.form.get("feed_type", "").strip().lower()
    if feed_type not in ("erp", "razorpay"):
        return jsonify({"error": "feed_type must be 'erp' or 'razorpay'"}), 400

    target_dir = STAGING_ROOT / batch_id / feed_type
    target_dir.mkdir(parents=True, exist_ok=True)

    uploaded = request.files.getlist("files")
    if not uploaded:
        return jsonify({"error": "No files provided"}), 400

    saved = []
    for f in uploaded:
        if f.filename:
            safe_name = Path(f.filename).name  # strip directory components
            dest = target_dir / safe_name
            f.save(str(dest))
            saved.append(safe_name)
            # Save file metadata to Supabase DB
            save_staged_file_to_db(batch_id, feed_type, safe_name, dest.stat().st_size)

    # Invalidate cached reconciliation result for this batch since new files were staged
    BATCH_RESULTS.pop(batch_id, None)

    return jsonify({"status": "ok", "batch_id": batch_id, "feed_type": feed_type, "files_saved": len(saved), "filenames": saved})


@app.route("/api/batch-state/<batch_id>", methods=["GET", "OPTIONS"])
def get_batch_state(batch_id):
    """Return the current staging and reconciliation state for a specific batch."""
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    # 1. Try fetching from Supabase Database
    db_data = get_batch_data_from_db(batch_id)
    if db_data and (db_data.get("reconciled") or (db_data.get("files") and (db_data["files"]["erp"] or db_data["files"]["razorpay"]))):
        BATCH_RESULTS[batch_id] = db_data
        return jsonify({"status": "ok", **db_data})

    # 2. Local File/Memory Fallback
    batch_dir = STAGING_ROOT / batch_id
    erp_files = [Path(f).name for f in glob.glob(str(batch_dir / "erp" / "*"))]
    rzp_files = [Path(f).name for f in glob.glob(str(batch_dir / "razorpay" / "*"))]

    # Special handling for default seed batch SETTLE_20260903 if not staged in subfolder
    if batch_id == "SETTLE_20260903" and not erp_files:
        erp_files = [Path(f).name for f in glob.glob(str(STAGING_ROOT / "erp" / "*.csv"))]
    if batch_id == "SETTLE_20260903" and not rzp_files:
        rzp_files = [Path(f).name for f in glob.glob(str(STAGING_ROOT / "razorpay" / "*.csv"))]

    cached = BATCH_RESULTS.get(batch_id)

    return jsonify({
        "status": "ok",
        "batch_id": batch_id,
        "files": {
            "erp": erp_files,
            "razorpay": rzp_files,
        },
        "reconciled": cached is not None and cached.get("reconciled", True),
        "kpi": cached.get("kpi") if cached else None,
        "diagnostics": cached.get("diagnostics", []) if cached else [],
        "exceptions": cached.get("exceptions", []) if cached else [],
    })


@app.route("/api/run-reconciliation", methods=["POST", "OPTIONS"])
def api_run_reconciliation():
    """
    Accept JSON { "batch_id": "..." }.
    Locate staged CSVs for the specific batch, run the matching engine,
    pass exceptions through Gemini diagnostics, return unified JSON.
    """
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200
    body = request.get_json(silent=True) or {}
    batch_id = body.get("batch_id", "SETTLE_20260903").strip()

    def _find_valid_csv(directory, target_col):
        csvs = sorted(glob.glob(str(directory / "*.csv")))
        for c in csvs:
            try:
                with open(c, mode="r", encoding="utf-8") as f:
                    fields = csv.DictReader(f).fieldnames or []
                    if target_col in fields:
                        return c
            except Exception:
                pass
        return csvs[0] if csvs else None

    # Locate batch-specific staged CSV files
    batch_dir = STAGING_ROOT / batch_id
    erp_dir = batch_dir / "erp"
    rzp_dir = batch_dir / "razorpay"

    erp_file = _find_valid_csv(erp_dir, "gross_amount")
    gtw_file = _find_valid_csv(rzp_dir, "captured_amount")

    # Fallback to root staging or datasets for pre-configured seed batches
    batch_date_suffix = batch_id.replace("SETTLE_", "")
    datasets_dir = Path(__file__).parent / "datasets"

    if not erp_file:
        specific_erp = datasets_dir / f"erp_sales_orders_{batch_date_suffix}.csv"
        if specific_erp.exists():
            erp_file = str(specific_erp)
        else:
            erp_file = _find_valid_csv(STAGING_ROOT / "erp", "gross_amount") or _find_valid_csv(datasets_dir, "gross_amount")

    if not gtw_file:
        specific_gtw = datasets_dir / f"razorpay_settlement_{batch_date_suffix}.csv"
        if specific_gtw.exists():
            gtw_file = str(specific_gtw)
        else:
            gtw_file = _find_valid_csv(STAGING_ROOT / "razorpay", "captured_amount") or _find_valid_csv(datasets_dir, "captured_amount")

    if not erp_file:
        return jsonify({"error": f"No ERP CSV found for batch {batch_id}. Please upload ERP files for this batch."}), 400
    if not gtw_file:
        return jsonify({"error": f"No Razorpay CSV found for batch {batch_id}. Please upload settlement files for this batch."}), 400

    try:
        # ── Step 1: Deterministic Matching Engine ───────────────────────
        reconciled, exceptions = run_reconciliation(erp_file, gtw_file)

        # ── Step 2: Compute KPI Metrics ─────────────────────────────────
        total_gross = Decimal("0.00")
        total_fee = Decimal("0.00")
        total_tax = Decimal("0.00")
        total_net = Decimal("0.00")

        for rec in reconciled:
            total_gross += Decimal(rec["gross_amount"])
            total_fee += Decimal(rec["fee"])
            total_tax += Decimal(rec["tax"])
            total_net += Decimal(rec["net_settlement"])

        total_count = len(reconciled) + len(exceptions)
        match_rate = (len(reconciled) / total_count * 100) if total_count > 0 else 0

        kpi = {
            "match_rate": f"{match_rate:.1f}%",
            "match_detail": f"{len(reconciled)} / {total_count} Clrd",
            "gross_revenue": f"\u20b9{total_gross:,.2f}",
            "gateway_fees": f"\u20b9{total_fee:,.2f}",
            "tax_itc": f"\u20b9{total_tax:,.2f}",
            "net_payout": f"\u20b9{total_net:,.2f}",
        }

        # ── Step 3: Gemini Diagnostic Layer ─────────────────────────────
        diagnostics = []
        if exceptions:
            try:
                diagnostics = diagnose_exceptions(exceptions)
            except Exception as diag_err:
                print(f"[WARN] Gemini diagnostics failed: {diag_err}")
                traceback.print_exc()

        result_payload = {
            "status": "ok",
            "batch_id": batch_id,
            "kpi": kpi,
            "verified_count": len(reconciled),
            "total_count": total_count,
            "exceptions": exceptions,
            "diagnostics": diagnostics,
        }

        # Store in cache
        BATCH_RESULTS[batch_id] = result_payload

        # Save to Supabase DB
        save_reconciliation_to_db(batch_id, kpi, len(reconciled), total_count, exceptions, diagnostics)

        return jsonify(result_payload)

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Reconciliation failed: {str(e)}"}), 500


@app.route("/api/download-report/<batch_id>", methods=["GET", "OPTIONS"])
def download_report(batch_id):
    """Generate and stream CSV reconciliation report for a given batch."""
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    cached = BATCH_RESULTS.get(batch_id)
    if not cached:
        return jsonify({"error": f"Batch {batch_id} has not been reconciled yet."}), 400

    # Build CSV content
    lines = ["Order ID,Status,Discrepancy Amount,Category,Root Cause Diagnosis,Accounting Action"]
    for diag in cached.get("diagnostics", []):
        order_id = diag.get("order_id", "")
        cat = diag.get("variance_category", "")
        root_cause = diag.get("root_cause_diagnosis", "").replace(",", ";")
        action = diag.get("accounting_action", "").replace(",", ";")
        risk = diag.get("risk_level", "MEDIUM")
        lines.append(f"{order_id},{risk},,{cat},{root_cause},{action}")

    csv_body = "\n".join(lines)
    from flask import Response
    return Response(
        csv_body,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=Reconciliation_Report_{batch_id}.csv"}
    )


# ── Main ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
