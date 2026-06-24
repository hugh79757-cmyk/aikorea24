#!/bin/bash
echo "=========================================="
echo "  🔍 Spotlight 인덱싱 현황 전체 파악"
echo "=========================================="
echo ""

echo "📂 [현재 Spotlight 제외 목록]"
sudo mdutil -s / 2>/dev/null | sed 's/^/  /'
echo ""

echo "💿 [마운트된 볼륨별 인덱싱 상태]"
sudo mdutil -as 2>/dev/null | sed 's/^/  /'
echo ""

echo "📁 [홈 디렉토리 주요 폴더 크기 TOP 20]"
du -sh ~/*(N) 2>/dev/null | sort -rh | head -20 | sed 's/^/  /'
echo ""

echo "📁 [현재 인덱싱 중인 경로 확인]"
sudo fs_usage -f filesys mdworker_shared 2>/dev/null &
FS_PID=$!
sleep 3
kill $FS_PID 2>/dev/null
echo ""

echo "🗂️  [개발/빌드 관련 폴더 탐색]"
echo "  --- Node modules ---"
find ~ -name "node_modules" -maxdepth 5 -type d 2>/dev/null | sed 's/^/  /'
echo ""
echo "  --- .git 폴더 ---"
find ~ -name ".git" -maxdepth 5 -type d 2>/dev/null | sed 's/^/  /'
echo ""
echo "  --- Hugo public 폴더 ---"
find ~ -name "public" -maxdepth 6 -type d 2>/dev/null | xargs -I{} sh -c 'test -f "{}/index.html" && echo "  {}"'
echo ""
echo "  --- Python venv 폴더 ---"
find ~ -name ".venv" -o -name "venv" -maxdepth 5 -type d 2>/dev/null | sed 's/^/  /'
echo ""
echo "  --- build / dist 폴더 ---"
find ~ \( -name "build" -o -name "dist" \) -maxdepth 5 -type d 2>/dev/null | sed 's/^/  /'
echo ""
echo "  --- .cache 폴더 ---"
find ~ -name ".cache" -maxdepth 4 -type d 2>/dev/null | sed 's/^/  /'
echo ""
echo "  --- Homebrew 캐시 ---"
du -sh ~/Library/Caches/Homebrew 2>/dev/null | sed 's/^/  /'
echo ""

echo "=========================================="
echo "✅ 파악 완료"
echo "=========================================="
