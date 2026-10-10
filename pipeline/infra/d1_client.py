import json
import logging
import re
import subprocess
import time
from typing import Optional

import logging as _logging

from pipeline.infra.config import project_root

logger = _logging.getLogger(__name__)


DB_NAME = "aikorea24-db"


WANGLER_BIN = "/opt/homebrew/bin/wrangler"


def _build_cmd(sql: str) -> list[str]:
    return [
        WANGLER_BIN, "d1", "execute",
        DB_NAME, "--remote", "--command", sql,
    ]


def _build_env() -> dict:
    # 2026-10-09 CF-MIGRATE-02: OAuth 프로필은 출발 계정(fac9808c)이라
    # 신규 계정 D1에 7404. env 주입 토큰(신규 계정)을 그대로 wrangler에 전달.
    return dict(__import__("os").environ)


def _parse_result(stdout: str) -> list[dict]:
    m = re.search(r'"results"\s*:\s*(\[[\s\S]*?\])\s*,\s*"success"', stdout)
    if m:
        return json.loads(m.group(1))
    return []


def d1_query(
    sql: str,
    params: Optional[dict] = None,
    retries: int = 2,
) -> list[dict]:
    _ = params
    root = project_root()
    cmd = _build_cmd(sql)
    last_error: Optional[str] = None
    env = _build_env()
    for attempt in range(retries):
        try:
            r = subprocess.run(
                cmd, capture_output=True, text=True, timeout=60, cwd=str(root),
                env=env,
            )
            if r.returncode != 0:
                stderr = r.stderr.strip()
                # 인증 오류 진단
                if "7403" in stderr:
                    logger.warning("  ⚠️ D1 인증 실패 [7403]: CLOUDFLARE_ACCOUNT_ID와 OAuth 프로필 충돌 의심")
                elif "10000" in stderr:
                    logger.warning("  ⚠️ D1 인증 실패 [10000]: CLOUDFLARE_API_TOKEN env var 충돌 의심")
                last_error = f"exit code {r.returncode}: {stderr[:300]}"
                if attempt < retries - 1:
                    time.sleep(1.0 * (2.0 ** attempt))
                continue
            return _parse_result(r.stdout)
        except subprocess.TimeoutExpired:
            last_error = f"timeout (60s)"
            if attempt < retries - 1:
                time.sleep(1.0 * (2.0 ** attempt))
        except Exception as e:
            last_error = str(e)
            if attempt < retries - 1:
                time.sleep(1.0 * (2.0 ** attempt))
    logger.warning("D1 query failed after %d attempts: %s", retries, last_error)
    return []
