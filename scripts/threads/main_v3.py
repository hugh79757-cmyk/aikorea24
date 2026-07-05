#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
"""
aikorea24 Threads v3 — Narrative-First Design
- GPT-4o-mini가 100개 기사에서 "이야기" 발견
- GPT-4o가 쓰레드 작성
- 기존 파일(v1/v2) 수정 금지, 병행 가능
"""
import os, sys, json, time, re
from pathlib import Path
from datetime import datetime, timedelta

_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from pipeline.infra.env_loader import EnvConfig
_config = EnvConfig()
_config.load_to_environ()
from pipeline.infra import project_root; PROJECT_DIR = project_root()

from pipeline.infra.logger import get_scrubbed_logger
logger = get_scrubbed_logger(__name__)

THREADS_DIR = os.path.join(PROJECT_DIR, 'scripts', 'threads')
sys.path.insert(0, THREADS_DIR)
LOGS_DIR = os.path.join(THREADS_DIR, 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)

import failed_articles

# Strangler Fig: replace with logger.info() in Phase 3
def log(msg):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f'[{ts}] {msg}')
    with open(os.path.join(LOGS_DIR, datetime.now().strftime('%Y-%m-%d') + '.log'), 'a', encoding='utf-8') as f:
        f.write(f'[{ts}] [v3] {msg}\n')

def send_telegram(message):
    import requests
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        log("  텔레그램 토큰/챗ID 없음, 알림 스킵")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        })
    except Exception as e:
        log(f"  텔레그램 전송 실패: {e}")

def validate_final_cards(cards):
    """발행 직전 최종 검증. 문제 있으면 (False, 이유_목록) 반환."""
    from v3.writer_v3 import INSTRUCTION_PATTERNS

    issues = []

    for i, card in enumerate(cards):
        for line in card.split('\n'):
            stripped = line.strip()
            if any(stripped.startswith(p) for p in INSTRUCTION_PATTERNS):
                issues.append(f'카드 {i+1}: 프롬프트 명령어 포함 ("{stripped[:40]}")')

        if not card.strip():
            issues.append(f'카드 {i+1}: 빈 카드')

        if len(card) > 500:
            issues.append(f'카드 {i+1}: {len(card)}자 (500자 초과)')

    last = cards[-1] if cards else ''
    if 'http' not in last and '🔗' not in last:
        issues.append('마지막 카드: 출처 링크 없음')

    for i, card in enumerate(cards):
        last_line = card.strip().split('\n')[-1].strip()
        trailing = last_line.rstrip('\'"」』)}')
        if trailing and trailing[-1] not in '.!?' and not last_line.startswith('🔗'):
            issues.append(f'카드 {i+1}: 미완결 문장 (끝: "...{last_line[-20:]}")')

    for i in range(1, len(cards)):
        prev_words = set(cards[i-1].split())
        curr_words = set(cards[i].split())
        if len(prev_words) < 10 or len(curr_words) < 10:
            continue
        common = prev_words & curr_words
        if len(common) >= len(prev_words) * 0.85 and len(common) >= len(curr_words) * 0.85:
            issues.append(f'카드 {i}, {i+1}: 내용 유사 ({(len(common)/len(prev_words)*100):.0f}% 중복)')

    # 한글+영어 붙어쓰기 검증 (3글자 이상 영어가 한글에 붙은 경우만 — AI, CEO 등 2자 약어와 고유명사+조사는 허용)
    ENG_LEAK_RE = re.compile(r'(?<![A-Z])[가-힣][A-Za-z]{3,}|[A-Za-z]{3,}[가-힣](?![가-힣])')
    for i, card in enumerate(cards):
        for line in card.split('\n'):
            # 고유명사(대문자 시작, MixCase 포함) + 조사 패턴은 허용
            clean = re.sub(r'\b[A-Z][A-Za-z0-9.\-]+[의을를이가과는은]', '', line)
            if ENG_LEAK_RE.search(clean):
                issues.append(f'카드 {i+1}: 한글+영어 붙어쓰기 ("{line.strip()[:50]}")')
                break

    if issues:
        for issue in issues:
            log(f'  ⚠️ [검증] {issue}')
        return False, issues
    return True, []

