#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
"""
aikorea24 Threads API 발행기
- 연속 답글 체인 발행 (reply_to_id)
- requests 라이브러리 사용
- 3회 재시도 + 토큰 자동 갱신
"""
import os, sys, json, time, requests
from datetime import datetime

PROJECT_DIR = '/Users/twinssn/Projects/aikorea24'
THREADS_DIR = os.path.join(PROJECT_DIR, 'scripts', 'threads')
POSTED_FILE = os.path.join(THREADS_DIR, 'posted.json')
LOGS_DIR = os.path.join(THREADS_DIR, 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f'[{ts}] {msg}')
    with open(os.path.join(LOGS_DIR, datetime.now().strftime('%Y-%m-%d') + '.log'), 'a', encoding='utf-8') as f:
        f.write(f'[{ts}] {msg}\n')

def load_env():
    envs = {}
    for path in [os.path.join(PROJECT_DIR, '.env'), os.path.join(PROJECT_DIR, 'api_test', '.env.sh')]:
        if os.path.exists(path):
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        if line.startswith('export '):
                            line = line[7:]
                        k, v = line.split('=', 1)
                        envs[k.strip()] = v.strip().strip('"').strip("'")
    return envs

def load_posted():
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"posted_links": [], "posted_ids": [], "history": [], "last_reset": ""}

def save_posted(data):
    with open(POSTED_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def refresh_token():
    """토큰 갱신"""
    envs = load_env()
    token = envs.get('THREADS_ACCESS_TOKEN', '')
    if not token:
        log('  ❌ 토큰 없음'); return None
    try:
        r = requests.get('https://graph.threads.net/refresh_access_token', params={
            'grant_type': 'th_refresh_token',
            'access_token': token
        }, timeout=15)
        data = r.json()
        new_token = data.get('access_token', '')
        if new_token:
            # .env 갱신
            env_path = os.path.join(PROJECT_DIR, '.env')
            with open(env_path, 'r') as f:
                lines = f.readlines()
            for i, line in enumerate(lines):
                if line.startswith('THREADS_ACCESS_TOKEN'):
                    lines[i] = f'THREADS_ACCESS_TOKEN={new_token}\n'
                    break
            with open(env_path, 'w') as f:
                f.writelines(lines)
            days = data.get('expires_in', 0) // 86400
            log(f'  토큰 갱신 완료 (만료 {days}일)')
            return new_token
        log(f'  ❌ 토큰 갱신 실패: {data}')
        return None
    except Exception as e:
        log(f'  ❌ 토큰 갱신 오류: {e}')
        return None

def publish_thread_chain(cards, article):
    """연속 답글 체인 발행"""
    envs = load_env()
    access_token = envs.get('THREADS_ACCESS_TOKEN', '')
    user_id = envs.get('THREADS_USER_ID', '')
    if not access_token or not user_id:
        log('  ❌ 토큰/USER_ID 없음'); return None

    root_post_id = None
    previous_post_id = None

    for i, card_text in enumerate(cards):
        params = {
            'media_type': 'TEXT',
            'text': card_text,
            'access_token': access_token
        }
        if previous_post_id:
            params['reply_to_id'] = previous_post_id

        # 컨테이너 생성 (3회 재시도)
        container_id = None
        for attempt in range(3):
            try:
                r = requests.post(
                    f'https://graph.threads.net/v1.0/{user_id}/threads',
                    params=params, timeout=15
                )
                data = r.json()
                if 'id' in data:
                    container_id = data['id']
                    break
                if data.get('error', {}).get('code') == 190:
                    log(f'  토큰 만료 → 갱신')
                    new_tok = refresh_token()
                    if new_tok:
                        params['access_token'] = new_tok
                        access_token = new_tok
                        continue
            except Exception as e:
                log(f'  컨테이너 생성 시도 {attempt+1}/3 실패: {e}')
            time.sleep(2)
        else:
            log(f'  ❌ 카드 {i+1} 컨테이너 생성 실패')
            return None

        time.sleep(3)

        # 발행 (3회 재시도)
        post_id = None
        for attempt in range(3):
            try:
                r2 = requests.post(
                    f'https://graph.threads.net/v1.0/{user_id}/threads_publish',
                    params={'creation_id': container_id, 'access_token': access_token},
                    timeout=15
                )
                data2 = r2.json()
                if 'id' in data2:
                    post_id = data2['id']
                    break
            except Exception as e:
                log(f'  발행 시도 {attempt+1}/3 실패: {e}')
            time.sleep(2)
        else:
            log(f'  ❌ 카드 {i+1} 발행 실패')
            return None

        if i == 0:
            root_post_id = post_id
        previous_post_id = post_id
        log(f'  카드 {i+1}/{len(cards)} 발행: {post_id}')
        time.sleep(3)



    # posted.json 저장
    posted = load_posted()
    link = article.get('link', '')
    aid = article.get('id')
    title = article.get('title', '')
    now = datetime.now().isoformat()

    if link and link not in posted['posted_links']:
        posted['posted_links'].append(link)
    if aid and aid not in posted['posted_ids']:
        posted['posted_ids'].append(aid)
    posted['history'].append({
        'id': aid, 'link': link, 'title': title, 'posted_at': now
    })
    save_posted(posted)
    log(f'  posted.json 업데이트 완료')

    return root_post_id


def parse_cards(text):
    cards = [c.strip() for c in text.split('---') if c.strip()]
    return cards


if __name__ == '__main__':
    import glob
    drafts = sorted(glob.glob(os.path.join(LOGS_DIR, 'drafts', '*.txt')))
    if drafts:
        latest = drafts[-1]
        with open(latest, 'r', encoding='utf-8') as f:
            text = f.read()
        cards = parse_cards(text)
        print(f'초안: {latest}')
        print(f'카드: {len(cards)}개')
        article = {'id': 99999, 'title': '테스트', 'link': ''}
        result = publish_thread_chain(cards, article)
        print(f'결과: {"✅ " + str(result) if result else "❌ 실패"}')
    else:
        print('초안 없음')
