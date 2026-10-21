"""tests/test_pipeline_early_warning_exit_code.py

AIK24-PIPE-08 — B-2 후보 풀 깊이 조기 경보 · B-1 수집 상태 요약 · B-6 exit code 전파.

2026-10-21 07:00 사고: D1 읽기 가드(82.1%)가 05:30 수집을 죽여 후보 풀이 전날 잔여분으로
고정 → 선정 3건이 Phase 2 dedup 에서 3/3 탈락 → 브리핑 0건 → 그런데도 exit 0 +
"✅ 에러 없음" + 텔레그램 "Briefing published"(가짜 성공).

- AIK24-PIPE-ALERT-01(31a32e19): 0건이면 exit 1 + 실제 건수 알림 (이미 반영됨)
- B-2 (여기): LLM 채점 **전에** 신선 후보 수가 MAX_COUNT 미만이면 조기 경보 1회.
               브리핑 생성을 막지 않는다 (조기 경보 = advisory).
- B-1 (여기): 수집기 상태 파일(scripts/.collector_state.json)을 **읽기만** 해서
               "후보 풀이 전날 잔여분일 수 있음" 을 요약에 남긴다.
- B-6 (여기): 래퍼가 내부 파이프라인의 returncode 를 버리지 않고 그대로 exit 한다.

실제 파이프라인·텔레그램·D1 은 이 테스트에서 절대 호출하지 않는다 (전부 스텁).
"""
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(SCRIPTS_DIR))

import run_pipeline as rp  # noqa: E402
import run_pipeline_with_notify as rpn  # noqa: E402


# --------------------------------------------------------------------------
# 공통 픽스처
# --------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolate_collector_state(monkeypatch, tmp_path):
    """실제 scripts/.collector_state.json 을 읽거나 쓰지 않는다 (tmp 로 우회)."""
    monkeypatch.setattr(rp, "COLLECTOR_STATE_PATH", tmp_path / ".collector_state.json")


@pytest.fixture(autouse=True)
def notifier(monkeypatch):
    """조기 경보 발송 기록기 — 실제 텔레그램은 **절대** 보내지 않는다.

    autouse 로 둔다: `import auto_news_selector` 는 프로젝트 .env 를 os.environ 에
    적재하므로(conftest 의 disable_telegram_in_tests 빈값을 덮어쓴다) 알림 경로만으로는
    보호되지 않는다. 알림 함수를 직접 스텁해야 실발송이 막힌다.
    """
    sent = []
    monkeypatch.setattr(rp, "_default_notifier", lambda msg: (sent.append(msg), True)[1])
    rp.reset_early_alert_state()
    yield sent
    rp.reset_early_alert_state()


@pytest.fixture
def fresh_count(monkeypatch):
    """count_fresh_candidates 스텁 — 인자로 건수를 지정한다."""
    def _set(n):
        monkeypatch.setattr(rp, "count_fresh_candidates", lambda *a, **k: n)
    return _set


def _write_state(path, **fields):
    path.write_text(json.dumps(fields, ensure_ascii=False), encoding="utf-8")


def _fake_subprocess(returncode, stdout="", stderr=""):
    """subprocess.run 을 스텁한 네임스페이스 (실제 프로세스를 띄우지 않는다)."""
    class _Fake:
        TimeoutExpired = subprocess.TimeoutExpired

        @staticmethod
        def run(*args, **kwargs):
            return subprocess.CompletedProcess(
                args=args, returncode=returncode, stdout=stdout, stderr=stderr)

    return _Fake


# --------------------------------------------------------------------------
# B-2 — 후보 풀 깊이 조기 경보
# --------------------------------------------------------------------------

def test_early_alert_fires_exactly_once_when_pool_is_shallow(notifier, fresh_count):
    """신선 후보 < MAX_COUNT → 조기 경보가 **정확히 1회** 나간다."""
    fresh_count(1)

    first = rp.check_candidate_depth()
    second = rp.check_candidate_depth()   # 같은 런에서 다시 검사해도 중복 발송 금지

    assert len(notifier) == 1
    assert first["alert_sent"] is True
    assert second["alert_sent"] is False
    assert "후보 풀 부족: 신선 후보 1건 (최소 3건 필요)" in first["warnings"]
    assert "후보 풀 부족" in notifier[0]


def test_no_early_alert_when_pool_is_deep_enough(notifier, fresh_count):
    """신선 후보 >= MAX_COUNT → 조기 경보 없음."""
    fresh_count(rp.MAX_COUNT_FALLBACK)

    depth = rp.check_candidate_depth()

    assert notifier == []
    assert depth["alert_sent"] is False
    assert not [w for w in depth["warnings"] if "후보 풀 부족" in w]


