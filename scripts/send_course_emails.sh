#!/bin/bash
set -e

# ============================
# Course Email Sender — launchd wrapper
# 매시간 send-daily API 호출
# ============================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# .env 로드
if [ -f "$PROJECT_DIR/.env" ]; then
  set -a
  source "$PROJECT_DIR/.env"
  set +a
fi

if [ -f ~/.env.common ]; then
  set -a
  source ~/.env.common
  set +a
fi

CRON_SECRET="${CRON_SECRET:-}"
SITE_URL="${SITE_URL:-https://aikorea24.kr}"

if [ -z "$CRON_SECRET" ]; then
  echo "[ERROR] CRON_SECRET not set" >&2
  exit 1
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting course email send..."
RESPONSE=$(curl -s -o - -w "\n%{http_code}" \
  -H "Authorization: Bearer $CRON_SECRET" \
  "${SITE_URL}/api/courses/send-daily")

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
  echo "[OK] Response: $BODY"
else
  echo "[ERROR] HTTP $HTTP_CODE: $BODY" >&2
  exit 1
fi
