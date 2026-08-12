# Cloudflare Pages 배포 스킬

> Astro 빌드 → Cloudflare Pages 배포. wrangler auth profile 처리, CLOUDFLARE_API_TOKEN 충돌 방지, 3회 재시도 포함.

---

## 1. 개요

Astro 프로젝트를 빌드하고 Cloudflare Pages에 배포하는 파이프라인. agent 세션에서 자동으로 설정되는 `CLOUDFLARE_API_TOKEN` 환경변수를 해제하고 OAuth auth profile을 사용해 인증 충돌을 방지.

**주요 스크립트:** `scripts/deploy.sh`

**배포 대상:** Cloudflare Pages (`aikorea24` 프로젝트, `main` 브랜치)

---

## 2. 사전 준비

### 2.1 wrangler 인증 설정

```bash
# wrangler whoami로 활성 profile 확인
wrangler whoami

# auth profile 설정 (처음 한 번만)
wrangler login
```

**Auth Profile 상태 (2026-07 기준):**

| Profile | 계정 | Bind Directory |
|---------|------|---------------|
| `hugh79757` (default) | hugh79757@gmail.com | aikorea24 등 |
| `farmsolution` | farmsolution 계정 | farmsolution |

### 2.2 wrangler 버전

```bash
wrangler --version
# 4.110.0 이상 권장 (auth profiles 지원)
```

### 2.3 환경 변수 충돌 주의

OpenCode/Codex agent 세션은 자동으로 `CLOUDFLARE_API_TOKEN`을 설정할 수 있으며, 이것이 wrangler OAuth auth보다 우선되어 배포가 실패합니다.

```
# BAD - CLOUDFLARE_API_TOKEN이 설정되어 있으면 인증 실패
wrangler pages deploy dist --project-name aikorea24

# GOOD - env var 해제 후 auth profile 사용
env -u CLOUDFLARE_API_TOKEN wrangler pages deploy dist --project-name aikorea24
```

### 2.4 Hugo 테마 디렉토리 (Hugo 블로그인 경우)

```bash
HUGO_THEMESDIR=/Users/twinssn/Projects/shared-themes hugo --gc --minify
```

---

## 3. 실행 방법

### 3.1 deploy.sh 실행 (권장)

```bash
cd /Users/twinssn/Projects/aikorea24
bash scripts/deploy.sh
```

**내부 동작:**
1. 블로그 포스트 검증 (`validate_blog_posts.py`)
2. Astro 빌드 (`npm run build`)
3. Cloudflare Pages 배포 (`wrangler pages deploy`)
   - `CLOUDFLARE_API_TOKEN` 해제
   - 3회 재시도 (일시적 오류 대응)
   - `--commit-dirty=true` (변경된 파일 포함)

### 3.2 수동 배포

```bash
cd /Users/twinssn/Projects/aikorea24

# 1. 빌드
npm run build

# 2. 배포
env -u CLOUDFLARE_API_TOKEN /opt/homebrew/bin/wrangler pages deploy dist \
  --project-name aikorea24 \
  --branch main \
  --commit-dirty=true
```

### 3.3 wrangler 설정 확인

`wrangler.toml`:
```toml
name = "aikorea24"
compatibility_date = "2024-12-01"
pages_build_output_dir = "./dist"

[[d1_databases]]
binding = "DB"
database_name = "aikorea24-db"
database_id = "bec650ce-f732-46bc-87c0-bd76ed17e42a"

[[r2_buckets]]
binding = "R2"
bucket_name = "aikorea24-files"
```

---

## 4. deploy.sh 상세

```bash
#!/bin/bash
set -e

# === nvm/node PATH fallback ===
# launchd 환경에서 PATH 누락 시 nvm/Homebrew로 node 찾기

# === .env 로드 ===
source "$PROJECT_DIR/.env" 2>/dev/null

# === Python 바이너리 결정 ===
PYTHON_BIN=$(command -v python3 || echo "$PROJECT_DIR/.venv/bin/python3")

# === [0/3] 블로그 포스트 검증 ===
"$PYTHON_BIN" "$PROJECT_DIR/scripts/validate_blog_posts.py" || exit 1

# === [1/3] 빌드 ===
npm run build

# === [2/3] Cloudflare Pages 배포 ===
WRANGLER="/opt/homebrew/bin/wrangler"
if [ ! -x "$WRANGLER" ]; then
  WRANGLER=$(command -v wrangler 2>/dev/null || echo "npx wrangler")
fi

# 3회 재시도
deploy_ok=0
for attempt in 1 2 3; do
  echo "  배포 시도 $attempt/3..."
  if env -u CLOUDFLARE_API_TOKEN $WRANGLER pages deploy dist \
    --project-name aikorea24 \
    --branch main \
    --commit-dirty=true; then
    deploy_ok=1
    break
  fi
  echo "  ⚠️ 배포 실패 (시도 $attempt/3), 5초 후 재시도..."
  sleep 5
done

if [ "$deploy_ok" -ne 1 ]; then
  echo "[ERROR] Cloudflare Pages 배포 실패 (3회 모두 실패)"
  exit 1
fi

echo "배포 완료: https://aikorea24.kr"
```

---

## 5. API 토큰 vs Auth Profile

| 방식 | 설정 | 장점 | 단점 |
|------|------|------|------|
| **API Token** | `CLOUDFLARE_API_TOKEN` env var | 자동화 쉬움 | agent 세션에서 충돌 |
| **Auth Profile** | `wrangler login` | 대화형 세션에서 안정적 | launchd/non-interactive에서 문제 가능 |

**현재 권장:** agent 세션에서는 `env -u CLOUDFLARE_API_TOKEN` + auth profile 사용.

---

## 6. 파일 구조

```
scripts/
└── deploy.sh                    # 배포 스크립트

wrangler.toml                    # wrangler 설정
```

---

## 7. 체크리스트

### 최초 설정
- [ ] `wrangler whoami`로 auth profile 확인
- [ ] `bash scripts/deploy.sh` 실행
- [ ] https://aikorea24.kr 에서 변경 사항 확인

### daily 배포
- [ ] `run_pipeline.py` 완료 후 deploy.sh 자동 실행 확인
- [ ] 배포 로그에서 에러 여부 확인
- [ ] 라이브 사이트 반영 확인

---

## 8. 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| `Authentication error code: 10000` | CLOUDFLARE_API_TOKEN env var 충돌 | `env -u CLOUDFLARE_API_TOKEN` 추가 |
| "no wrangler found" | wrangler 설치/경로 | `/opt/homebrew/bin/wrangler` 또는 `npx wrangler` |
| 빌드 실패 | Astro 오류 | `npm run build` 단독 실행해 오류 확인 |
| 배포 후 변경 안 보임 | 캐시/프라우닝 | `--commit-dirty=true` 확인, 하드 리프레시 |
| D1/R2 바인딩 오류 | wrangler.toml 설정 | database_id/bucket_name 확인 |

---

*문서 버전: 1.0 | 생성일: 2026-08-07*
