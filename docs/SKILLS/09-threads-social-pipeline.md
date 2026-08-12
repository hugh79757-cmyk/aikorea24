# Threads/X 소셜 파이프라인 스킬

> 콘텐츠 소스 → AI 프롬프트 처리 → Threads/X API 발행 → 발행 후 검증/모니터링/스케줄링까지 엔드투엔드 소셜 미디어 자동화 파이프라인

---

## 1. 개요

Threads와 X(트위터)에 AI 생성 콘텐츠를 자동 발행하는 파이프라인.

**주요 디렉토리:** `scripts/threads/`

**서브모듈:**
| 모듈 | 역할 |
|------|------|
| `threads/v3/main_v3.py` | 메인 오케스트레이터 |
| `threads/v3/narrative_pitcher.py` | 콘텐츠 아이디어 피치 생성 |
| `threads/v3/writer_v3.py` | 피치 → 실제 콘텐츠 작성 |
| `threads/v3/pitch_evaluator.py` | 피치 품질 평가 |
| `threads/v3/model_router.py` | LLM 모델 라우팅 (폴백 체인) |
| `threads/v3/auto_poster/` | 발행 자동화 (HTML→PNG, TTS, 스케줄러, Instagram) |
| `threads/db_reader.py` | D1 DB 읽기 유틸리티 |
| `threads/dedup.py` | 중복 콘텐츠 제거 |
| `threads/publisher.py` | API 발행 |
| `threads/token_refresh.py` | 토큰 갱신 |

---

## 2. 사전 준비

### 2.1 환경변수

```bash
# MIMO/DeepSeek API
MIMO_API_KEY=xxx
DEEPSEEK_API_TOKEN=sk-xxx

# Threads API (Meta)
THREADS_ACCESS_TOKEN=THAAxxx
THREADS_USER_ID=xxx
THREADS_REDIRECT_URI=https://localhost/callback

# X (Twitter) API
# (필요한 경우)

# Cloudflare
CLOUDFLARE_ACCOUNT_ID=xxx

# Telegram 알림
TELEGRAM_BOT_TOKEN=xxx
TELEGRAM_CHAT_ID=xxx
```

### 2.2 Python 의존성

```bash
pip install requests beautifulsoup4 openai
```

---

## 3. 콘텐츠 생성 흐름

### 3.1 피치 생성 (narrative_pitcher.py)

콘텐츠 아이디어를 generating. 소스(뉴스/트렌드)에서 주제 선정 → 피치 문서로 변환.

### 3.2 피치 평가 (pitch_evaluator.py)

생성된 피치의 품질을 평가. 기준 미달 시 재생성 또는 폐기.

### 3.3 콘텐츠 작성 (writer_v3.py)

평가 통과 피치를 실제 Threads/X 콘텐츠로 작성. 플랫폼별 구조 적용:
- **Threads**: 4단 구조 (훅 → 본문 → 인사이트 → CTA)
- **X**: 7~8 트윗 구조 (훅 15자 이내, 트윗당 4줄 제한)

### 3.4 중복 검사 (dedup.py)

D1 DB에 저장된 기존 콘텐츠와 비교해 중복 발행 방지.

---

## 4. 발행 흐름

### 4.1 auto_poster 모듈

`threads/v3/auto_poster/`:

| 파일 | 역할 |
|------|------|
| `main.py` | 발행 오케스트레이터 |
| `orchestrator.py` | 전체 흐름 조율 |
| `html_to_png.py` | HTML 콘텐츠 → PNG 이미지 생성 |
| `video_builder.py` | 비디오 콘텐츠 생성 |
| `tts_generator.py` | 텍스트 → 음성 합성 |
| `scheduler.py` | 발행 스케줄링 |
| `instagram_publish.py` | Instagram 교차 발행 |

### 4.2 Threads API 발행 (publisher.py)

Meta Threads API를 사용해 게시물 생성.

```python
# Threads API 발행 예시
import requests

def publish_to_threads(access_token, user_id, text, media_urls=None):
    url = "https://graph.facebook.com/v18.0/{user_id}/threads"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {"text": text}
    if media_urls:
        payload["media"] = media_urls
    resp = requests.post(url, headers=headers, json=payload)
    return resp.json()
```

---

## 5. 모델 라우팅 (model_router.py)

LLM 폴백 체인 관리. MIMO → DeepSeek 등 여러 모델 간 전환.

```python
# 모델 라우팅 예시
from model_router import chat_completion

response = chat_completion(
    messages=[{"role": "user", "content": "..."}],
    preferred_models=["mimo-v2.5", "deepseek-v4-pro"]
)
```

---

## 6. 파일 구조

```
scripts/
└── threads/
    ├── main_v3.py                      # 메인 오케스트레이터
    ├── db_reader.py                    # D1 DB 읽기
    ├── dedup.py                        # 중복 제거
    ├── publisher.py                    # API 발행
    ├── token_refresh.py                # 토큰 갱신
    ├── failed_articles.py              # 실패 기사 관리
    ├── migrate_to_vectorize.py        # Vectorize 마이그레이션
    └── v3/
        ├── model_router.py             # LLM 모델 라우팅
        ├── narrative_pitcher.py       # 콘텐츠 피치 생성
        ├── writer_v3.py                # 콘텐츠 작성
        ├── pitch_evaluator.py          # 피치 평가
        └── auto_poster/
            ├── main.py                 # 발행 오케스트레이터
            ├── orchestrator.py         # 흐름 조율
            ├── html_to_png.py          # HTML→PNG
            ├── video_builder.py        # 비디오 생성
            ├── tts_generator.py        # TTS
            ├── scheduler.py            # 스케줄링
            └── instagram_publish.py    # Instagram 발행
```

---

## 7. 체크리스트

### 최초 설정
- [ ] Threads API 접근 토큰 발급 (Meta Developers)
- [ ] `THREADS_ACCESS_TOKEN`, `THREADS_USER_ID` 설정
- [ ] `python3 scripts/threads/main_v3.py` 테스트 실행
- [ ] 테스트 게시물 발행 확인

### 정기 실행
- [ ] launchd 스케줄 등록 확인
- [ ] 매일 실행 로그 확인
- [ ] 발행 실패 시 재시도/대체 처리 확인
- [ ] 중복 발행 방지 확인

---

## 8. 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| API 인증 오류 | 토큰 만료 | token_refresh.py로 갱신 |
| 발행 실패 | API rate limit | 재시도 + 대기 |
| 중복 발행 | dedup 실패 | db_reader/is_already_posted 확인 |
| 모델 응답 없음 | API 키/네트워크 | model_router 폴백 체인 확인 |

---

*문서 버전: 1.0 | 생성일: 2026-08-07*
