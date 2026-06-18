#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
"""
aikorea24 Threads 자동 발행 메인
- 2시간 간격 자동 실행
- 매일 자정 posted.json 정리
- 토큰 30일 전 자동 갱신
"""
import os, sys, schedule, time
from datetime import datetime, timedelta

PROJECT_DIR = '/Users/twinssn/Projects/aikorea24'
THREADS_DIR = os.path.join(PROJECT_DIR, 'scripts', 'threads')
POSTED_FILE = os.path.join(THREADS_DIR, 'posted.json')
LOGS_DIR = os.path.join(THREADS_DIR, 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)
sys.path.insert(0, THREADS_DIR)

def log(msg):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f'[{ts}] {msg}')
    with open(os.path.join(LOGS_DIR, datetime.now().strftime('%Y-%m-%d') + '.log'), 'a', encoding='utf-8') as f:
        f.write(f'[{ts}] {msg}\n')

def load_posted():
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"posted_links": [], "posted_ids": [], "history": [], "last_reset": ""}

def save_posted(data):
    with open(POSTED_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def reset_daily():
    """매일 자정: 30일치 history 유지 정리"""
    posted = load_posted()
    today = datetime.now().strftime('%Y-%m-%d')
    cutoff = (datetime.now() - timedelta(days=30)).isoformat()
    if posted.get('last_reset') != today:
        old = len(posted.get('history', []))
        posted['history'] = [h for h in posted.get('history', []) if h.get('posted_at', '') >= cutoff]
        posted['last_reset'] = today
        save_posted(posted)
        log(f'  자정 정리: {old}→{len(posted["history"])}개 (30일치)')

def check_token():
    """30일 경과 시 토큰 갱신"""
    token_log = os.path.join(LOGS_DIR, 'token_check.json')
    now = datetime.now()
    if os.path.exists(token_log):
        with open(token_log, 'r') as f:
            last = datetime.fromisoformat(json.load(f).get('last_refresh', '2020-01-01'))
        if (now - last).days >= 30:
            log('  토큰 갱신 (30일 경과)')
            from token_refresh import refresh_token
            if refresh_token():
                with open(token_log, 'w') as f:
                    json.dump({'last_refresh': now.isoformat()}, f)
                log('  토큰 갱신 완료')
    else:
        with open(token_log, 'w') as f:
            json.dump({'last_refresh': now.isoformat()}, f)

def run_once(dry_run=False):
    log(f'실행 시작 (dry_run={dry_run})')

    # 1. 기사 풀 로드
    from db_reader import get_articles
    articles = get_articles()
    if not articles:
        log('  발행할 기사 없음')
        return

    # 2. 점수화
    from scorer import score_articles, determine_format
    scored = score_articles(articles)
    if not scored:
        log('  점수화 실패')
        return

    top = scored[0]
    fmt = determine_format(top['score'])
    log(f'선택: [{top["score"]}점|{fmt}] {top["title"][:50]} (ID: {top["id"]})')

    # 3. 글 작성
    from writer import write_thread, save_draft
    content = write_thread(top)
    if not content:
        log('  글 작성 실패')
        return
    save_draft(content, top)

    if dry_run:
        log('[DRY RUN] 발행 생략')
        return

    # 4. 발행
    from publisher import publish_thread_chain, parse_cards
    cards = parse_cards(content)
    if not cards:
        log('  카드 파싱 실패')
        return

    root_id = publish_thread_chain(cards, top)
    if root_id:
        log(f'발행 완료: 루트 포스트 ID {root_id}')
        next_run = (datetime.now() + timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S')
        log(f'다음 실행: {next_run}')
    else:
        log(f'발행 실패')

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--daemon', action='store_true')
    args = parser.parse_args()

    if args.dry_run or args.once:
        run_once(dry_run=args.dry_run)
        return

    if args.daemon:
        log('데몬 모드 시작 (2시간 간격)')
        run_once()
        schedule.every(2).hours.do(run_once)
        schedule.every().day.at('00:00').do(reset_daily)
        while True:
            schedule.run_pending()
            time.sleep(60)
    else:
        run_once()

if __name__ == '__main__':
    main()
