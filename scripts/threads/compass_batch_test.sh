#!/bin/bash
# Compass 배치 드라이런 테스트
# 생성일: 2026-09-22
# 목적: 10개 기사 × tone 자동 배정 → 다양성 검증
# 선택 기준: 5카테고리×2, 최대 2개 동일 출처, URL 중복 없음

URLS=(
  "https://the-decoder.com/google-deepmind-launches-interdisciplinary-institute-to-tackle-the-big-questions-around-agi/"
  "https://www.cityam.com/former-anthropic-researcher-behind-ai-could-kill-us-warning-called-to-uk-parliament/"
  "https://thenextweb.com/news/arcee-ai-series-b-1bn-valuation-open-weight-trinity"
  "https://www.ft.com/content/29f0dac0-0523-46c4-a573-cd681a69b445"
  "https://www.wired.com/story/washington-wont-be-regulating-ai-anytime-soon/"
  "https://www.fastcompany.com/91608263/how-concerned-americans-about-ais-environmental-impact-new-poll-reveals-data?utm_source=postup&utm_medium=email&utm_campaign=artificial-intelligence&position=6&partner=newsletter&campaign_date=09172026"
  "https://thenextweb.com/news/dynamic-creatures-aldebaran"
  "https://techcrunch.com/2026/09/09/suno-replaces-its-ai-models-with-a-new-one-trained-on-licensed-music-as-copyright-suits-pile-up/"
  "https://9to5google.com/2026/09/16/google-home-widget-battery/"
  "https://www.androidcentral.com/gaming/virtual-reality/snap-specs-can-work-and-play-ai-intelligence-platform-anticipates-your-needs"
)

TONES=("neutral_careful" "fan_friendly" "analytical" "neutral_careful" "fan_friendly" "analytical" "neutral_careful" "fan_friendly" "analytical" "neutral_careful")

echo "=== Compass 배치 테스트 시작 ==="
echo "기사 수: ${#URLS[@]}"
echo "posted.json 카운터 백업..."

# 카운터 백업
INTRO_BEFORE=$(python3 -c "import json; d=json.load(open('pipeline/posted.json')); print(d.get('compass_intro_rotation',0))")
H2_BEFORE=$(python3 -c "import json; d=json.load(open('pipeline/posted.json')); print(d.get('compass_h2_rotation',0))")
echo "BEFORE: intro=$INTRO_BEFORE h2=$H2_BEFORE"

RESULTS=()
ERRORS=()

for i in "${!URLS[@]}"; do
  IDX=$((i+1))
  URL="${URLS[$i]}"
  TONE="${TONES[$i]}"
  echo ""
  echo "--- [$IDX/10] tone=$TONE ---"
  echo "URL: $URL"

  OUTPUT=$(python3 scripts/threads/compass_dryrun.py "$URL" --tone "$TONE" --skip-g4 2>&1)
  EXIT_CODE=$?

  if [ $EXIT_CODE -eq 0 ]; then
    SAVED=$(echo "$OUTPUT" | grep "SAVED" | tail -1)
    echo "✅ 성공 $SAVED"
    RESULTS+=("$IDX:$TONE:SUCCESS")
  else
    echo "❌ 실패 (exit=$EXIT_CODE)"
    ERRORS+=("$IDX:$TONE:FAIL:$URL")
  fi
done

# 카운터 복원
python3 -c "
import json
with open('pipeline/posted.json','r') as f: d=json.load(f)
d['compass_intro_rotation']=$INTRO_BEFORE
d['compass_h2_rotation']=$H2_BEFORE
with open('pipeline/posted.json','w') as f: json.dump(d,f,ensure_ascii=False,indent=2)
print('카운터 복원: intro=$INTRO_BEFORE h2=$H2_BEFORE')
"

echo ""
echo "=== 결과 요약 ==="
echo "성공: ${#RESULTS[@]}/10"
echo "실패: ${#ERRORS[@]}/10"
for e in "${ERRORS[@]}"; do echo "  ❌ $e"; done

# 카운터 확인
INTRO_AFTER=$(python3 -c "import json; d=json.load(open('pipeline/posted.json')); print(d.get('compass_intro_rotation',0))")
H2_AFTER=$(python3 -c "import json; d=json.load(open('pipeline/posted.json')); print(d.get('compass_h2_rotation',0))")
echo "AFTER: intro=$INTRO_AFTER h2=$H2_AFTER"

echo ""
echo "=== 생성된 파일 목록 ==="
ls -la /tmp/compass_dryrun_*.md | tail -10
