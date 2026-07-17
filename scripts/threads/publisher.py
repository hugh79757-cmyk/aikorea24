#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
"""
aikorea24 Threads API 발행기
- 연속 답글 체인 발행 (reply_to_id)
- requests 라이브러리 사용
- 3회 재시도 + 토큰 자동 갱신
"""
import os, sys, json, time, socket, requests
from datetime import datetime

from pipeline.infra.env_loader import EnvConfig
_config = EnvConfig()
_config.load_to_environ()
from pipeline.infra import project_root; PROJECT_DIR = project_root()

from pipeline.infra.logger import get_scrubbed_logger
logger = get_scrubbed_logger(__name__)

THREADS_DIR = os.path.join(PROJECT_DIR, 'scripts', 'threads')
POSTED_FILE = os.path.join(THREADS_DIR, 'posted.json')
LOGS_DIR = os.path.join(THREADS_DIR, 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)

# Strangler Fig: replace with logger.info() in Phase 3
def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f'[{ts}] {msg}')
    with open(os.path.join(LOGS_DIR, datetime.now().strftime('%Y-%m-%d') + '.log'), 'a', encoding='utf-8') as f:
        f.write(f'[{ts}] {msg}\n')

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
        }, timeout=30)
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

    # DNS 사전체크 — 실패 시 아예 발행 시작 안 함 (카드 1만 떠있는 현상 방지)
    try:
        socket.getaddrinfo('graph.threads.net', 443)
    except socket.gaierror as e:
        log(f'  ❌ DNS 조회 실패 (graph.threads.net): {e}')
        return None

    # Threads API 500자 제한 (비상 안전장치, 프롬프트가 우선)
    MAX_CHARS = 500
    import re as _re
    for i, card_text in enumerate(cards):
        if len(card_text) > MAX_CHARS:
            # 문장 분할 (.!? 기준)
            sentences = _re.split(r'(?<=[.!?])\s+', card_text)
            if len(sentences) <= 2:
                # 문장이 2개 이하면 강제 절단
                cards[i] = card_text[:MAX_CHARS]
            else:
                # 첫 문장 + 마지막 문장은 유지, 중간 문장 제거
                first = sentences[0]
                last = sentences[-1]
                middle = sentences[1:-1]
                # 중간 문장을 하나씩 제거하면서 500자 이하로
                while middle and len(first + ' ' + ' '.join(middle) + ' ' + last) > MAX_CHARS:
                    middle.pop()
                if middle:
                    cards[i] = first + ' ' + ' '.join(middle) + ' ' + last
                else:
                    cards[i] = first + ' ' + last
                    if len(cards[i]) > MAX_CHARS:
                        cards[i] = card_text[:MAX_CHARS]
            log(f'  ✂️ 카드 {i+1}: {len(card_text)}자 → {len(cards[i])}자 (중간 문장 제거)')

    for i, card_text in enumerate(cards):
        params = {
            'media_type': 'TEXT',
            'text': add_line_spacing(card_text),
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
                    params=params, timeout=30
                )
                data = r.json()
                if 'id' in data:
                    container_id = data['id']
                    break
                log(f'  컨테이너 응답 (id 없음): {str(data)[:200]}')
                if data.get('error', {}).get('code') == 190:
                    log(f'  토큰 만료 → 갱신')
                    new_tok = refresh_token()
                    if new_tok:
                        params['access_token'] = new_tok
                        access_token = new_tok
                        continue
            except Exception as e:
                log(f'  컨테이너 생성 시도 {attempt+1}/3 실패: {e}')
            time.sleep(10)
        else:
            log(f'  ❌ 카드 {i+1} 컨테이너 생성 실패')
            return None

        time.sleep(10)

        # 발행 (3회 재시도)
        post_id = None
        for attempt in range(3):
            try:
                r2 = requests.post(
                    f'https://graph.threads.net/v1.0/{user_id}/threads_publish',
                    params={'creation_id': container_id, 'access_token': access_token},
                    timeout=30
                )
                data2 = r2.json()
                if 'id' in data2:
                    post_id = data2['id']
                    break
                log(f'  발행 응답 (id 없음): {str(data2)[:200]}')
            except Exception as e:
                log(f'  발행 시도 {attempt+1}/3 실패: {e}')
            time.sleep(10)
        else:
            log(f'  ❌ 카드 {i+1} 발행 실패')
            return None

        if i == 0:
            root_post_id = post_id
        previous_post_id = post_id
        log(f'  카드 {i+1}/{len(cards)} 발행: {post_id}')
        time.sleep(10)



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

def add_line_spacing(text):
    """AI가 이미 stanza 구조로 작성했다면 유지, 아니면 문장 단위로 공백 추가"""
    import re as _re
    # 방어: 리터럴 \n → 실제 개행 (DeepSeek JSON 이중 이스케이프 대응)
    text = text.replace('\\n', '\n')
    # 이미 빈 줄로 구분된 구조면 그대로 반환 (AI가 의도한 리듬 유지)
    if '\n\n' in text.strip():
        return text
    sentences = _re.split(r'(?<=[.!?])\s+', text)
    result = '\n\n'.join(s.strip() for s in sentences if s.strip())
    return result


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
