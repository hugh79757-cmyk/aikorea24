#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
"""
Threads API 토큰 갱신 (단독 실행 가능)
- GET https://graph.threads.net/refresh_access_token
- 갱신 토큰을 .env에 저장
- 남은 만료일 출력
"""
import os, sys, json, requests
from datetime import datetime

PROJECT_DIR = '/Users/twinssn/Projects/aikorea24'
ENV_FILE = os.path.join(PROJECT_DIR, '.env')

def load_env():
    envs = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    if line.startswith('export '):
                        line = line[7:]
                    k, v = line.split('=', 1)
                    envs[k.strip()] = v.strip().strip('"').strip("'")
    return envs

def refresh_token():
    envs = load_env()
    token = envs.get('THREADS_ACCESS_TOKEN', '')
    if not token:
        print('  ❌ THREADS_ACCESS_TOKEN 없음')
        return None

    try:
        r = requests.get('https://graph.threads.net/refresh_access_token', params={
            'grant_type': 'th_refresh_token',
            'access_token': token
        }, timeout=15)
        data = r.json()
        new_token = data.get('access_token', '')
        expires_in = data.get('expires_in', 0)
        days_left = expires_in // 86400

        if new_token:
            with open(ENV_FILE, 'r') as f:
                lines = f.readlines()
            for i, line in enumerate(lines):
                if line.strip().startswith('THREADS_ACCESS_TOKEN'):
                    if line.strip().startswith('export '):
                        lines[i] = f'export THREADS_ACCESS_TOKEN="{new_token}"\n'
                    else:
                        lines[i] = f'THREADS_ACCESS_TOKEN="{new_token}"\n'
                    break
            with open(ENV_FILE, 'w') as f:
                f.writelines(lines)
            print(f'  ✅ 갱신 성공 (만료 {days_left}일)')
            print(f'  🔑 토큰 갱신 완료 ({len(new_token)}자)')
            return new_token
        else:
            print(f'  ❌ 응답 오류: {data}')
            return None
    except Exception as e:
        print(f'  ❌ 오류: {e}')
        return None


if __name__ == '__main__':
    print(f'[{datetime.now().strftime("%H:%M:%S")}] Threads 토큰 갱신')
    result = refresh_token()
    sys.exit(0 if result else 1)
