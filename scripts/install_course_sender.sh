#!/bin/bash
set -e

# ============================
# Course Email Sender — launchd 설치 스크립트
# ============================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

TEMPLATE="$SCRIPT_DIR/course-email-sender.plist.template"
PLIST_DEST="$HOME/Library/LaunchAgents/kr.aikorea24.course-email-sender.plist"
PLIST_NAME="kr.aikorea24.course-email-sender"
LOG_DIR="$PROJECT_DIR/scripts/course_sender_logs"

if [ ! -f "$TEMPLATE" ]; then
  echo "[ERROR] 템플릿 파일 없음: $TEMPLATE"
  exit 1
fi

# .env에서 CRON_SECRET 로드
if [ -f "$PROJECT_DIR/.env" ]; then
  export $(grep -v '^#' "$PROJECT_DIR/.env" | xargs 2>/dev/null || true)
fi

CRON_SECRET="${CRON_SECRET:-}"
SITE_URL="${SITE_URL:-https://aikorea24.kr}"

if [ -z "$CRON_SECRET" ]; then
  echo "[ERROR] CRON_SECRET이 .env에 설정되지 않았습니다."
  exit 1
fi

# 로그 디렉토리
mkdir -p "$LOG_DIR"

# Python string.Template으로 plist 생성
python3 -c "
from string import Template
import sys

with open('$TEMPLATE', 'r') as f:
    template_content = f.read()

result = Template(template_content).safe_substitute(
    SCRIPT_PATH='$PROJECT_DIR/scripts/send_course_emails.sh',
    PROJECT_DIR='$PROJECT_DIR',
    LOG_DIR='$LOG_DIR',
    CRON_SECRET='$CRON_SECRET',
    SITE_URL='$SITE_URL',
)

with open('$PLIST_DEST', 'w') as f:
    f.write(result)

print('plist 생성 완료: $PLIST_DEST')
"

# 기존 언로드
launchctl unload "$PLIST_DEST" 2>/dev/null || true

# 로드
launchctl load "$PLIST_DEST"
echo "Launchd agent loaded: $PLIST_NAME (interval: 3600s, 매시간 실행)"
