#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
"""
aikorea24 Threads v3 — Narrative-First Design
- GPT-4o-mini가 100개 기사에서 "이야기" 발견
- GPT-4o가 쓰레드 작성
- 기존 파일(v1/v2) 수정 금지, 병행 가능
"""
import os, sys, json, time
from datetime import datetime, timedelta

PROJECT_DIR = '/Users/twinssn/Projects/aikorea24'
THREADS_DIR = os.path.join(PROJECT_DIR, 'scripts', 'threads')
sys.path.insert(0, THREADS_DIR)
LOGS_DIR = os.path.join(THREADS_DIR, 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)

def log(msg):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f'[{ts}] {msg}')
    with open(os.path.join(LOGS_DIR, datetime.now().strftime('%Y-%m-%d') + '.log'), 'a', encoding='utf-8') as f:
        f.write(f'[{ts}] [v3] {msg}\n')

def load_env():
    for p in [os.path.join(PROJECT_DIR, '.env'), os.path.join(PROJECT_DIR, 'api_test', '.env.sh')]:
        if os.path.exists(p):
            with open(p) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        if line.startswith('export '):
                            line = line[7:]
                        k, v = line.split('=', 1)
                        os.environ[k.strip()] = v.strip().strip('"').strip("'")

def reset_posted_daily():
    """매일 자정 posted.json 정리"""
    import json as _json
    posted_path = os.path.join(THREADS_DIR, 'posted.json')
    if os.path.exists(posted_path):
        with open(posted_path) as f:
            data = _json.load(f)
        today = datetime.now().strftime('%Y-%m-%d')
        if data.get('last_reset') != today:
            # 7일 이상 지난 피치 이력 정리
            old_pitches = data.get('pitch_history', [])
            cutoff = (datetime.now() - timedelta(days=7)).isoformat()
            data['pitch_history'] = [p for p in old_pitches if p.get('date', '') >= cutoff[:10]]
            data['last_reset'] = today
            with open(posted_path, 'w') as f:
                _json.dump(data, f, ensure_ascii=False, indent=2)
            log(f'  자정 정리: 피치 이력 {len(old_pitches)}→{len(data["pitch_history"])}개')

def run_v3(dry_run=False):
    load_env()
    max_retries = 3
    retry_delay = 300  # 5분

    for attempt in range(1, max_retries + 1):
        if attempt > 1:
            log(f'  ⏳ {attempt}번째 재시도 (5분 대기)...')
            time.sleep(retry_delay)

        log(f'🚀 v3 실행 시작 (시도 {attempt}/{max_retries})')

        # 1. 기사 로드
        from db_reader import get_articles
        articles = get_articles()
        if not articles:
            log('  기사 없음 → 스킵')
            if attempt < max_retries:
                continue
            return
        log(f'  기사: {len(articles)}개 로드')

        # 2. 피치 생성
        from v3.narrative_pitcher import get_pitches
        log('  피치 생성...')
        pitches = get_pitches(articles, max_articles=500)

        if not pitches:
            log(f'  ❌ 흥미로운 이야기 발견 실패 (시도 {attempt}/{max_retries})')
            continue

        pitch = pitches[0]
        log(f'  ✅ 피치: "{pitch.get("hook", "")[:40]}" ({pitch.get("emotion", "")})')
        log(f'     기사: {pitch.get("article_ids", [])}')

        # 3. 쓰레드 작성
        from v3.writer_v3 import write_thread, save_draft
        log('  쓰레드 작성...')
        cards = write_thread(pitch, articles)

        if not cards:
            log(f'  ❌ 쓰레드 작성 실패 (시도 {attempt}/{max_retries})')
            continue

        save_draft(cards, pitch)
        log(f'  ✅ {len(cards)}개 조각 작성 완료')

        if dry_run:
            # dry-run에서도 posted_ids/links 저장 (중복 방지)
            from db_reader import load_posted, save_posted
            posted = load_posted()
            for aid in pitch.get('article_ids', []):
                aid_str = str(aid)
                if aid_str not in posted.get('posted_ids', []):
                    posted.setdefault('posted_ids', []).append(aid_str)
                for a in articles:
                    if str(a.get('id', '')) == aid_str:
                        link = a.get('link', '')
                        if link and link not in posted.get('posted_links', []):
                            posted.setdefault('posted_links', []).append(link)
                        break
            save_posted(posted)
            log(f'[DRY RUN] 발행 생략 (posted_ids/links {len(posted["posted_ids"])}개)')
            print(f'\n{"="*60}')
            print(f'Hook: {pitch.get("hook")}')
            print(f'Narrative: {pitch.get("narrative")}')
            print(f'Twist: {pitch.get("twist")}')
            print(f'{":"*60}')
            print('\n---\n'.join(cards))
            print(f'\n{"="*60}')
            return

        # 4. 발행 (실제 사용한 기사 ID로 posted.json 저장)
        from publisher import publish_thread_chain
        log('  발행 시작...')
        # article_ids[0]의 실제 기사 찾기 (중복 발행 방지)
        pitch_id = str(pitch.get('article_ids', [None])[0]).lstrip('#').strip() if pitch.get('article_ids') else None
        publish_article = articles[0]  # fallback
        if pitch_id:
            for a in articles:
                if str(a.get('id', '')) == pitch_id:
                    publish_article = a
                    break
        result = publish_thread_chain(cards, publish_article)
        if result:
            log(f'  ✅ 발행 완료: 루트 ID {result}')
            # 피치의 모든 article_ids 저장 (보조 기사 중복 방지)
            from db_reader import load_posted, save_posted
            posted = load_posted()
            pitch_ids = [str(aid).lstrip('#').strip() for aid in pitch.get('article_ids', [])]
            for aid_str in pitch_ids:
                if aid_str not in posted.get('posted_ids', []):
                    posted.setdefault('posted_ids', []).append(aid_str)
                # 링크도 저장
                for a in articles:
                    if str(a.get('id', '')) == aid_str:
                        link = a.get('link', '')
                        if link and link not in posted.get('posted_links', []):
                            posted.setdefault('posted_links', []).append(link)
                        break
            save_posted(posted)
            log(f'  ✅ posted_ids 업데이트: {len(pitch_ids)}개 기사 등록')
            next_run = (datetime.now() + timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S')
            log(f'  다음 실행: {next_run}')
            return
        else:
            log(f'  ❌ 발행 실패 — 쓰레드는 생성됨, 2시간 후 재시도')
            return  # 쓰레드는 생성됨. 발행 API 실패는 재시도로 해결 불가

    log(f'  ❌ {max_retries}회 모두 실패 — 2시간 후 재시도')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='발행 없이 글만 생성')
    parser.add_argument('--once', action='store_true', help='1회 실행')
    parser.add_argument('--daemon', action='store_true', help='2시간 간격 자동 실행')
    args = parser.parse_args()

    if args.daemon:
        import schedule
        log('🔄 데몬 모드 시작 (2시간 간격)')
        run_v3()
        schedule.every(2).hours.do(run_v3)
        schedule.every().day.at('00:00').do(reset_posted_daily)
        while True:
            schedule.run_pending()
            time.sleep(60)
    else:
        run_v3(dry_run=args.dry_run)
