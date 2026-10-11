#!/bin/bash
set -e

# ============================
# nvm/node PATH fallback (launchd 환경에서 실행 시 PATH 누락 대응)
# ============================
if ! command -v npm &>/dev/null; then
  # nvm
  export NVM_DIR="$HOME/.nvm"
  if [ -s "$NVM_DIR/nvm.sh" ]; then
    source "$NVM_DIR/nvm.sh"
  fi
  # Homebrew fallback
  if ! command -v npm &>/dev/null && [ -x /opt/homebrew/bin/npm ]; then
    export PATH="/opt/homebrew/bin:$PATH"
  fi
  # 최종 실패
  if ! command -v npm &>/dev/null; then
    echo "[ERROR] npm을 찾을 수 없습니다. PATH=$PATH"
    echo "  nvm이나 homebrew로 node를 설치했는지 확인하세요."
    exit 1
  fi
fi

# .env 로드 — deploy.sh 자체는 PROJECT_DIR/.env 만 참조
# pipeline 스크립트(pipeline/infra/config.py)는 런타임에 ~/.env.common 도 fallback 으로 로드하지만
# deploy.sh 내에서는 api_test/.env.sh 등의 cross-project 참조가 없음 (POR-04)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
if [ -f "$PROJECT_DIR/.env" ]; then
  # .env 내부(또는 .env.common)의 오류가 set -e로 인해 배포를 멈추지 않도록 일시적으로 끔
  set +e
  source "$PROJECT_DIR/.env" 2>/dev/null
  set -e
else
  echo "[ERROR] .env 파일 없음: $PROJECT_DIR/.env"
  exit 1
fi

# Python 바이너리 결정 (launchd 환경에서 PATH 누락 대응)
PYTHON_BIN=$(command -v python3 || echo "$PROJECT_DIR/.venv/bin/python3")
if ! [ -x "$PYTHON_BIN" ]; then
  echo "[ERROR] 실행 가능한 python3를 찾을 수 없습니다."
  exit 1
fi

echo "=== [0/3] 블로그 포스트 검증 ==="
"$PYTHON_BIN" "$PROJECT_DIR/scripts/validate_blog_posts.py" || exit 1

echo "=== [0.5/3] 승인 툴 submission → md 동기화 (정적 tools 페이지용) ==="
# 실패 시 md 누락 → 배포된 사이트에서 승인건이 사라지므로 fail-loud
node "$PROJECT_DIR/scripts/sync_submissions_to_md.mjs" || exit 1

echo "=== [1/3] 빌드 ==="
# 빌드 모드가 바뀌면(Astro 7 Workers 산출 vs Astro 5 Pages 산출) 빌드가 남긴
# .wrangler/deploy/config.json이 옛 산출 경로를 가리킨 채 남을 수 있다.
# 빌드가 새로 덮어쓰므로 배포 전에 지우는 게 아니라 빌드 전에 지워야 안전하다.
rm -rf "$PROJECT_DIR/.wrangler/deploy"
npm run build

echo "=== [1.5/3] data-layer 청크 확인 ==="
# AIK24-MIGRATE-01로 Astro 7 + experimental.collectionStorage:'chunked'를 켰다.
# Astro 5에선 스토어가 dist/_worker.js/chunks/에 24MB 단일 파일로 생겨 Cloudflare
# 25MiB 한도(91.96%)를 넘겼고, 그랬다가 rm으로 지워 Worker가 스토어 없이 떴다.
# Astro 7은 스토어를 dist/server/chunks/에 여러 청크로 나눠 담는다(실측 최대 1.1MB).
# 청크는 Workers가 실행에 필요하므로 제거하지 않고, 청크 수만 확인해 0이면
# 스토어가 유실된 배포를 막는다.
chunks=$(find dist/server/chunks -name '_astro_data-layer-content-chunk_*' 2>/dev/null | wc -l | tr -d ' ')

