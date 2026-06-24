#!/bin/bash
echo "=============================="
echo "  ⚡ 재기동 후 빠른 상태 체크"
echo "=============================="
echo "🕐 $(date)"
echo ""

echo "💾 [메모리 현황]"
vm_stat | awk '
  /Pages free/                   {free=$3+0}
  /Pages active/                 {active=$3+0}
  /Pages inactive/               {inactive=$3+0}
  /Pages wired down/             {wired=$4+0}
  /Pages occupied by compressor/ {comp=$5+0}
  END {
    p=4096/1073741824
    printf "  Free      : %.2f GB\n", free*p
    printf "  Active    : %.2f GB\n", active*p
    printf "  Inactive  : %.2f GB\n", inactive*p
    printf "  Wired     : %.2f GB\n", wired*p
    printf "  Compressed: %.2f GB\n", comp*p
  }'
echo ""

echo "🔥 [CPU 점유율 TOP 5]"
ps -Ao pid,pcpu,pmem,comm -r | head -6 | \
  awk 'NR==1{printf "  %-8s %-8s %-8s %s\n","PID","%CPU","%MEM","COMMAND"}
       NR>1 {printf "  %-8s %-8s %-8s %s\n",$1,$2,$3,$4}'
echo ""

echo "📈 [부하 평균]"
L=$(sysctl -n vm.loadavg)
echo "  $L  (코어: $(sysctl -n hw.logicalcpu)개)"
echo ""

echo "🔋 [배터리]"
pmset -g batt | grep -v "^Now" | sed 's/^/  /'
echo "=============================="
