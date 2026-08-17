#!/bin/bash
set -e

# ============================
# 경로 계산 — 이 스크립트의 위치 기준
# ============================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# ============================
# 멱등 설치 헬퍼
# ============================
install_plist() {
  local TEMPLATE="$1"
  local PLIST_DEST="$2"
  local SCRIPT_PATH="$3"
  local PLIST_NAME="$4"

  if [ ! -f "$TEMPLATE" ]; then
    echo "[ERROR] 템플릿 파일 없음: $TEMPLATE"
    exit 1
  fi

  # Python string.Template 으로 plist 생성
  python3 -c "
from string import Template
import sys

with open('$TEMPLATE', 'r') as f:
    template_content = f.read()

result = Template(template_content).safe_substitute(
    VENV_PYTHON='$PROJECT_DIR/.venv/bin/python3',
    PROJECT_DIR='$PROJECT_DIR',
    SCRIPT_PATH='$SCRIPT_PATH',
    LOG_DIR='$PROJECT_DIR/scripts/threads/logs',
)

with open('$PLIST_DEST', 'w') as f:
    f.write(result)

print('plist 생성 완료: $PLIST_DEST')
"

  # 기존 launchd agent 언로드 (실패 무시 — 멱등)
  launchctl unload "$PLIST_DEST" 2>/dev/null || true

  # 새 launchd agent 로드
  launchctl load "$PLIST_DEST"
  echo "Launchd agent loaded: $PLIST_NAME"
}

# ============================
# 1) Threads 발행기
# ============================
install_plist \
  "$SCRIPT_DIR/threads/threads-publisher.plist.template" \
  "$HOME/Library/LaunchAgents/kr.aikorea24.threads-publisher.plist" \
  "$PROJECT_DIR/scripts/threads/main_v3.py" \
  "kr.aikorea24.threads-publisher"

# ============================
# 2) Threads 토큰 갱신기 (1일 1회, 발행 전 선행)
# ============================
install_plist \
  "$SCRIPT_DIR/threads/threads-token-refresh.plist.template" \
  "$HOME/Library/LaunchAgents/kr.aikorea24.threads-token-refresh.plist" \
  "$PROJECT_DIR/scripts/threads/token_refresh.py" \
  "kr.aikorea24.threads-token-refresh"
