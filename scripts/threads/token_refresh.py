#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
"""
Threads API 토큰 관리 (단독 실행 가능)

책임:
  - validate_token():          계정 조회로 토큰 유효성 확인 (네트워크/인증 오류 구분)
  - exchange_short_lived_token(): 단기 → 장기 교환 (th_exchange_token, 서버 측 전용)
  - refresh_long_lived_token():    장기 토큰 갱신 (th_refresh_token, 60일 연장)
  - update_env_atomically():       검증 성공 후 .env 의 THREADS_ACCESS_TOKEN 만 원자 교체
  - run_exchange_classified():     교환 1회 시도 + 6분류 버킷 + 안전 필드만 기록
  - run_daily():                  launchd용 1일 1회 갱신 (선제 갱신/ expiry_unknown 처리)

보안:
  - 토큰/시크릿 값은 어디에도 출력·로그·저장하지 않는다.
  - state JSON 에는 토큰 값을 절대 저장하지 않는다 (마지막 검증시각/상태/에러코드/만료시각만).
  - 백업 파일은 0600 권한, .env.bak* 패턴으로 git 미추적.
  - 실패 시 기존 토큰을 빈 값으로 덮어쓰지 않는다.
  - 만료된 토큰은 무한 재시도하지 않고 재인증 필요 상태로 종료한다.

공식 호스트: graph.threads.com (단일 출처 — publisher.py 도 이 상수 import 사용)
"""
import os
import sys
import json
import stat
import socket
import tempfile
from datetime import datetime, timedelta

# 스크립트를 어디서든 실행 가능하게 프로젝트 루트를 sys.path 에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import requests

from pipeline.infra.env_loader import EnvConfig
from pipeline.infra import project_root
from pipeline.infra.logger import get_scrubbed_logger, ScrubRegistry

logger = get_scrubbed_logger(__name__)

PROJECT_DIR = project_root()
ENV_FILE = os.path.join(PROJECT_DIR, '.env')
THREADS_DIR = os.path.join(PROJECT_DIR, 'scripts', 'threads')
STATE_FILE = os.path.join(THREADS_DIR, '.token_refresh_state.json')

# 공식 최신 호스트 (단일 출처)
THREADS_API_HOST = "graph.threads.net"

REQUEST_TIMEOUT = 20

# ── 상태 상수 ──────────────────────────────────────────
TOKEN_VALID = "token_valid"
TOKEN_EXPIRED = "token_expired"
TOKEN_INVALID = "token_invalid"
PERMISSION_DENIED = "permission_denied"
TOKEN_REFRESH_FAILED = "token_refresh_failed"
NETWORK_ERROR = "network_error"
SECRET_MISSING = "secret_missing"

# 교환 실패 6분류 버킷 (작업 명세)
EXCHANGE_SUCCESS = "exchange_success"
EXCHANGE_EXPIRED = "exchange_expired_token"
EXCHANGE_INVALID_REQUEST = "exchange_invalid_request"
EXCHANGE_INVALID_SECRET = "exchange_invalid_secret"
EXCHANGE_PERMISSION = "exchange_permission_error"
EXCHANGE_UNKNOWN = "exchange_unknown_error"
REFRESH_SUCCESS = "refresh_success"

EXPIRY_UNKNOWN = "expiry_unknown"
# 선제 갱신 여유 (만료 D-7 이내면 갱신)
RENEWAL_MARGIN_DAYS = 7


# ── 환경 로드 ─────────────────────────────────────────────
def _config() -> EnvConfig:
    cfg = EnvConfig()
    cfg.load_to_environ()
    return cfg


def load_secrets() -> dict:
    """THREADS_ACCESS_TOKEN / THREADS_USER_ID / THREADS_APP_SECRET 로드 (값 미노출)."""
    cfg = _config()
    return {
        "token": cfg.get("THREADS_ACCESS_TOKEN", ""),
        "user_id": cfg.get("THREADS_USER_ID", ""),
        "app_secret": cfg.get("THREADS_APP_SECRET", ""),
        "redirect_uri": cfg.get("THREADS_REDIRECT_URI", ""),
    }


# ── 상태 저장 (토큰 값 미저장) ──────────────────────────
def _state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_state(data: dict) -> None:
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _compute_expires_at(expires_in: int):
    if not expires_in or expires_in <= 0:
        return None
    return (datetime.now() + timedelta(seconds=expires_in)).isoformat()