def test_early_warning_is_advisory_only(notifier, fresh_count):
    """조기 경보는 권고다 — summary['errors'] 를 건드리지 않아 exit 코드에 영향이 없다."""
    fresh_count(1)
    summary = {"news": [], "briefings": 0, "thumbnails": [], "errors": [], "warnings": []}

    depth = rp.apply_depth_warnings(summary)

    assert summary["errors"] == []
    assert any("후보 풀 부족" in w for w in summary["warnings"])
    assert depth["fresh"] == 1
    assert depth["max_count"] == rp.MAX_COUNT_FALLBACK


def test_pipeline_continues_after_early_warning(monkeypatch, notifier, fresh_count):
    """조기 경보 뒤에도 Step 1(뉴스 선정)·Step 2(브리핑)까지 진행한다 — 게이트가 아니다."""
    fresh_count(1)
    steps = []

    monkeypatch.setattr(rp, "step_news_selection", lambda: (steps.append("news"), [])[1])
    monkeypatch.setattr(rp, "step_briefing_with_log",
                        lambda arts: (steps.append("briefing"), (7, ""))[1])
    monkeypatch.setattr(rp, "step_blog_link", lambda: steps.append("blog_link"))
    monkeypatch.setattr(sys, "argv", [
        "run_pipeline.py", "--skip-thumbnails", "--skip-email", "--skip-deploy"])

    rp.main()

    assert steps[:2] == ["news", "briefing"]
    assert len(notifier) == 1


def test_missing_helper_fails_soft(monkeypatch, notifier):
    """count_fresh_candidates 헬퍼가 없으면 조기 경보만 건너뛴다 (파이프라인은 안 죽는다)."""
    import auto_news_selector

    monkeypatch.delattr(auto_news_selector, "count_fresh_candidates", raising=False)

    assert rp.count_fresh_candidates() is None
    depth = rp.check_candidate_depth()
    assert depth["fresh"] is None
    assert depth["alert_sent"] is False


# --------------------------------------------------------------------------
# B-1 — 수집기 상태 파일 통합 (읽기 전용)
# --------------------------------------------------------------------------

def test_collector_state_not_ok_is_summarized(tmp_path, notifier, fresh_count):
    """status != 'ok' + 오늘 파일 → 요약에 '수집 단계 이상' 경고."""
    fresh_count(5)
    state_path = tmp_path / ".collector_state.json"
    _write_state(state_path, status="aborted", reason="D1 가드 한도 초과",
                 at=datetime.now().astimezone().isoformat(), collected=0)

    depth = rp.check_candidate_depth(state_path=state_path)

    joined = "\n".join(depth["warnings"])
    assert "수집 단계 이상: aborted (D1 가드 한도 초과)" in joined
    assert "전날 잔여분" in joined


def test_collector_state_ok_produces_no_warning(tmp_path, notifier, fresh_count):
    """status == 'ok' + 오늘 파일 → 경고 없음."""
    fresh_count(5)
    state_path = tmp_path / ".collector_state.json"
    _write_state(state_path, status="ok", reason="", collected=130,
                 at=datetime.now().astimezone().isoformat())

    depth = rp.check_candidate_depth(state_path=state_path)

    assert depth["warnings"] == []
    assert depth["collector"]["status"] == "ok"
    assert depth["collector"]["freshness"] == "fresh"


def test_missing_collector_state_does_not_crash_and_stays_soft(tmp_path, notifier, fresh_count):
    """파일 없음 → 예외 없이 '알 수 없음'. 후보 풀이 충분하면 조용히(경고 없음)."""
    fresh_count(5)

    depth = rp.check_candidate_depth(state_path=tmp_path / "없는파일.json")

    assert depth["collector"]["status"] == "missing"
    assert depth["warnings"] == []


def test_missing_collector_state_is_reported_when_pool_is_shallow(tmp_path, notifier, fresh_count):
    """파일 없음 + 후보 풀이 부족 → '알 수 없음' 이 함께 남는다."""
    fresh_count(1)

    depth = rp.check_candidate_depth(state_path=tmp_path / "없는파일.json")

    joined = "\n".join(depth["warnings"])
    assert "수집 상태 알 수 없음" in joined


def test_stale_collector_state_uses_soft_wording(tmp_path, notifier, fresh_count):
    """어제 파일 → '오래됨' (다른, 약한 표현)로 표기."""
    fresh_count(5)
    state_path = tmp_path / ".collector_state.json"
    yesterday = (datetime.now().astimezone() - timedelta(days=1)).isoformat()
    _write_state(state_path, status="aborted", reason="D1 가드 한도 초과",
                 at=yesterday, collected=0)

    depth = rp.check_candidate_depth(state_path=state_path)

    assert depth["collector"]["freshness"] == "stale"
    joined = "\n".join(depth["warnings"])
    assert "수집 상태 오래됨" in joined
    assert "수집 단계 이상" not in joined


