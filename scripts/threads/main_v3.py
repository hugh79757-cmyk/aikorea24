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
    # 공통 환경변수 먼저 로드 (~/.env.common)
    common = os.path.expanduser('~/.env.common')
    if os.path.exists(common):
        with open(common) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') \
                   and '=' in line and not line.startswith('source'):
                    k, v = line.split('=', 1)
                    os.environ.setdefault(k.strip(),
                                         v.strip().strip('"').strip("'"))

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
            data['last_reset'] = today
            with open(posted_path, 'w') as f:
                _json.dump(data, f, ensure_ascii=False, indent=2)

def run_v3(dry_run=False):
    load_env()
    max_retries = 5
    retry_delays = [60, 120, 300, 600]  # 1분 → 2분 → 5분 → 10분 (기하급수적 백오프)

    for attempt in range(1, max_retries + 1):
        if attempt > 1:
            delay = retry_delays[min(attempt - 2, len(retry_delays) - 1)]
            log(f'  ⏳ {attempt}번째 재시도 ({delay//60}분 {delay%60}초 대기)...')
            time.sleep(delay)

        log(f'🚀 v3 실행 시작 (시도 {attempt}/{max_retries})')

        # 1. 기사 로드
        from db_reader import get_articles
        articles = get_articles()
        if not articles:
            log('  기사 없음 → 스킵')
            if attempt < max_retries:
                log('  네트워크/D1 일시적 장애 의심 → 백오프 후 재시도')
                continue
            return
        log(f'  기사: {len(articles)}개 로드')

        # 2. 피치 생성 (2단계: 브리핑 우선 → 전체 fallback)
        from v3.narrative_pitcher import get_pitches
        briefing_articles = [a for a in articles if a.get('priority') == 1]
        pitches = []

        # 1단계: 브리핑 기사 우선 시도
        if briefing_articles:
            log(f'  [1단계] 브리핑 기사 {len(briefing_articles)}개 우선 피치 시도')
            pitches = get_pitches(briefing_articles, max_articles=len(briefing_articles), batch_size=len(briefing_articles))
            if pitches:
                log(f'  [1단계] 브리핑 기사로 피치 선정 성공 → 발행 진행')
            else:
                log(f'  [1단계] 브리핑 기사 피치 실패 → 전체 풀 fallback')
        else:
            log(f'  [1단계] 브리핑 기사 없음 → 전체 풀로 진행')

        # 2단계: 전체 풀 fallback
        if not pitches:
            log(f'  [2단계] 전체 기사 {len(articles)}개 → 배치 처리 시작')
            pitches = get_pitches(articles, max_articles=600)

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
            # dry-run에서도 posted_ids/links/titles 저장 (중복 방지)
            from db_reader import load_posted, save_posted, normalize_url
            posted = load_posted()
            # 업데이트 전 스냅샷
            before = {k: len(v) for k, v in posted.items() if isinstance(v, list)}
            posted.setdefault('posted_article_meta', {})
            pitch_ids = [str(aid).lstrip('#').strip() for aid in pitch.get('article_ids', []) if str(aid).strip()]
            for aid_str in pitch_ids:
                if aid_str and aid_str not in posted.get('posted_ids', []):
                    posted.setdefault('posted_ids', []).append(aid_str)
                # 기사 필드에서 매핑
                for a in articles:
                    if str(a.get('id', '')).lstrip('#').strip() == aid_str:
                        link = normalize_url(a.get('link', ''))
                        title = (a.get('title', '') or '')[:30]
                        orig_title = (a.get('original_title', '') or '')[:30]
                        if link and link not in posted.get('posted_links', []):
                            posted.setdefault('posted_links', []).append(link)
                        if title and title not in posted.get('posted_titles', []):
                            posted.setdefault('posted_titles', []).append(title)
                        if orig_title and orig_title not in posted.get('posted_original_titles', []):
                            posted.setdefault('posted_original_titles', []).append(orig_title)
                        # posted_article_meta: FULL text for semantic dedup
                        posted['posted_article_meta'][aid_str] = {
                            'title': a.get('title', '') or '',
                            'original_title': a.get('original_title', '') or '',
                            'description': a.get('description', '') or '',
                        }
                        break
            save_posted(posted)
            from v3.narrative_pitcher import save_pitch_to_history
            save_pitch_to_history(pitch)
            # 업데이트 후 상세 로그
            after = {k: len(v) for k, v in posted.items() if isinstance(v, list)}
            log(f'[DRY RUN] posted.json 업데이트:')
            log(f'  posted_ids: 기존 {before.get("posted_ids",0)}개 → 추가 {after.get("posted_ids",0)-before.get("posted_ids",0)}개 → 총 {after.get("posted_ids",0)}개')
            log(f'  posted_links: 기존 {before.get("posted_links",0)}개 → 추가 {after.get("posted_links",0)-before.get("posted_links",0)}개 → 총 {after.get("posted_links",0)}개')
            log(f'  posted_titles: 기존 {before.get("posted_titles",0)}개 → 추가 {after.get("posted_titles",0)-before.get("posted_titles",0)}개 → 총 {after.get("posted_titles",0)}개')
            log(f'  posted_original_titles: 기존 {before.get("posted_original_titles",0)}개 → 추가 {after.get("posted_original_titles",0)-before.get("posted_original_titles",0)}개 → 총 {after.get("posted_original_titles",0)}개')
            log(f'  pitch_history: 총 {after.get("pitch_history",0)}개')
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
            from db_reader import load_posted, save_posted, normalize_url
            posted = load_posted()
            # 업데이트 전 스냅샷
            before = {k: len(v) for k, v in posted.items() if isinstance(v, list)}
            posted.setdefault('posted_article_meta', {})
            pitch_ids = [str(aid).lstrip('#').strip() for aid in pitch.get('article_ids', []) if str(aid).strip()]
            for aid_str in pitch_ids:
                if aid_str and aid_str not in posted.get('posted_ids', []):
                    posted.setdefault('posted_ids', []).append(aid_str)
                # 기사 필드에서 매핑
                for a in articles:
                    if str(a.get('id', '')).lstrip('#').strip() == aid_str:
                        link = normalize_url(a.get('link', ''))
                        title = (a.get('title', '') or '')[:30]
                        orig_title = (a.get('original_title', '') or '')[:30]
                        if link and link not in posted.get('posted_links', []):
                            posted.setdefault('posted_links', []).append(link)
                        if title and title not in posted.get('posted_titles', []):
                            posted.setdefault('posted_titles', []).append(title)
                        if orig_title and orig_title not in posted.get('posted_original_titles', []):
                            posted.setdefault('posted_original_titles', []).append(orig_title)
                        # posted_article_meta: FULL text for semantic dedup
                        posted['posted_article_meta'][aid_str] = {
                            'title': a.get('title', '') or '',
                            'original_title': a.get('original_title', '') or '',
                            'description': a.get('description', '') or '',
                        }
                        break
            save_posted(posted)
            from v3.narrative_pitcher import save_pitch_to_history
            save_pitch_to_history(pitch)
            # 업데이트 후 상세 로그
            after = {k: len(v) for k, v in posted.items() if isinstance(v, list)}
            log(f'[발행 완료] posted.json 업데이트:')
            log(f'  posted_ids: 기존 {before.get("posted_ids",0)}개 → 추가 {after.get("posted_ids",0)-before.get("posted_ids",0)}개 → 총 {after.get("posted_ids",0)}개')
            log(f'  posted_links: 기존 {before.get("posted_links",0)}개 → 추가 {after.get("posted_links",0)-before.get("posted_links",0)}개 → 총 {after.get("posted_links",0)}개')
            log(f'  posted_titles: 기존 {before.get("posted_titles",0)}개 → 추가 {after.get("posted_titles",0)-before.get("posted_titles",0)}개 → 총 {after.get("posted_titles",0)}개')
            log(f'  posted_original_titles: 기존 {before.get("posted_original_titles",0)}개 → 추가 {after.get("posted_original_titles",0)-before.get("posted_original_titles",0)}개 → 총 {after.get("posted_original_titles",0)}개')
            log(f'  pitch_history: 총 {after.get("pitch_history",0)}개')
            next_run = (datetime.now() + timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S')
            log(f'  다음 실행: {next_run}')
            return
        else:
            log(f'  ❌ 발행 실패 — 쓰레드는 생성됨, 2시간 후 재시도')
            return

    log(f'  ❌ {max_retries}회 모두 실패 (네트워크/D1 장애 의심) — 2시간 후 재시도')


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
