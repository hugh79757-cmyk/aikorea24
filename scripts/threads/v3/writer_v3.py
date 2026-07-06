#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
"""
writer_v3.py — Re-export wrapper (Phase 4 Strangler Fig).
All functionality moved to pipeline.threads.validator, pipeline.threads.crawler,
and pipeline.threads.writer. This file exists for backward compatibility.
"""
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_project_root))

from pipeline.threads.crawler import fetch_article_body, log_failed_crawl  # noqa: F401, E402
from pipeline.threads.validator import validate_cards, validate_year, validate_keywords  # noqa: F401, E402
from pipeline.threads.validator import FORMAT_CARD_COUNTS, FORMAT_CARD_COUNT_TOLERANCE  # noqa: F401, E402
from pipeline.threads.writer import (  # noqa: F401, E402
    write_thread, save_draft, fix_cards, assemble_final,
    humanize_cards, load_style_examples, build_system_prompt_D,
    FORMAT_LABELS, FORMAT_BUILDERS, INSTRUCTION_PATTERNS,
    STYLE_EXAMPLES_PATH,
    _clean_english_leakage, _fix_korean_particle_spacing,
    _cleanup_source_attribution, _strip_instruction_leak,
)

if __name__ == '__main__':
    from pipeline.threads.pitch import get_pitches
    from db_reader import get_articles
    articles = get_articles()
    pitches, _ = get_pitches(articles)
    if pitches:
        cards = write_thread(pitches[0], articles)
        if cards:
            print(f'\n{"=" * 60}')
            print('\n---\n'.join(cards))
            print(f'\n{"=" * 60}')
            save_draft(cards, pitches[0])
    else:
        print('피치 없음 → 스킵')
