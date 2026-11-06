"""tests/test_blog_fact_guard.py

2026-11-06 사고 회귀 테스트 — 발행 글의 날짜 날조 + 광고/제휴 링크 유입.

실측 사고(2026-11-05 네이버클라우드 국방 AI 글):
  · 원문은 "김유원 대표는 3일 행사 기조연설" 인데, 생성 글은
    "2024년 5월 3일 개최된 국방·클라우드 융합 포럼" 이라고 6회 썼다 (2년 전 날짜 날조).
  · 원문 페이지 템플릿에서 긁힌 링크.coupang.com(제휴)·windows.microsoft.com/.../
    internet-explorer/download-ie(브라우저 안내) 링크가 '인용'으로 들어가
    MIN_LINKS(3개) 요구를 채우고 있었다.

계약:
  1. 본문 연도는 원문(제목·설명) 또는 올해에 근거해야 한다. 아니면 게이트 미달.
  2. 광고·제휴·브라우저 업그레이드 링크는 본문에 있으면 게이트 미달.
  3. 링크 수집(collect_real_links)에서 그런 링크는 애초에 후보로 올리지 않는다.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import blog_quality_gate as gate  # noqa: E402
import blog_draft_generator as bdg  # noqa: E402


DATE_MD = """## 본문
네이버클라우드는 2024년 5월 3일 개최된 국방·클라우드 융합 포럼에서 김유원 대표의
기조연설을 통해 "미래 강군은 AI"라는 비전을 제시했습니다.
"""
SRC_3IL = "김유원 네이버클라우드 대표는 3일 행사 기조연설을 통해 국방 인공지능(AI)의 안전한 운용을 제안했다."


def test_ungrounded_year_is_flagged():
    """원문에 없는 2024년 → 게이트 미달 (2026-11-05 실측 그대로)."""
    issues = gate.date_grounding_issues(DATE_MD, SRC_3IL, current_year="2026")
    assert len(issues) == 1, issues
    assert "2024" in issues[0]
    assert "원문에 없는 연도" in issues[0]


def test_grounded_year_passes():
    """원문에 2024 가 있으면 통과한다."""
    src = "이 사업은 2024년 10월에 시작됐다고 회사가 밝혔다."
    md = "## 본문\n해당 서비스는 2024년 10월 착수됐다."
    assert gate.date_grounding_issues(md, src, current_year="2026") == []


def test_current_year_is_allowed():
    """올해 표기는 원문에 없어도 허용 (기사 자체가 오늘 사건)."""
    md = "## 본문\n김유원 대표는 2026년 11월 3일 행사에서 기조연설을 했다."
    assert gate.date_grounding_issues(md, SRC_3IL, current_year="2026") == []


def test_nbsp_dates_are_detected():
    """실측 데이터는 '2024년\\u00a05월\\u00a03일' 처럼 NBSP 로 들어왔다."""
    md = "## 본문\n2024년\u00a05월\u00a03일 개최된 포럼에서 발표했다."
    issues = gate.date_grounding_issues(md, SRC_3IL, current_year="2026")
    assert issues and "2024" in issues[0]


def test_empty_source_skips_check():
    """원문 텍스트가 없으면 판정 불가 — 오탐을 만들지 않는다."""
    assert gate.date_grounding_issues(DATE_MD, "", current_year="2026") == []
    assert gate.date_grounding_issues(DATE_MD, None, current_year="2026") == []


def test_junk_links_are_flagged():
    """쿠팡 제휴 링크·IE 다운로드 링크는 게이트 미달."""
    md = ("## 본문\n[쿠팡 구독 서비스 예시](https://link.coupang.com/a/cAgdK8) 와 "
          "[브라우저](http://windows.microsoft.com/ko-kr/internet-explorer/download-ie) ")
    issues = gate.junk_link_issues(md)
    assert len(issues) == 1, issues
    assert "광고·제휴" in issues[0]


def test_normal_source_links_pass():
    """원문·공식 출처 링크는 통과."""
    md = ("## 본문\n[원문](https://www.cbci.co.kr/news/articleView.html?idxno=623088) "
          "[로이터](https://www.reuters.com/markets/us) ")
    assert gate.junk_link_issues(md) == []


def test_screen_extended_wires_both_checks():
    """screen_extended 가 두 검사를 실제로 호출한다 (네트워크 검사는 끈다)."""
    md = ("## 본문\n2024년 5월 3일 포럼에서 발표했다. "
          "[쿠팡](https://link.coupang.com/a/cAgdK8)\n" + "내용 " * 400)
    issues = gate.screen_extended(md, verify_links=False, source_text=SRC_3IL)
    assert any("원문에 없는 연도" in i for i in issues), issues
    assert any("광고·제휴" in i for i in issues), issues


def test_collect_real_links_drops_junk(monkeypatch):
    """링크 수집 단계에서 제휴·브라우저 링크를 후보에서 제외한다."""
    html = ('<a href="https://link.coupang.com/a/cAgdK8">광고</a>'
            '<a href="http://windows.microsoft.com/ko-kr/internet-explorer/download-ie">IE</a>'
            '<a href="https://www.reuters.com/markets/us/ai-chips">기사</a>')
    monkeypatch.setattr(gate, '_fetch', lambda url, timeout=10.0: html)
    monkeypatch.setattr(gate, '_verify_many', lambda urls, timeout=6.0, workers=6: {u: True for u in urls})
    gate._listing_cache.clear()
    links = gate.collect_real_links({'link': 'https://example.com/news/1'}, limit=5)
    urls = [l['url'] for l in links]
    assert all('coupang' not in u for u in urls), urls
    assert all('internet-explorer' not in u for u in urls), urls
    assert 'https://www.reuters.com/markets/us/ai-chips' in urls, urls


def test_source_text_of_collects_article_fields():
    """생성기 원문 텍스트 헬퍼 — 제목·원제목·설명을 합친다."""
    txt = bdg._source_text_of([{'title': '제목', 'original_title': 'Orig',
                                'description': '설명', 'source': '무시'}])
    assert '제목' in txt and 'Orig' in txt and '설명' in txt
    assert '무시' not in txt


# ------------------------------------------------ 참고 자료 링크 (2026-11-06)


def test_unlinked_reference_item_is_flagged():
    """'Cbci 뉴스 원문 보기'가 링크 없이 있으면 게이트 미달 (실측 사고)."""
    md = "## 참고 자료\n- Cbci 뉴스 원문 보기\n"
    issues = gate.reference_link_issues(md)
    assert len(issues) == 1, issues
    assert '링크 없는 항목' in issues[0]


def test_linked_reference_item_passes():
    md = "## 참고 자료\n- [Cbci 뉴스 원문 보기](https://www.cbci.co.kr/news/articleView.html?idxno=623088)\n"
    assert gate.reference_link_issues(md) == []


def test_reference_section_stops_at_next_heading():
    """본문 목록은 검사 대상이 아니다 — '## 참고 자료' 섹션만 본다."""
    md = ("## 참고 자료\n- [원문](https://a.example.com/x)\n"
          "## 마무리\n- 링크 없는 실행 항목\n")
    assert gate.reference_link_issues(md) == []


def test_restore_dangling_links_repairs_span_marks():
    """markDefs 에만 있고 span 이 참조하지 않는 링크를 복원한다(실측: 화면에 링크 미표시)."""
    import repair_emdash_fact_errors as R
    data = {"content": [{
        "_type": "block", "_key": "b1", "style": "normal", "listItem": "bullet",
        "markDefs": [{"_key": "l1", "_type": "link", "href": "https://www.cbci.co.kr/x"}],
        "children": [{"_type": "span", "_key": "s1", "text": "Cbci 뉴스 원문 보기", "marks": []}],
    }]}
    assert R.restore_dangling_links(data) == 1
    assert data["content"][0]["children"][0]["marks"] == ["l1"]
