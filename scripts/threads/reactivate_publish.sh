#!/bin/bash
# aikorea24 Threads 발행 재개 스크립트 (2026-10-09 중단 후 작성)
#
# 사용법:  bash scripts/threads/reactivate_publish.sh
#
# 무엇을 하냐:
#   1. 프로젝트 .env 에 신규 Cloudflare 계정 토큰이 있는지 확인 (없으면 중단)
#   2. Threads 토큰 유효성 사전 검증 (만료면 여기서 실패)
#   3. main_v3.py --dry-run 으로 후보 조회 1회 (D1 계정 연결 확인)
#   4. publisher + token-refresh job 재적용
#
# 전제: plist 에 하드코딩된 CLOUDFLARE_API_TOKEN 은 2026-10-09 에 제거했다.
#       프로세스 환경은 프로젝트 .env 로만 구성된다.
set -euo pipefail

PROJ=/Users/twinssn/projects/aikorea24
PLIST_DIR="$HOME/Library/LaunchAgents"
VENV="$PROJ/.venv/bin/python3"
rc=0

echo "== 1/4 프로젝트 .env 확인"
for k in THREADS_ACCESS_TOKEN THREADS_USER_ID THREADS_APP_SECRET CLOUDFLARE_API_TOKEN CLOUDFLARE_ACCOUNT_ID; do
  if grep -q "^$k=" "$PROJ/.env"; then
    echo "  OK   $k"
  else
    echo "  FAIL $k 없음"; rc=1
  fi
done
[ "$rc" -eq 0 ] || { echo "중단: .env 에 필요한 키가 없다"; exit 1; }

echo "== 2/4 Threads 토큰 유효성 검증"
cd "$PROJ"
tok_rc=0
"$VENV" - <<'PYEOF' || tok_rc=$?
import sys
sys.path.insert(0, 'scripts/threads')
from token_refresh import load_secrets, validate_token, TOKEN_VALID
s = load_secrets()
state, _ = validate_token(s['token'], s['user_id'])
print('  token state:', state)
sys.exit(0 if state == TOKEN_VALID else 1)
PYEOF
if [ "$tok_rc" -ne 0 ]; then
  echo "중단: Threads 토큰 무효. 재발급 후 다시 실행."
  echo "  python3 scripts/threads/token_refresh.py daily"
  exit 1
fi

echo "== 3/4 D1 연결 확인 (read-only)"
d1_rc=0
"$VENV" - <<'PYEOF' || d1_rc=$?
import sys, os, subprocess
sys.path.insert(0, '.')
from pipeline.infra.env_loader import EnvConfig
EnvConfig().load_to_environ()
r = subprocess.run(['/opt/homebrew/bin/wrangler', 'd1', 'execute', 'aikorea24-db', '--remote',
                    '--command', 'SELECT COUNT(*) AS c FROM news'],
                   capture_output=True, text=True, env=dict(os.environ), timeout=180)
print('  account:', os.environ.get('CLOUDFLARE_ACCOUNT_ID'))
sys.exit(0 if r.returncode == 0 else 1)
PYEOF
if [ "$d1_rc" -ne 0 ]; then
  echo "중단: D1 조회 실패"; exit 1
fi

echo "== 4/4 launchd 재적용"
launchctl bootstrap gui/$(id -u) "$PLIST_DIR/kr.aikorea24.threads-publisher.plist"    && echo "  OK   threads-publisher"
launchctl bootstrap gui/$(id -u) "$PLIST_DIR/kr.aikorea24.threads-token-refresh.plist" && echo "  OK   threads-token-refresh"

echo
echo "재개 완료. threads-compass(09:30/15:30/21:30 D1 쓰기)는 계속 비활성 상태."
echo "필요하면: launchctl bootstrap gui/\$(id -u) $PLIST_DIR/kr.aikorea24.threads-compass.plist"
