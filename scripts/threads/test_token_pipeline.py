#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
"""
Threads 토큰 파이프라인 테스트 (실제 게시 없음)

- API 응답은 requests 를 mock 하여 검증 (네트워크 의존 없음)
- 작업5 테스트1(계정 조회 HTTP 200)은 THREADS_LIVE_TEST=1 일 때만 실제 호출
- 토큰/시크릿 값은 어디에도 출력하지 않음
"""
import os
import sys
import json
import stat
import shutil
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import token_refresh as tr
import publisher as pb

TOKEN = "TEST_SHORT_TOKEN_PLACEHOLDER"
UID = "27538818229088576"
SECRET = "TEST_SECRET_PLACEHOLDER"


def _resp(status, payload):
    m = mock.Mock()
    m.status_code = status
    m.json.return_value = payload
    return m


# ── 작업5-1: validate (mock 200) ───────────────────────
def test_validate_ok():
    with mock.patch.object(tr.requests, "get", return_value=_resp(200, {"id": UID, "username": "aikorea24"})):
        state, acct = tr.validate_token(TOKEN, UID)
    assert state == tr.TOKEN_VALID, state
    assert acct["username"] == "aikorea24"


# ── 작업5-1b: live account lookup (gated) ──────────────
def test_validate_live():
    if os.environ.get("THREADS_LIVE_TEST") != "1":
        print("  (live 생략 — THREADS_LIVE_TEST=1 설정 시 실행)")
        return
    sec = tr.load_secrets()
    state, acct = tr.validate_token(sec["token"], sec["user_id"])
    assert state == tr.TOKEN_VALID, f"live 상태={state}"
    print(f"  (live) 상태={state} username={acct['username']}")


# ── 작업5-2: exchange mock ────────────────────────────
def test_exchange_ok():
    with mock.patch.object(tr.requests, "get", return_value=_resp(200, {"access_token": "NEW_LONG", "expires_in": 5184000})):
        state, new, exp, detail = tr.exchange_short_lived_token(TOKEN, SECRET)
    assert state == tr.TOKEN_VALID and new == "NEW_LONG" and exp == 5184000


def test_exchange_no_secret():
    state, new, exp, detail = tr.exchange_short_lived_token(TOKEN, "")
    assert state == tr.SECRET_MISSING and new is None


def test_exchange_bad_secret():
    # error_code=100 → 교환 불가 (시크릿 오류/이미 장기토큰 등 — 의미 임의 단정 안 함)
    with mock.patch.object(tr.requests, "get", return_value=_resp(400, {"error": {"code": 100, "type": "OAuthException"}})):
        state, new, exp, detail = tr.exchange_short_lived_token(TOKEN, SECRET)
    assert state == tr.TOKEN_INVALID and new is None


# ── 작업5-3: refresh mock ─────────────────────────────
def test_refresh_ok():
    with mock.patch.object(tr.requests, "get", return_value=_resp(200, {"access_token": "NEW_LONG", "expires_in": 5184000})):
        state, new, exp, detail = tr.refresh_long_lived_token(TOKEN)
    assert state == tr.TOKEN_VALID and new == "NEW_LONG"


def test_refresh_452():
    # 갱신 시도 실패 → token_refresh_failed 로 구분 (452 의미 임의 단정 안 함)
    with mock.patch.object(tr.requests, "get", return_value=_resp(400, {"error": {"code": 452, "type": "OAuthException"}})):
        state, new, exp, detail = tr.refresh_long_lived_token(TOKEN)
    assert state == tr.TOKEN_REFRESH_FAILED and new is None


# ── 작업6 신규: 교환 6분류 (classify_exchange_failure) ──
def test_classify_exchange_expired():
    assert tr.classify_exchange_failure(190, "OAuthException", "Session has expired") == tr.EXCHANGE_EXPIRED


def test_classify_exchange_invalid_secret():
    assert tr.classify_exchange_failure(100, "OAuthException", "Invalid client_secret") == tr.EXCHANGE_INVALID_SECRET


def test_classify_exchange_permission():
    assert tr.classify_exchange_failure(10, "OAuthException", "Permission denied") == tr.EXCHANGE_PERMISSION


def test_classify_exchange_invalid_request_100():
    # code 100 → invalid_request (message 근거)
    assert tr.classify_exchange_failure(100, "OAuthException", "Invalid parameter") == tr.EXCHANGE_INVALID_REQUEST


def test_classify_exchange_unknown_452():
    # code 452 + message 없음 → unknown (의미 단정 안 함)
    assert tr.classify_exchange_failure(452, "OAuthException", "") == tr.EXCHANGE_UNKNOWN


