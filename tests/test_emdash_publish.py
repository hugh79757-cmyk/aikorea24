"""AIK24-EMDASH-01 — scripts/emdash_publish.py 테스트.

네트워크는 전부 monkeypatch (emdash04_migrate.api 를 갈아끼움).
"""
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import emdash04_migrate as em  # noqa: E402
import emdash_publish as ep  # noqa: E402


def _no_pat(monkeypatch):
    monkeypatch.delenv("EMDASH_AIKOREA24_API_TOKEN", raising=False)
    monkeypatch.delenv("EMDASH_PAT", raising=False)


def test_pat_from_env_only(monkeypatch):
    """PAT 는 환경변수에서만 읽는다 (코드 하드코딩 금지)."""
    _no_pat(monkeypatch)
    assert ep.get_pat() is None
    monkeypatch.setenv("EMDASH_AIKOREA24_API_TOKEN", '  "pat-xyz"  ')
    assert ep.get_pat() == "pat-xyz"


def test_no_pat_returns_none(monkeypatch):
    _no_pat(monkeypatch)
    assert ep.publish_post("t", "b") is None


def test_create_then_publish(monkeypatch):
    monkeypatch.setenv("EMDASH_AIKOREA24_API_TOKEN", "pat-xyz")
    calls = []

    def fake_api(path, method="GET", body=None):
        calls.append((path, method, body))
        if path.endswith("/publish"):
            return 200, {"data": {}}
        return 201, {"data": {"item": {"id": "p1", "slug": "hello-world"}}}

    monkeypatch.setattr(em, "api", fake_api)
    url = ep.publish_post("Hello", "본문", excerpt="설명",
                          featured_image="/images/x/thumbnail.webp",
                          published_at="2026-10-14T09:00:00+09:00")
    assert url == "https://emdash.aikorea24.kr/posts/hello-world"
    assert calls[0][0] == "/_emdash/api/content/posts"
    assert calls[0][1] == "POST"
    d = calls[0][2]["data"]
    assert d["title"] == "Hello"
    assert d["excerpt"] == "설명"
    # AIK24-EVAL-09(2026-10-15 커밋 8404cd26): '/' 로 시작하는 상대경로는
    # https://aikorea24.kr 로 절대화된다 — emdash 도메인에서 /images/... 는 404(실측).
    assert d["featured_image"] == "https://aikorea24.kr/images/x/thumbnail.webp"
    assert d["content"][0]["_type"] == "block"
    assert calls[1][0] == "/_emdash/api/content/posts/p1/publish"
    assert calls[1][2] == {"publishedAt": "2026-10-14T09:00:00+09:00"}


def test_datetime_published_at_serialized(monkeypatch):
    """yaml 가 date 를 datetime 으로 주면 isoformat 으로 직렬화돼야 한다."""
    import datetime
    monkeypatch.setenv("EMDASH_AIKOREA24_API_TOKEN", "pat-xyz")
    seen = {}

    def fake_api(path, method="GET", body=None):
        if path.endswith("/publish"):
            seen.update(body or {})
            return 200, {"data": {}}
        return 201, {"data": {"item": {"id": "p1", "slug": "s"}}}

    monkeypatch.setattr(em, "api", fake_api)
    ep.publish_post("t", "b", published_at=datetime.datetime(2026, 10, 14, 9, 0, 0))
    assert seen["publishedAt"] == "2026-10-14T09:00:00"


def test_create_failure_returns_none(monkeypatch):
    monkeypatch.setenv("EMDASH_AIKOREA24_API_TOKEN", "pat-xyz")
    monkeypatch.setattr(em, "api", lambda *a, **k: (400, {"error": "bad"}))
    assert ep.publish_post("t", "b") is None


