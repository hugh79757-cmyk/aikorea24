#!/usr/bin/env python3
"""Tests for weekly_blog_publisher.py"""

import json
import os
import sys
import tempfile
import pytest
from unittest.mock import patch

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
sys.path.insert(0, _PROJECT_ROOT)


SAMPLE_DEEP_DIVE = {
    "title": "EU vs 중국 AI 규제의 향방",
    "body": "## 대비의 발견\n\nEU와 중국이 정반대 방향으로.\n\n## 분석\n\n지정학적 경쟁.",
    "tags": ["weekly-analysis", "contrast", "규제"],
    "source_links": ["https://example.com/1", "https://example.com/2"],
}


class TestMakeSlug:
    """slug 생성 테스트."""

    def test_korean_title(self):
        """한국어 제목에서 slug 생성."""
        from scripts.weekly_blog_publisher import _make_slug
        slug = _make_slug("EU vs 중국 AI 규제의 향방")
        assert "eu" in slug
        assert "중국" in slug
        assert len(slug) <= 80

    def test_empty_title(self):
        """빈 제목은 기본 slug."""
        from scripts.weekly_blog_publisher import _make_slug
        slug = _make_slug("")
        assert slug == "weekly-contrast"


class TestPublishBlogPost:
    """블로그 포스트 발행 테스트."""

    def test_creates_file_with_frontmatter(self):
        """파일 생성 + frontmatter 포함."""
        from scripts.weekly_blog_publisher import publish_blog_post

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("scripts.weekly_blog_publisher.BLOG_DIR", tmpdir):
                path = publish_blog_post(SAMPLE_DEEP_DIVE)
                assert os.path.exists(path)
                assert path.endswith(".md")

                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()

                assert "---" in content
                assert 'title: "EU vs 중국 AI 규제의 향방"' in content
                assert "weekly-analysis" in content
                assert "## 대비의 발견" in content
                assert "https://example.com/1" in content

    def test_filename_format(self):
        """파일명 형식: weekly-contrast-YYYYMMDD-NNN-slug.md."""
        from scripts.weekly_blog_publisher import publish_blog_post

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("scripts.weekly_blog_publisher.BLOG_DIR", tmpdir):
                path = publish_blog_post(SAMPLE_DEEP_DIVE)
                basename = os.path.basename(path)
                assert basename.startswith("weekly-contrast-")
                assert basename.endswith(".md")

    def test_incremental_file_number(self):
        """같은 날짜에 파일이 있으면 번호 증가."""
        from scripts.weekly_blog_publisher import publish_blog_post, _next_file_number

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("scripts.weekly_blog_publisher.BLOG_DIR", tmpdir):
                path1 = publish_blog_post(SAMPLE_DEEP_DIVE)
                path2 = publish_blog_post(SAMPLE_DEEP_DIVE)
                assert path1 != path2
                # 두 번째 파일 번호가 더 높음
                import re
                num1 = int(re.search(r'-(\d{3})-', os.path.basename(path1)).group(1))
                num2 = int(re.search(r'-(\d{3})-', os.path.basename(path2)).group(1))
                assert num2 == num1 + 1


class TestPublishAll:
    """복수 발행 테스트."""

    def test_publishes_multiple(self):
        """여러 포스트 발행."""
        from scripts.weekly_blog_publisher import publish_all

        dives = [SAMPLE_DEEP_DIVE, dict(SAMPLE_DEEP_DIVE, title="두 번째 분석")]

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("scripts.weekly_blog_publisher.BLOG_DIR", tmpdir):
                paths = publish_all(dives)
                assert len(paths) == 2
                for p in paths:
                    assert os.path.exists(p)

    def test_empty_list(self):
        """빈 리스트 발행 시 빈 결과."""
        from scripts.weekly_blog_publisher import publish_all
        assert publish_all([]) == []