# ── 작업6 신규: run_exchange_classified (비밀 누락/성공 실패) ──
def _patch_valid_and_secrets(secret):
    return (
        mock.patch.object(tr, "validate_token", return_value=(tr.TOKEN_VALID, {"id": UID, "username": "aikorea24"})),
        mock.patch.object(tr, "load_secrets", return_value={"token": TOKEN, "user_id": UID, "app_secret": secret}),
    )


def test_exchange_classified_no_secret():
    with mock.patch.object(tr, "validate_token", return_value=(tr.TOKEN_VALID, {"id": UID, "username": "aikorea24"})), \
         mock.patch.object(tr, "load_secrets", return_value={"token": TOKEN, "user_id": UID, "app_secret": ""}):
        res = tr.run_exchange_classified()
    assert res["result"] == tr.EXCHANGE_INVALID_SECRET


def test_exchange_classified_success_writes_env_and_state():
    tmp = tempfile.mkdtemp()
    try:
        env = os.path.join(tmp, ".env")
        with open(env, "w") as f:
            f.write(f"THREADS_ACCESS_TOKEN=OLD\nTHREADS_USER_ID={UID}\n")
        orig_env, orig_state = tr.ENV_FILE, tr.STATE_FILE
        tr.ENV_FILE, tr.STATE_FILE = env, os.path.join(tmp, "state.json")
        try:
            with mock.patch.object(tr, "validate_token", return_value=(tr.TOKEN_VALID, {"id": UID, "username": "aikorea24"})), \
                 mock.patch.object(tr, "load_secrets", return_value={"token": TOKEN, "user_id": UID, "app_secret": SECRET}), \
                 mock.patch.object(tr.requests, "get", return_value=_resp(200, {"access_token": "NEW", "expires_in": 5184000})):
                res = tr.run_exchange_classified()
            assert res["result"] == tr.EXCHANGE_SUCCESS
            assert res["expires_at"] is not None
            with open(env) as f:
                assert "NEW" in f.read()
            with open(tr.STATE_FILE) as f:
                st = json.load(f)
            assert st["last_successful_token_operation"] == "exchange"
            assert st["expiry_known"] is True
            assert "THREADS_ACCESS_TOKEN" not in st  # 토큰 값 미저장
        finally:
            tr.ENV_FILE, tr.STATE_FILE = orig_env, orig_state
    finally:
        shutil.rmtree(tmp)


def test_exchange_classified_failure_preserves_env():
    tmp = tempfile.mkdtemp()
    try:
        env = os.path.join(tmp, ".env")
        with open(env, "w") as f:
            f.write(f"THREADS_ACCESS_TOKEN=OLD_KEEP\nTHREADS_USER_ID={UID}\n")
        orig_env, orig_state = tr.ENV_FILE, tr.STATE_FILE
        tr.ENV_FILE, tr.STATE_FILE = env, os.path.join(tmp, "state.json")
        try:
            with mock.patch.object(tr, "validate_token", return_value=(tr.TOKEN_VALID, {"id": UID, "username": "aikorea24"})), \
                 mock.patch.object(tr, "load_secrets", return_value={"token": TOKEN, "user_id": UID, "app_secret": SECRET}), \
                 mock.patch.object(tr.requests, "get", return_value=_resp(400, {"error": {"code": 100, "type": "OAuthException"}})):
                res = tr.run_exchange_classified()
            assert res["result"] == tr.EXCHANGE_INVALID_REQUEST
            with open(env) as f:
                assert "OLD_KEEP" in f.read()
            with open(tr.STATE_FILE) as f:
                st = json.load(f)
            assert st.get("sanitized_error_code") == 100
            assert "THREADS_ACCESS_TOKEN" not in st
        finally:
            tr.ENV_FILE, tr.STATE_FILE = orig_env, orig_state
    finally:
        shutil.rmtree(tmp)


