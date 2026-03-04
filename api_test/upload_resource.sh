#!/bin/bash
# CSV 파일을 R2에 업로드하고 DB에 리소스로 등록
# 사용법: bash api_test/upload_resource.sh /path/to/file.csv "리소스 제목" "설명" "event-code"

cd /Users/twinssn/Projects/aikorea24

FILE="$1"
TITLE="$2"
DESC="${3:-}"
EVENT="${4:-feb2026-feedback}"

if [ -z "$FILE" ] || [ -z "$TITLE" ]; then
    echo "사용법: bash api_test/upload_resource.sh <CSV파일> <제목> [설명] [이벤트코드]"
    exit 1
fi

if [ ! -f "$FILE" ]; then
    echo "파일 없음: $FILE"
    exit 1
fi

FILENAME=$(basename "$FILE")
R2_KEY="events/${EVENT}/${FILENAME}"

echo "=== R2 업로드 ==="
echo "파일: $FILE"
echo "R2 키: $R2_KEY"
npx wrangler r2 object put "aikorea24-files/${R2_KEY}" --file="$FILE" --remote

if [ $? -ne 0 ]; then
    echo "R2 업로드 실패"
    exit 1
fi

echo ""
echo "=== DB 리소스 등록 ==="
npx wrangler d1 execute aikorea24-db --remote \
  --command "INSERT INTO resources (title, description, filename, r2_key, event_code) VALUES ('${TITLE}', '${DESC}', '${FILENAME}', '${R2_KEY}', '${EVENT}');"

echo ""
echo "=== 등록 확인 ==="
npx wrangler d1 execute aikorea24-db --remote \
  --command "SELECT id, title, filename, r2_key FROM resources ORDER BY id DESC LIMIT 3;"

echo ""
echo "완료! /admin/event/ 에서 권한을 부여하세요."