def _record_state(status=None, sanitized_error_code=None, error_type=None,
                  sanitized_error_subcode=None, sanitized_error_message=None,
                  last_successful=None, expires_in=None, expires_at=None) -> None:
    """안전한 상태만 기록. 토큰 값은 절대 저장하지 않음."""
    st = _state()
    st["last_validation_at"] = datetime.now().isoformat()
    if status is not None:
        st["status"] = status
    if sanitized_error_code is not None:
        st["sanitized_error_code"] = sanitized_error_code
    if error_type is not None:
        st["sanitized_error_type"] = error_type
    if sanitized_error_subcode is not None:
        st["sanitized_error_subcode"] = sanitized_error_subcode
    if sanitized_error_message is not None:
        st["sanitized_error_message"] = sanitized_error_message
    if last_successful is not None:
        st["last_successful_token_operation"] = last_successful
    if expires_in is not None:
        st["expires_in"] = expires_in
        st["expires_at"] = _compute_expires_at(expires_in)
        st["expiry_known"] = True
    if expires_at is not None:
        st["expires_at"] = expires_at
        st["expiry_known"] = True
    # 성공적 교환/갱신 정보가 없으면 만료시각 미확정
    if last_successful is None and expires_at is None and expires_in is None:
        st.setdefault("expiry_known", False)
        if "status" not in st:
            st["status"] = EXPIRY_UNKNOWN
    _save_state(st)


# ── 오류 상세 추출 (안전 필드만) ───────────────────────
def _extract_error_detail(resp) -> dict:
    detail = {"http_status": getattr(resp, "status_code", None),
              "error_code": None, "error_type": None, "error_subcode": None, "message": None}
    try:
        body = resp.json()
    except Exception:
        return detail
    err = body.get("error", {}) if isinstance(body, dict) else {}
    raw_msg = str(err.get("message", "") or "")
    detail["error_code"] = err.get("code")
    detail["error_type"] = err.get("type")
    detail["error_subcode"] = err.get("error_subcode")
    # 토큰/시크릿이 message 에 포함될 수 있으므로 스크럽 후 저장
    detail["message"] = ScrubRegistry.scrub(raw_msg) if raw_msg else None
    return detail


def _classify_api_error(code, etype, msg) -> str:
    """계정 조회 실패 분류 (네트워크 아님). 추측 지양, 안전 필드 기반."""
    msg = (msg or "").lower()
    if code == 190 or "session has expired" in msg or "expired" in msg:
        return TOKEN_EXPIRED
    if "permission" in msg or "not authorized" in msg or ("access token" in msg and "invalid" in msg):
        return PERMISSION_DENIED
    return TOKEN_INVALID


def classify_exchange_failure(code, etype, message) -> str:
    """교환 실패 6분류. code 100/452 의미를 임의 단정하지 않고 message 와 함께 판단."""
    msg = (message or "").lower()
    if code == 190 or "session has expired" in msg or "expired" in msg:
        return EXCHANGE_EXPIRED
    if "secret" in msg or "client_secret" in msg:
        return EXCHANGE_INVALID_SECRET
    if "permission" in msg or "not authorized" in msg:
        return EXCHANGE_PERMISSION
    if code == 100 or "invalid" in msg or "parameter" in msg:
        return EXCHANGE_INVALID_REQUEST
    return EXCHANGE_UNKNOWN


# ── 유효성 검증 (계정 조회) ───────────────────────────────
def validate_token(token: str, user_id: str):
    """계정 조회로 토큰 유효성 확인.

    Returns:
        (state, account_or_None)  — 2-튜플 (publisher 호환)
    """
    if not token or not user_id:
        return TOKEN_INVALID, None
    url = f"https://{THREADS_API_HOST}/v1.0/{user_id}"
    params = {"fields": "id,username", "access_token": token}
    try:
        r = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
    except (requests.RequestException, socket.timeout, OSError) as e:
        logger.error("[validate] 네트워크 오류: %s", type(e).__name__)
        return NETWORK_ERROR, None
    if r.status_code == 200:
        try:
            data = r.json()
        except Exception:
            return TOKEN_INVALID, None
        return TOKEN_VALID, {"id": data.get("id"), "username": data.get("username")}
    detail = _extract_error_detail(r)
    logger.error("[validate] HTTP %s / code=%s type=%s",
                 detail["http_status"], detail["error_code"], detail["error_type"])
    return _classify_api_error(detail["error_code"], detail["error_type"], detail["message"]), None


