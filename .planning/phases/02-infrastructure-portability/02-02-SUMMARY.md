# Phase 2-02 Summary: Batch Wiring

**Date:** 2026-06-30
**Status:** EXECUTED

## Changes Applied
### PROJECT_DIR → project_root()
Replaced hardcoded absolute paths in **19** scripts:
- scripts/auto_news_selector.py, auto_briefing.py, dynamic_seed_generator.py, tools_collector.py, backfill_tasks.py, run_pipeline_with_notify.py, blog_draft_generator.py, keyword_updater.py, fix_ph_urls.py, backfill_humanize.py
- scripts/threads/db_reader.py, main_v3.py, token_refresh.py, publisher.py
- scripts/threads/v3/writer_v3.py, narrative_pitcher.py, model_router.py
- scripts/thread_topics/thread_topic_finder.py, outline_generator.py

### load_env() → EnvConfig() (Strangler Fig, kept old function)
Added to **9** scripts:
- scripts/dynamic_seed_generator.py, tools_collector.py, run_pipeline_with_notify.py, test_email_send.py
- scripts/threads/main_v3.py, token_refresh.py, publisher.py
- scripts/threads/v3/narrative_pitcher.py, model_router.py

### d1_query → d1_client.d1_query (Strangler Fig, kept old function)
Added to **3** scripts:
- scripts/auto_news_selector.py
- scripts/threads/db_reader.py
- scripts/threads/backfill_meta.py

### Logging imports added
Added `get_scrubbed_logger` to **21** scripts with log()/print() patterns.

### conftest.py
Added dual mock for both `auto_news_selector.d1_query` and `pipeline.infra.d1_client.d1_query`.

## Verification
- ✅ Full import chain works
- ✅ Zero hardcoded PROJECT_DIR paths in scripts/ (except exempted validator.py, run_dry.py, test_model.py)
- ✅ All 25+ modified files pass `python3 -m py_compile`
- ✅ All 103 existing tests pass
- ✅ conftest.py has dual mock for d1_query
