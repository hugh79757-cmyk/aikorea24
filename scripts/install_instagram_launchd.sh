#!/bin/bash
set -e

# ============================
# Instagram launchd 스케줄러 설치
# 캐러셀: 매일 08:00 KST / 릴스: 매일 19:00 KST
# ============================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

TEMPLATE="$SCRIPT_DIR/instagram-publisher.plist.template"
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"

if [ ! -f "$TEMPLATE" ]; then
  echo "[ERROR] 템플릿 파일 없음: $TEMPLATE"
  exit 1
fi

mkdir -p "$LAUNCH_AGENTS"

# ============================
# Python string.Template 으로 plist 생성
# ============================
python3 -c "
from string import Template

with open('$TEMPLATE', 'r') as f:
    tpl = Template(f.read())

configs = [
    {
        'label': 'kr.aikorea24.instagram-carousel',
        'step_name': 'instagram_carousel',
        'hour': 8,
        'minute': 0,
        'log_dir': '$PROJECT_DIR/scripts/instagram/logs',
    },
    {
        'label': 'kr.aikorea24.instagram-reel',
        'step_name': 'instagram_reel',
        'hour': 19,
        'minute': 0,
        'log_dir': '$PROJECT_DIR/scripts/instagram/logs',
    },
]

for cfg in configs:
    import os
    os.makedirs(cfg['log_dir'], exist_ok=True)

    result = tpl.safe_substitute(
        VENV_PYTHON='$PROJECT_DIR/.venv/bin/python3',
        PROJECT_DIR='$PROJECT_DIR',
        LABEL=cfg['label'],
        STEP_NAME=cfg['step_name'],
        HOUR=cfg['hour'],
        MINUTE=cfg['minute'],
        LOG_DIR=cfg['log_dir'],
    )

    dest = '$LAUNCH_AGENTS/' + cfg['label'] + '.plist'
    with open(dest, 'w') as f:
        f.write(result)
    print(f'plist 생성 완료: {dest}')
"

# ============================
# 기존 agent 언로드 (실행 무시)
# ============================
launchctl unload "$LAUNCH_AGENTS/kr.aikorea24.instagram-carousel.plist" 2>/dev/null || true
launchctl unload "$LAUNCH_AGENTS/kr.aikorea24.instagram-reel.plist" 2>/dev/null || true

# ============================
# 새 agent 로드
# ============================
launchctl load "$LAUNCH_AGENTS/kr.aikorea24.instagram-carousel.plist"
launchctl load "$LAUNCH_AGENTS/kr.aikorea24.instagram-reel.plist"
echo "Launchd agents loaded:"
echo "  - kr.aikorea24.instagram-carousel (매일 08:00 KST)"
echo "  - kr.aikorea24.instagram-reel (매일 19:00 KST)"
