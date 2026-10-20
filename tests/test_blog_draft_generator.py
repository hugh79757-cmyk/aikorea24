"""
Tests for blog_draft_generator.py — Phase 28.1

Focus:
1. Import scoping (UnboundLocalError regression)
2. Module-level DEEPSEEK_POOL availability
3. py_compile sanity
"""

import ast
import py_compile
import sys
from pathlib import Path

import pytest

# Path to the target module
SCRIPT_DIR = Path(__file__).resolve().parent.parent / "scripts"
BLOG_DRAFT_PATH = SCRIPT_DIR / "blog_draft_generator.py"


# ── helpers ──────────────────────────────────────────────────────────

def _get_function_imports(tree: ast.AST, func_name: str) -> list[ast.ImportFrom]:
    """Return all `from X import Y` nodes inside a named function."""
    results = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            for child in ast.walk(node):
                if isinstance(child, ast.ImportFrom):
                    results.append(child)
    return results


def _get_module_imports(tree: ast.AST) -> list[ast.ImportFrom]:
    """Return all top-level `from X import Y` nodes."""
    return [n for n in ast.iter_child_nodes(tree) if isinstance(n, ast.ImportFrom)]


# ── tests ────────────────────────────────────────────────────────────

class TestImportScoping:
    """Task 28.1-01: Verify UnboundLocalError fix — no function-level
    `from auto_thumbnail import process_thumbnail` inside main()."""

    def setup_method(self):
        with open(BLOG_DRAFT_PATH, encoding="utf-8") as f:
            self.tree = ast.parse(f.read())

    def test_no_function_level_process_thumbnail_import(self):
        """No `from auto_thumbnail import process_thumbnail` inside main()."""
        main_imports = _get_function_imports(self.tree, "main")
        offending = [
            n for n in main_imports
            if getattr(n, "module", "") == "auto_thumbnail"
            and any(
                alias.name == "process_thumbnail"
                for alias in n.names
            )
        ]
        assert len(offending) == 0, (
            f"main() contains `from auto_thumbnail import process_thumbnail` "
            f"at line {offending[0].lineno} — UnboundLocalError risk"
        )

    def test_module_level_has_deepseek_pool(self):
        """DEEPSEEK_POOL is imported at module level from auto_thumbnail."""
        top_imports = _get_module_imports(self.tree)
        auto_thumb_imports = [
            n for n in top_imports
            if getattr(n, "module", "") == "auto_thumbnail"
        ]
        assert len(auto_thumb_imports) == 1, (
            f"Expected exactly 1 module-level `from auto_thumbnail import ...`, "
            f"found {len(auto_thumb_imports)}"
        )
        names = [alias.name for alias in auto_thumb_imports[0].names]
        assert "DEEPSEEK_POOL" in names, (
            f"DEEPSEEK_POOL not in module-level auto_thumbnail imports: {names}"
        )

    def test_no_function_level_deepseek_pool_import(self):
        """No `from auto_thumbnail import DEEPSEEK_POOL` inside main()."""
        main_imports = _get_function_imports(self.tree, "main")
        offending = [
            n for n in main_imports
            if getattr(n, "module", "") == "auto_thumbnail"
        ]
        assert len(offending) == 0, (
            f"main() contains `from auto_thumbnail import ...` "
            f"at line {offending[0].lineno} — UnboundLocalError risk"
        )


class TestModuleCompiles:
    """Task 28.1-01 & 28.1-04: py_compile sanity."""

    def test_py_compile_passes(self):
        """blog_draft_generator.py compiles without syntax or scoping errors."""
        try:
            py_compile.compile(str(BLOG_DRAFT_PATH), doraise=True)
        except py_compile.PyCompileError as e:
            pytest.fail(f"py_compile failed: {e}")


class TestQualityChecklistPerPost:
    """AIK24-PIPE-06 Phase A: 썸네일 게이트는 글 단위로 처리한다.

    이전 계약(Task 28.1-02)은 "생성된 글 전체의 썸네일이 실패하면 return 해서 배포 차단" 이었다.
    그 return 이 5c(EmDash 발행) **이전**에 함수를 끝내서, 초안이 메모리에서 유실되게
    만들었다(2026-10-20 09:30 minimax 초안 실증). 이제 계약은:
      · 썸네일 판정 = 글 단위 (classify_thumbnails)
      · 썸네일 실패 글만 hold 로 초안 보존 + 발행 보류 (hold_thumbnail_failures)
      · 전면 차단 return 없음
    """

    def setup_method(self):
        with open(BLOG_DRAFT_PATH, encoding="utf-8") as f:
            source = f.read()
        self.source = source

    def test_no_blanket_blocking_return(self):
        """전면 차단 return 이 남아있으면 안 된다 (초안 유실 재발 방지)."""
        assert "모든 썸네일 품질 검증 실패 — 배포 차단" not in self.source, (
            "블록킹 return 이 되살아나면 5c 이전에 함수가 끝나 초안이 유실된다"
        )

    def test_per_post_classification_exists(self):
        """글 단위 썸네일 판정 함수가 있어야 한다."""
        assert "def classify_thumbnails(" in self.source
        assert "def hold_thumbnail_failures(" in self.source

    def test_failed_post_is_held_not_dropped(self):
        """실패 글은 hold 로 초안을 보존한다 (초안이 사라지지 않아야 한다)."""
        assert "_quality_gate.hold(" in self.source
        idx = self.source.find("def hold_thumbnail_failures(")
        assert idx != -1
        body = self.source[idx:idx + 1200]
        assert "hold(" in body, "보류 글은 hold 로 초안을 보존해야 한다"

    def test_telegram_alert_mentions_hold_reason(self):
        """보류 알림에 사유가 포함되어야 한다."""
        assert "썸네일 미달" in self.source, "보류 알림 문구가 없다"
        assert "발행 보류" in self.source, "발행 보류 사유 표기가 없다"

    def test_publish_list_filters_failed_posts(self):
        """실패 글은 발행 대상에서 빠지고 통과 글은 남는다."""
        assert "generated = [x for x in generated if x[0] not in bad_fps]" in self.source
