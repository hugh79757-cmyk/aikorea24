#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
"""
narrative_pitcher.py — Re-export wrapper (Phase 4 Strangler Fig).
All functions moved to pipeline.threads.pitch.
"""
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_project_root))

from pipeline.threads.pitch import (  # noqa: F401, E402
    fill_article_ids,
    parse_pitches_from_text,
    parse_top_pitch,
    load_pitch_history,
    is_duplicate_pitch,
    save_pitch_to_history,
    get_pitches,
    _regenerate_pitch_from_crawl,
)

from pipeline.threads.pitch import SYSTEM_PROMPT  # noqa: F401, E402
from pipeline.threads.crawler import fetch_article_body  # noqa: F401, E402

load_env = lambda: None  # noqa: E731

if __name__ == '__main__':
    from db_reader import get_articles
    articles = get_articles()
    pitches = get_pitches(articles)
    if pitches:
        p = pitches[0]
        print(f'\n=== TOP PITCH ===')
        print(f'  Hook: {p.get("hook")}')
        print(f'  Narrative: {p.get("narrative")}')
        print(f'  Twist: {p.get("twist")}')
        print(f'  Emotion: {p.get("emotion")}')
        print(f'  Articles: {p.get("article_ids")}')
    else:
        print('\n❌ 피치 없음')
