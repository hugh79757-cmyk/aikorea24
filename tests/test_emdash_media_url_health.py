"""tests/test_emdash_media_url_health.py

AIK24-EMDASH-15 — featured_image 미디어 URL 헬스체크의 순수 함수 검증.

배경 (2026-10-16): EmDash 미디어 URL `/_emdash/api/media/file/<X>.<ext>` 의 <X> 는
media.id 가 아니라 storage_key 다. media.id 로 만든 URL 2건만 404 였고 storage_key 로
바꾸면 200 이 됐다. 이 테스트는 그 판정 로직(추출·대체 URL 생성·분류)과, 저장값을 쓰는
SQL 리터럴 이스케이프를 네트워크·D1 없이 검증한다.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

import emdash15_media_url_health as h  # noqa: E402

PRE = "https://emdash.aikorea24.kr/_emdash/api/media/file/"


def test_extract_key_returns_filename():
    assert h.extract_key(PRE + "01M4Z863RB6XQAB0E420NADMXC.webp") == "01M4Z863RB6XQAB0E420NADMXC.webp"
    assert h.extract_key(PRE + "abc.PNG") == "abc.PNG"


def test_extract_key_tolerates_query_string():
    assert h.extract_key(PRE + "abc.webp?v=2") == "abc.webp"


def test_extract_key_ignores_other_urls():
    assert h.extract_key("https://aikorea24.kr/images/x/thumbnail.webp") is None
    assert h.extract_key("") is None
    assert h.extract_key(None) is None


def test_fixed_src_swaps_key_keeps_prefix():
    old = PRE + "01M4Z863RB6XQAB0E420NADMXC.webp"
    new = h.fixed_src(old, "01M4Z862G3D1AY7Z4N9SYGC41R.webp")
    assert new == PRE + "01M4Z862G3D1AY7Z4N9SYGC41R.webp"
    # storage_key 가 없으면 만들지 않는다 (추측 URL 금지)
    assert h.fixed_src(old, None) is None
    assert h.fixed_src("https://aikorea24.kr/x.webp", "k.webp") is None


def test_classify_ok_fixable_broken():
    assert h.classify("200", None) == "ok"
    assert h.classify("404", "01M4Z862.webp", "200") == "fixable"
    assert h.classify("404", "01M4Z862.webp", "404") == "broken"
    assert h.classify("404", None, None) == "broken"       # media 행 없음
    assert h.classify("ERR", "k.webp", "200") == "fixable"  # 네트워크 오류라도 대체안이 살아 있으면


def test_sql_literal_escapes_quotes():
    assert h._lit("a'b") == "'a''b'"


def test_rows_unwraps_d1_http_shape():
    resp = {"result": [{"results": [{"slug": "x"}, {"slug": "y"}]}]}
    assert [r["slug"] for r in h._rows(resp)] == ["x", "y"]
    assert h._rows({}) == []
    assert h._rows(None) == []
