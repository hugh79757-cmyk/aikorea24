"""
model_router.py - AI 모델 호출 라우터
- 1순위: GPT-4o-mini (OpenAI)
- 2순위: DeepSeek V4 Flash (fallback)
- 3순위: MiMo v2.5 (fallback)
- .env / ~/.env.common에서 OPENAI_API_KEY / DEEPSEEK_API_TOKEN / MIMO_API_KEY 자동 로드
"""
import os, sys
from openai import OpenAI

PROJECT_DIR = '/Users/twinssn/Projects/aikorea24'
sys.path.insert(0, os.path.join(PROJECT_DIR, 'scripts', 'threads'))
ENV_FILE = os.path.join(PROJECT_DIR, '.env')

def load_env():
    """.env에서 API 키 로드"""
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
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    if line.startswith('export '):
                        line = line[7:]
                    k, v = line.split('=', 1)
                    envs[k.strip()] = v.strip().strip('"').strip("'")
    for k, v in envs.items():
        os.environ[k] = v
    return envs

load_env()

# === GPT-4o-mini (1순위) ===
OPENAI_MODEL = 'gpt-4o-mini'

# === DeepSeek V4 Flash (2순위 fallback) ===
DEEPSEEK_BASE_URL = os.environ.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com/v1')
DEEPSEEK_MODEL = 'deepseek-v4-flash'

# === MiMo v2.5 (3순위 fallback) ===
MIMO_BASE_URL = os.environ.get('MIMO_BASE_URL', 'https://api.xiaomimimo.com/v1')
MIMO_MODEL = os.environ.get('MIMO_MODEL', 'mimo-v2.5')

def get_openai_client():
    api_key = os.environ.get('OPENAI_API_KEY', '')
    if not api_key:
        return None
    return OpenAI(api_key=api_key)

def get_deepseek_client():
    api_key = os.environ.get('DEEPSEEK_API_TOKEN', '')
    if not api_key:
        return None
    return OpenAI(base_url=DEEPSEEK_BASE_URL, api_key=api_key)

def get_mimo_client():
    api_key = os.environ.get('MIMO_API_KEY', '')
    if not api_key:
        return None
    return OpenAI(base_url=MIMO_BASE_URL, api_key=api_key)

def chat_completion(messages, system_prompt=None, temperature=0.7, max_tokens=2000, model_override=None, deepseek_model=None):
    """
    통합 채팅 completions 함수
    - 1순위: GPT-4o-mini (OpenAI)
    - 2순위: DeepSeek V4 Flash (fallback)
    - 3순위: MiMo v2.5 (fallback)

    model_override='mimo': OpenAI+DeepSeek 건너뛰고 MiMo 사용
    model_override='openai': OpenAI 건너뛰고 DeepSeek 사용
    Returns: 응답 텍스트 (string), 실패 시 None
    """
    full_messages = []
    if system_prompt:
        full_messages.append({"role": "system", "content": system_prompt})
    full_messages.extend(messages)

    if model_override not in ("mimo", "openai"):
        client = get_openai_client()
        if client:
            try:
                print(f'  [모델] GPT-4o-mini')
                resp = client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=full_messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                text = resp.choices[0].message.content
                if text and text.strip():
                    return text.strip()
            except Exception as e:
                print(f'  [경고] GPT-4o-mini 실패: {type(e).__name__}')
                print(f'  [폴백] → DeepSeek')
        else:
            print(f'  [안내] OPENAI_API_KEY 없음 → DeepSeek')

    if model_override != "mimo":
        ds_client = get_deepseek_client()
        if ds_client:
            active_model = deepseek_model or DEEPSEEK_MODEL
            try:
                print(f'  [모델] DeepSeek {active_model}')
                resp = ds_client.chat.completions.create(
                    model=active_model,
                    messages=full_messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                text = resp.choices[0].message.content
                if text and text.strip():
                    return text.strip()
            except Exception as e:
                print(f'  [경고] DeepSeek 실패: {type(e).__name__}')
                print(f'  [폴백] → MiMo')
        else:
            print(f'  [안내] DEEPSEEK_API_TOKEN 없음 → MiMo')

    if model_override != "deepseek":
        mimo_client = get_mimo_client()
        if mimo_client:
            try:
                print(f'  [모델] MiMo {MIMO_MODEL}')
                resp = mimo_client.chat.completions.create(
                    model=MIMO_MODEL,
                    messages=full_messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                text = resp.choices[0].message.content
                if text and text.strip():
                    return text.strip()
            except Exception as e:
                print(f'  [오류] MiMo 실패: {type(e).__name__}')
        else:
            print(f'  [오류] MIMO_API_KEY 없음')

    return None


if __name__ == '__main__':
    print("=== model_router 테스트 ===")
    text = chat_completion(
        messages=[{"role": "user", "content": "안녕하세요! 간단히 인사해주세요."}],
        temperature=0.3,
        max_tokens=100,
    )
    if text:
        print(f'응답: {text}')
    else:
        print('실패')
