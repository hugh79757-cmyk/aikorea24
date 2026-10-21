#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
"""
aikorea24 파이프라인 실행기 + 텔레그램 알림
- run_pipeline.py 실행
- 결과를 텔레그램으로 발송
"""
import argparse
import os
import sys
import subprocess
import html
import re
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

# AIK24-PIPE-08 B-6: load_env 호출은 main() 안에서 한다 (module import 시점에는 하지 않는다).
# 2026-10-10 BRIEF-01: PROJECT_DIR 은 scripts/ 로 재할당돼 루트 .env 를 못 읽었다 → _PROJECT_DIR 을 쓴다.


# AIK24-PIPE-ALERT-01: run_pipeline.summary 의 실제 건수를 그대로 알림에 싣는다.
# "📖 Briefing published" 같은 뭉뚱그린 문구는 0건일 때도 그대로 나가서
# "없는 것을 발행했다고 알리는" 사고를 만든다 (2026-10-21 실측).
def _parse_count(output, label):
    """run_pipeline 출력에서 '<label>: N건' 을 뽑는다. 없으면 None(확인 불가)."""
    hits = re.findall(rf"{re.escape(label)}\s*:\s*(\d+)\s*건", output or "")
    return int(hits[-1]) if hits else None


def _counts_text(output):
    """(선정 뉴스 표기, 생성 브리핑 표기) — 파싱 실패 시 '확인 불가'."""
    news_n = _parse_count(output, "선정 뉴스")
    brief_n = _parse_count(output, "생성 브리핑")
    news_txt = f"{news_n}건" if news_n is not None else "확인 불가"
    brief_txt = f"{brief_n}건" if brief_n is not None else "확인 불가"
    return news_txt, brief_txt, brief_n


# AIK24-PIPE-08 B-2: run_pipeline 요약의 경고 블록("⚠️  경고: N건" + "    - 사유")을
# 읽어 알림 본문에 싣는다 — 조기 경보 사유(후보 풀 부족·수집 단계 이상)를 운영자가
# 텔레그램에서 바로 본다.
# ⚠ + 선택적 VS16 (U+26A0 U+FE0F) — run_pipeline.py 가 출력하는 경고 헤더와 맞춘다.
# run_pipeline 의 log() 는 각 줄 앞에 "[HH:MM:SS] " 타임스탬프를 붙이므로 허용한다.
_LOG_PREFIX_RE = re.compile(r"^\[[^\]\n]*\][ \t]*")
_WARNING_HEADER_RE = re.compile(
    r"^(?:\[[^\]\n]*\][ \t]*)?\u26a0\ufe0f?[ \t]+경고:[ \t]*(\d+)건[ \t]*$", re.M)


def _strip_log_prefix(line):
    """run_pipeline.log() 의 '[HH:MM:SS] ' 접두를 벗긴다."""
    return _LOG_PREFIX_RE.sub("", line)


def _warning_lines(output):
    """요약 경고 블록에서 사유 줄만 뽑는다 (없으면 빈 리스트)."""
    text = output or ""
    m = _WARNING_HEADER_RE.search(text)
    if not m:
        return []
    lines = []
    for raw in text[m.end():].splitlines():
        stripped = _strip_log_prefix(raw).strip()
        if not stripped:
            continue
        if stripped.startswith("- "):
            lines.append(stripped[2:].strip())
            continue
        break
    return lines


def _warning_block(output):
    """알림 본문용 경고 블록 (비어 있으면 빈 문자열)."""
    warns = _warning_lines(output)
    if not warns:
        return ""
    return "\n".join(f"⚠️ {html.escape(w)}" for w in warns)


