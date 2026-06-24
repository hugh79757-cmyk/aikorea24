#!/bin/bash
echo "=========================================="
echo "  🔍 Spotlight 인덱싱 현황 전체 파악"
echo "=========================================="
echo ""

echo "📁 [홈 디렉토리 주요 폴더 크기 TOP 20]"
du -sh "$HOME"//* 2>/dev/null | sort -rh | head -20 | sed 's/^/  /'
echo ""

echo "🗂️  [개발/빌드 관련 폴더 탐색]"

echo "  --- Hugo public 폴더 ---"
find "$HOME" -name "public" -maxdepth 6 -type d 2>/dev/null | while read d; do
  test -f "$d/index.html" && echo "  $d"
done
echo ""

echo "  --- node_modules 폴더 ---"
find "$HOME" -name "node_modules" -maxdepth 6 -type d 2>/dev/null | sed 's/^/  /'
echo ""

echo "  --- .git 폴더 ---"
find "$HOME" -name ".git" -maxdepth 6 -type d 2>/dev/null | sed 's/^/  /'
echo ""

echo "  --- Python venv 폴더 ---"
find "$HOME" \( -name ".venv" -o -name "venv" \) -maxdepth 6 -type d 2>/dev/null | sed 's/^/  /'
echo ""

echo "  --- build / dist / out 폴더 ---"
find "$HOME" \( -name "build" -o -name "dist" -o -name "out" \) -maxdepth 6 -type d 2>/dev/null | sed 's/^/  /'
echo ""

echo "  --- .cache 폴더 ---"
find "$HOME" -name ".cache" -maxdepth 5 -type d 2>/dev/null | sed 's/^/  /'
echo ""

echo "  --- Homebrew 캐시 ---"
du -sh "$HOME/Library/Caches/Homebrew" 2>/dev/null | sed 's/^/  /'
echo ""

echo "  --- npm / yarn / pip 캐시 ---"
du -sh "$HOME/Library/Caches/pip" 2>/dev/null | sed 's/^/  /'
du -sh "$HOME/Library/Caches/node" 2>/dev/null | sed 's/^/  /'
du -sh "$HOME/.npm" 2>/dev/null | sed 's/^/  /'
du -sh "$HOME/.yarn" 2>/dev/null | sed 's/^/  /'
echo ""

echo "  --- VSCode 확장/캐시 ---"
du -sh "$HOME/.vscode" 2>/dev/null | sed 's/^/  /'
du -sh "$HOME/Library/Application Support/Code" 2>/dev/null | sed 's/^/  /'
echo ""

echo "  --- 로그 폴더 ---"
du -sh "$HOME/Library/Logs" 2>/dev/null | sed 's/^/  /'
du -sh "/var/log" 2>/dev/null | sed 's/^/  /'
echo ""

echo "  --- Trash ---"
du -sh "$HOME/.Trash" 2>/dev/null | sed 's/^/  /'
echo ""

echo "=========================================="
echo "✅ 파악 완료 - 결과 붙여넣어 주세요!"
echo "=========================================="