def test_pipeline_never_writes_the_collector_state_file(tmp_path, notifier, fresh_count):
    """파이프라인은 수집 상태 파일을 **읽기만** 한다 (쓰는 쪽은 B-1 담당)."""
    fresh_count(1)
    state_path = tmp_path / ".collector_state.json"

    rp.check_candidate_depth(state_path=state_path)

    assert not state_path.exists()


def test_reader_accepts_the_collector_writer_payload_format(tmp_path, notifier, fresh_count):
    """B-1 작성자(api_test/news_collector.py::write_collector_state) 의 payload 와 호환된다.

    작성자가 만드는 'at' 은 KST ISO8601(timespec='seconds') 이다 — 이 형태를 그대로
    읽어 '오늘 수집 결과'로 판정해야 한다.
    """
    fresh_count(5)
    state_path = tmp_path / ".collector_state.json"
    at = datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds")
    payload = {"status": "aborted", "reason": "D1 가드 한도 초과",
               "at": at, "collected": 0}
    state_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    depth = rp.check_candidate_depth(state_path=state_path)

    assert depth["collector"]["status"] == "aborted"
    assert depth["collector"]["freshness"] == "fresh"
    assert depth["collector"]["at"] == at
    assert depth["collector"]["collected"] == 0
    assert "수집 단계 이상: aborted (D1 가드 한도 초과)" in "\n".join(depth["warnings"])


# --------------------------------------------------------------------------
# B-6 — exit code 전파 (단위)
# --------------------------------------------------------------------------

@pytest.mark.parametrize("rc", [0, 1, 3, 124])
def test_wrapper_returns_inner_returncode(monkeypatch, rc):
    """래퍼 main() 은 내부 파이프라인의 returncode 를 그대로 돌려준다."""
    monkeypatch.setattr(sys, "argv", ["run_pipeline_with_notify.py"])
    monkeypatch.setattr(rpn, "load_env", lambda path: None)   # 실제 .env 읽지 않는다
    monkeypatch.setattr(rpn, "subprocess", _fake_subprocess(rc))
    sent = []
    monkeypatch.setattr(rpn, "send_telegram", lambda msg: sent.append(msg) or True)

    assert rpn.main() == rc
    assert len(sent) == 1


def test_wrapper_timeout_is_reported_as_failure(monkeypatch):
    """타임아웃은 실패다 (이전엔 exit 0 이었음)."""
    monkeypatch.setattr(sys, "argv", ["run_pipeline_with_notify.py"])
    monkeypatch.setattr(rpn, "load_env", lambda path: None)
    sent = []

    class _Timeout:
        TimeoutExpired = subprocess.TimeoutExpired

        @staticmethod
        def run(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd=args, timeout=600)

    monkeypatch.setattr(rpn, "subprocess", _Timeout)
    monkeypatch.setattr(rpn, "send_telegram", lambda msg: sent.append(msg) or True)

    assert rpn.main() == 124
    assert len(sent) == 1


# --------------------------------------------------------------------------
# B-6 — exit code 전파 (프로세스 수준, 내부 파이프라인은 스텁)
# --------------------------------------------------------------------------

def _make_stub_project(tmp_path):
    """래퍼를 임시 프로젝트로 복사하고 내부 파이프라인을 스텁으로 교체한다.

    - 내부 파이프라인 = scripts/run_pipeline.py 스텁 (절대 실제 파이프라인을 돌리지 않는다)
    - pipeline 패키지는 심볼릭 링크로 참조 (실제 코드를 그대로 쓴다)
    - tmp 에 .env 가 없으므로 load_env 는 ~/.env.common 만 읽는다 (setdefault → 토큰 미설정)
    """
    proj = tmp_path / "proj"
    scripts = proj / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy2(SCRIPTS_DIR / "run_pipeline_with_notify.py",
                 scripts / "run_pipeline_with_notify.py")
    (proj / "pipeline").symlink_to(REPO_ROOT / "pipeline")
    (scripts / "run_pipeline.py").write_text(
        "import os, sys\n"
        "sys.stdout.write('[stub] 선정 뉴스: 1건\\n')\n"
        "sys.stdout.write('[stub] 생성 브리핑: 1건\\n')\n"
        "sys.exit(int(os.environ.get('STUB_RC', '0')))\n",
        encoding="utf-8")
    return proj


