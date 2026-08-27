""""
model_router.py - AI 모델 호출 라우터 (무료 LLM 폴백 체인 통합)
- 무료 체인: config/models.yaml의 tier_order 16개 무료 모델 순차 시도
- 최후 수단: 유료 DeepSeek V4 Flash (default tier)
- 평가/후처리: 무료 LLM 폴백 체인 (model_override=None) — GPT-4o-mini 2026-08-12 제거
- .env / ~/.env.common에서 각 프로바이더 API 키 자동 로드
"""
import os, sys, time, json, tempfile
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

# 폴백 체인 타이밍 상수 (llm-fallback-chain-management 계약)
TIER_TIMEOUT_SEC = 90.0      # 단일 tier 호출 타임아웃 (기존 180s → 90s 단축)
CONNECT_TIMEOUT_SEC = 10.0   # 연결 타임아웃
GLOBAL_BUDGET_SEC = 300.0    # 요청 1회당 전체 wall-clock 예산 (초과 시 체인 중단)
QUOTA_COOLDOWN_SEC = 300     # 429/quota → 해당 tier만 5분 쿨다운
STRUCTURAL_COOLDOWN_SEC = 86400  # 401/403/404 → 해당 tier만 24h 구조 쿨다운
# 상태 영속 경로: 환경변수로 오버라이드 가능, 기본은 /tmp 등가 경로
STATE_PATH = os.environ.get(
    'LLM_FALLBACK_STATE_PATH',
    os.path.join(tempfile.gettempdir(), 'aikorea24_llm_fallback_state.json'),
)