# ── 작업6 신규: run_daily 상태 저장/선제갱신 ──
def test_daily_records_validation_and_expiry_unknown_when_no_op():
    """종류 미상 → exchange 시도(code=100) → refresh 폴백(code=452) → 기존 토큰 유지."""
    tmp = tempfile.mkdtemp()
    try:
        env = os.path.join(tmp, ".env")
        with open(env, "w") as f:
            f.write(f"THREADS_ACCESS_TOKEN=T\nTHREADS_USER_ID={UID}\n")
        orig_env, orig_state = tr.ENV_FILE, tr.STATE_FILE
        tr.ENV_FILE, tr.STATE_FILE = env, os.path.join(tmp, "state.json")
        try:
            ok_resp = _resp(200, {"id": UID, "username": "aikorea24"})
            with mock.patch.object(tr, "load_secrets", return_value={"token": TOKEN, "user_id": UID, "app_secret": SECRET}), \
                 mock.patch.object(tr.requests, "get", side_effect=[
                     ok_resp,  # 1. run_daily validate
                     ok_resp,  # 2. renew_token validate
                     ok_resp,  # 3. run_exchange_classified validate
                     _resp(400, {"error": {"code": 100, "subcode": 4279023, "message": "Invalid parameter", "type": "OAuthException"}}),  # 4. exchange GET → code=100 (이미 장기)
                     ok_resp,  # 5. run_refresh_classified validate
                     _resp(400, {"error": {"code": 452, "type": "OAuthException"}}),  # 6. refresh GET → 452 (아직 24h 미경과)
                 ]):
                rc = tr.run_daily()
            assert rc == 1
            with open(env) as f:
                assert "T" in f.read()
            with open(tr.STATE_FILE) as f:
                st = json.load(f)
            assert "last_validation_at" in st
            assert st.get("expiry_known") is False
            assert st.get("sanitized_error_code") == 452
            assert "THREADS_ACCESS_TOKEN" not in st
        finally:
            tr.ENV_FILE, tr.STATE_FILE = orig_env, orig_state
    finally:
        shutil.rmtree(tmp)


def test_daily_skips_when_expiry_far():
    tmp = tempfile.mkdtemp()
    try:
        env = os.path.join(tmp, ".env")
        with open(env, "w") as f:
            f.write(f"THREADS_ACCESS_TOKEN=T\nTHREADS_USER_ID={UID}\n")
        orig_env, orig_state = tr.ENV_FILE, tr.STATE_FILE
        tr.ENV_FILE, tr.STATE_FILE = env, os.path.join(tmp, "state.json")
        far = (datetime.now() + timedelta(days=50)).isoformat()
        with open(tr.STATE_FILE, "w") as f:
            json.dump({"expires_at": far}, f)
        try:
            with mock.patch.object(tr, "load_secrets", return_value={"token": TOKEN, "user_id": UID, "app_secret": SECRET}), \
                 mock.patch.object(tr.requests, "get", return_value=_resp(200, {"id": UID, "username": "aikorea24"})):
                rc = tr.run_daily()
            assert rc == 0  # 만료 여유 충분 → 갱신 보류
        finally:
            tr.ENV_FILE, tr.STATE_FILE = orig_env, orig_state
    finally:
        shutil.rmtree(tmp)



# ── 작업5-4: code 190 (만료) ──────────────────────────
def test_validate_expired_190():
    with mock.patch.object(tr.requests, "get", return_value=_resp(400, {"error": {"code": 190, "type": "OAuthException"}})):
        state, acct = tr.validate_token(TOKEN, UID)
    assert state == tr.TOKEN_EXPIRED and acct is None


# ── 작업5-5: 잘못된 토큰 (401 generic) ─────────────────
def test_validate_invalid():
    with mock.patch.object(tr.requests, "get", return_value=_resp(401, {"error": {"code": 4, "type": "OAuthException"}})):
        state, acct = tr.validate_token(TOKEN, UID)
    assert state == tr.TOKEN_INVALID


# ── 작업5-6: 네트워크 타임아웃 ─────────────────────────
def test_network_error():
    with mock.patch.object(tr.requests, "get", side_effect=tr.requests.RequestException("boom")):
        state, acct = tr.validate_token(TOKEN, UID)
    assert state == tr.NETWORK_ERROR and acct is None


# ── 작업5-7: .env 원자 교체 성공/실패 보존 ──────────────
def test_env_atomic_success():
    tmp = tempfile.mkdtemp()
    try:
        env = os.path.join(tmp, ".env")
        with open(env, "w") as f:
            f.write(f"THREADS_ACCESS_TOKEN=OLD\nTHREADS_USER_ID={UID}\n")
        bak_before = set(os.listdir(tmp))
        orig_env, orig_state = tr.ENV_FILE, tr.STATE_FILE
        tr.ENV_FILE, tr.STATE_FILE = env, os.path.join(tmp, "state.json")
        try:
            ok = tr.update_env_atomically("BRAND_NEW_TOKEN")
            assert ok
            with open(env) as f:
                assert 'THREADS_ACCESS_TOKEN="BRAND_NEW_TOKEN"' in f.read()
            # 백업 생성 + 0600
            baks = [f for f in os.listdir(tmp) if f.startswith(".env.bak.")]
            assert baks, "백업 미생성"
            mode = stat.S_IMODE(os.stat(os.path.join(tmp, baks[0])).st_mode)
            assert mode == 0o600, oct(mode)
        finally:
            tr.ENV_FILE, tr.STATE_FILE = orig_env, orig_state
    finally:
        shutil.rmtree(tmp)


