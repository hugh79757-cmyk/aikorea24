"""AIK24-STATE-GUARD-01 — state.md 안전 도구 3종 테스트.

사고 2건(2026-10-14 f6ed99a8: 6,559→25줄 / 2026-10-17 02c5da8f: 2,811→53줄)의
원인 관용구는 아래 한 줄이다.

    open(p,'w',encoding='utf-8').write(report + open(p,encoding='utf-8').read())

모드 'w' 가 인자 평가 전에 파일을 0바이트로 자르고, 그 다음 읽으므로 '' 가 붙는다.
이 테스트는 (1) 정상 경로에서 기존 내용이 전부 보존되는지, (2) 손실이 감지되면
쓰기를 거부하고 파일을 건드리지 않는지, (3) 사후 검증 실패 시 백업으로 복원되는지를
확인한다.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import state_guard as sg  # noqa: E402
import state_prepend as sp  # noqa: E402
import state_rotate as sr  # noqa: E402

OLD = """# state

## 2026-10-16 10:00 첫 항목 — 요약
본문 A
### 하위
A-1

## 2026-10-15 09:00 둘째 항목 — 요약
본문 B
"""

REPORT = """## 2026-10-17 12:30 새 작업 — 요약

### 한 일
- 새 내용

### 잔존 위험
- 없음
"""


def _write(tmp_path, name="state.md", text=OLD):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------- state_prepend

def test_prepend_top_keeps_every_old_heading(tmp_path):
    path = _write(tmp_path)
    stats = sp.apply_report(path, REPORT, bottom=False, backup=False)
    result = path.read_text(encoding="utf-8")
    assert sp.headings(result) == sp.headings(REPORT) + sp.headings(OLD)
    assert result.startswith("## 2026-10-17 12:30")
    assert "본문 A" in result and "본문 B" in result
    assert stats["before_lines"] == len(OLD.splitlines())
    assert stats["after_lines"] > stats["before_lines"]


def test_bottom_append_places_oldest_last(tmp_path):
    path = _write(tmp_path)
    sp.apply_report(path, REPORT, bottom=True, backup=False)
    result = path.read_text(encoding="utf-8")
    assert sp.headings(result) == sp.headings(OLD) + sp.headings(REPORT)
    assert "본문 B" in result.split("## 2026-10-17 12:30")[0]


def test_build_on_empty_target_returns_report(tmp_path):
    path = _write(tmp_path, text="")
    sp.apply_report(path, REPORT, backup=False)
    assert sp.headings(path.read_text(encoding="utf-8")) == sp.headings(REPORT)


def test_assert_no_loss_detects_missing_heading():
    with pytest.raises(sp.ContentLossError):
        sp.assert_no_loss(OLD, REPORT)


def test_assert_no_loss_detects_line_shrink_even_without_heading_loss():
    # 헤딩은 남았지만 본문만 사라진 경우도 손실로 본다
    shrunk = OLD.replace("A-1\n", "")
    assert set(sp.headings(shrunk)) == set(sp.headings(OLD))
    with pytest.raises(sp.ContentLossError):
        sp.assert_no_loss(OLD, shrunk)


def test_refuses_and_leaves_file_untouched_when_build_drops_content(tmp_path, monkeypatch):
    """사고 재현 — 합치기 단계가 기존 내용을 빠뜨리면 쓰지 않는다."""
    path = _write(tmp_path)
    before_mtime = path.stat().st_mtime_ns
    monkeypatch.setattr(sp, "build", lambda current, report, bottom=False: report)
    with pytest.raises(sp.ContentLossError):
        sp.apply_report(path, REPORT, backup=False)
    assert path.read_text(encoding="utf-8") == OLD
    assert path.stat().st_mtime_ns == before_mtime


def _write_report_only(target, text):
    """write_atomic 대체용 — REPORT 만 쓰는 (의도적으로 깨진) 쓰기 함수."""
    with open(target, "w", encoding="utf-8") as fh:
        fh.write(text)


def test_post_write_verification_restores_backup(tmp_path, monkeypatch):
    """쓰기 자체가 깨졌을 때(디스크 검증 실패) 백업으로 되돌린다."""
    path = _write(tmp_path)
    monkeypatch.setattr(sp, "write_atomic", lambda target, text: _write_report_only(target, REPORT))
    with pytest.raises(sp.ContentLossError):
        sp.apply_report(path, REPORT, backup=True)
    assert path.read_text(encoding="utf-8") == OLD


def test_duplicate_heading_detected(tmp_path):
    path = _write(tmp_path, text=OLD + "\n" + REPORT)
    stats = sp.apply_report(path, REPORT, backup=False)
    assert stats["duplicate_headings"] == ["## 2026-10-17 12:30 새 작업 — 요약"]


def test_dry_run_does_not_write(tmp_path):
    path = _write(tmp_path)
    stats = sp.apply_report(path, REPORT, dry_run=True)
    assert stats["dry_run"] is True
    assert path.read_text(encoding="utf-8") == OLD


def test_concurrent_modification_aborts(tmp_path, monkeypatch):
    """읽은 뒤 쓰기 직전 외부 변경이 있으면 중단한다."""
    path = _write(tmp_path)
    real_build = sp.build

    def build_then_tamper(current, report, bottom=False):
        path.write_text(OLD + "\n## 2026-10-17 12:00 외부 세션 기록\n", encoding="utf-8")
        return real_build(current, report, bottom=bottom)

    monkeypatch.setattr(sp, "build", build_then_tamper)
    with pytest.raises(sp.ContentLossError):
        sp.apply_report(path, REPORT, backup=False)
    assert "외부 세션 기록" in path.read_text(encoding="utf-8")


def test_backup_file_naming(tmp_path):
    path = _write(tmp_path)
    stats = sp.apply_report(path, REPORT, backup=True)
    backup = stats["backup"]
    assert backup and backup.startswith(str(path) + ".bak.")
    assert "본문 A" in open(backup, encoding="utf-8").read()


def test_stats_only_reports_oldest_and_newest(tmp_path):
    path = _write(tmp_path)
    info = sp.stats_only(path)
    assert info["lines"] == len(OLD.splitlines())
    assert info["headings"] == 2
    assert info["newest"].startswith("## 2026-10-16")
    assert info["oldest"].startswith("## 2026-10-15")


# ------------------------------------------------------------------ state_guard

def test_guard_classify_shrink_at_threshold():
    assert sg.classify(3000, 3010, 100) == ("ok", 10)
    assert sg.classify(3000, 2901, 100)[0] == "ok"      # 임계 미만 감소는 통과
    assert sg.classify(3000, 2900, 100) == ("shrink", -100)  # 임계 도달 시 차단
    assert sg.classify(3000, 2899, 100)[0] == "shrink"
    assert sg.classify(2811, 53, 100) == ("shrink", -2758)
    assert sg.classify(None, 100, 100)[0] == "unknown"
    assert sg.classify(100, None, 100)[0] == "unknown"


def test_guard_count_lines_real_repo_refs():
    """HEAD 커밋본 기준 — 작업 트리 상태(복구/편집)와 무관하게 검증한다."""
    import subprocess

    committed = subprocess.run(
        ["git", "show", "HEAD:docs/state.md"],
        capture_output=True,
        text=True,
        cwd=str(sr.REPO_ROOT),
    ).stdout
    assert sg.count_lines("HEAD") == len(committed.splitlines())
    assert sg.count_lines("no-such-ref-xyz") is None


def test_guard_bypass_env(monkeypatch):
    monkeypatch.setenv(sg.BYPASS_ENV, "1")
    assert sg.is_bypassed() is True
    monkeypatch.setenv(sg.BYPASS_ENV, "0")
    assert sg.is_bypassed() is False
    monkeypatch.delenv(sg.BYPASS_ENV, raising=False)
    assert sg.is_bypassed() is False


def test_guard_shrink_via_cli_exit_code(capsys, monkeypatch):
    """실제 사고 재현 — old=HEAD(3011줄), new=f6ed99a8(25줄) 이면 exit 1."""
    monkeypatch.delenv(sg.BYPASS_ENV, raising=False)
    code = sg.main(["--old", "HEAD", "--new", "f6ed99a8", "--threshold", "100"])
    assert code == 1
    err = capsys.readouterr().err
    assert "push 중단" in err


def test_guard_increase_passes(capsys, monkeypatch):
    monkeypatch.delenv(sg.BYPASS_ENV, raising=False)
    code = sg.main(["--old", "f6ed99a8", "--new", "HEAD", "--threshold", "100"])
    assert code == 0


# ----------------------------------------------------------------- state_rotate

SAMPLE = """# state (preamble)

