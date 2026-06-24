#!/bin/bash
echo "=========================================="
echo "  🌡️  현재 온도 & 발열 상태 체크"
echo "=========================================="
echo "🕐 $(date)"
echo ""

echo "🌡️  [CPU/GPU/배터리 온도 - powermetrics]"
sudo powermetrics --samplers smc -n 1 -i 2000 2>/dev/null \
  | grep -iE "temp|thermal|die|battery|gpu|cpu|skin" \
  | grep -v "^$" \
  | sed 's/^/  /'
echo ""

echo "🔥 [CPU 점유율 TOP 8]"
ps -Ao pid,pcpu,pmem,comm -r 2>/dev/null | head -9 \
  | awk 'NR==1{printf "  %-8s %-8s %-8s %s\n","PID","%CPU","%MEM","COMMAND"}
         NR>1 {printf "  %-8s %-8s %-8s %s\n",$1,$2,$3,$4}'
echo ""

echo "💾 [메모리]"
vm_stat | awk '
  /Pages free/                   {free=$3+0}
  /Pages active/                 {active=$3+0}
  /Pages wired down/             {wired=$4+0}
  /Pages occupied by compressor/ {comp=$5+0}
  END {
    p=4096/1073741824
    printf "  Free: %.2f GB  |  Active: %.2f GB  |  Wired: %.2f GB  |  Compressed: %.2f GB\n",free*p,active*p,wired*p,comp*p
  }'
echo ""

echo "📈 [부하 평균]"
sysctl -n vm.loadavg | awk '{printf "  1분: %s  5분: %s  15분: %s  (코어: 10개)\n",$2,$3,$4}'
echo ""

echo "🔋 [배터리]"
pmset -g batt | grep -v "^Now" | sed 's/^/  /'
echo ""

echo "💨 [kernel_task CPU - 발열 제어 지표]"
KTASK=$(ps -Ao pid,pcpu,comm -r 2>/dev/null | grep kernel_task | head -1)
KTASK_CPU=$(echo "$KTASK" | awk '{print $2}')
echo "  kernel_task CPU: ${KTASK_CPU}%"
if [ $(echo "$KTASK_CPU > 20" | bc 2>/dev/null) -eq 1 ] 2>/dev/null; then
  echo "  → 🚨 kernel_task가 높음 = 맥이 아직 발열 제어 중"
elif [ $(echo "$KTASK_CPU > 5" | bc 2>/dev/null) -eq 1 ] 2>/dev/null; then
  echo "  → ⚠️  발열 감지 중, 서서히 내려가는 중"
else
  echo "  → ✅ 발열 정상 범위"
fi
echo "=========================================="