# ── 단기 → 장기 교환 ─────────────────────────────────────
def exchange_short_lived_token(token: str, app_secret: str):
    """단기 토큰을 장기 토큰으로 교환 (서버 측 전용).

    Returns:
        (state, new_token_or_None, expires_in_or_0, error_detail_or_{})
    """
    if not app_secret:
        logger.error("[exchange] THREADS_APP_SECRET 없음 — 교환 불가")
        return SECRET_MISSING, None, 0, {}
    url = f"https://{THREADS_API_HOST}/v1.0/access_token"
    params = {
        "grant_type": "th_exchange_token",
        "client_secret": app_secret,
        "access_token": token,
    }
    try:
        r = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
    except (requests.RequestException, socket.timeout, OSError) as e:
        logger.error("[exchange] 네트워크 오류: %s", type(e).__name__)
        return NETWORK_ERROR, None, 0, {}
    if r.status_code == 200:
        try:
            data = r.json()
        except Exception:
            return TOKEN_INVALID, None, 0, {}
        new_tok = data.get("access_token")
        if new_tok:
            return TOKEN_VALID, new_tok, int(data.get("expires_in", 0)), {}
        return TOKEN_INVALID, None, 0, {}
    detail = _extract_error_detail(r)
    logger.error("[exchange] HTTP %s / code=%s type=%s",
                 detail["http_status"], detail["error_code"], detail["error_type"])
    return TOKEN_INVALID, None, 0, detail


# ── 장기 토큰 갱신 ───────────────────────────────────────
def refresh_long_lived_token(token: str):
    """유효한 장기 토큰을 60일 연장.

    Returns:
        (state, new_token_or_None, expires_in_or_0, error_detail_or_{})
    """
    url = f"https://{THREADS_API_HOST}/v1.0/refresh_access_token"
    params = {"grant_type": "th_refresh_token", "access_token": token}
    try:
        r = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
    except (requests.RequestException, socket.timeout, OSError) as e:
        logger.error("[refresh] 네트워크 오류: %s", type(e).__name__)
        return NETWORK_ERROR, None, 0, {}
    if r.status_code == 200:
        try:
            data = r.json()
        except Exception:
            return TOKEN_INVALID, None, 0, {}
        new_tok = data.get("access_token")
        if new_tok:
            return TOKEN_VALID, new_tok, int(data.get("expires_in", 0)), {}
        return TOKEN_INVALID, None, 0, {}
    detail = _extract_error_detail(r)
    logger.error("[refresh] HTTP %s / code=%s type=%s",
                 detail["http_status"], detail["error_code"], detail["error_type"])
    return TOKEN_REFRESH_FAILED, None, 0, detail


# ── .env 원자 교체 ───────────────────────────────────────
def _backup_env() -> str:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = f"{ENV_FILE}.bak.{ts}"
    import shutil
    shutil.copy2(ENV_FILE, backup)
    os.chmod(backup, stat.S_IRUSR | stat.S_IWUSR)  # 0600
    logger.info("[env] 백업 생성: %s", os.path.basename(backup))
    return backup


def update_env_atomically(new_token: str) -> bool:
    """검증 성공 후 THREADS_ACCESS_TOKEN 만 안전하게 교체.

    - 백업 생성(0600)
    - 임시 파일 작성 후 os.replace 로 원자 교체
    - 교체 실패 시 백업에서 복원, 기존 토큰 보존
    - new_token 이 빈 값이면 절대 덮어쓰지 않음
    """
    if not new_token:
        logger.error("[env] 빈 토큰 — 교체 중단 (기존 토큰 보존)")
        return False
    if not os.path.exists(ENV_FILE):
        logger.error("[env] .env 파일 없음")
        return False

    backup = _backup_env()
    try:
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()

        replaced = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("THREADS_ACCESS_TOKEN") and not stripped.startswith("#"):
                prefix = "export " if stripped.startswith("export ") else ""
                rest = stripped[7:] if prefix else stripped
                key = rest.split("=", 1)[0] if "=" in rest else "THREADS_ACCESS_TOKEN"
                lines[i] = f'{prefix}{key}="{new_token}"\n'
                replaced = True
                break

        if not replaced:
            logger.error("[env] THREADS_ACCESS_TOKEN 키를 찾지 못함 — 교체 중단")
            return False

        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(ENV_FILE), prefix=".env.tmp.")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.writelines(lines)
            os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
            os.replace(tmp, ENV_FILE)
        except Exception:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise

        logger.info("[env] THREADS_ACCESS_TOKEN 교체 완료 (검증 통과 후)")
        return True
    except Exception as e:
        logger.error("[env] 교체 실패 — 백업에서 복원: %s", type(e).__name__)
        if os.path.exists(backup):
            import shutil
            shutil.copy2(backup, ENV_FILE)
        return False


