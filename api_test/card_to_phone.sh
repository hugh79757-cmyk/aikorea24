#!/bin/bash
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
cd /Users/twinssn/Projects/aikorea24
source api_test/venv/bin/activate

KDE_CLI="/Applications/KDE Connect.app/Contents/MacOS/kdeconnect-cli"
DEVICE_ID="95ba25f5ac1b44ab9453bf2d15773be1"
OUTPUT_DIR="api_test/card_output"
PENDING_DIR="api_test/card_pending"
LOG="/tmp/card_to_phone.log"

mkdir -p "$PENDING_DIR"
echo "$(date): 카드뉴스 생성 시작" >> "$LOG"

touch /tmp/.card_last_run
python3 api_test/card_news_generator.py carousel_cover >> "$LOG" 2>&1

NEW_FILES=$(find "$OUTPUT_DIR" -name "*.png" -newer /tmp/.card_last_run)
if [ -z "$NEW_FILES" ]; then
    echo "$(date): 새 카드뉴스 없음" >> "$LOG"
    exit 0
fi

if "$KDE_CLI" -l 2>/dev/null | grep "$DEVICE_ID" | grep -q "reachable"; then
    for f in $NEW_FILES; do
        echo "$(date): 전송: $(basename $f)" >> "$LOG"
        "$KDE_CLI" --device "$DEVICE_ID" --share "$f" >> "$LOG" 2>&1
    done
else
    echo "$(date): KDE 미연결, pending 저장" >> "$LOG"
    for f in $NEW_FILES; do
        cp "$f" "$PENDING_DIR/"
    done
fi
echo "$(date): 완료" >> "$LOG"
