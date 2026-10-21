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

load_env(os.path.join(_PROJECT_DIR, '.env'))  # 2026-10-10 BRIEF-01: PROJECT_DIR은 scripts/로 재할당돼 루트 .env를 못 읽었다


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


def main():
    parser = argparse.ArgumentParser(description="aikorea24 파이프라인 실행기 + 텔레그램 알림 (나머지 인자는 run_pipeline.py로 전달)")
    parser.add_argument("--no-email", action="store_true",
                        help="이메일 발송 안 함 (수동 실행용. 자동 스케줄 실행에는 사용 금지)")
    args, _ = parser.parse_known_args()
    if args.no_email:
        print("[pipeline] --no-email: 이메일 발송 건너뜀")

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
        if result.returncode == 0:
            body = html.escape(output[-1000:] if len(output) > 1000 else output)
            # 0건이면 "발행했다"고 말하지 않는다 (성공/실패 어느 쪽이든 동일).
            brief_line = (f"📖 생성 브리핑: {brief_txt} (발행 없음)"
                          if brief_n == 0 else f"📖 생성 브리핑: {brief_txt}")
            message = f"""✅ <b>aikorea24 파이프라인 완료</b>
⏰ {now}

📰 선정 뉴스: {news_txt} · {brief_line}

<pre>{body}</pre>"""

            # blog-draft는 별도 launchd 작업(kr.aikorea24.blog-draft)에서 15분 후 실행됨
            # 여기서는 호출하지 않음 (중복 실행 방지)
        else:
            err_body = html.escape(error[-500:] if len(error) > 500 else error)
            out_body = html.escape(output[-500:] if len(output) > 500 else output)
            message = f"""❌ <b>aikorea24 파이프라인 실패</b>
⏰ {now}

📰 선정 뉴스: {news_txt} · 📖 생성 브리핑: {brief_txt}

에러:
<pre>{err_body}</pre>

출력:
<pre>{out_body}</pre>"""

        # 텔레그램 발송
        send_telegram(message)

    except subprocess.TimeoutExpired:
        message = f"""⏰ <b>aikorea24 파이프라인 타임아웃</b>
⏰ {now}

10분 초과"""
        send_telegram(message)
    except Exception as e:
        err = html.escape(str(e))
        message = f"""❌ <b>aikorea24 파이프라인 에러</b>
⏰ {now}

{err}"""
        send_telegram(message)

if __name__ == '__main__':
    main()
