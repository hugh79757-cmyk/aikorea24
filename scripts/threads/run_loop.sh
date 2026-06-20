#!/bin/bash
# dry-run 반복 루프 — 결과가 나올 때까지
VENV="/Users/twinssn/Projects/aikorea24/.venv/bin/python3"
SCRIPT="/Users/twinssn/Projects/aikorea24/scripts/threads/main_v3.py"
LOG_DIR="/Users/twinssn/Projects/aikorea24/scripts/threads/logs/drafts"

attempt=0
while true; do
  attempt=$((attempt + 1))
  echo ""
  echo "=========================================="
  echo "  Attempt #$attempt at $(date '+%H:%M:%S')"
  echo "=========================================="
  
  output=$($VENV "$SCRIPT" --dry-run 2>&1)
  
  # Check if a thread was successfully generated (look for the separator line in output)
  if echo "$output" | grep -q "^===="; then
    echo "$output"
    echo ""
    echo "✅ 성공! 평가해주세요."
    # Save to file
    echo "$output" > "$LOG_DIR/loop_attempt_${attempt}_$(date '+%H%M%S').txt"
    echo "저장됨: loop_attempt_${attempt}.txt"
    break
  else
    echo "$output" | tail -5
    echo "❌ 실패 — 재시도..."
  fi
  
  sleep 1
done
