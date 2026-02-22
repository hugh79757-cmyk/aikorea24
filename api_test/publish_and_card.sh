#!/bin/bash
# 브리핑 발행 후 카드 생성 + 모바일 전송
cd /Users/twinssn/Projects/aikorea24
source api_test/.env.sh 2>/dev/null
source .venv/bin/activate

echo "=== $(date): 카드뉴스 생성 시작 ==="
python3 api_test/card_news_generator.py

# 생성된 카드를 pending으로 이동
CARD_DIR="api_test/card_output"
PENDING_DIR="api_test/card_pending"
TODAY=$(date +%Y%m%d)

for f in "$CARD_DIR"/card_*_${TODAY}_*.png; do
    [ -f "$f" ] && mv "$f" "$PENDING_DIR/"
done

echo "=== 모바일 전송 ==="
KDE_CLI="/Applications/KDE Connect.app/Contents/MacOS/kdeconnect-cli"
DEVICE_ID="95ba25f5ac1b44ab9453bf2d15773be1"

ls "$PENDING_DIR"/*.png >/dev/null 2>&1 || { echo "전송할 카드 없음"; exit 0; }

if ! "$KDE_CLI" -l 2>/dev/null | grep "$DEVICE_ID" | grep -q "reachable"; then
    echo "폰 연결 안됨 — 다음에 send_pending이 전송"
    exit 0
fi

for f in "$PENDING_DIR"/*.png; do
    "$KDE_CLI" --device "$DEVICE_ID" --share "$f"
    sleep 3
    if [ $? -eq 0 ]; then
        rm "$f"
        echo "전송 완료: $(basename $f)"
    fi
done
echo "=== 완료 ==="
