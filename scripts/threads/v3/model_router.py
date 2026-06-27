"""
model_router.py - AI 모델 호출 라우터
- 1순위: NVIDIA Gemma 3n (build.nvidia.com)
- 2순위: OpenRouter MiMo (fallback)
- .env에서 NVIDIA_API_KEY / OPENROUTER_API_KEY 자동 로드
"""
import os, sys
from openai import OpenAI

PROJECT_DIR = '/Users/twinssn/Projects/aikorea24'
sys.path.insert(0, os.path.join(PROJECT_DIR, 'scripts', 'threads'))
ENV_FILE = os.path.join(PROJECT_DIR, '.env')

def load_env():
    """.env에서 API 키 로드"""
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
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    if line.startswith('export '):
                        line = line[7:]
                    k, v = line.split('=', 1)
                    envs[k.strip()] = v.strip().strip('"').strip("'")
    # 환경 변수에도 설정
    for k, v in envs.items():
        os.environ[k] = v
    return envs

load_env()

# === NVIDIA Qwen3 Next 80B 설정 ===
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
# 기사 선택용 (pitcher)
NVIDIA_MODEL = "google/gemma-3n-e4b-it"
# 쓰레드 작성용 (writer)
WRITER_NVIDIA_MODEL = "deepseek-ai/deepseek-v4-flash"

# === Fallback: OpenRouter MiMo ===
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = "xiaomi/mimo-v2-flash:free"  # 무료 MiMo v2 Flash

def get_nvidia_client():
    api_key = os.environ.get('NVIDIA_API_KEY', '')
    if not api_key:
        return None
    return OpenAI(base_url=NVIDIA_BASE_URL, api_key=api_key)

def get_openai_client():
    api_key = os.environ.get('OPENAI_API_KEY', '')
    if not api_key:
        return None
    return OpenAI(api_key=api_key)

def get_openrouter_client():
    api_key = os.environ.get('OPENROUTER_API_KEY', '')
    if not api_key:
        return None
    return OpenAI(base_url=OPENROUTER_BASE_URL, api_key=api_key)

def chat_completion(messages, system_prompt=None, temperature=0.7, max_tokens=2000, model_override=None, nvidia_model=None):
    """
    통합 채팅 completions 함수
    - 1순위: NVIDIA 모델 (지정 가능, 기본=Gemma 3n)
    - 2순위: OpenRouter MiMo (fallback)
    
    nvidia_model: 사용할 NVIDIA 모델명 (기본=NVIDIA_MODEL)
    model_override='openai': NVIDIA 스킵
    Returns: 응답 텍스트 (string), 실패 시 None
    """
    # system_prompt 처리
    full_messages = []
    if system_prompt:
        full_messages.append({"role": "system", "content": system_prompt})
    full_messages.extend(messages)
    
    # 1순위: NVIDIA 모델
    if model_override != "openai":
        nv_client = get_nvidia_client()
        if nv_client:
            active_model = nvidia_model or NVIDIA_MODEL
            try:
                print(f'  [모델] NVIDIA {active_model}')
                resp = nv_client.chat.completions.create(
                    model=active_model,
                    messages=full_messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                text = resp.choices[0].message.content
                if text and text.strip():
                    return text.strip()
            except Exception as e:
                print(f'  [경고] NVIDIA 실패: {type(e).__name__}')
                print(f'  [폴백] → OpenAI')
        else:
            print(f'  [안내] NVIDIA_API_KEY 없음 → OpenAI 사용')
    
    # 2순위: OpenRouter MiMo (fallback)
    if model_override != "nvidia":
        or_client = get_openrouter_client()
        if or_client:
            try:
                print(f'  [모델] OpenRouter {OPENROUTER_MODEL}')
                resp = or_client.chat.completions.create(
                    model=OPENROUTER_MODEL,
                    messages=full_messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                text = resp.choices[0].message.content
                if text and text.strip():
                    return text.strip()
            except Exception as e:
                print(f'  [오류] OpenRouter 실패: {type(e).__name__}')
        else:
            print(f'  [오류] OPENROUTER_API_KEY 없음')
    
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
