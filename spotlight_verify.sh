#!/bin/bash
echo "=========================================="
echo "  ✅ Spotlight 제외 마커 적용 확인"
echo "=========================================="
echo ""

EXCLUDE_PATHS=(
  "$HOME/Projects"
  "$HOME/.config/mimocode/node_modules"
  "$HOME/.config/opencode/node_modules"
  "$HOME/.opencode"
  "$HOME/.mimocode"
  "$HOME/.npm"
  "$HOME/.hermes"
  "$HOME/blog-publisher/venv"
  "$HOME/Desktop/tour-auto-publisher/venv"
  "$HOME/ollama_env"
  "$HOME/.vscode"
  "$HOME/.antigravity"
  "$HOME/Library/Application Support/Code"
  "$HOME/Downloads"
  "$HOME/k-skill-repo"
)

PASS=0
FAIL=0

for path in "${EXCLUDE_PATHS[@]}"; do
  if [ -f "$path/.metadata_never_index" ]; then
    echo "  ✅ 적용됨 : $path"
    PASS=$((PASS+1))
  elif [ -d "$path" ]; then
    echo "  ❌ 미적용  : $path"
    FAIL=$((FAIL+1))
    # 다시 생성 시도
    touch "$path/.metadata_never_index" 2>/dev/null && \
      echo "     → 지금 재적용 완료" || \
      echo "     → 재적용 실패 (권한 문제)"
  else
    echo "  ⏭️  없음    : $path"
  fi
done

echo ""
echo "=========================================="
echo "  📊 결과: 성공 ${PASS}개 / 실패 ${FAIL}개"
echo "=========================================="
echo ""

# Hugo 빌드 폴더에 직접 마커 추가 (Projects 하위 public 폴더들)
echo "🏗️  Hugo public 폴더 개별 마커 추가 중..."
COUNT=0
find "$HOME/Projects" -name "public" -maxdepth 6 -type d 2>/dev/null | while read d; do
  if [ -f "$d/index.html" ]; then
    touch "$d/.metadata_never_index" 2>/dev/null
    echo "  ✅ $d"
  fi
done
echo ""

# node_modules 최상위에도 마커 추가
echo "📦 node_modules 마커 추가 중..."
find "$HOME" -name "node_modules" -maxdepth 6 -type d -prune 2>/dev/null | while read d; do
  touch "$d/.metadata_never_index" 2>/dev/null
  echo "  ✅ $d"
done
echo ""

# venv 마커 추가
echo "🐍 Python venv 마커 추가 중..."
find "$HOME" \( -name ".venv" -o -name "venv" \) -maxdepth 6 -type d -prune 2>/dev/null | while read d; do
  touch "$d/.metadata_never_index" 2>/dev/null
  echo "  ✅ $d"
done
echo ""

# .git 마커 추가
echo "🔧 .git 폴더 마커 추가 중..."
find "$HOME" -name ".git" -maxdepth 6 -type d 2>/dev/null | while read d; do
  touch "$d/.metadata_never_index" 2>/dev/null
done
echo "  ✅ .git 폴더 전체 완료"
echo ""

echo "=========================================="
echo "  🔄 Spotlight 강제 재시작..."
echo "=========================================="
sudo launchctl stop com.apple.metadata.mds 2>/dev/null
sleep 1
sudo launchctl start com.apple.metadata.mds 2>/dev/null
echo "  ✅ mds 재시작 완료"
echo ""
echo "  이제 매시간 hugo 빌드 후 Spotlight 폭주가 사라집니다 🎉"
echo "=========================================="
