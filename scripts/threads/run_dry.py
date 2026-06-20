#!/usr/bin/env python3
"""run_dry.py — 반복 dry-run 래퍼. 호출마다 다른 seed로 실행"""
import subprocess, sys, time
from datetime import datetime

VENV = "/Users/twinssn/Projects/aikorea24/.venv/bin/python3"
SCRIPT = "/Users/twinssn/Projects/aikorea24/scripts/threads/main_v3.py"

for i in range(5):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f"\n{'='*60}")
    print(f"  Dry-run #{i+1} at {ts}")
    print(f"{'='*60}")
    
    r = subprocess.run([VENV, SCRIPT, '--dry-run'], capture_output=True, text=True, timeout=120)
    output = (r.stdout or '') + (r.stderr or '')
    
    # Check if thread was generated
    if '✅ 쓰레드:' in output and '============================================================' in output:
        # Extract the thread section
        lines = output.split('\n')
        in_thread = False
        thread_lines = []
        for line in lines:
            if '============================================================' in line:
                if in_thread:
                    break
                in_thread = True
                continue
            if in_thread:
                thread_lines.append(line)
        
        print('\n'.join(thread_lines))
        print(f"\n✅ 성공! #{i+1}번째 시도")
        sys.exit(0)
    else:
        # Show last few lines
        tail = '\n'.join(output.split('\n')[-8:])
        print(tail)
        print(f"  ❌ 실패")
    
    time.sleep(2)

print("\n❌ 5회 모두 실패")
sys.exit(1)
