#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
"""
main_v2.py — v2 전체 파이프라인
- 클러스터링 → 점수화 → 보강 → 작성 → 검증 → 발행
"""
import os, sys
from datetime import datetime, timedelta

THREADS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, THREADS_DIR)
LOGS_DIR = os.path.join(THREADS_DIR, 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)

def log(msg):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f'[{ts}] {msg}')
    with open(os.path.join(LOGS_DIR, datetime.now().strftime('%Y-%m-%d') + '.log'), 'a', encoding='utf-8') as f:
        f.write(f'[{ts}] {msg}\n')

def run_v2(dry_run=False):
    log('🚀 v2 실행 시작')

    # 1. 클러스터 로드
    from db_reader_v2 import get_clusters
    clusters = get_clusters()
    if not clusters:
        log('  클러스터 없음'); return
    log(f'  클러스터: {len(clusters)}개')

    # 2. 점수화
    from scorer_v2 import score_clusters, select_best_cluster
    scored = score_clusters(clusters)
    best = select_best_cluster(scored)
    if not best:
        log('  선택된 클러스터 없음')
        # fallback: 기존 v1
        log('  → v1 fallback')
        from db_reader import get_articles
        from scorer import score_articles, determine_format
        from writer import write_thread, save_draft
        arts = get_articles()
        if not arts: return
        scored_arts = score_articles(arts)
        if not scored_arts: return
        top = scored_arts[0]
        content = write_thread(top)
        if not content: return
        save_draft(content, top)
        if dry_run: log('[DRY RUN] v1 fallback 발행 생략'); return
        from publisher import publish_thread_chain, parse_cards
        cards = parse_cards(content)
        publish_thread_chain(cards, top)
        return

    log(f'  선택: {best["id"]} ({best["total_score"]}점, {len(best["articles"])}개 기사)')

    # 3. 컨텍스트 보강
    from enricher import enrich_cluster
    enriched = enrich_cluster(best)

    # 4. 쓰레드 작성 (+ 품질 검증 내장)
    from writer_v2 import write_thread_v2, save_draft
    content = write_thread_v2(enriched)
    if not content:
        log('  쓰레드 작성 실패')
        return

    save_draft(content, enriched)

    if dry_run:
        log('[DRY RUN] 발행 생략')
        print(f'\n{"="*70}')
        print(content)
        print(f'{"="*70}')
        return

    # 5. 발행
    from publisher import publish_thread_chain, parse_cards
    cards = parse_cards(content)
    if not cards:
        log('  카드 파싱 실패')
        return
    root_id = publish_thread_chain(cards, enriched['articles'][0])
    if root_id:
        log(f'  ✅ 발행 완료: {root_id}')
        next_run = (datetime.now() + timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S')
        log(f'  다음 실행: {next_run}')
    else:
        log('  ❌ 발행 실패')

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    run_v2(dry_run=args.dry_run)
