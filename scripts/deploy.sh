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

echo "=== [1/3] 빌드 ==="
npm run build

echo "=== [2/3] Cloudflare Pages 배포 ==="
# auth profile(hugh79757) 사용, CLOUDFLARE_API_TOKEN env var 우회 방지
WRANGLER="/opt/homebrew/bin/wrangler"
if [ ! -x "$WRANGLER" ]; then
  WRANGLER=$(command -v wrangler 2>/dev/null || echo "npx wrangler")
fi
env -u CLOUDFLARE_API_TOKEN $WRANGLER pages deploy dist \
  --project-name aikorea24 \
  --branch main \
  --commit-dirty=true

echo ""
echo "배포 완료: https://aikorea24.kr"
