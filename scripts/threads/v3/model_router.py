""""
model_router.py - AI 모델 호출 라우터 (무료 LLM 폴백 체인 통합)
- 무료 체인: config/models.yaml의 tier_order 16개 무료 모델 순차 시도
- 최후 수단: 유료 DeepSeek V4 Flash (default tier)
- 평가/후처리: GPT-4o-mini (OpenAI, model_override='openai')
- .env / ~/.env.common에서 각 프로바이더 API 키 자동 로드
"""
import os, sys, time
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

# === 레거시 상수 (기존 호환 유지) ===
MIMO_BASE_URL = os.environ.get('MIMO_BASE_URL', 'https://api.xiaomimimo.com/v1')
MIMO_MODEL = os.environ.get('MIMO_MODEL', 'mimo-v2.5')
DEEPSEEK_BASE_URL = os.environ.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com/v1')
DEEPSEEK_MODEL = 'deepseek-v4-flash'
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

# =====================================================================
# 무료 LLM 폴백 체인 (config/models.yaml)
# =====================================================================
import yaml

def _load_chain_config():
    """config/models.yaml 로드 → None이면 체인 비활성"""
    yaml_path = os.path.join(PROJECT_DIR, 'config', 'models.yaml')
    if not os.path.exists(yaml_path):
        _log_to_file('⚠️ config/models.yaml 없음 → 체인 비활성 (deepseek 단독)')
        return None
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        _log_to_file(f'⚠️ models.yaml 로드 실패: {e} → 체인 비활성')
        return None

CHAIN_CONFIG = _load_chain_config()

# 서킷브레이커 (모듈 전역 — 프로세스 수명 동안 유지)
_chain_state = {'failures': 0, 'open_until': 0.0}
CIRCUIT_BREAKER_THRESHOLD = 10   # 연속 실패 → 개방
CIRCUIT_BREAKER_RESET_SEC = 300  # 5분 후 자동 복구
CHAIN_MAX_RETRIES = 2            # tier당 재시도 횟수 (기존 deepseek 2회와 일치)
CHAIN_BACKOFF = [10, 20]         # 초 단위 백오프

_client_cache = {}

def get_provider_client(provider_name, base_url, api_key_env):
    """프로바이더별 OpenAI 호환 클라이언트 (연결 풀 캐시)"""
    if provider_name in _client_cache:
        return _client_cache[provider_name]
    api_key = os.environ.get(api_key_env, '')
    if not api_key:
        _client_cache[provider_name] = None
        return None
    client = OpenAI(
        base_url=base_url,
        api_key=api_key,
        timeout=httpx.Timeout(180.0, connect=30.0),
    )
    _client_cache[provider_name] = client
    return client


def _call_tier_once(tier_name, tier_cfg, full_messages, temperature, max_tokens,
                    response_format, extra_body, model_override_name=None):
    """단일 tier 1회 호출. 성공 시 응답 텍스트, 실패/빈 응답 시 None"""
    provider = tier_cfg['provider']
    model = model_override_name or tier_cfg['model']
    prov_cfg = CHAIN_CONFIG['providers'][provider]
    client = get_provider_client(provider, prov_cfg['base_url'], prov_cfg['api_key_env'])
    if client is None:
        print(f'  [안내] {provider} API 키 없음 ({prov_cfg["api_key_env"]})')
        return None

    kwargs = {}
    # response_format / caller extra_body는 유료 deepseek에만 (무료 모델 호환성 불확실)
    if response_format is not None and provider == 'deepseek':
        kwargs['response_format'] = response_format
    if tier_cfg.get('reasoning_effort'):
        kwargs['reasoning_effort'] = tier_cfg['reasoning_effort']
    tier_extra = {}
    if tier_cfg.get('extra_body'):
        tier_extra.update(tier_cfg['extra_body'])
    if extra_body and provider == 'deepseek':
        tier_extra.update(extra_body)
    if tier_extra:
        kwargs['extra_body'] = tier_extra

    print(f'  [모델] {provider} {model}')
    resp = client.chat.completions.create(
        model=model,
        messages=full_messages,
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs,
    )
    choice = resp.choices[0] if resp.choices else None
    if not choice:
        print(f'  [경고] {tier_name} choices 배열 비어있음')
        _log_to_file(f'⚠️ {tier_name} choices=[] (빈 배열)')
        return None
    text = choice.message.content
    finish_reason = choice.finish_reason
    refusal = getattr(choice.message, 'refusal', None)
    _log_to_file(f'{tier_name} finish_reason={finish_reason} content_len={len(text) if text else 0} refusal={str(refusal)[:100] if refusal else "none"}')
    if not text or not text.strip():
        if finish_reason == 'content_filter':
            print(f'  [경고] {tier_name} 콘텐츠 필터 차단 (refusal={refusal})')
            _log_to_file(f'⚠️ content_filter 차단: {refusal[:200] if refusal else "없음"}')
        elif finish_reason == 'length':
            print(f'  [경고] {tier_name} 토큰 제한 도달 (max_tokens={max_tokens})')
            _log_to_file(f'⚠️ max_tokens={max_tokens} 초과')
        else:
            print(f'  [경고] {tier_name} 빈 응답 (finish_reason={finish_reason})')
            _log_to_file(f'⚠️ 빈 응답 finish_reason={finish_reason}')
        return None
    return text.strip()