def test_publish_failure_returns_none(monkeypatch):
    """create 는 성공하고 publish 가 실패하면 None — Astro 폴백으로 넘어간다."""
    monkeypatch.setenv("EMDASH_AIKOREA24_API_TOKEN", "pat-xyz")

    def fake_api(path, method="GET", body=None):
        if path.endswith("/publish"):
            return 500, {"error": "boom"}
        return 201, {"data": {"item": {"id": "p1", "slug": "s"}}}

    monkeypatch.setattr(em, "api", fake_api)
    assert ep.publish_post("t", "b") is None


def test_featured_image_absolutized():
    """AIK24-EVAL-09 계약 — 상대경로만 절대화하고, 절대 URL·dict 는 그대로 둔다."""
    assert ep._featured_image_data(None) is None
    assert ep._featured_image_data("") is None
    assert ep._featured_image_data("/images/x.webp") == "https://aikorea24.kr/images/x.webp"
    assert (ep._featured_image_data("https://cdn.example.com/x.webp")
            == "https://cdn.example.com/x.webp")
    assert ep._featured_image_data({"src": "/images/x.webp", "alt": "a"}) == {
        "src": "https://aikorea24.kr/images/x.webp", "alt": "a"}
    assert ep._featured_image_data({"src": ""}) is None


def test_no_featured_image_key_when_absent(monkeypatch):
    """featured_image 를 주지 않으면 키 자체가 없다(빈 값으로 덮어쓰지 않는다)."""
    monkeypatch.setenv("EMDASH_AIKOREA24_API_TOKEN", "pat-xyz")
    calls = []

    def fake_api(path, method="GET", body=None):
        calls.append((path, method, body))
        if path.endswith("/publish"):
            return 200, {"data": {}}
        return 201, {"data": {"item": {"id": "p1", "slug": "s"}}}

    monkeypatch.setattr(em, "api", fake_api)
    ep.publish_post("t", "b")
    assert "featured_image" not in calls[0][2]["data"]

def test_get_post_korean_slug_retries_percent_encoded(monkeypatch):
    """한글 slug 는 raw 요청이 http=0 으로 실패 → 인코딩 재시도로 id 를 얻는다.

    2026-10-17 실측: raw '무료-llm-beam-free-...' → http 0 / percent-encoding → 200.
    """
    monkeypatch.setenv("EMDASH_AIKOREA24_API_TOKEN", "pat-xyz")
    slug = "무료-llm-beam-free-테스트"
    calls = []

    def fake_api(path, method="GET", body=None):
        calls.append(path)
        if "%" in path:  # 인코딩 경로만 200
            return 200, {"data": {"item": {"id": "01ABC", "slug": slug}, "_rev": "r1"}}
        return 0, {"error": "UnicodeEncodeError"}

    monkeypatch.setattr(em, "api", fake_api)
    it = ep.get_post(slug)
    assert it is not None
    assert it.get("id") == "01ABC"      # id 승격
    assert len(calls) == 2 and "%" in calls[1]


def test_upsert_korean_slug_updates_by_id(monkeypatch):
    """조회가 되면 한글 slug 라도 CREATE 하지 않고 id 경로로 PUT 한다(중복 생성 방지)."""
    monkeypatch.setenv("EMDASH_AIKOREA24_API_TOKEN", "pat-xyz")
    slug = "무료-llm-beam-free-테스트"
    seen = []

    def fake_api(path, method="GET", body=None):
        seen.append((path, method))
        if "%" in path:
            return 200, {"data": {"item": {"id": "01ABC", "slug": slug}, "_rev": "r1"}}
        if method == "GET":
            return 0, {"error": "unicode"}
        if path.endswith("/publish"):
            return 200, {"data": {}}
        return 200, {"data": {"item": {"id": "01ABC", "slug": slug}}}

    monkeypatch.setattr(em, "api", fake_api)
    url = ep.upsert_post(slug, "제목", "본문")
    assert url == "https://emdash.aikorea24.kr/posts/" + slug
    assert [p for p, m in seen if m == "PUT"] == ["/_emdash/api/content/posts/01ABC"], seen
    assert ("/_emdash/api/content/posts", "POST") not in seen, seen
