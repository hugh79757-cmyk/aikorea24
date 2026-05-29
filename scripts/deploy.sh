#!/bin/bash
set -e

# .env 로드
if [ -f /Users/twinssn/Projects/5000/.env ]; then
  export $(grep -E '^(CLOUDFLARE_API_TOKEN|CLOUDFLARE_ACCOUNT_ID)' /Users/twinssn/Projects/5000/.env | xargs)
else
  echo "[ERROR] .env 파일 없음: /Users/twinssn/Projects/5000/.env"
  exit 1
fi

echo "=== [1/3] 빌드 ==="
npm run build

echo "=== [2/3] git push ==="
git add -A
git diff --cached --quiet || git commit -m "content: update $(date '+%Y-%m-%d')"
git push origin main

echo "=== [3/3] Cloudflare Pages 배포 ==="
npx wrangler pages deploy dist \
  --project-name aikorea24 \
  --branch main \
  --commit-dirty=true

echo ""
echo "배포 완료: https://aikorea24.kr"
