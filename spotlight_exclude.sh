#!/bin/bash
echo "=========================================="
echo "  🚫 Spotlight 인덱싱 제외 설정 시작"
echo "=========================================="

# 제외할 경로 목록
EXCLUDE_PATHS=(
  # Hugo public 폴더 (빌드 결과물 - 인덱싱 완전 불필요)
  "$HOME/Projects"

  # node_modules (수백만 개 JS 파일 - 절대 불필요)
  "$HOME/.config/mimocode/node_modules"
  "$HOME/.config/opencode/node_modules"
  "$HOME/.opencode"
  "$HOME/.mimocode"
  "$HOME/.npm"
  "$HOME/.hermes"

  # Python venv (바이너리/라이브러리 - 불필요)
  "$HOME/blog-publisher/venv"
  "$HOME/Desktop/tour-auto-publisher/venv"
  "$HOME/ollama_env"

  # VSCode 확장 (컴파일된 JS - 불필요)
  "$HOME/.vscode"
  "$HOME/.antigravity"

  # 개발 도구 설정
  "$HOME/Library/Application Support/Code"

  # 기타
  "$HOME/Downloads"
  "$HOME/k-skill-repo"
)

echo ""
echo "📋 다음 경로들을 Spotlight에서 제외합니다:"
echo ""

for path in "${EXCLUDE_PATHS[@]}"; do
  if [ -d "$path" ]; then
    # .metadata_never_index 파일 생성 (Spotlight 제외 마커)
    touch "$path/.metadata_never_index"

    # mdutil로 직접 제외 (시스템 설정에 등록)
    sudo mdutil -i off "$path" 2>/dev/null

    echo "  ✅ 제외됨: $path"
  else
    echo "  ⏭️  없음 (스킵): $path"
  fi
done

echo ""
echo "=========================================="
echo "  🔄 Spotlight 인덱스 재시작 중..."
echo "=========================================="

# 변경사항 적용을 위해 mds 재시작
sudo killall mds 2>/dev/null
sleep 2
sudo mdutil -a -i on 2>/dev/null

echo ""
echo "✅ 완료! 적용까지 1~2분 소요됩니다."
echo ""
echo "📊 현재 제외 목록 확인:"
sudo mdutil -as 2>/dev/null | grep -A1 "off" | sed 's/^/  /'
echo "=========================================="
