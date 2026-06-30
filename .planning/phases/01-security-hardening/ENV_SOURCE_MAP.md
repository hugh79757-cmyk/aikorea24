# Env Source Map — aikorea24.kr

> 생성: 2026-06-30 (Phase 1, Plan 2 — Security Hardening)
> 목적: 프로젝트 내 모든 환경 변수 출처를 문서화하고, 통합 관리 체계를 확립합니다.

---

## Source Overview

| # | Source | Status | Contents | Consumer |
|---|--------|--------|----------|----------|
| 1 | `~/.env.common` | **Canonical** | 공유 비밀 — API 키, 클라우드 토큰, DB 자격증명, 경로 설정 | `env_loader.py` fallback (setdefault) |
| 2 | `.env` (project root) | **Active — project-specific** | 프로젝트 고유 설정, Threads 토큰, 네이버 광고 키, Brevo 키 | `env_loader.py` primary — common 값보다 우선 |
| 3 | `scripts/threads/threads-publisher.plist` | **CLEANED** | 경로 설정만 포함 — 모든 비밀 제거됨 | launchd |
| 4 | `api_test/.env.sh` | **DELETED** (D-06) | Shadow config — 본 `.env` 와 중복 | — (삭제 완료) |
| 5 | `.env.bak.telegram` | **Review — gitignored, not committed** | Telegram + Cloudflare 자격증명 백업 | 전체 키 인벤토리 검토 필요 |
| 6 | `scripts/deploy.sh` | **FIXED** (D-07) | 교차 프로젝트 참조 제거 — `$PROJECT_DIR/.env` 만 사용 | Cloudflare Pages 배포 |

---

## Complete Env Var Inventory

### `~/.env.common` (Fallback — 모든 프로젝트 공유)

| 변수명 | 설명 |
|--------|------|
| `OPENAI_API_KEY` | OpenAI API 키 (GPT-4o-mini / GPT-4o) |
| `OPENAI_MODEL` | OpenAI 모델명 (`gpt-4o-mini`) |
| `CLOVA_API_KEY` | 네이버 클로바 API 키 |
| `UPSTAGE_API_KEY` | Upstage API 키 |
| `TELEGRAM_BOT_TOKEN` | 텔레그램 봇 토큰 (알림 발송) |
| `TELEGRAM_CHAT_ID` | 텔레그램 수신 채팅 ID |
| `GOOGLE_APPLICATION_CREDENTIALS` | GCP 서비스 계정 JSON 경로 |
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare 계정 ID |
| `CLOUDFLARE_API_TOKEN` | Cloudflare API 토큰 |
| `BLOGDEX_API_URL` | Blogdex API URL |
| `COUPANG_ACCESS_KEY` | 쿠팡 파트너스 액세스 키 |
| `COUPANG_SECRET_KEY` | 쿠팡 파트너스 시크릿 키 |
| `COUPANG_PARTNER_ID` | 쿠팡 파트너스 ID |
| `DART_API_KEY` | 금융감독원 DART API 키 |
| `FINLIFE_API_KEY` | 핀라이프 API 키 |
| `R2_ACCOUNT_ID` | Cloudflare R2 계정 ID |
| `R2_ACCESS_KEY_ID` | Cloudflare R2 액세스 키 ID |
| `R2_SECRET_ACCESS_KEY` | Cloudflare R2 시크릿 액세스 키 |
| `R2_BUCKET_NAME` | R2 버킷 이름 |
| `R2_PUBLIC_URL` | R2 퍼블릭 URL |
| `R2_ENDPOINT` | R2 엔드포인트 |
| `D1_API_TOKEN` | D1(Cloudflare) API 토큰 |
| `NAVER_CLIENT_ID` | 네이버 API 클라이언트 ID |
| `NAVER_CLIENT_SECRET` | 네이버 API 클라이언트 시크릿 |
| `GITHUB_TOKEN` | GitHub Personal Access Token |
| `GITHUB_USER` | GitHub 사용자명 |
| `NVIDIA_API_KEY` | NVIDIA API 키 (NVAIE) |
| `NVIDIA_BASE_URL` | NVIDIA API 베이스 URL |
| `HF_TOKEN` | Hugging Face 토큰 |
| `MIMO_API_KEY` | MiMo API 키 |
| `MIMO_BASE_URL` | MiMo API 베이스 URL |
| `MIMO_MODEL` | MiMo 모델명 |
| `DEEPSEEK_API_TOKEN` | DeepSeek API 토큰 |
| `DEEPSEEK_BASE_URL` | DeepSeek API 베이스 URL |
| `OPENROUTER_API_KEY` | OpenRouter API 키 |
| `BREVO_API_KEY` | Brevo (Sendinblue) API 키 (이메일) |
| `ZHIPU_API_KEY` | Zhipu AI API 키 |
| `CLOUDFLARE_WORKERS_AI_API_TOKEN` | Cloudflare Workers AI 토큰 |
| `AI_BACKEND` | AI 백엔드 스위치 (`openai` / `local`) |
| `AI_LOCAL_URL` | 로컬 AI 서버 URL |
| `AI_LOCAL_MODEL` | 로컬 AI 모델명 |

### `.env` (Project Root — aikorea24 전용)