@pytest.mark.parametrize("rc", [0, 1, 5])
def test_wrapper_process_exit_code_matches_inner(tmp_path, rc):
    """래퍼 프로세스의 종료코드가 내부 파이프라인의 종료코드와 같다."""
    proj = _make_stub_project(tmp_path)
    env = dict(os.environ)
    env["STUB_RC"] = str(rc)
    env["TELEGRAM_BOT_TOKEN"] = ""   # 실제 발송 금지 (load_env 는 setdefault 라 덮어쓰지 않음)
    env["TELEGRAM_CHAT_ID"] = ""

    proc = subprocess.run(
        [sys.executable, str(proj / "scripts" / "run_pipeline_with_notify.py")],
        env=env, capture_output=True, text=True, timeout=120)

    assert proc.returncode == rc, proc.stderr


# --------------------------------------------------------------------------
# 알림 중복 방지
# --------------------------------------------------------------------------

def test_wrapper_sends_exactly_one_telegram_message(monkeypatch):
    """성공/실패 어느 쪽이든 래퍼는 텔레그램을 **1회만** 보낸다."""
    monkeypatch.setattr(sys, "argv", ["run_pipeline_with_notify.py"])
    monkeypatch.setattr(rpn, "load_env", lambda path: None)
    sent = []
    monkeypatch.setattr(rpn, "send_telegram", lambda msg: sent.append(msg) or True)

    monkeypatch.setattr(rpn, "subprocess",
                        _fake_subprocess(0, stdout="선정 뉴스: 1건\n생성 브리핑: 1건\n"))
    rpn.main()
    assert len(sent) == 1

    sent.clear()
    monkeypatch.setattr(rpn, "subprocess",
                        _fake_subprocess(1, stdout="선정 뉴스: 0건\n", stderr="boom"))
    rpn.main()
    assert len(sent) == 1


def test_early_alert_and_final_summary_are_distinct_messages(monkeypatch, notifier, fresh_count):
    """조기 경보와 최종 요약 알림은 서로 다른 메시지다 (같은 내용 중복 발송 아님)."""
    fresh_count(1)
    rp.check_candidate_depth()
    assert len(notifier) == 1

    monkeypatch.setattr(sys, "argv", ["run_pipeline_with_notify.py"])
    monkeypatch.setattr(rpn, "load_env", lambda path: None)
    sent = []
    monkeypatch.setattr(rpn, "send_telegram", lambda msg: sent.append(msg) or True)
    monkeypatch.setattr(rpn, "subprocess",
                        _fake_subprocess(0, stdout="선정 뉴스: 0건\n생성 브리핑: 0건\n"))

    rpn.main()

    assert len(sent) == 1
    assert sent[0] != notifier[0]
    assert "조기 경보" in notifier[0]


def test_wrapper_message_includes_pipeline_warning_reason(monkeypatch):
    """파이프라인 요약의 경고 사유가 텔레그램 알림 본문에 들어간다."""
    monkeypatch.setattr(sys, "argv", ["run_pipeline_with_notify.py"])
    monkeypatch.setattr(rpn, "load_env", lambda path: None)
    sent = []
    monkeypatch.setattr(rpn, "send_telegram", lambda msg: sent.append(msg) or True)
    stdout = (
        "[t] 선정 뉴스: 0건\n"
        "[t] 생성 브리핑: 0건\n"
        "  ⚠️  경고: 1건\n"
        "    - 후보 풀 부족: 신선 후보 1건 (최소 3건 필요)\n"
        "  ✅ 에러 없음\n"
    )
    monkeypatch.setattr(rpn, "subprocess", _fake_subprocess(0, stdout=stdout))

    rpn.main()

    assert len(sent) == 1
    assert "후보 풀 부족: 신선 후보 1건 (최소 3건 필요)" in sent[0]


def test_real_pipeline_summary_output_is_parsed_by_wrapper(monkeypatch, capsys,
                                                            notifier, fresh_count, tmp_path):
    """형식 계약 — run_pipeline 이 실제로 찍는 요약 출력이 래퍼 파서로 읽힌다."""
    fresh_count(1)
    state_path = tmp_path / ".collector_state.json"
    _write_state(state_path, status="aborted", reason="D1 가드 한도 초과",
                 at=datetime.now().astimezone().isoformat(), collected=0)
    monkeypatch.setattr(rp, "COLLECTOR_STATE_PATH", state_path)
    monkeypatch.setattr(rp, "step_news_selection", lambda: [])
    monkeypatch.setattr(rp, "step_briefing_with_log", lambda arts: (7, ""))
    monkeypatch.setattr(rp, "step_blog_link", lambda: {})
    monkeypatch.setattr(sys, "argv", [
        "run_pipeline.py", "--skip-thumbnails", "--skip-email", "--skip-deploy"])

    rp.main()
    output = capsys.readouterr().out

    warns = rpn._warning_lines(output)
    assert any("후보 풀 부족" in w for w in warns)
    assert any("수집 단계 이상: aborted" in w for w in warns)
    assert "후보 풀 부족" in rpn._warning_block(output)