## 2026-10-17 12:00 최신 항목
본문 최신

## 2026-08-25 09:00 오래된 항목
본문 오래됨

## 진행 중 (2026-10-17, 날짜 없는 헤딩)
표식

## 2026-08-10 08:00 더 오래된 항목
본문 더 오래됨
"""


def test_split_blocks_keeps_preamble_and_all_blocks():
    preamble, blocks = sr.split_blocks(SAMPLE)
    assert preamble.startswith("# state (preamble)")
    assert len(blocks) == 4
    assert blocks[0][0].startswith("## 2026-10-17 12:00")
    assert "본문 더 오래됨" in blocks[3][1]


def test_plan_rotation_moves_only_old_dated_blocks():
    _, blocks = sr.split_blocks(SAMPLE)
    keep, move = sr.plan_rotation(blocks, days=30, today=__import__("datetime").date(2026, 10, 17))
    assert [h[:30] for h, _ in move] == [
        "## 2026-08-25 09:00 오래된 항목",
        "## 2026-08-10 08:00 더 오래된 항목",
    ]
    kept = " ".join(h for h, _ in keep)
    assert "## 2026-10-17 12:00" in kept         # 30일 이내 → 유지
    assert "## 진행 중" in kept                   # 날짜 없음 → 유지


def test_rotation_preserves_all_headings(tmp_path):
    target = tmp_path / "state.md"
    target.write_text(SAMPLE, encoding="utf-8")
    before = sr.heading_counter([SAMPLE])
    result = sr.apply_rotation(target, days=30, apply=True)
    after_texts = [target.read_text(encoding="utf-8")]
    for month in result["archives"]:
        after_texts.append((tmp_path / "state-archive" / f"{month}.md").read_text(encoding="utf-8"))
    assert sr.heading_counter(after_texts) == before
    assert result["move"] == 2
    assert "본문 더 오래됨" not in target.read_text(encoding="utf-8")


def test_rotation_dry_run_writes_nothing(tmp_path):
    target = tmp_path / "state.md"
    target.write_text(SAMPLE, encoding="utf-8")
    result = sr.apply_rotation(target, days=30, apply=False)
    assert result["applied"] is False
    assert target.read_text(encoding="utf-8") == SAMPLE
    assert not (tmp_path / "state-archive").exists()


def test_rotation_pointer_is_idempotent(tmp_path):
    target = tmp_path / "state.md"
    target.write_text(SAMPLE, encoding="utf-8")
    sr.apply_rotation(target, days=30, apply=True)
    first = target.read_text(encoding="utf-8")
    sr.apply_rotation(target, days=30, apply=True)
    second = target.read_text(encoding="utf-8")
    assert first.count(sr.POINTER_PREFIX) == 1
    assert second.count(sr.POINTER_PREFIX) == 1
    assert first == second


def test_rotation_archive_prepends_newer_entries(tmp_path):
    """나중에 내려간 항목이 아카이브에서 더 위(최신)에 있어야 한다."""
    target = tmp_path / "state.md"
    target.write_text(SAMPLE, encoding="utf-8")
    sr.apply_rotation(target, days=30, apply=True)
    archive_path = tmp_path / "state-archive" / "2026-08.md"
    assert archive_path.read_text(encoding="utf-8").startswith("## 2026-08-25 09:00")

    # 두 번째 회전 — 8월 30일 항목이 추가로 내려간다
    text = target.read_text(encoding="utf-8")
    text = text.replace(
        "## 2026-10-17 12:00 최신 항목",
        "## 2026-10-17 12:00 최신 항목\n본문 최신\n\n## 2026-08-30 09:00 조금 오래된 항목\n본문 조금 오래됨",
    )
    target.write_text(text, encoding="utf-8")
    result = sr.apply_rotation(target, days=30, apply=True)
    assert result["move"] == 1
    archive = archive_path.read_text(encoding="utf-8")
    assert archive.index("## 2026-08-30 09:00") < archive.index("## 2026-08-25 09:00")


# ------------------------------------------- state_prepend: 진행 중 표식 제거

MARKER = "## 진행 중 (2026-10-17, AIK24-EMDASH-01)"

STATE_WITH_MARKER = (
    "# state\n\n"
    + MARKER
    + "\n\n## 2026-10-16 10:00 첫 항목 — 요약\n본문 A\n\n## 2026-10-15 09:00 둘째 항목 — 요약\n본문 B\n"
)


def test_remove_headings_drops_marker_and_following_blank():
    new_text, removed = sp.remove_headings(STATE_WITH_MARKER, [MARKER])
    assert removed == [MARKER, ""]
    assert MARKER not in new_text
    assert sp.headings(new_text) == sp.headings(STATE_WITH_MARKER)[1:]
    assert "본문 A" in new_text and "본문 B" in new_text


def test_remove_headings_requires_exact_line_match():
    new_text, removed = sp.remove_headings(STATE_WITH_MARKER, ["## 진행 중"])
    assert removed == []
    assert new_text == STATE_WITH_MARKER


def test_apply_removal_refuses_when_marker_absent(tmp_path):
    path = _write(tmp_path)  # 표식 없는 OLD
    with pytest.raises(ValueError):
        sp.apply_removal(path, [MARKER], backup=False)
    assert path.read_text(encoding="utf-8") == OLD


def test_apply_removal_replaces_marker_with_report_and_keeps_old_headings(tmp_path):
    path = _write(tmp_path, text=STATE_WITH_MARKER)
    stats = sp.apply_removal(path, [MARKER], backup=True, report_text=REPORT)
    result = path.read_text(encoding="utf-8")
    assert result.startswith("## 2026-10-17 12:30 새 작업 — 요약")
    assert MARKER not in result
    assert sp.headings(result) == sp.headings(REPORT) + sp.headings(OLD)
    assert stats["removed_lines"] == [MARKER, ""]
    assert stats["backup"] and "본문 A" in open(stats["backup"], encoding="utf-8").read()


def test_apply_removal_dry_run_writes_nothing(tmp_path):
    path = _write(tmp_path, text=STATE_WITH_MARKER)
    stats = sp.apply_removal(path, [MARKER], dry_run=True)
    assert stats["dry_run"] is True
    assert stats["removed_lines"] == [MARKER, ""]
    assert path.read_text(encoding="utf-8") == STATE_WITH_MARKER


def test_apply_removal_restores_backup_when_write_is_broken(tmp_path, monkeypatch):
    """쓰기가 REPORT 만 남긴 경우 — 디스크 재검사가 잡아 백업으로 복원한다."""
    path = _write(tmp_path, text=STATE_WITH_MARKER)
    monkeypatch.setattr(sp, "write_atomic", lambda target, text: _write_report_only(target, REPORT))
    with pytest.raises(sp.ContentLossError):
        sp.apply_removal(path, [MARKER], backup=True)
    assert path.read_text(encoding="utf-8") == STATE_WITH_MARKER


def test_apply_removal_refuses_to_empty_the_file(tmp_path):
    path = _write(tmp_path, name="only_marker.md", text=MARKER + "\n")
    with pytest.raises(sp.ContentLossError):
        sp.apply_removal(path, [MARKER], backup=False)
    assert path.read_text(encoding="utf-8") == MARKER + "\n"


def test_apply_removal_removes_every_occurrence(tmp_path):
    text = STATE_WITH_MARKER + "\n" + MARKER + "\n\n## 2026-10-14 09:00 셋째\n본문 C\n"
    path = _write(tmp_path, text=text)
    stats = sp.apply_removal(path, [MARKER], backup=False)
    result = path.read_text(encoding="utf-8")
    assert MARKER not in result
    assert "본문 C" in result
    assert stats["removed_lines"].count(MARKER) == 2


def test_apply_removal_refuses_unexpected_line_loss(tmp_path, monkeypatch):
    """표식이 아닌 본문 한 줄이 사라져도 거부한다 (multiset 검증)."""
    path = _write(tmp_path, text=STATE_WITH_MARKER)
    real_remove = sp.remove_headings

    def sneaky(text, needles):
        new_text, removed = real_remove(text, needles)
        return new_text.replace("본문 A\n", ""), removed

    monkeypatch.setattr(sp, "remove_headings", sneaky)
    with pytest.raises(sp.ContentLossError):
        sp.apply_removal(path, [MARKER], backup=False)
    assert "본문 A" in path.read_text(encoding="utf-8")


def test_cli_remove_heading_exit_codes(tmp_path):
    path = _write(tmp_path, text=STATE_WITH_MARKER)
    assert sp.main(["--target", str(path), "--remove-heading", MARKER, "--no-backup"]) == sp.EXIT_OK
    assert MARKER not in path.read_text(encoding="utf-8")
    # 대상이 이미 없으면 거부 (exit 2) — 조용히 성공하지 않는다
    assert sp.main(["--target", str(path), "--remove-heading", MARKER, "--no-backup"]) == sp.EXIT_REFUSED


def test_cli_report_still_requires_report_or_remove(tmp_path):
    path = _write(tmp_path)
    with pytest.raises(SystemExit):
        sp.main(["--target", str(path)])
