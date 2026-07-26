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


class TestQualityChecklistBlocking:
    """Task 28.1-02: Quality checklist blocking logic exists in source."""

    def setup_method(self):
        with open(BLOG_DRAFT_PATH, encoding="utf-8") as f:
            source = f.read()
        self.source = source

    def test_quality_blocker_present(self):
        """Source contains the quality checklist blocker comment."""
        assert "모든 썸네일 품질 검증 실패 — 배포 차단" in self.source, (
            "Quality checklist blocker (hard block) not found in source"
        )

    def test_quality_blocker_sends_telegram(self):
        """Blocker path sends a Telegram alert."""
        assert "썸네일 전면 실패" in self.source, (
            "Telegram alert for total thumbnail failure not found in source"
        )

    def test_quality_blocker_returns_early(self):
        """Blocker path has a `return` statement to prevent deployment."""
        # Find the blocker comment and check there's a `return` after it
        idx = self.source.find("모든 썸네일 품질 검증 실패 — 배포 차단")
        assert idx != -1, "Blocker comment not found"
        tail = self.source[idx:]
        assert "return" in tail, (
            "No `return` found after quality blocker — deployment will proceed"
        )

    def test_quality_blocker_condition(self):
        """Blocker condition checks quality_passed == 0 and issues exist."""
        assert "quality_passed == 0" in self.source, (
            "Condition `quality_passed == 0` not found"
        )
        assert "len(quality_issues) > 0" in self.source, (
            "Condition `len(quality_issues) > 0` not found"
        )