def run_v3(dry_run=False):
    max_retries = 5
    retry_delays = [60, 120, 300, 600] # 1분 → 2분 → 5분 → 10분 (기하급수적 백오프)
    failed_article_ids = failed_articles.load_failed_articles()

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
        failed_ids: set[str] = set()

        # 1단계: 브리핑 기사 우선 시도
        if briefing_articles:
            log(f'  [1단계] 브리핑 기사 {len(briefing_articles)}개 우선 피치 시도')
            _pitches, _failed = get_pitches(
                briefing_articles,
                max_articles=len(briefing_articles),
                batch_size=len(briefing_articles),
                exclude_ids=failed_article_ids,
            )
            pitches = _pitches
            failed_ids.update(_failed)
            if pitches:
                log(f'  [1단계] 브리핑 기사로 피치 선정 성공 → 발행 진행')
            else:
                log(f'  [1단계] 브리핑 기사 피치 실패 → 전체 풀 fallback')
        else:
            log(f'  [1단계] 브리핑 기사 없음 → 전체 풀로 진행')

        # 2단계: 전체 풀 fallback
        if not pitches:
            log(f'  [2단계] 전체 기사 {len(articles)}개 → 배치 처리 시작')
            _pitches, _failed = get_pitches(
                articles,
                max_articles=600,
                exclude_ids=failed_article_ids,
            )
            pitches = _pitches
            failed_ids.update(_failed)

        failed_article_ids.update(failed_ids)

        if not pitches:
            log(f'  ❌ 흥미로운 이야기 발견 실패 (시도 {attempt}/{max_retries})')
            if failed_ids:
                log(f'     크롤링 실패 기사: {failed_ids}')
                log(f'     누적 제외 기사: {failed_article_ids}')
            continue

        pitch = pitches[0]
        log(f'  ✅ 피치: "{pitch.get("hook", "")[:40]}" ({pitch.get("emotion", "")})')
        log(f'     기사: {pitch.get("article_ids", [])}')

        # 3. 쓰레드 작성
        from v3.writer_v3 import write_thread, save_draft
        log('  쓰레드 작성...')
        cards = write_thread(pitch, articles)

        if not cards:
            log(f' ❌ 쓰레드 작성 실패 (시도 {attempt}/{max_retries})')
            pitch_ids = pitch.get('article_ids', [])
            for aid in pitch_ids:
                aid_str = str(aid).lstrip('#').strip()
                if aid_str:
                    failed_articles.save_failed_article(aid_str, reason="write_validation_failed", title=pitch.get('title', ''), url=pitch.get('link', ''))
            continue

        save_draft(cards, pitch)
        log(f' ✅ {len(cards)}개 조각 작성 완료')

        # 발행 전 최종 검증
        valid, issues = validate_final_cards(cards)
        if not valid:
            log(f'  ❌ 최종 검증 실패 — 발행 중단')
            if not dry_run:
                send_telegram(f'❌ Threads 검증 실패 ({len(issues)}개): {issues[0][:60]}')
            continue

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
            send_telegram(f'❌ Threads 발행 실패: {pitch.get("hook","")[:60]}')
            return

    log(f'  ❌ {max_retries}회 모두 실패 (네트워크/D1 장애 의심) — 2시간 후 재시도')
    send_telegram(f'❌ [{datetime.now().strftime("%m/%d %H:%M")}] Threads {max_retries}회 모두 실패')


def main():
    # 단일 스케줄러 (launchd) — --daemon 모드 제거됨 (THR-01)
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='발행 없이 글만 생성')
    args = parser.parse_args()

    run_v3(dry_run=args.dry_run)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        log(f'  ❌ 예상치 못한 오류: {type(e).__name__}: {e}')
        send_telegram(f'❌ [{datetime.now().strftime("%m/%d %H:%M")}] Threads 예외: {type(e).__name__}: {str(e)[:100]}')
        raise