# ── 교환 1회 시도 + 6분류 ────────────────────────────────
def run_exchange_classified() -> dict:
    """단기→장기 교환을 1회 안전하게 시도하고 6분류 버킷 + 안전 필드만 반환/기록.

    실제 교환 요청은 서버 측에서만 실행. 성공 시에만 .env 원자 교체.
    """
    result = {
        "result": None, "http_status": None, "error_code": None,
        "error_subcode": None, "error_type": None, "message": None,
        "expires_in": 0, "expires_at": None,
    }
    sec = load_secrets()

    # 1) 현재 토큰 유효성
    state, _ = validate_token(sec["token"], sec["user_id"])
    if state == NETWORK_ERROR:
        result["result"] = EXCHANGE_UNKNOWN
        result["message"] = "network_error"
        _record_state(status=NETWORK_ERROR)
        return result
    if state == TOKEN_EXPIRED:
        result["result"] = EXCHANGE_EXPIRED
        _record_state(status=TOKEN_EXPIRED)
        logger.error("[exchange] 현재 토큰 만료 — 교환 불가 (재인증 필요)")
        return result
    if state != TOKEN_VALID:
        result["result"] = EXCHANGE_UNKNOWN
        _record_state(status=state)
        logger.error("[exchange] 현재 토큰 상태=%s — 교환 불가", state)
        return result

    # 2) 시크릿 보유 확인
    if not sec["app_secret"]:
        result["result"] = EXCHANGE_INVALID_SECRET
        result["message"] = "THREADS_APP_SECRET missing"
        _record_state(status=SECRET_MISSING)
        logger.error("[exchange] THREADS_APP_SECRET 없음 — 사용자 조치 필요")
        return result

    # 3) 교환 요청 (서버 측)
    est, new_tok, expires_in, err = exchange_short_lived_token(sec["token"], sec["app_secret"])
    if est == TOKEN_VALID and new_tok:
        vstate, account = validate_token(new_tok, sec["user_id"])
        if vstate == TOKEN_VALID and update_env_atomically(new_tok):
            expires_at = _compute_expires_at(expires_in)
            _record_state(status=EXCHANGE_SUCCESS, last_successful="exchange",
                          expires_in=expires_in, expires_at=expires_at)
            result.update(result=EXCHANGE_SUCCESS, expires_in=expires_in, expires_at=expires_at)
            logger.info("[exchange] 완료 — 장기 토큰 적용, 만료 %s일", expires_in // 86400)
            return result
        # 새 토큰 검증/교체 실패
        result["result"] = EXCHANGE_UNKNOWN
        result["message"] = "new_token_validation_failed"
        _record_state(status=(vstate if vstate != TOKEN_VALID else TOKEN_REFRESH_FAILED))
        logger.error("[exchange] 새 토큰 검증/교체 실패 — .env 미변경")
        return result

    # 4) 교환 실패 → 6분류
    result.update(http_status=err.get("http_status"), error_code=err.get("error_code"),
                  error_subcode=err.get("error_subcode"),
                  error_type=err.get("error_type"), message=err.get("message"))
    bucket = classify_exchange_failure(err.get("error_code"), err.get("error_type"), err.get("message"))
    result["result"] = bucket
    _record_state(status=bucket, sanitized_error_code=err.get("error_code"),
                  error_type=err.get("error_type"),
                  sanitized_error_subcode=err.get("error_subcode"),
                  sanitized_error_message=err.get("message"))
    logger.error("[exchange] 실패 분류=%s (HTTP %s / code=%s)",
                 bucket, err.get("http_status"), err.get("error_code"))
    return result


# ── 갱신 분류 흐름 ──────────────────────────────────────
def run_refresh_classified() -> dict:
    """장기 토큰 갱신 → 검증 → .env 교체까지 분류 결과 포함 반환."""
    result = {"result": None, "http_status": None, "error_code": None,
              "error_subcode": None, "error_type": None, "message": None,
              "expires_in": 0, "expires_at": None}
    sec = load_secrets()
    state, _ = validate_token(sec["token"], sec["user_id"])
    if state == NETWORK_ERROR:
        result.update(result="refresh_network_error", message="network_error")
        _record_state(status=NETWORK_ERROR)
        return result
    if state != TOKEN_VALID:
        result.update(result="refresh_token_invalid", message=state)
        _record_state(status=state)
        return result
    rstate, new_tok, expires_in, err = refresh_long_lived_token(sec["token"])
    if rstate == TOKEN_VALID and new_tok:
        vstate, account = validate_token(new_tok, sec["user_id"])
        if vstate == TOKEN_VALID and update_env_atomically(new_tok):
            expires_at = _compute_expires_at(expires_in)
            _record_state(status=TOKEN_VALID, last_successful="refresh",
                          expires_in=expires_in, expires_at=expires_at)
            result.update(result=REFRESH_SUCCESS, expires_in=expires_in, expires_at=expires_at)
            logger.info("[refresh-classified] 완료 — 만료 %s일", expires_in // 86400)
            return result
        result.update(result="refresh_validate_failed", message="new_token_validation_failed")
        _record_state(status=vstate)
        return result
    result.update(http_status=err.get("http_status"), error_code=err.get("error_code"),
                  error_subcode=err.get("error_subcode"), error_type=err.get("error_type"),
                  message=err.get("message"))
    result["result"] = TOKEN_REFRESH_FAILED
    _record_state(status=TOKEN_REFRESH_FAILED,
                  sanitized_error_code=err.get("error_code"),
                  sanitized_error_subcode=err.get("error_subcode"),
                  error_type=err.get("error_type"))
    logger.error("[refresh-classified] 실패 상태=%s (code=%s) — .env 미변경",
                 TOKEN_REFRESH_FAILED, err.get("error_code"))
    return result


# ── 분기 갱신 (단기→교환 / 장기→갱신) ─────────────────────
def renew_token() -> dict:
    """토큰 종류에 따라 자동 분기.

    - 알려진 장기 토큰: th_refresh_token 으로 갱신만 시도 (교환 시도 안 함)
    - 종류 미상: 단기 가정 → 교환 시도, 이미 장기이면 갱신으로 폴백
    """
    sec = load_secrets()
    state, _ = validate_token(sec["token"], sec["user_id"])
    if state != TOKEN_VALID:
        logger.error("[renew] 토큰 무효(%s) — 재인증 필요", state)
        return {"result": state, "expires_at": None}

    st = _state()
    known_long = (
        st.get("expiry_known") is True
        or st.get("last_successful_token_operation") in ("exchange", "refresh")
    )
    if known_long:
        logger.info("[renew] 알려진 장기 토큰 → th_refresh_token")
        return run_refresh_classified()

    # 종류 미상 → 단기 가정, 교환 시도
    logger.info("[renew] 토큰 종류 미상 → th_exchange_token 시도")
    ex = run_exchange_classified()
    if ex["result"] == EXCHANGE_SUCCESS:
        return ex
    # 교환 실패가 '이미 장기' 신호면 갱신으로 폴백
    if ex["result"] in (EXCHANGE_INVALID_REQUEST, EXCHANGE_UNKNOWN):
        logger.info("[renew] 교환 실패(%s) → 이미 장기 토큰 가능성, 갱신 폴백", ex["result"])
        return run_refresh_classified()
    # 그 외(secret/만료/권한) → 중단
    logger.error("[renew] 교환 실패(%s) — 갱신 폴백 안 함", ex["result"])
    return ex


# ── 상위 흐름 (기존 호환) ────────────────────────────────
def cmd_check() -> int:
    sec = load_secrets()
    state, account = validate_token(sec["token"], sec["user_id"])
    if state == TOKEN_VALID and account:
        logger.info("[check] 상태=%s / id=%s username=%s",
                    state, account.get("id"), account.get("username"))
    else:
        logger.warning("[check] 상태=%s (계정 조회 실패)", state)
    return 0 if state == TOKEN_VALID else 1


def cmd_exchange() -> int:
    res = run_exchange_classified()
    logger.info("[exchange] 결과=%s HTTP=%s code=%s subcode=%s type=%s message=%s expires_at=%s",
                res["result"], res["http_status"], res["error_code"], res["error_subcode"],
                res["error_type"], res["message"], res["expires_at"])
    return 0 if res["result"] == EXCHANGE_SUCCESS else 1


def cmd_refresh() -> int:
    sec = load_secrets()
    state, _ = validate_token(sec["token"], sec["user_id"])
    if state != TOKEN_VALID:
        logger.error("[refresh] 현재 토큰 상태=%s — 갱신 불가", state)
        _record_state(status=state)
        return 1
    rstate, new_tok, expires_in, err = refresh_long_lived_token(sec["token"])
    if rstate == TOKEN_VALID and new_tok:
        vstate, account = validate_token(new_tok, sec["user_id"])
        if vstate == TOKEN_VALID and update_env_atomically(new_tok):
            expires_at = _compute_expires_at(expires_in)
            _record_state(status=TOKEN_VALID, last_successful="refresh",
                          expires_in=expires_in, expires_at=expires_at)
            logger.info("[refresh] 완료 — 만료 %s일", expires_in // 86400)
            return 0
        _record_state(status=vstate, sanitized_error_code=err.get("error_code"))
        return 1
    _record_state(status=rstate, sanitized_error_code=err.get("error_code"),
                  error_type=err.get("error_type"))
    logger.error("[refresh] 실패 상태=%s (code=%s) — .env 미변경", rstate, err.get("error_code"))
    return 1


def run_daily() -> int:
    """launchd 1일 1회 갱신 (단기→교환 / 장기→갱신 자동 분기).

    - 네트워크 오류: today 보류
    - 만료/무효: 자동 재인증 불가 → 재인증 필요 상태 종료
    - expires_at 알려진 경우: D-7 이내면 선제 갱신, 여유 있으면 보류
    - expires_at 모르는 경우: renew_token()이 종류 감지 후 분기 처리
    """
    sec = load_secrets()
    state, account = validate_token(sec["token"], sec["user_id"])

    if state == NETWORK_ERROR:
        _record_state(status=NETWORK_ERROR)
        logger.error("[daily] 네트워크 오류 — 오늘 갱신 보류")
        return 1
    if state != TOKEN_VALID:
        _record_state(status=state)
        logger.error("[daily] 토큰 상태=%s — 자동 갱신 불가, 사용자 재인증 필요", state)
        return 2

    # 만료시각 알려진 경우 선제 갱신 판단
    st = _state()
    expires_at = st.get("expires_at")
    if expires_at:
        try:
            ea = datetime.fromisoformat(expires_at)
            if ea - datetime.now() >= timedelta(days=RENEWAL_MARGIN_DAYS):
                logger.info("[daily] 만료 여유 충분(%s) — 갱신 보류", expires_at[:19])
                _record_state(status=TOKEN_VALID)
                return 0
            logger.info("[daily] 만료 임박(%s) — 선제 갱신", expires_at[:19])
        except Exception:
            pass  # 파싱 실패 시 아래 1회 시도로 진행

    # expires_at 모름 또는 임박 → 분기 갱신
    res = renew_token()
    ok = res.get("result") in (EXCHANGE_SUCCESS, REFRESH_SUCCESS, TOKEN_VALID)
    if ok:
        logger.info("[daily] 갱신 완료 — 결과=%s", res.get("result"))
    else:
        logger.error("[daily] 갱신 실패 — 결과=%s", res.get("result"))
    return 0 if ok else 1


def cmd_state() -> int:
    st = _state()
    logger.info("[state] %s", json.dumps({k: v for k, v in st.items()}, ensure_ascii=False))
    return 0


def cmd_renew() -> int:
    """단기→교환 / 장기→갱신 자동 분기 실행."""
    res = renew_token()
    logger.info("[renew] 결과=%s expires_at=%s",
                res.get("result"), res.get("expires_at"))
    return 0 if res.get("result") in (EXCHANGE_SUCCESS, REFRESH_SUCCESS, TOKEN_VALID) else 1


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    handlers = {
        "check": cmd_check,
        "exchange": cmd_exchange,
        "refresh": cmd_refresh,
        "renew": cmd_renew,
        "daily": run_daily,
        "state": cmd_state,
    }
    fn = handlers.get(cmd, cmd_check)
    sys.exit(fn())