class TestPublishGate:
    """발행 게이트: 추천만 발행, 보류→drafts, 폐기→삭제."""

    def test_recommend_publishes_to_blog(self):
        """추천 → src/content/blog/에 발행."""
        from scripts.weekly_blog_publisher import publish_blog_post, BLOG_DIR

        dive = dict(SAMPLE_DEEP_DIVE)
        dive["quality_judgment"] = {"verdict": "추천", "issues": []}

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("scripts.weekly_blog_publisher.BLOG_DIR", tmpdir):
                with patch("scripts.weekly_blog_publisher.DRAFTS_DIR", os.path.join(tmpdir, "_drafts")):
                    path = publish_blog_post(dive)
                    assert path
                    assert os.path.exists(path)
                    assert "_drafts" not in path
                    # draft: false 확인
                    with open(path, "r") as f:
                        assert "draft: false" in f.read()

    def test_hold_saves_to_drafts(self):
        """보류 → _drafts/ 폴더에 저장."""
        from scripts.weekly_blog_publisher import publish_blog_post, DRAFTS_DIR

        dive = dict(SAMPLE_DEEP_DIVE)
        dive["quality_judgment"] = {"verdict": "보류", "issues": ["미검증 인용"]}

        with tempfile.TemporaryDirectory() as tmpdir:
            drafts_dir = os.path.join(tmpdir, "_drafts")
            with patch("scripts.weekly_blog_publisher.BLOG_DIR", tmpdir):
                with patch("scripts.weekly_blog_publisher.DRAFTS_DIR", drafts_dir):
                    path = publish_blog_post(dive)
                    assert path
                    assert drafts_dir in path
                    assert os.path.exists(path)
                    # draft: true 확인
                    with open(path, "r") as f:
                        assert "draft: true" in f.read()

    def test_disposed_does_not_save(self):
        """폐기 → 저장하지 않음."""
        from scripts.weekly_blog_publisher import publish_blog_post

        dive = dict(SAMPLE_DEEP_DIVE)
        dive["quality_judgment"] = {"verdict": "폐기", "issues": ["환각 인용"]}

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("scripts.weekly_blog_publisher.BLOG_DIR", tmpdir):
                path = publish_blog_post(dive)
                assert path == ""
                # 파일 없음 확인
                files = os.listdir(tmpdir)
                assert len(files) == 0

    def test_publish_all_skip_disposed(self):
        """publish_all: 폐기는 제외, 추천/보류만 처리."""
        from scripts.weekly_blog_publisher import publish_all

        dives = [
            dict(SAMPLE_DEEP_DIVE, title="추천 포스트",
                 quality_judgment={"verdict": "추천", "issues": []}),
            dict(SAMPLE_DEEP_DIVE, title="보류 포스트",
                 quality_judgment={"verdict": "보류", "issues": ["미검증"]}),
            dict(SAMPLE_DEEP_DIVE, title="폐기 포스트",
                 quality_judgment={"verdict": "폐기", "issues": ["환각"]}),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("scripts.weekly_blog_publisher.BLOG_DIR", tmpdir):
                with patch("scripts.weekly_blog_publisher.DRAFTS_DIR", os.path.join(tmpdir, "_drafts")):
                    paths = publish_all(dives)
                    # 추천 1 + 보류 1 = 2건 (폐기 1건 제외)
                    assert len(paths) == 2

    def test_publish_all_no_recommend_skips(self):
        """추천 0건이면 발행 스킵 로그."""
        from scripts.weekly_blog_publisher import publish_all

        dives = [
            dict(SAMPLE_DEEP_DIVE, title="보류만",
                 quality_judgment={"verdict": "보류", "issues": ["미검증"]}),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("scripts.weekly_blog_publisher.BLOG_DIR", tmpdir):
                with patch("scripts.weekly_blog_publisher.DRAFTS_DIR", os.path.join(tmpdir, "_drafts")):
                    paths = publish_all(dives)
                    # 보류 1건은 drafts에 저장되지만 paths에는 포함
                    assert len(paths) == 1
