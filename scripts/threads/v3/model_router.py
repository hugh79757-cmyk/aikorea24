"""
model_router.py - AI 모델 호출 라우터
- 1순위: MiMo v2.5 (xiaomimimo.com)
- 2순위: DeepSeek V4 Flash (deepseek.com, fallback)
- 3순위: GPT-4o-mini (OpenAI, fallback)
- .env / ~/.env.common에서 MIMO_API_KEY / DEEPSEEK_API_TOKEN / OPENAI_API_KEY 자동 로드
"""
import os, sys
from datetime import datetime
from openai import OpenAI
import httpx

from pipeline.infra.env_loader import EnvConfig
_config = EnvConfig()
_config.load_to_environ()
from pipeline.infra import project_root; PROJECT_DIR = project_root()
sys.path.insert(0, os.path.join(PROJECT_DIR, 'scripts', 'threads'))
ENV_FILE = os.path.join(PROJECT_DIR, '.env')
LOGS_DIR = os.path.join(PROJECT_DIR, 'scripts', 'threads', 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)


def _log_to_file(msg):
    """일일 로그 파일에 기록 (print와 별개로 파일에만 씀)"""
    ts = datetime.now().strftime('%H:%M:%S')
    with open(os.path.join(LOGS_DIR, datetime.now().strftime('%Y-%m-%d') + '.log'), 'a', encoding='utf-8') as f:
        f.write(f'[{ts}] [v3] [model_router] {msg}\n')

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

# === MiMo v2.5 (1순위) ===
MIMO_BASE_URL = os.environ.get('MIMO_BASE_URL', 'https://api.xiaomimimo.com/v1')
MIMO_MODEL = os.environ.get('MIMO_MODEL', 'mimo-v2.5')

# === DeepSeek V4 Flash (2순위 fallback) ===
DEEPSEEK_BASE_URL = os.environ.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com/v1')
DEEPSEEK_MODEL = 'deepseek-v4-flash'

# === GPT-4o-mini (3순위 fallback) ===
OPENAI_MODEL = 'gpt-4o-mini'

def get_openai_client():
    api_key = os.environ.get('OPENAI_API_KEY', '')
    if not api_key:
        return None
    return OpenAI(api_key=api_key)

def get_deepseek_client():
    api_key = os.environ.get('DEEPSEEK_API_TOKEN', '')
    if not api_key:
        return None
    return OpenAI(
        base_url=DEEPSEEK_BASE_URL,
        api_key=api_key,
        timeout=httpx.Timeout(180.0, connect=30.0),
    )

def get_mimo_client():
    api_key = os.environ.get('MIMO_API_KEY', '')
    if not api_key:
        return None
    return OpenAI(base_url=MIMO_BASE_URL, api_key=api_key)

def chat_completion(messages, system_prompt=None, temperature=0.7, max_tokens=2000, model_override=None, deepseek_model=None, response_format=None, extra_body=None):
    """
    통합 채팅 completions 함수
    - 1순위: MiMo v2.5 (xiaomimimo.com)
    - 2순위: DeepSeek V4 Flash (deepseek.com, fallback)
    - 3순위: GPT-4o-mini (OpenAI, fallback)

    model_override='mimo': MiMo 강제 사용
    model_override='deepseek': DeepSeek 강제 사용
    model_override='openai': OpenAI 강제 사용
    response_format: OpenAI-compatible response format (e.g. {'type': 'json_object'})
    extra_body: extra body parameters (e.g. {"thinking": {"type": "disabled"}})
    Returns: 응답 텍스트 (string), 실패 시 None
    """
    kwargs = {}
    if response_format:
        kwargs['response_format'] = response_format
    if extra_body:
        kwargs['extra_body'] = extra_body

    full_messages = []
    if system_prompt:
        full_messages.append({"role": "system", "content": system_prompt})
    full_messages.extend(messages)

    # 1순위: MiMo v2.5 (명시적 요청 시에만)
    if model_override == "mimo":
        mimo_client = get_mimo_client()
        if mimo_client:
            try:
                print(f'  [모델] MiMo {MIMO_MODEL}')
                resp = mimo_client.chat.completions.create(
                    model=MIMO_MODEL,
                    messages=full_messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )
                text = resp.choices[0].message.content
                if text and text.strip():
                    return text.strip()
            except Exception as e:
                print(f'  [경고] MiMo 실패: {type(e).__name__}')
                if model_override == "mimo":
                    print(f'  [오류] MiMo 강제 모드 실패')
                    return None
                print(f'  [폴백] → DeepSeek')
        else:
            if model_override == "mimo":
                print(f'  [오류] MIMO_API_KEY 없음')
                return None
            print(f'  [안내] MIMO_API_KEY 없음 → DeepSeek')

    # 2순위: DeepSeek V4 Flash
    if model_override in ("deepseek", None):
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
                    **kwargs,
                )
                choice = resp.choices[0] if resp.choices else None
                if choice:
                    text = choice.message.content
                    finish_reason = choice.finish_reason
                    refusal = getattr(choice.message, 'refusal', None)

                    _log_to_file(f'DeepSeek finish_reason={finish_reason} content_len={len(text) if text else 0} refusal={str(refusal)[:100] if refusal else "none"}')

                    if text and text.strip():
                        return text.strip()

                    if not text and finish_reason == 'content_filter':
                        print(f'  [경고] DeepSeek 콘텐츠 필터 차단 (refusal={refusal})')
                        _log_to_file(f'⚠️ content_filter 차단: {refusal[:200] if refusal else "없음"}')
                    elif not text and finish_reason == 'length':
                        print(f'  [경고] DeepSeek 토큰 제한 도달 (max_tokens={max_tokens})')
                        _log_to_file(f'⚠️ max_tokens={max_tokens} 초과')
                    else:
                        print(f'  [경고] DeepSeek 빈 응답 (finish_reason={finish_reason})')
                        _log_to_file(f'⚠️ 빈 응답 finish_reason={finish_reason}')
                else:
                    print(f'  [경고] DeepSeek choices 배열 비어있음')
                    _log_to_file(f'⚠️ choices=[] (빈 배열)')
            except Exception as e:
                status = getattr(e, 'status_code', 'unknown') if hasattr(e, 'status_code') else 'unknown'
                print(f'  [경고] DeepSeek 실패: HTTP {status} {type(e).__name__}: {e}')
                _log_to_file(f'⚠️ 예외: HTTP {status} {type(e).__name__}: {str(e)[:200]}')
                if model_override == "deepseek":
                    print(f'  [오류] DeepSeek 강제 모드 실패')
                    return None
                print(f'  [폴백] → OpenAI')
        else:
            if model_override == "deepseek":
                print(f'  [오류] DEEPSEEK_API_TOKEN 없음')
                return None
            print(f'  [안내] DEEPSEEK_API_TOKEN 없음 → OpenAI')

    # 3순위: GPT-4o-mini
    if model_override in ("openai", None):
        client = get_openai_client()
        if client:
            try:
                print(f'  [모델] GPT-4o-mini')
                resp = client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=full_messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )
                text = resp.choices[0].message.content
                if text and text.strip():
                    return text.strip()
            except Exception as e:
                print(f'  [경고] GPT-4o-mini 실패: {type(e).__name__}')
                if model_override == "openai":
                    print(f'  [오류] OpenAI 강제 모드 실패')
                    return None
        else:
            if model_override == "openai":
                print(f'  [오류] OPENAI_API_KEY 없음')
                return None
            print(f'  [안내] OPENAI_API_KEY 없음')

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
