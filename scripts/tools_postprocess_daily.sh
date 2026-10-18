#!/bin/bash
# 도구 상세페이지 후처리 일일 따라잡기 — launchd kr.aikorea24.tools-postprocess (매일 07:30)
#
# 역할: 신규 수집 파이프라인(tools_collector, 06:00)이 놓친 항목을 따라잡는다.
#   ① 실제 URL 승격  ② 심화 스키마 v2  ③ 썸네일  — 미완료 항목만 대상(멱등)
#   실패 항목은 7일 쿨다운으로 매일 재시도하지 않는다(tools_postprocess.COOLDOWN_DAYS).
#
# 왜 별도 잡인가:
#   - 수집 잡은 "새 도구"만 처리한다. 실패·누락분은 아무도 다시 보지 않으면 영구 미완료로 남는다.
#   - 수집 잡의 런타임을 늘리지 않기 위해 따라잡기는 분리했다(수집은 06:00, 따라잡기는 07:30).
#
# 배포 규칙: public/images/ 는 .gitignore 대상이라 이미지는 커밋되지 않고 배포 시 로컬 파일이
#   업로드된다. 따라서 md 가 바뀌면(또는 이미지가 새로 생기면) 배포까지 해야 사이트에 반영된다.
#   D1 tools 테이블은 다음 06:00 수집 잡의 sync_tools_to_d1() 이 밀린 만큼 따라잡는다.
set -u

PROJECT_DIR="/Users/twinssn/Projects/aikorea24"
PY="$PROJECT_DIR/.venv/bin/python3"
SWEEP="${SWEEP:-15}"      # 한 번에 따라잡을 최대 건수
BUDGET="${BUDGET:-900}"   # 후처리 시간 예산(초) — 무한 실행 금지
cd "$PROJECT_DIR" || exit 1

echo "=== $(date '+%F %T') 도구 후처리 시작 (sweep=$SWEEP, budget=${BUDGET}s) ==="

"$PY" scripts/tools_postprocess.py --sweep "$SWEEP" --budget "$BUDGET"
rc=$?

# ── 변경분만 커밋·배포 (다른 작업의 미커밋 변경을 휩쓸지 않도록 경로를 한정한다) ──
git add -A -- src/content/tools || true
[ -f scripts/logs/tools_postprocess.jsonl ] && git add -- scripts/logs/tools_postprocess.jsonl

if git diff --cached --quiet; then
  echo "  변경 없음 — 커밋·배포 생략"
else
  n=$(git diff --cached --numstat -- src/content/tools | wc -l | tr -d ' ')
  git commit -q -m "content(tools): 자동 후처리 — URL 승격·심화·썸네일 갱신 (${n}건)"
  echo "  커밋 완료 (${n}건)"
  if bash scripts/deploy.sh >/dev/null 2>&1; then
    echo "  배포 완료 ✅"
  else
    echo "  ⚠️ 배포 실패 — 다음 실행에서 재시도(커밋은 유지)"
  fi
fi

echo "=== $(date '+%F %T') 종료 (후처리 rc=$rc) ==="
