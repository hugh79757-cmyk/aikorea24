#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
"""
aikorea24 파이프라인 실행기 + 텔레그램 알림
- run_pipeline.py 실행
- 결과를 텔레그램으로 발송
- 문제 감지 시 1시간 후 자동 재시도 (1회). 재시도 성공 시 블로그 초안 보충 생성.
"""
import os
import sys
import time
import subprocess
import html
from datetime import datetime

# 프로젝트 루트 먼저 path에 추가
_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_DIR)

from pipeline.infra.telegram import send_telegram

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(_PROJECT_DIR, 'scripts')

# 환경변수 로드
def load_env(path):
    common = os.path.expanduser('~/.env.common')
    if os.path.exists(common):
        with open(common) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line and not line.startswith('source'):
                    k, v = line.split('=', 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    if line.startswith('export '):
                        line = line[7:]
                    k, v = line.split('=', 1)
                    os.environ[k.strip()] = v.strip().strip('"').strip("'")

load_env(os.path.join(PROJECT_DIR, '.env'))

RETRY_DELAY = 3600  # 1시간
RETRY_LOCK = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'aikorea24_pipeline_retry.lock')
RETRY_REASON_FILE = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'aikorea24_pipeline_retry_reason.txt')
BLOG_DRAFT_SCRIPT = os.path.join(SCRIPTS_DIR, 'blog_draft_generator.py')

# 문제 징후: 뉴스 0건(수집/DB 실패) 또는 브리핑 생성 실패.
# 주의: dedup 스킵("이미 브리핑된 주제")은 정상 동작이므로 재시도 대상 아님.
FAILURE_MARKERS = ['D1 조회: 0건', '브리핑 생성 실패']


def is_retry_attempt():
    return '--retry' in sys.argv


def acquire_retry_lock():
    """재시도 중복 실행 방지. 이미 lock 있으면 False."""
    if os.path.exists(RETRY_LOCK):
        try:
            mtime = os.path.getmtime(RETRY_LOCK)
            if time.time() - mtime < 4 * 3600:
                return False  # 최근 4시간 내 lock = 이미 예약됨
        except OSError:
            pass
    with open(RETRY_LOCK, 'w') as f:
        f.write(datetime.now().isoformat())
    return True


def detect_problem(result, output):
    """파이프라인 결과에서 재시도 필요 문제 감지."""
    if result.returncode != 0:
        return f"exit code {result.returncode}"
    for marker in FAILURE_MARKERS:
        if marker in output:
            return marker
    return None


def save_retry_reason(reason):
    try:
        with open(RETRY_REASON_FILE, 'w') as f:
            f.write(str(reason))
    except OSError:
        pass


def load_retry_reason():
    try:
        with open(RETRY_REASON_FILE) as f:
            return f.read().strip() or '이전 실행 실패'
    except OSError:
        return '이전 실행 실패'


def schedule_retry(reason):
    """1시간 후 --retry 모드로 자기 자신 재실행 (1회만).

    재시도 프로세스는 wait_and_retry()에서 1시간 대기 후 실행."""
    if is_retry_attempt():
        print(f"재시도에서도 문제 발생 ({reason}) — 추가 재시도 없음")
        return False
    if not acquire_retry_lock():
        print("재시도 이미 예약됨 — 중복 예약 스킵")
        return False
    save_retry_reason(reason)
    args = [sys.executable, os.path.abspath(__file__), '--retry']
    subprocess.Popen(
        args,
        stdout=open(os.path.join(SCRIPTS_DIR, 'pipeline_retry.log'), 'a'),
        stderr=subprocess.STDOUT,
        cwd=_PROJECT_DIR,
        start_new_session=True,  # launchd가 끝나도 재시도 프로세스 생존
    )
    send_telegram(f"🔄 <b>aikorea24 파이프라인 재시도 예약</b>\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n사유: {html.escape(str(reason))}\n1시간 후 자동 재실행")
    print(f"⏰ 1시간 후 재시도 예약 (사유: {reason})")
    return True


def run_blog_draft():
    """재시도 성공 시 블로그 초안 보충 생성 (06:15 슬롯 이미 지났으므로)."""
    try:
        result = subprocess.run(
            [sys.executable, BLOG_DRAFT_SCRIPT],
            capture_output=True, text=True, timeout=1800,
            cwd=_PROJECT_DIR,
        )
        print("=== 블로그 초안 보충 출력 ===")
        print(result.stdout[-2000:])
        if result.returncode != 0:
            print(f"블로그 초안 보충 실패: {result.stderr[-500:]}")
        return result.returncode == 0
    except Exception as e:
        print(f"블로그 초안 보충 예외: {e}")
        return False


