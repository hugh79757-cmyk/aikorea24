#!/bin/bash
KDE_CLI="/Applications/KDE Connect.app/Contents/MacOS/kdeconnect-cli"
DEVICE_ID="95ba25f5ac1b44ab9453bf2d15773be1"
PENDING_DIR="/Users/twinssn/Projects/aikorea24/api_test/card_pending"
LOG="/tmp/card_to_phone.log"

ls "$PENDING_DIR"/*.png >/dev/null 2>&1 || exit 0

if ! "$KDE_CLI" -l 2>/dev/null | grep "$DEVICE_ID" | grep -q "reachable"; then
    exit 0
fi

for f in "$PENDING_DIR"/*.png; do
    "$KDE_CLI" --device "$DEVICE_ID" --share "$f" >> "$LOG" 2>&1
    if [ $? -eq 0 ]; then
        rm "$f"
        echo "$(date): pending 전송 성공: $(basename $f)" >> "$LOG"
    fi
done
