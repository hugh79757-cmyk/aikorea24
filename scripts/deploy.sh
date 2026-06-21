#!/bin/bash
set -e

# ============================
# nvm/node PATH fallback (launchd 환경 대응)
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

# .env 로드
if [ -f /Users/twinssn/Projects/5000/.env ]; then
  export $(grep -E '^(CLOUDFLARE_API_TOKEN|CLOUDFLARE_ACCOUNT_ID)' /Users/twinssn/Projects/5000/.env | xargs)
else
  echo "[ERROR] .env 파일 없음: /Users/twinssn/Projects/5000/.env"
  exit 1
fi

echo "=== [1/2] 빌드 ==="
npm run build

echo "=== [2/2] Cloudflare Pages 배포 ==="
npx wrangler pages deploy dist \
  --project-name aikorea24 \
  --branch main \
  --commit-dirty=true

echo ""
echo "배포 완료: https://aikorea24.kr"
