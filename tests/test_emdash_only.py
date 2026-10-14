"""AIK24-EMDASH-03: Astro 저장 제거, EmDash 단독 발행.

1. `_save_file` 이 src/content/blog/ 에 파일을 만들지 않는다
2. `_add_image_to_frontmatter` 가 디스크가 아니라 인메모리 초안을 고친다
3. 발행 성공 → D1 deep_dive_url / 코멘트 링크가 EmDash URL 로 연결된다
4. 발행 실패 → 폴백 없고 파일도 생기지 않는다
"""
import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import blog_draft_generator as b  # noqa: E402
import emdash04_migrate as em  # noqa: E402

BODY = "본문 문장입니다. " * 120  # 1,000자 품질 게이트 통과용
GPT_OUT = "TITLE: 테스트 제목\n---\n\n" + BODY


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(b, "PROJECT_DIR", str(tmp_path))
    b._EMDASH_PENDING.clear()
    yield
    b._EMDASH_PENDING.clear()


def _make(tmp_path, articles=None, monkeypatch=None):
    """save_draft 경로로 생성 (D1 브리핑 조회는 차단)."""
    if monkeypatch is not None:
        monkeypatch.setattr(b, "query_d1", lambda sql: [])
    return b.save_draft(GPT_OUT, "키워드", 1, "2026-10-14", articles)


def test_save_file_writes_nothing_to_disk(tmp_path):
    """핵심: src/content/blog/ 아래 .md 가 하나도 생기지 않는다."""
    fp, seo_title = b._save_file(GPT_OUT, "키워드", 1, "2026-10-14")
    blog_dir = tmp_path / "src" / "content" / "blog"
    assert list(blog_dir.glob("*.md")) == []
    assert not Path(fp).exists()
    assert seo_title == "테스트 제목"
    assert fp in b._EMDASH_PENDING
    assert "TITLE" not in b._EMDASH_PENDING[fp]["md"]


def test_add_image_mutates_memory_not_disk(tmp_path, monkeypatch):
    """image: 는 파일이 아니라 인메모리 초안에 들어간다."""
    monkeypatch.setattr(b, "is_placeholder_copy", lambda p: False)
    fp, _ = _make(tmp_path)
    b._add_image_to_frontmatter(fp, "/images/foo/thumbnail.webp")
    md = b._EMDASH_PENDING[fp]["md"]
    assert 'image: "/images/foo/thumbnail.webp"' in md
    assert not Path(fp).exists()
    # 앞선 실행과 같은 게이트: image: 가 이미 있으면 중복 주입 안 함
    b._add_image_to_frontmatter(fp, "/images/bar/thumbnail.webp")
    assert "/images/bar/" not in b._EMDASH_PENDING[fp]["md"]


def test_publish_links_d1_with_emdash_url(tmp_path, monkeypatch):
    """발행 성공 → deep_dive_url 과 코멘트 링크가 EmDash URL 로 연결된다."""
    seen = {}

    def fake_api(path, method="GET", body=None):
        seen["path"] = path
        if path.endswith("/publish"):
            return 200, {"data": {}}
        seen["body"] = body
        return 201, {"data": {"item": {"id": "p1", "slug": "s1"}}}

    monkeypatch.setattr(em, "api", fake_api)
    links = []
    monkeypatch.setattr(b, "update_deep_dive_url", lambda nid, url: links.append(("dd", nid, url)) or True)
    monkeypatch.setattr(b, "append_comment_link", lambda nid, url: links.append(("cm", nid, url)) or True)
    monkeypatch.setenv("EMDASH_PAT", "test-token")

    fp, title = _make(tmp_path, articles=[{"id": 42, "v2_tag": "free-llm"}], monkeypatch=monkeypatch)
    b._publish_generated_to_emdash([(fp, title, 1, 1)])

    url = "https://emdash.aikorea24.kr/posts/s1"
    assert seen["path"].endswith("/p1/publish")
    assert seen["body"]["data"]["title"] == "테스트 제목"
    assert links == [("dd", 42, url), ("cm", 42, url)]
    assert not Path(fp).exists()


def test_publish_failure_has_no_fallback(tmp_path, monkeypatch):
    """발행 실패 시 Astro 폴백도 D1 연결도 없다 (EmDash 단독)."""
    monkeypatch.setattr(em, "api", lambda p, method="GET", body=None: (500, {"error": "boom"}))
    monkeypatch.setattr(b, "update_deep_dive_url", lambda nid, url: pytest.fail("연결되면 안 됨"))
    monkeypatch.setenv("EMDASH_PAT", "test-token")

    fp, title = _make(tmp_path, articles=[{"id": 42}], monkeypatch=monkeypatch)
    b._publish_generated_to_emdash([(fp, title, 1, 1)])

    assert not Path(fp).exists()
    assert list((tmp_path / "src").rglob("*.md")) == []