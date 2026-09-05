-- ============================================================================
-- RECONCILE-IT SUPABASE DATABASE SCHEMA
-- Execute this SQL script in your Supabase SQL Editor:
-- https://supabase.com/dashboard/project/fnbdluqahcdyldmmktnu/sql
-- ============================================================================

-- 1. Batches Table
CREATE TABLE IF NOT EXISTS public.batches (
    batch_id TEXT PRIMARY KEY,
    cutoff_time TEXT DEFAULT '23:50:00 IST',
    reconciled BOOLEAN DEFAULT FALSE,
    kpi JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Staged Files Table
CREATE TABLE IF NOT EXISTS public.staged_files (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    batch_id TEXT REFERENCES public.batches(batch_id) ON DELETE CASCADE,
    feed_type TEXT NOT NULL CHECK (feed_type IN ('erp', 'razorpay')),
    filename TEXT NOT NULL,
    file_size BIGINT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Reconciliation Results Table
CREATE TABLE IF NOT EXISTS public.reconciliation_results (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    batch_id TEXT UNIQUE REFERENCES public.batches(batch_id) ON DELETE CASCADE,
    verified_count INT DEFAULT 0,
    total_count INT DEFAULT 0,
    kpi JSONB,
    exceptions JSONB,
    diagnostics JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Enable Row Level Security (RLS) & Public Policies for Anon Key
ALTER TABLE public.batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.staged_files ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.reconciliation_results ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow all access to batches" ON public.batches;
CREATE POLICY "Allow all access to batches" ON public.batches FOR ALL USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Allow all access to staged_files" ON public.staged_files;
CREATE POLICY "Allow all access to staged_files" ON public.staged_files FOR ALL USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Allow all access to reconciliation_results" ON public.reconciliation_results;
CREATE POLICY "Allow all access to reconciliation_results" ON public.reconciliation_results FOR ALL USING (true) WITH CHECK (true);

-- 5. Seed Default Batches
INSERT INTO public.batches (batch_id, cutoff_time, reconciled)
VALUES 
    ('SETTLE_20260903', '23:50:00 IST', FALSE),
    ('SETTLE_20260904', '23:50:00 IST', FALSE),
    ('SETTLE_20260905', '23:50:00 IST', FALSE),
    ('SETTLE_20260906', '23:50:00 IST', FALSE),
    ('SETTLE_20260907', '23:50:00 IST', FALSE),
    ('SETTLE_20260908', '23:50:00 IST', FALSE),
    ('SETTLE_20260902', '23:50:00 IST', FALSE),
    ('SETTLE_20260901', '23:50:00 IST', FALSE)
ON CONFLICT (batch_id) DO NOTHING;