def test_env_atomic_failure_preserves_old():
    tmp = tempfile.mkdtemp()
    try:
        env = os.path.join(tmp, ".env")
        with open(env, "w") as f:
            f.write(f"THREADS_ACCESS_TOKEN=OLD_VALUE\nTHREADS_USER_ID={UID}\n")
        orig_env, orig_state = tr.ENV_FILE, tr.STATE_FILE
        tr.ENV_FILE, tr.STATE_FILE = env, os.path.join(tmp, "state.json")
        try:
            # os.replace 실패 → 기존 토큰 보존
            with mock.patch.object(tr.os, "replace", side_effect=OSError("disk full")):
                ok = tr.update_env_atomically("SHOULD_NOT_WRITE")
            assert ok is False
            with open(env) as f:
                assert "OLD_VALUE" in f.read()
        finally:
            tr.ENV_FILE, tr.STATE_FILE = orig_env, orig_state
    finally:
        shutil.rmtree(tmp)


def test_env_atomic_rejects_empty():
    tmp = tempfile.mkdtemp()
    try:
        env = os.path.join(tmp, ".env")
        with open(env, "w") as f:
            f.write(f"THREADS_ACCESS_TOKEN=OLD_VALUE\n")
        orig_env, orig_state = tr.ENV_FILE, tr.STATE_FILE
        tr.ENV_FILE, tr.STATE_FILE = env, os.path.join(tmp, "state.json")
        try:
            ok = tr.update_env_atomically("")
            assert ok is False
            with open(env) as f:
                assert "OLD_VALUE" in f.read()
        finally:
            tr.ENV_FILE, tr.STATE_FILE = orig_env, orig_state
    finally:
        shutil.rmtree(tmp)


# ── 작업5-8: publisher 인증 실패 시 게시 API 호출 안 함 ─
def test_publisher_aborts_on_invalid_token():
    with mock.patch.object(pb, "validate_token", return_value=(tr.TOKEN_EXPIRED, None)), \
         mock.patch.object(pb.requests, "Session") as Sess:
        result = pb.publish_thread_chain(["카드1", "카드2"], {"id": 1, "title": "t", "link": ""})
    assert result is None
    Sess.return_value.post.assert_not_called()


def test_publisher_auth_error_no_retry():
    # 컨테이너 생성 시 code 190 → AuthError → 재시도(백오프) 없이 즉시 중단
    resp = mock.Mock(); resp.json.return_value = {"error": {"code": 190, "type": "OAuthException"}}
    sess = mock.Mock(); sess.post.return_value = resp
    with mock.patch.object(pb, "validate_token", return_value=(tr.TOKEN_VALID, {"id": UID, "username": "aikorea24"})), \
         mock.patch.object(pb.requests, "Session", return_value=sess), \
         mock.patch.object(pb, "time") as fake_time:
        try:
            pb.publish_thread_chain(["카드1"], {"id": 1, "title": "t", "link": ""})
        except pb.AuthError:
            pass
    # 재시도 대기(time.sleep) 없이 1회만 호출되어야 함
    assert sess.post.call_count == 1, sess.post.call_count
    fake_time.sleep.assert_not_called()


# ── 작업5-9: launchd plist 문법/경로 검증 ───────────────
def test_plist_template_valid():
    tpl = os.path.join(os.path.dirname(os.path.abspath(__file__)), "threads-token-refresh.plist.template")
    assert os.path.exists(tpl), "plist 템플릿 없음"
    # ${VAR} 치환 후 파싱
    with open(tpl) as f:
        content = f.read()
    from string import Template
    rendered = Template(content).safe_substitute(
        VENV_PYTHON="/x/venv/python3",
        PROJECT_DIR="/x/project",
        SCRIPT_PATH="/x/project/scripts/threads/token_refresh.py",
        LOG_DIR="/x/project/scripts/threads/logs",
    )
    ET.fromstring(rendered)  # 파싱 성공 = well-formed
    assert "kr.aikorea24.threads-token-refresh" in rendered
    assert "daily" in rendered


def test_install_script_has_refresh_job():
    path = os.path.join(ROOT, "scripts", "install_launchd.sh")
    with open(path) as f:
        content = f.read()
    assert "threads-token-refresh" in content
    assert "threads-token-refresh.plist.template" in content


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  ✅ {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  ❌ {t.__name__}: {e}")
            failed += 1
    print(f"\n결과: {passed} 통과 / {failed} 실패 (총 {len(tests)})")
    sys.exit(1 if failed else 0)
