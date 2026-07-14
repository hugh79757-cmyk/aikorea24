import json
import re
import subprocess
import time
from typing import Optional

from pipeline.infra.config import project_root


DB_NAME = "aikorea24-db"


WANGLER_BIN = "/opt/homebrew/bin/wrangler"


def _build_cmd(sql: str) -> list[str]:
    return [
        WANGLER_BIN, "d1", "execute",
        DB_NAME, "--remote", "--command", sql,
    ]


def _build_env() -> dict:
    """CLOUDFLARE_API_TOKEN 제거 — auth profile 우선"""
    env = dict(__import__("os").environ)
    env.pop("CLOUDFLARE_API_TOKEN", None)
    return env


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
                last_error = f"exit code {r.returncode}: {r.stderr.strip()}"
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
    return []
