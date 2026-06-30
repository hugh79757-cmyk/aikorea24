#!/bin/bash
set -e

# ============================
# 경로 계산 — 이 스크립트의 위치 기준
# ============================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# ============================
# 템플릿 파일 경로
# ============================
TEMPLATE="$SCRIPT_DIR/threads/threads-publisher.plist.template"
PLIST_DEST="$HOME/Library/LaunchAgents/kr.aikorea24.threads-publisher.plist"
PLIST_NAME="kr.aikorea24.threads-publisher"

# ============================
# 템플릿 존재 확인
# ============================
if [ ! -f "$TEMPLATE" ]; then
  echo "[ERROR] 템플릿 파일 없음: $TEMPLATE"
  exit 1
fi

# ============================
# Python string.Template 으로 plist 생성
# ============================
python3 -c "
from string import Template
import sys

with open('$TEMPLATE', 'r') as f:
    template_content = f.read()

result = Template(template_content).safe_substitute(
    VENV_PYTHON='$PROJECT_DIR/.venv/bin/python3',
    PROJECT_DIR='$PROJECT_DIR',
    SCRIPT_PATH='$PROJECT_DIR/scripts/threads/main_v3.py',
    LOG_DIR='$PROJECT_DIR/scripts/threads/logs',
)

with open('$PLIST_DEST', 'w') as f:
    f.write(result)

print('plist 생성 완료: $PLIST_DEST')
"

# ============================
# 기존 launchd agent 언로드 (실패 무시)
# ============================
launchctl unload "$PLIST_DEST" 2>/dev/null || true

# ============================
# 새 launchd agent 로드
# ============================
launchctl load "$PLIST_DEST"
echo "Launchd agent loaded: $PLIST_NAME"
