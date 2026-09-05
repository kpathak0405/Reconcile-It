# ReconcileIt — Autonomous Settlement Auditor & Financial Exception Engine

![License](https://img.shields.io/badge/License-MIT-blue.svg)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)
![Flask](https://img.shields.io/badge/Framework-Flask_3.x-green?logo=flask)
![Supabase](https://img.shields.io/badge/Database-Supabase_PostgreSQL-emerald?logo=supabase)
![Gemini AI](https://img.shields.io/badge/AI-Google_Gemini-orange?logo=google)

**ReconcileIt** is an enterprise-grade automated financial reconciliation platform designed for merchants and platforms. It matches internal ERP sales registers against payment gateway settlement reports (such as Razorpay), detects mathematical and operational discrepancies, and leverages **Google Gemini AI** to produce root-cause diagnoses and accounting resolution memos.

---

## 🌟 Key Features

- 📁 **Dual Feed File Ingestion Deck**: Drag-and-drop or select multi-format sales registers (`.csv`, `.txt`, `.pdf`, `.xml`) for ERP and Payment Gateway feeds.
- ⚡ **Deterministic Matching Engine**: Automates mathematical verification of Gross Revenue, MDR Gateway Processing Fees (2% standard, 3% AMEX), 18% Input Tax Credit (ITC GST), and Net Bank Payouts.
- 🤖 **Gemini AI Diagnostic Layer**: Analyzes unmatched items and generates automated accounting resolution steps for finance controllers.
- 🔒 **Per-Batch State Isolation**: Keeps datasets, KPI metrics, suspense queues, and report downloads isolated per settlement batch (`SETTLE_20260903` to `SETTLE_20260908`).
- ☁️ **Supabase Cloud Persistence**: Built-in integration with Supabase PostgreSQL for cloud storage of batches, staged files, and reconciliation results, with graceful local fallback.
- 🎨 **Floating Label Authentication**: Sleek Material-modern login screen (`lf-03`) with zero JavaScript trackers.
- 📊 **Dynamic Audit Report Export**: Instantly export full reconciliation summaries into CSV format for external auditing.

---

## 📁 Project Structure

```text
Razorpay/
├── agentic.py                  # Gemini AI diagnostic layer for exception analysis
├── reconciliation.py           # Deterministic matching & clearance engine
├── server.py                   # Flask REST API server & static route handlers
├── database.py                 # Supabase PostgreSQL client & persistence layer
├── generate_datasets.py        # Data generator for multi-batch test datasets
├── schema.sql                  # PostgreSQL DDL schema & RLS policies for Supabase
├── datasets/                   # Sample & generated ERP and Razorpay audit CSV pairs
│   ├── internal_sales_orders.csv
│   ├── razorpay_settlement_report.csv
│   ├── erp_sales_orders_20260904.csv
│   ├── razorpay_settlement_20260904.csv
│   └── ...
├── templates/
│   └── index.html              # Main Single-Page Application (SPA) canvas
└── static/
    ├── css/                    # Modular Design System
    │   ├── main.css            # Stylesheet importer
    │   ├── base/               # Reset, typography, and CSS variables
    │   ├── layout/             # Topbar, grid, and full-width container styles
    │   └── components/         # Upload deck, KPI cards, suspense queue, login UI
    └── js/
        └── app.js              # Frontend state management & API interaction script
```

---

## 🔍 Reconciliation & Exception Handling

The deterministic engine (`reconciliation.py`) classifies transactions into clean clearances or 7 financial exception types:

| Exception Type | Description |
| :--- | :--- |
| `TIMING_CUTOFF` | Orders placed past the 23:50 IST midnight cut-off window; funds roll into T+2 cycle. |
| `CRITICAL_BANK_DROP` | Upstream customer debit failure recorded as `FAILED_BANK_DEBIT` at the gateway. |
| `DISPUTE_CHARGEBACK_HOLD` | Customer chargeback active; funds held back by gateway. |
| `ESCROW_RETURN_WINDOW_ACTIVE` | Active 14-day return window policy; funds held in escrow. |
| `LATE_AUTHORIZATION_DESYNC` | Customer funds captured by gateway, but ERP status is still `PENDING_VERIFICATION`. |
| `GHOST_PAYMENT_IN_GATEWAY` | Payment captured in gateway, but missing from internal merchant ERP. |
| `MATHEMATICAL_VARIANCE` | Net settlement value deviates from expected `captured - fee - tax - refund`. |

---

## 🚀 Quick Start Guide

### Prerequisites

- **Python 3.10+** installed
- **Pip** package manager

### 1. Clone the Repository & Install Dependencies

```bash
git clone https://github.com/kpathak0405/Reconcile-It.git
cd Reconcile-It
pip install flask python-dotenv supabase requests httpx google-genai
```

### 2. Configure Environment Variables

Create or update `.env` in the root project directory:

```env
# Google Gemini API Key for Exception Diagnostics
GEMINI_API_KEY=your_gemini_api_key_here

# Supabase Credentials (Optional for Cloud Persistence)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_supabase_anon_key_here
```

### 3. Setup Supabase Database (Optional)

If using Supabase, copy the contents of [`schema.sql`](file:///c:/Users/HP/Desktop/Razorpay/schema.sql) and run it inside your [Supabase SQL Editor](https://supabase.com/dashboard).

### 4. Launch the Server

```bash
python server.py
```

Open your browser and navigate to:
👉 **`http://127.0.0.1:5000/`**

---

## 📡 REST API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Renders the single-page application dashboard |
| `POST` | `/api/stage-files` | Uploads and stages multipart files for a specific `batch_id` |
| `GET` | `/api/batch-state/<batch_id>` | Retrieves staging files, KPI metrics, and diagnostics for a batch |
| `POST` | `/api/run-reconciliation` | Triggers deterministic matching & Gemini AI exception analysis |
| `GET` | `/api/download-report/<batch_id>` | Downloads a CSV reconciliation report for the batch |

---

## 🧪 Generating Additional Datasets

To create new synthetic ERP and Razorpay settlement CSV pairs for testing:

```bash
python generate_datasets.py
```

This will populate `datasets/` with 5 distinct settlement batch file pairs (`SETTLE_20260904` through `SETTLE_20260908`).

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for details.
