#!/usr/bin/env python3
"""빌드 워치독 — `npm run build` 실패 시 Telegram 알림.

왜 필요한가: astro 5.x는 config 오류(ZodError 등)를 오류 메시지 없이 exit 1로 죽인다.
2026-10-01 20:36 커밋(output: 'hybrid') 이후 2.5일 동안 빌드가 조용히 실패 →
dist 정지 → 뉴스레터 링크(/tools/*) 404. 감지 장치가 없어Newsletter 발송 뒤에야 발견.

사용: python3 scripts/build_watchdog.py     (launchd: kr.aikorea24.build-watchdog, 매일 07:10)
"""
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NPM = shutil.which("npm") or "/opt/homebrew/bin/npm"
DEPLOY_LOCK = Path("/tmp/wrangler_deploy.lock")


def load_env():
    """dotenv 수동 파싱 — bash source 금지(값에 $ 또는 # 있으면 오염)"""
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def notify(text):
    """Telegram sendMessage — 실패해도 watchdog 본체는 죽이지 않는다"""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("[알림 없음] TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID 미설정 — 아래 stdout만 확인")
        return
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=urllib.parse.urlencode({"chat_id": chat, "text": text}).encode(),
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            print(f"[telegram] sent http={r.status}")
    except Exception as e:
        print(f"[telegram 실패] {e}")


def build_error_detail(stdout, stderr):
    """astro는 config 오류 본문을 숨긴다. --verbose 재실행으로 ZodError를 건져낸다."""
    # ponytail: 실패 시에만 빌드 1회 추가(정상 경로 비용 0). 더 정확한 원인은 CI 로그에서.
    v = subprocess.run(
        ["npx", "astro", "build", "--verbose"], cwd=ROOT, capture_output=True, text=True
    )
    blob = v.stdout + v.stderr
    m = re.search(r"ASTRO_CLI_ERROR.{0,500}", blob, re.S)
    if m:
        return m.group(0)
    tail = (stdout + stderr).strip()
    return tail[-800:] or "(출력 없음 — astro가 오류를 숨김)"


def main():
    if DEPLOY_LOCK.exists():
        print("[skip] 배포 진행 중(/tmp/wrangler_deploy.lock) — 건너뜀")
        return 0

    r = subprocess.run([NPM, "run", "build"], cwd=ROOT, capture_output=True, text=True)
    if r.returncode == 0:
        idx = ROOT / "dist" / "index.html"
        stamp = (
            __import__("datetime").datetime.fromtimestamp(idx.stat().st_mtime).strftime(
                "%Y-%m-%d %H:%M"
            )
            if idx.exists()
            else "dist/index.html 없음"
        )
        print(f"[ok] 빌드 성공 (exit 0) — dist/index.html mtime={stamp}")
        return 0

    detail = build_error_detail(r.stdout, r.stderr)
    print(f"[FAIL] 빌드 실패 exit={r.returncode}\n{detail}")
    load_env()
    notify(f"🚨 aikorea24 빌드 실패 (exit {r.returncode})\n{detail[:1500]}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
