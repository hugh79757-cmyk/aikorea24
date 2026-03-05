#!/bin/bash
# 카드뉴스 전송 전용 (생성 없이 전송만)
cd /Users/twinssn/Projects/aikorea24
source api_test/.env.sh 2>/dev/null

CARD_DIR="api_test/card_output"
PENDING_DIR="api_test/card_pending"
TODAY=$(date +%Y%m%d)
LOG="/tmp/card_to_phone.log"

echo "=== $(date): 카드 전송 시작 ===" >> "$LOG"

# card_output에 남아있으면 pending으로 이동
for f in "$CARD_DIR"/card_*_${TODAY}_*.png; do
    [ -f "$f" ] && mv "$f" "$PENDING_DIR/"
done

KDE_CLI="/Applications/KDE Connect.app/Contents/MacOS/kdeconnect-cli"
DEVICE_ID="95ba25f5ac1b44ab9453bf2d15773be1"

ls "$PENDING_DIR"/*.png >/dev/null 2>&1 || { echo "전송할 카드 없음" >> "$LOG"; exit 0; }

if ! "$KDE_CLI" -l 2>/dev/null | grep "$DEVICE_ID" | grep -q "reachable"; then
    echo "폰 연결 안됨" >> "$LOG"
    exit 1
fi

for f in "$PENDING_DIR"/*.png; do
    echo "전송: $(basename $f)" >> "$LOG"
    "$KDE_CLI" --device "$DEVICE_ID" --share "$f"
    sleep 5
    if [ $? -eq 0 ]; then
        rm "$f"
        echo "전송 완료: $(basename $f)" >> "$LOG"
    else
        echo "전송 실패: $(basename $f)" >> "$LOG"
    fi
done
echo "=== 전송 완료 ===" >> "$LOG"
