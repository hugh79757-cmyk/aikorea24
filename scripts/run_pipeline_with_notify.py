#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
"""
aikorea24 파이프라인 실행기 + 텔레그램 알림
- run_pipeline.py 실행
- 결과를 텔레그램으로 발송
"""
import os
import sys
import subprocess
import json
import urllib.request
import html
from datetime import datetime

PROJECT_DIR = '/Users/twinssn/Projects/aikorea24'
SCRIPTS_DIR = os.path.join(PROJECT_DIR, 'scripts')

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

# 텔레그램 알림 함수
def send_telegram(message):
    """텔레그램으로 메시지 발송"""
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID', '')
    
    if not bot_token or not chat_id:
        print(f"  ⚠ 텔레그램 설정 없음: {message}")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = json.dumps({
            "chat_id": chat_id,
            "message": message,
            "parse_mode": "HTML"
        }).encode()
        
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read())
        if result.get("ok"):
            print(f"  ✅ 텔레그램 알림 발송 완료")
            return True
        else:
            print(f"  ❌ 텔레그램 에러: {result}")
            return False
    except Exception as e:
        print(f"  ❌ 텔레그램 발송 실패: {e}")
        return False

def main():
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    print(f"=" * 60)
    print(f"aikorea24 파이프라인 실행 - {now}")
    print(f"=" * 60)
    
    # run_pipeline.py 실행
    pipeline_script = os.path.join(SCRIPTS_DIR, 'run_pipeline.py')
    
    try:
        # 심층글/썸네일은 blog-draft launchd job(07:00)이 대체
        pipeline_args = [
            sys.executable, pipeline_script,
            "--skip-deep",
            "--skip-thumbnails",
        ]
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
        
        # 결과 메시지 생성 (HTML 태그 파싱 오류 방지: 본문은 escape 후 <pre>로 감쌈)
        if result.returncode == 0:
            body = html.escape(output[-1000:] if len(output) > 1000 else output)
            message = f"""✅ <b>aikorea24 파이프라인 완료</b>
⏰ {now}

<pre>{body}</pre>"""
        else:
            err_body = html.escape(error[-500:] if len(error) > 500 else error)
            out_body = html.escape(output[-500:] if len(output) > 500 else output)
            message = f"""❌ <b>aikorea24 파이프라인 실패</b>
⏰ {now}

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