def _call_tier_with_retry(tier_name, tier_cfg, full_messages, temperature, max_tokens,
                          response_format, extra_body, model_override_name=None):
    """tier당 재시도 포함 호출. 성공 시 (text, True), 실패 시 (None, False)"""
    last_err = None
    for attempt in range(CHAIN_MAX_RETRIES + 1):
        try:
            text = _call_tier_once(tier_name, tier_cfg, full_messages, temperature,
                                   max_tokens, response_format, extra_body, model_override_name)
            if text:
                return text, True
            # 빈 응답/truncation은 재시도 없이 다음 tier (기존 동작과 동일)
            return None, False
        except Exception as e:
            status = getattr(e, 'status_code', 'unknown') if hasattr(e, 'status_code') else 'unknown'
            last_err = e
            print(f'  [경고] {tier_name} 실패: HTTP {status} {type(e).__name__}: {e}')
            _log_to_file(f'⚠️ {tier_name} 예외: HTTP {status} {type(e).__name__}: {str(e)[:200]}')
            if attempt < CHAIN_MAX_RETRIES:
                delay = CHAIN_BACKOFF[attempt]
                print(f'  [재시도] {tier_name} {delay}초 후 재시도 ({attempt+1}/{CHAIN_MAX_RETRIES})')
                time.sleep(delay)
    print(f'  ❌ {tier_name} 재시도 모두 실패: {last_err}')
    return None, False


def _chain_completion(full_messages, temperature, max_tokens, response_format, extra_body, deepseek_model=None):
    """무료 체인 순차 시도 → 전부 실패 시 유료 DeepSeek (최후 수단).
    성공 시 (text, tier_name), 실패 시 (None, None)"""
    tier_order = CHAIN_CONFIG['tier_order']
    models_cfg = CHAIN_CONFIG['models']
    free_tiers = [t for t in tier_order if t != 'default']

    now = time.time()
    if _chain_state['open_until'] > now:
        print(f'  [서킷브레이커] 개방 중 (무료 스킵 → 유료 직행)')
        text, ok = _call_tier_with_retry('default', models_cfg['default'], full_messages,
                                         temperature, max_tokens, response_format, extra_body,
                                         model_override_name=deepseek_model)
        return (text, 'default') if ok else (None, None)

    fallback_count = 0
    for tier in free_tiers:
        tier_cfg = models_cfg.get(tier)
        if not tier_cfg:
            continue
        text, ok = _call_tier_with_retry(tier, tier_cfg, full_messages, temperature,
                                         max_tokens, response_format, extra_body)
        if ok:
            _chain_state['failures'] = 0
            print(f'  [체인] 성공: {tier} (fallback {fallback_count}회)')
            return text, tier
        fallback_count += 1

    # 무료 전체 실패 → 서킷브레이커 갱신
    _chain_state['failures'] += 1
    if _chain_state['failures'] >= CIRCUIT_BREAKER_THRESHOLD:
        _chain_state['open_until'] = time.time() + CIRCUIT_BREAKER_RESET_SEC
        _chain_state['failures'] = 0
        print(f'  [서킷브레이커] {CIRCUIT_BREAKER_THRESHOLD}회 연속 실패 → {CIRCUIT_BREAKER_RESET_SEC}초 개방')

    # 최후 수단: 유료 DeepSeek
    print('  [체인] 무료 16개 모두 실패 → 유료 DeepSeek (최후 수단)')
    text, ok = _call_tier_with_retry('default', models_cfg['default'], full_messages,
                                     temperature, max_tokens, response_format, extra_body,
                                     model_override_name=deepseek_model)
    if ok:
        print(f'  [체인] 성공: default (유료)')
        return text, 'default'
    return None, None


# =====================================================================
# 통합 채팅 completions
# =====================================================================
def chat_completion(messages, system_prompt=None, temperature=0.7, max_tokens=2000, model_override=None, deepseek_model=None, response_format=None, extra_body=None):
    """
    통합 채팅 completions 함수
    - model_override=None 또는 'deepseek': 무료 LLM 폴백 체인 (config/models.yaml)
      → 무료 16개 순차 → 전부 실패 시 유료 DeepSeek V4 Flash (최후 수단)
    - model_override='openai': GPT-4o-mini 단독 (평가/후처리)
    - model_override='mimo': MiMo v2.5 단독
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
        else:
            print(f'  [오류] MIMO_API_KEY 없음')
        return None

    # 2순위: 무료 LLM 폴백 체인 → 유료 DeepSeek
    if model_override in ("deepseek", None):
        if CHAIN_CONFIG:
            text, tier = _chain_completion(full_messages, temperature, max_tokens,
                                           response_format, extra_body, deepseek_model)
            return text
        # config 없으면 레거시 deepseek 단독 동작
        ds_client = get_deepseek_client()
        if ds_client:
            active_model = deepseek_model or DEEPSEEK_MODEL
            max_ds_retries = 2
            for ds_attempt in range(max_ds_retries + 1):
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
                        elif not text and finish_reason == 'length':
                            print(f'  [경고] DeepSeek 토큰 제한 도달 (max_tokens={max_tokens})')
                        else:
                            print(f'  [경고] DeepSeek 빈 응답 (finish_reason={finish_reason})')
                    else:
                        print(f'  [경고] DeepSeek choices 배열 비어있음')
                except Exception as e:
                    status = getattr(e, 'status_code', 'unknown') if hasattr(e, 'status_code') else 'unknown'
                    print(f'  [경고] DeepSeek 실패: HTTP {status} {type(e).__name__}: {e}')
                    _log_to_file(f'⚠️ 예외: HTTP {status} {type(e).__name__}: {str(e)[:200]}')
                    if ds_attempt < max_ds_retries:
                        delay = 10 * (ds_attempt + 1)
                        print(f'  [재시도] DeepSeek {delay}초 후 재시도 ({ds_attempt+1}/{max_ds_retries})')
                        time.sleep(delay)
                        continue
                break
        print(f'  [안내] DEEPSEEK_API_TOKEN 없음')
        return None

    # 3순위: GPT-4o-mini (명시적 요청 시)
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
        else:
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
