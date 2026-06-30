-- Migration: create pipeline_runs table for Phase 3 orchestrator. Applied: 2026-06-30
-- pipeline/migrations/20260630_create_pipeline_runs.sql

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    step_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('success', 'failure')),
    duration_seconds REAL,
    error_message TEXT,
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_run_id ON pipeline_runs(run_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started_at ON pipeline_runs(started_at);