| 변수명 | 설명 | 참고 |
|--------|------|------|
| `NAVER_CLIENT_ID` | 네이버 API 클라이언트 ID | common 과 중복 (project 우선) |
| `NAVER_CLIENT_SECRET` | 네이버 API 시크릿 | common 과 중복 (project 우선) |
| `OPENAI_API_KEY` | OpenAI API 키 | common 과 중복 (project 우선) |
| `DATA_GO_KR_KEY` | 공공데이터포털 API 키 | aikorea24 전용 |
| `GOOGLE_CLIENT_ID` | Google OAuth 클라이언트 ID | aikorea24 전용 |
| `GOOGLE_CLIENT_SECRET` | Google OAuth 클라이언트 시크릿 | aikorea24 전용 |
| `BIZINFO_API_KEY` | 비즈인포 API 키 | aikorea24 전용 |
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare 계정 ID | common 과 중복 |
| `CLOUDFLARE_API_TOKEN` | Cloudflare API 토큰 | common 과 중복 |
| `CLOUDFLARE_ZONE_ID` | Cloudflare Zone ID | aikorea24 전용 |
| `NAVER_AD_CUSTOMER_ID` | 네이버 광고 고객 ID | aikorea24 전용 |
| `NAVER_AD_CLIENT_ID` | 네이버 광고 클라이언트 ID | aikorea24 전용 |
| `NAVER_AD_CLIENT_SECRET` | 네이버 광고 클라이언트 시크릿 | aikorea24 전용 |
| `BREVO_API_KEY` | Brevo API 키 (뉴스레터) | common 과 중복 |
| `BREVO_LIST_ID` | Brevo 구독자 리스트 ID | aikorea24 전용 |
| `SUBSCRIBER_EMAIL` | 구독자/관리자 이메일 | aikorea24 전용 |
| `THREADS_REDIRECT_URI` | Threads OAuth 리다이렉트 URI | aikorea24 전용 |
| `THREADS_ACCESS_TOKEN` | Threads API 액세스 토큰 | aikorea24 전용 |
| `THREADS_USER_ID` | Threads 사용자 ID | aikorea24 전용 |
| `DEEPSEEK_API_TOKEN` | DeepSeek API 토큰 | common 과 중복 |
| `DEEPSEEK_BASE_URL` | DeepSeek API 베이스 URL | common 과 중복 |
| `SESSION_SECRET` | 웹 세션 HMAC 시크릿 | aikorea24 전용 |

---

## Key Rotation Checklist

> Phase 1 Plan 2 완료 시점에서, 다음 키들은 `api_test/.env.sh` (삭제됨) 에 평문으로 존재했거나
> `.env` 파일에 기록되어 있습니다. Git history 에는 유출 이력이 없으나,
> Disk 에 노출된 파일을 통한 유출 가능성이 있으므로 정기적인 키 교체를 권장합니다.

### Rotate Immediately (in `api_test/.env.sh` — deleted, but existed on disk)

1. **NAVER_CLIENT_ID** / **NAVER_CLIENT_SECRET** — 네이버 API
2. **OPENAI_API_KEY** — OpenAI API (공통 키, `.env` 및 `~/.env.common` 모두 갱신)
3. **DATA_GO_KR_KEY** — 공공데이터포털
4. **GOOGLE_CLIENT_ID** / **GOOGLE_CLIENT_SECRET** — Google OAuth
5. **BIZINFO_API_KEY** — 비즈인포
6. **AUTH_SECRET** — 세션 시크릿 (legacy, `SESSION_SECRET` 으로 교체됨)

### Rotate Soon (in `.env` only — lower exposure risk)

7. **CLOUDFLARE_API_TOKEN** — Cloudflare API (다중 프로젝트 공유)
8. **DEEPSEEK_API_TOKEN** — DeepSeek API
9. **THREADS_ACCESS_TOKEN** — Threads API (정기 갱신 필요)
10. **BREVO_API_KEY** — Brevo 이메일 API

### How to Rotate

각 서비스의 API 대시보드에서 새 키를 발급받고, `~/.env.common` 과 `.env` 를 모두 업데이트하세요.
이전 키는 즉시 폐기(Revoke)해야 유출 위험이 완전히 제거됩니다.

- OpenAI: https://platform.openai.com/api-keys
- 네이버: https://developers.naver.com/apps
- Cloudflare: https://dash.cloudflare.com/profile/api-tokens
- Google Cloud: https://console.cloud.google.com/apis/credentials
- DeepSeek: https://platform.deepseek.com/api_keys
- Brevo: https://app.brevo.com/settings/keys/api
- Threads: 액세스 토큰은 `scripts/threads/token_refresh.py` 로 갱신

---

## Transformation Log

| Date | Change | Detail |
|------|--------|--------|
| 2026-06-30 | `scripts/threads/threads-publisher.plist` cleared | EnvironmentVariables block removed — 경로 설정만 남음 |
| 2026-06-30 | `api_test/.env.sh` deleted | Shadow config 제거 — D-06 |
| 2026-06-30 | `scripts/deploy.sh` fixed | `/Users/twinssn/Projects/5000/.env` → `$PROJECT_DIR/.env` — D-07 |
| 2026-06-30 | `pipeline/infra/env_loader.py` created | 통합 env 로더 — .env (priority) → ~/.env.common (fallback) |

---

## Notes

- `.env.bak.telegram` 은 git-ignored 상태로, 레거시 Telegram/Cloudflare 자격증명 백업입니다.
  Phase 2 에서 정식 삭제 또는 통합을 검토합니다.
- `scripts/threads/token_refresh.py` 는 자체 `load_env()` 함수로 `.env` 를 직접 읽습니다.
  Phase 2 에서 `EnvConfig` 로 교체 예정 (Strangler Fig).
