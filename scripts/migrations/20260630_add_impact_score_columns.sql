-- Migration: add impact_score and score_breakdown columns to briefing_items
-- Applied: 2026-06-30 (Week 1: Dry-run + Shadow 준비)
-- Review: Week 2에서 가중치 튜닝 후 score_breakdown 포맷 확정 예정

ALTER TABLE briefing_items ADD COLUMN impact_score INTEGER;
ALTER TABLE briefing_items ADD COLUMN score_breakdown JSON;

-- 기존 row는 NULL 허용 (역산 backfill은 Week 2 별도 작업)
-- _review: backfill script 위치 → scripts/backfill_briefing_scores.py (미작성)