def get_deepseek_client():
    api_key = os.environ.get('DEEPSEEK_API_TOKEN', '')
    if not api_key:
        return None
    return OpenAI(
        base_url=DEEPSEEK_BASE_URL,
        api_key=api_key,
        timeout=httpx.Timeout(TIER_TIMEOUT_SEC, connect=CONNECT_TIMEOUT_SEC),
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

# =====================================================================
# 영속 폴백 상태 관리 (서킷브레이커 제거 → per-tier 격리 쿨다운)
# - last_success_tier 승격, quota_until/structural_until 는 tier별 격리
# - 파일에 원자적(temp + os.replace) 저장 → fresh-process-per-run 에서도 회전 유지
# =====================================================================
class _FallbackState:
    """per-tier 쿨다운 + last_success_tier 를 env-설정 경로에 영속."""

    def __init__(self, path=STATE_PATH):
        self.path = path
        self._state = self._load()

    def _load(self):
        try:
            if os.path.exists(self.path):
                with open(self.path, 'r', encoding='utf-8') as f:
                    d = json.load(f)
                d.setdefault('last_success_tier', None)
                d.setdefault('quota_until', {})
                d.setdefault('structural_until', {})
                # 기동 시 만료된 쿨다운 정리
                now = time.time()
                d['quota_until'] = {k: v for k, v in d['quota_until'].items() if now < v}
                d['structural_until'] = {k: v for k, v in d['structural_until'].items() if now < v}
                return d
        except Exception:
            pass
        return {'last_success_tier': None, 'quota_until': {}, 'structural_until': {}}

    def _save(self):
        try:
            d = os.path.dirname(self.path)
            if d:
                os.makedirs(d, exist_ok=True)
            tmp = self.path + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(self._state, f, ensure_ascii=False)
            os.replace(tmp, self.path)  # 원자적 교체
        except Exception:
            pass  # 상태 저장 실패가 본 호출을 막지 않음

    def _clear_expired(self):
        now = time.time()
        q = self._state.setdefault('quota_until', {})
        s = self._state.setdefault('structural_until', {})
        for k in [k for k, v in q.items() if now >= v]:
            del q[k]
        for k in [k for k, v in s.items() if now >= v]:
            del s[k]

    def is_quota(self, tier):
        return time.time() < self._state.get('quota_until', {}).get(tier, 0)

    def is_structural(self, tier):
        return time.time() < self._state.get('structural_until', {}).get(tier, 0)

    def record_success(self, tier, paid=False):
        """성공 기록. 유료 tier는 맨 뒤 고정이므로 승격 안 함."""
        self._clear_expired()
        if not paid:
            self._state['last_success_tier'] = tier
        self._state.setdefault('quota_until', {}).pop(tier, None)
        self._save()

    def record_quota(self, tier):
        self._state.setdefault('quota_until', {})[tier] = time.time() + QUOTA_COOLDOWN_SEC
        self._save()

    def record_structural(self, tier):
        self._state.setdefault('structural_until', {})[tier] = time.time() + STRUCTURAL_COOLDOWN_SEC
        self._save()

    def order(self, free_tiers, paid_tier='default'):
        """동적 호출 순서:
        1) 쿼터/구조 쿨다운 아닌 무료 tier (last_success 1순위)
        2) 전부 쿨다운 중 → 가장 빨리 만료되는 무료 1회
        3) 유료 tier 항상 맨 뒤 고정
        """
        self._clear_expired()
        usable = [t for t in free_tiers
                  if not self.is_structural(t) and not self.is_quota(t)]
        cooling = [t for t in free_tiers
                   if self.is_quota(t) and not self.is_structural(t)]
        cooling.sort(key=lambda t: self._state.get('quota_until', {}).get(t, 0))
        last_ok = self._state.get('last_success_tier')
        ordered = []
        if last_ok in usable:
            ordered.append(last_ok)
        ordered += [t for t in usable if t != last_ok]
        if not ordered and cooling:
            ordered.append(cooling[0])  # 전부 쿨다운 → 가장 빨리 만료되는 1회
        ordered.append(paid_tier)
        return ordered


_FALLBACK_STATE = _FallbackState()

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
        timeout=httpx.Timeout(TIER_TIMEOUT_SEC, connect=CONNECT_TIMEOUT_SEC),
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


def _classify_error(e):
    """예외 → 'timeout'|'connection'|'quota'(429)|'structural'(401/403/404)|'server'(5xx)|'unknown'"""
    status = getattr(e, 'status_code', None)
    if status is not None:
        if status == 429:
            return 'quota'
        if status in (401, 403, 404):
            return 'structural'
        if 500 <= status < 600:
            return 'server'
        return 'unknown'
    cls = type(e).__name__
    if 'Timeout' in cls or isinstance(e, httpx.TimeoutException):
        return 'timeout'
    if 'Connection' in cls or isinstance(e, (httpx.ConnectError, httpx.ConnectTimeout, httpx.RequestError)):
        return 'connection'
    if isinstance(e, (httpx.RemoteProtocolError, httpx.ProtocolError)):
        return 'server'  # connection reset → 1회 재시도 대상
    return 'unknown'


def _call_tier_with_retry(tier_name, tier_cfg, full_messages, temperature, max_tokens,
                           response_format, extra_body, model_override_name=None, state=None):
    """tier 1회 호출 + 최소 재시도. 성공 시 (text, True), 실패 시 (None, False).

    재시도/쿨다운 정책 (llm-fallback-chain-management 계약):
    - 빈 응답        → 재시도 0, 즉시 다음 tier (쿨다운 없음)
    - timeout/connection → 재시도 0, 즉시 다음 tier
    - 429(quota)     → 재시도 0, 해당 tier만 300s 쿨다운
    - 401/403/404    → 재시도 0, 해당 tier만 86400s 구조 쿨다운
    - 5xx/connection reset → 1회 재시도(유계 백오프) 후 실패
    """
    for attempt in range(2):  # 1차 시도 + server 에러 한정 1회 재시도
        try:
            text = _call_tier_once(tier_name, tier_cfg, full_messages, temperature,
                                   max_tokens, response_format, extra_body, model_override_name)
            if text:
                return text, True
            # 빈 응답 → 재시도 없이 즉시 다음 tier
            return None, False
        except Exception as e:
            status = getattr(e, 'status_code', 'unknown')
            print(f'  [경고] {tier_name} 실패: HTTP {status} {type(e).__name__}: {e}')
            _log_to_file(f'⚠️ {tier_name} 예외: HTTP {status} {type(e).__name__}: {str(e)[:200]}')
            kind = _classify_error(e)
            if kind == 'quota':
                if state:
                    state.record_quota(tier_name)
                return None, False
            if kind == 'structural':
                if state:
                    state.record_structural(tier_name)
                return None, False
            if kind in ('timeout', 'connection', 'unknown'):
                return None, False  # 즉시 다음 tier, 재시도 0
            if kind == 'server':
                if attempt == 0:
                    delay = 5  # 유계 백오프 (단 1회)
                    print(f'  [재시도] {tier_name} {delay}초 후 1회 재시도 (5xx/connection reset)')
                    time.sleep(delay)
                    continue
                return None, False
    return None, False


def _chain_completion(full_messages, temperature, max_tokens, response_format, extra_body, deepseek_model=None):
    """무료 체인 순차 시도 → 전부 실패 시 유료 DeepSeek (최후 수단).
    성공 시 (text, tier_name), 실패 시 (None, None)"""
    tier_order = CHAIN_CONFIG['tier_order']
    models_cfg = CHAIN_CONFIG['models']
    free_tiers = [t for t in tier_order if t != 'default']
    state = _FALLBACK_STATE

    # 동적 순서: last_success 승격 + per-tier 쿨다운 무시 + 유료 맨 뒤 고정
    ordered = state.order(free_tiers, paid_tier='default')

    start = time.time()
    for tier in ordered:
        # 전체 wall-clock 예산 초과 시 체인 중단 (무한 대기 방지)
        if time.time() - start > GLOBAL_BUDGET_SEC:
            _log_to_file(f'⚠️ global budget {GLOBAL_BUDGET_SEC}s 초과 → 체인 중단')
            print(f'  [체인] global budget 초과 → 중단')
            break
        tier_cfg = models_cfg.get(tier)
        if not tier_cfg:
            continue
        paid = (tier == 'default')
        text, ok = _call_tier_with_retry(tier, tier_cfg, full_messages, temperature,
                                         max_tokens, response_format, extra_body,
                                         model_override_name=deepseek_model, state=state)
        if ok:
            state.record_success(tier, paid=paid)
            print(f'  [체인] 성공: {tier}' + (' (유료)' if paid else ''))
            return text, tier
        # 실패 시 쿨다운은 _call_tier_with_retry 내부에서 기록됨 (quota/structural)
        continue

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

    # GPT-4o-mini는 2026-08-12부로 쓰레드 파이프라인에서 완전 제거됨
    # 이유: 구형 모델, RHYTHM 지침 준수율 낮음, 무료 체인으로 충분
    # 어떤 용도로도 model_override='openai' 호출 금지
    if model_override == "openai":
        print('  [차단] GPT-4o-mini는 쓰레드 파이프라인에서 제거됨 (model_override="openai" 사용 금지)')
        return None

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