def wait_and_retry(reason):
    """재시도 프로세스의 본체: 1시간 대기 → 파이프라인 재실행 → 성공 시 초안 보충.

    사유는 schedule_retry에서 이미 텔레그램 발송됨 — 여기선 대기부터."""
    print(f"1시간 대기 중... (재시도 사유: {reason})")
    time.sleep(RETRY_DELAY)
    result, output, error = run_pipeline_subprocess()
    retry_result = run_pipeline_result(result, output, error, retrying=True)

    if retry_result == 'published':
        print("재시도 성공 — 블로그 초안 보충 실행")
        draft_ok = run_blog_draft()
        send_telegram("✅ <b>aikorea24 파이프라인 재시도 성공" + (" + 블로그 초안 보충 완료" if draft_ok else " (초안 보충 실패 — 20:15 정기 슬롯 확인 필요)") + "</b>")
    elif retry_result == 'ok_no_news':
        send_telegram("📭 재시도 완료: 브리핑 발행 없음 (뉴스 중복 스킵 등 정상 종료) — 다음 정기 실행 대기")
    else:
        send_telegram("❌ 재시도 실패 — 추가 재시도 없음. 수동 확인 필요")
    try:
        os.remove(RETRY_LOCK)
    except OSError:
        pass


def run_pipeline_subprocess():
    """run_pipeline.py 실행 후 (result, stdout, stderr) 반환."""
    pipeline_script = os.path.join(SCRIPTS_DIR, 'run_pipeline.py')
    result = subprocess.run(
        [sys.executable, pipeline_script, '--skip-thumbnails'],
        capture_output=True,
        text=True,
        timeout=600,  # 10분 타임아웃
        cwd=_PROJECT_DIR
    )
    return result, result.stdout, result.stderr


def run_pipeline_result(result, output, error, retrying=False):
    """파이프라인 결과 판정 + 텔레그램 발송. 반환: 'published'|'ok_no_news'|'failed'."""
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    print("=== 파이프라인 출력 ===")
    print(output)
    if error:
        print("=== 에러 ===")
        print(error)

    problem = detect_problem(result, output)
    briefing_ok = ('브리핑 id=' in output) or ('브리핑 발행' in output)

    if problem and not briefing_ok:
        err_body = html.escape(error[-500:] if error else '')
        out_body = html.escape(output[-500:] if output else '')
        message = f"""❌ <b>aikorea24 파이프라인 실패{' (재시도)' if retrying else ''}</b>
⏰ {now}

문제: {html.escape(problem)}

에러:
<pre>{err_body}</pre>

출력:
<pre>{out_body}</pre>"""
        send_telegram(message)
        return 'failed'
    elif problem and briefing_ok:
        # 예: 일부 배경기사 조회 실패(LIKE)에도 브리핑은 발행됨 — 성공 간주
        body = html.escape(output[-1000:] if len(output) > 1000 else output)
        message = f"""✅ <b>aikorea24 파이프라인 완료 (부분 경고: {html.escape(problem)})</b>
⏰ {now}

📰 News selection + 📖 Briefing published

<pre>{body}</pre>"""
        send_telegram(message)
        return 'published'
    elif briefing_ok:
        body = html.escape(output[-1000:] if len(output) > 1000 else output)
        message = f"""✅ <b>aikorea24 파이프라인 완료</b>
⏰ {now}

📰 News selection + 📖 Briefing published

<pre>{body}</pre>"""
        send_telegram(message)
        return 'published'
    else:
        # rc=0, 브리핑 없음, 명시적 실패 마커 없음 = dedup 스킵 등 정상 종료
        body = html.escape(output[-500:] if output else '')
        message = f"""📭 <b>aikorea24 파이프라인 종료 (브리핑 없음)</b>
⏰ {now}

<pre>{body}</pre>"""
        send_telegram(message)
        return 'ok_no_news'


def main():
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    retrying = is_retry_attempt()
    print(f"=" * 60)
    print(f"aikorea24 파이프라인 실행{' (재시도)' if retrying else ''} - {now}")
    print(f"=" * 60)

    if retrying:
        # --retry 프로세스: 1시간 대기 후 재실행 (wait_and_retry가 본체)
        wait_and_retry(load_retry_reason())
        return

    try:
        result, output, error = run_pipeline_subprocess()
    except subprocess.TimeoutExpired:
        message = f"""⏰ <b>aikorea24 파이프라인 타임아웃</b>
⏰ {now}

10분 초과"""
        send_telegram(message)
        if not retrying:
            schedule_retry('타임아웃')
        return
    except Exception as e:
        err = html.escape(str(e))
        message = f"""❌ <b>aikorea24 파이프라인 에러</b>
⏰ {now}

{err}"""
        send_telegram(message)
        if not retrying:
            schedule_retry(f'실행 예외: {e}')
        return

    outcome = run_pipeline_result(result, output, error, retrying=retrying)

    # 정기 실행에서 실패 감지 → 1시간 후 재시도 예약
    if outcome == 'failed' and not retrying:
        problem = detect_problem(result, output)
        schedule_retry(problem or '알 수 없는 실패')
    # 재시도 성공 시 초안 보충은 wait_and_retry 안에서 처리됨

if __name__ == '__main__':
    main()