def main():
    parser = argparse.ArgumentParser(description="aikorea24 파이프라인 실행기 + 텔레그램 알림 (나머지 인자는 run_pipeline.py로 전달)")
    parser.add_argument("--no-email", action="store_true",
                        help="이메일 발송 안 함 (수동 실행용. 자동 스케줄 실행에는 사용 금지)")
    args, _ = parser.parse_known_args()
    if args.no_email:
        print("[pipeline] --no-email: 이메일 발송 건너뜀")

    # AIK24-PIPE-08 B-6: 환경변수 로드를 모듈 import 시점이 아니라 main() 안으로 옮겼다.
    # 이유: import 시점에 ~/.env.common·.env 를 읽으면 테스트가 모듈만 import 해도
    # os.environ 에 실제 토큰이 주입된다. 동작은 동일하다 — send_telegram 은 main() 안에서만
    # 호출되고, env 는 그 전에 로드된다.
    # 2026-10-10 BRIEF-01: PROJECT_DIR 은 scripts/ 로 재할당돼 루트 .env 를 못 읽는다 → _PROJECT_DIR.
    load_env(os.path.join(_PROJECT_DIR, '.env'))

    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    print(f"=" * 60)
    print(f"aikorea24 파이프라인 실행 - {now}")
    print(f"=" * 60)
    
    # run_pipeline.py 실행
    pipeline_script = os.path.join(SCRIPTS_DIR, 'run_pipeline.py')
    
    try:
        # 블로그/썸네일은 blog-draft launchd job(07:00/20:00)이 대체
        pipeline_args = [
            sys.executable, pipeline_script,
            "--skip-thumbnails",
        ]
        # v2 (AIK24-PIPE-02 Step 6): 인자 전달. launchd 는 인자 없이 호출하므로 기본 동작은 동일.
        # 수동 실행 시 `--dry-run` 등을 그대로 run_pipeline.py 로 넘긴다.
        pipeline_args.extend(sys.argv[1:])
        result = subprocess.run(
            pipeline_args,
            capture_output=True,
            text=True,
            timeout=600,  # 10분 타임아웃
            cwd=PROJECT_DIR
        )
        
        output = result.stdout
        error = result.stderr
        
        print("=== 파이프라인 출력 ===")
        print(output)
        
        if error:
            print("=== 에러 ===")
            print(error)
        
        # 결과 메시지 생성 (실제 브리핑 건수를 함께 알림 — AIK24-PIPE-ALERT-01)
        news_txt, brief_txt, brief_n = _counts_text(output)
        # AIK24-PIPE-08 B-2: 조기 경보 사유(후보 풀 부족·수집 단계 이상)를 알림에 싣는다.
        warn_block = _warning_block(output)
        warn_line = f"\n\n{warn_block}" if warn_block else ""
        if result.returncode == 0:
            body = html.escape(output[-1000:] if len(output) > 1000 else output)
            # 0건이면 "발행했다"고 말하지 않는다 (성공/실패 어느 쪽이든 동일).
            brief_line = (f"📖 생성 브리핑: {brief_txt} (발행 없음)"
                          if brief_n == 0 else f"📖 생성 브리핑: {brief_txt}")
            message = f"""✅ <b>aikorea24 파이프라인 완료</b>
⏰ {now}

📰 선정 뉴스: {news_txt} · {brief_line}{warn_line}

<pre>{body}</pre>"""

            # blog-draft는 별도 launchd 작업(kr.aikorea24.blog-draft)에서 15분 후 실행됨
            # 여기서는 호출하지 않음 (중복 실행 방지)
        else:
            err_body = html.escape(error[-500:] if len(error) > 500 else error)
            out_body = html.escape(output[-500:] if len(output) > 500 else output)
            message = f"""❌ <b>aikorea24 파이프라인 실패</b>
⏰ {now}

📰 선정 뉴스: {news_txt} · 📖 생성 브리핑: {brief_txt}{warn_line}

에러:
<pre>{err_body}</pre>

출력:
<pre>{out_body}</pre>"""

        # 텔레그램 발송 (성공/실패 경로 모두 **1회만** 발송)
        send_telegram(message)

        # AIK24-PIPE-08 B-6: 내부 파이프라인의 종료코드를 그대로 전파한다.
        # (이전에는 버리고 항상 exit 0 → launchd·모니터링이 실패를 실패로 보지 못함)
        return result.returncode

    except subprocess.TimeoutExpired:
        message = f"""⏰ <b>aikorea24 파이프라인 타임아웃</b>
⏰ {now}

10분 초과"""
        send_telegram(message)
        return 124  # 타임아웃은 실패 — launchd 가 알아야 한다
    except Exception as e:
        err = html.escape(str(e))
        message = f"""❌ <b>aikorea24 파이프라인 에러</b>
⏰ {now}

{err}"""
        send_telegram(message)
        return 1

if __name__ == '__main__':
    # AIK24-PIPE-08 B-6: 내부 파이프라인의 returncode 를 그대로 프로세스 종료코드로 쓴다.
    sys.exit(main())
