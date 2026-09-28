"""validate_tool_url / strip_tracking_params 회귀 테스트.

배경: validate_tool_url()이 '?ref=producthunt' 포함 URL을 거부해
Product Hunt 소스 툴 88건의 url이 빈값으로 저장되던 버그(#url-backfill).
"""
from tools_collector import validate_tool_url, strip_tracking_params


class TestValidateToolUrl:
    def test_rejects_empty(self):
        assert validate_tool_url("") is False
        assert validate_tool_url(None) is False

    def test_accepts_product_url_with_tracking_param(self):
        assert validate_tool_url("https://www.pair2fa.com/?ref=producthunt") is True
        assert validate_tool_url(
            "https://openai.com/index/introducing-gpt-6-sol-and-luna/?ref=producthunt"
        ) is True
        assert validate_tool_url("https://kaiku.tech/en?utm_source=producthunt") is True

    def test_rejects_producthunt_listing_and_redirect(self):
        assert validate_tool_url("https://www.producthunt.com/products/pair2fa") is False
        assert validate_tool_url(
            "https://www.producthunt.com/r/p/1257374?app_id=123"
        ) is False

    def test_rejects_github_repo_but_allows_blob(self):
        assert validate_tool_url("https://github.com/x/y") is False
        assert validate_tool_url("https://github.com/x/y/blob/main/z.py") is True


class TestStripTrackingParams:
    def test_strips_ref(self):
        assert strip_tracking_params(
            "https://www.pair2fa.com/?ref=producthunt"
        ) == "https://www.pair2fa.com/"

    def test_strips_utm_keeps_meaningful_query(self):
        assert strip_tracking_params(
            "https://a.b/c?utm_source=ph&q=1&utm_medium=x"
        ) == "https://a.b/c?q=1"

    def test_no_query_unchanged(self):
        assert strip_tracking_params("https://a.b/c") == "https://a.b/c"