echo "=== [1.6/3] 파일 크기 검증 (fail-safe) ==="
# AIK24-BUILD-DATALAYER-02: 조용한 오배포를 막기 위해 배포를 중단한다.
# 25MiB 한도 여유를 두어 20MB 초과 파일이 있으면 중단한다.
oversized=$(find dist -type f -size +20M 2>/dev/null)
if [ -n "$oversized" ]; then
  echo "[ERROR] 20MB 초과 파일 발견. 배포를 중단합니다:"
  echo "$oversized"
  exit 1
fi
if [ "$chunks" -eq 0 ]; then
  echo "[ERROR] data-layer 청크가 0개입니다. 스토어 유실 배포를 막기 위해 중단합니다."
  exit 1
fi
echo "  ✅ 20MB 초과 파일 없음, data-layer 청크 ${chunks}개"

echo "=== [2/3] Cloudflare Workers 배포 ==="
# AIK24-MIGRATE-01 Phase 2: Pages → Workers.
# 이 프로젝트는 신 계정(stylefactory9ai)에 배포한다. 셸에 구 계정(hugh79757) 토큰이
# 공존해 있어, .env 값이 덮여써지지 않았는지 배포 직전에 확인한다.
EXPECTED_ACCOUNT_ID="7eb1b8cd178de269758ec94b2e03330b"
if [ -z "$CLOUDFLARE_API_TOKEN" ]; then
  echo "[ERROR] CLOUDFLARE_API_TOKEN이 설정되지 않았습니다. .env를 확인하세요."
  exit 1
fi
if [ "$CLOUDFLARE_ACCOUNT_ID" != "$EXPECTED_ACCOUNT_ID" ]; then
  echo "[ERROR] CLOUDFLARE_ACCOUNT_ID가 신 계정($EXPECTED_ACCOUNT_ID)이 아닙니다."
  echo "        현재: ${CLOUDFLARE_ACCOUNT_ID:-미설정}"
  echo "        구 계정 토큰으로 배포하면 Authentication error 10000이 납니다."
  exit 1
fi
echo "  ✅ 계정 확인: $CLOUDFLARE_ACCOUNT_ID"
# 주의: .wrangler/deploy/config.json을 지우면 안 된다. Astro 7 빌드가 여기다
# dist/server/wrangler.json(Worker 엔트리포인트 경로)을 등록하고, wrangler는 그
# 파일로만 Workers 대상임을 안다. 지우면 루트 wrangler.jsonc(main 없음)를 보고
# 'assets-only Worker'로 오인해 3회 연속 실패한다.
# 옛 산출 경로가 섞인 채로 빌드 모드가 바뀌는 것만 막으려면 빌드 직전에 지운다.

WRANGLER="/opt/homebrew/bin/wrangler"
if [ ! -x "$WRANGLER" ]; then
  WRANGLER=$(command -v wrangler 2>/dev/null || echo "npx wrangler")
fi

# retry wrapper: 3회 재시도 (일시적 네트워크/Cloudflare 오류 대응)
deploy_ok=0
for attempt in 1 2 3; do
  echo "  배포 시도 $attempt/3..."
  if $WRANGLER deploy; then
    deploy_ok=1
    break
  fi
  echo "  ⚠️ 배포 실패 (시도 $attempt/3), 5초 후 재시도..."
  sleep 5
done
if [ "$deploy_ok" -ne 1 ]; then
  echo "[ERROR] Cloudflare Workers 배포 실패 (3회 모두 실패)"
  exit 1
fi

echo ""
echo "배포 완료: https://aikorea24.kr"

# --- 배포 후 sitemap ping (검색엔진 크롤 요청) ---
# ping 실패는 배포 실패로 간주하지 않음 (크롤 요청은 best-effort)
if [ -f "$PROJECT_DIR/scripts/sitemap_ping.py" ]; then
  echo ""
  echo "--- sitemap ping ---"
  python3 "$PROJECT_DIR/scripts/sitemap_ping.py" \
    --sitemap "https://aikorea24.kr/sitemap.xml" \
    || echo "  ⚠️ sitemap ping 실패 (배포는 성공)"
fi
