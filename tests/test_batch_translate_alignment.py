#!/usr/bin/env python3
"""AIK24-TRANSLATE-ALIGN-01 — 배치 번역 제목 밀림(교차 오염) 회귀 테스트

배경(2026-11-19 실사고):
  05:30 수집분 news 61933~61940 의 **제목이 한 칸씩 밀렸다.**
  · 61939 원제목 "The AI Hype Index: AI is everywhere" ← 제목 "AI 코가 인간만큼 뛰어나다고…"
  · 61940 원제목 "This smell startup says its AI nose is as good as a human's"
        ← 제목 "오픈소스 진영, 젠슨 황의 복귀를 원해"
  설명(DESC)은 자기 기사 것이 정확히 붙었는데 제목만 밀려서, 브리핑 페이지·뉴스레터·
  EmDash 심층글이 "제목과 내용이 완전히 다른" 상태로 발행됐다.

원인:
  `batch_translate()` 가 응답의 TITLE 줄과 DESC 줄을 **각각 순서대로** 모아
  같은 인덱스로 짝지었다. 응답에서 한 줄이 빠지거나 하나가 더 생기는 순간
  이후 모든 기사에 다른 기사의 제목이 붙고, DESC 배열은 따로 놀아 불일치가 숨는다.

검증 대상: api_test/news_collector.py::parse_batch_translation() / batch_translate()
  · 번호를 무시하고 순서대로 붙이지 않는다 (본 사고의 핵심)
  · 한 항목이 빠져도 나머지 제목이 밀리지 않는다
  · 블록 순서가 뒤바뀌어도 번호대로 간다
  · 제목과 설명은 같은 번호 블록에만 붙는다
  · 배치 내 제목 중복은 원문 제목으로 되돌린다

D1·네트워크 호출 0회 — chat_completion 을 스텁으로 바꿔 LLM 응답만 주입한다.
사용: pytest tests/test_batch_translate_alignment.py -q
"""
import importlib.util
import os

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COLLECTOR_PATH = os.path.join(REPO_ROOT, 'api_test', 'news_collector.py')


@pytest.fixture(scope='module')
def nc():
    spec = importlib.util.spec_from_file_location('aik24_news_collector_align', COLLECTOR_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _articles(n):
    return [
        {
            "title": f"English title {i}",
            "description": f"English desc {i}",
            "country": "us",
        }
        for i in range(n)
    ]


def _stub(response):
    calls = []

    def fake(**kwargs):
        calls.append(kwargs)
        return response

    fake.calls = calls
    return fake


def test_well_formed_batch_aligns_titles_and_descs(nc, monkeypatch):
    response = "\n".join([
        "1. TITLE: 첫 번째 한국어 제목",
        "   DESC: 첫 번째 설명",
        "2. TITLE: 두 번째 한국어 제목",
        "   DESC: 두 번째 설명",
    ])
    monkeypatch.setattr(nc, "chat_completion", _stub(response))

    out = nc.batch_translate(_articles(2))

    assert [a["title"] for a in out] == ["첫 번째 한국어 제목", "두 번째 한국어 제목"]
    assert [a["description"] for a in out] == ["첫 번째 설명", "두 번째 설명"]


def test_missing_first_title_does_not_shift_the_rest(nc, monkeypatch):
    """본 사고 재현: 1번 TITLE 이 빠진 응답.

    종전 코드는 2번 제목을 1번 기사에, 3번 제목을 2번 기사에 붙였다.
    수정 후에는 1번 기사만 원문 제목이 남고, 2·3번은 제자리 제목을 받아야 한다.
    """
    response = "\n".join([
        "1. DESC: 1번 설명만 있고 제목 줄이 없다",
        "2. TITLE: 두 번째 기사 제목",
        "   DESC: 두 번째 설명",
        "3. TITLE: 세 번째 기사 제목",
        "   DESC: 세 번째 설명",
    ])
    monkeypatch.setattr(nc, "chat_completion", _stub(response))

    out = nc.batch_translate(_articles(3))

    assert out[0]["title"] == "English title 0"          # 원문 유지 (밀림 없음)
    assert out[1]["title"] == "두 번째 기사 제목"
    assert out[2]["title"] == "세 번째 기사 제목"
    # 설명도 자기 번호에만 붙는다.
    assert out[0]["description"] == "1번 설명만 있고 제목 줄이 없다"
    assert out[1]["description"] == "두 번째 설명"


def test_reordered_blocks_map_by_number(nc, monkeypatch):
    response = "\n".join([
        "2. TITLE: 두 번째",
        "   DESC: 둘",
        "1. TITLE: 첫 번째",
        "   DESC: 하나",
    ])
    monkeypatch.setattr(nc, "chat_completion", _stub(response))

    out = nc.batch_translate(_articles(2))

    assert [a["title"] for a in out] == ["첫 번째", "두 번째"]
    assert [a["description"] for a in out] == ["하나", "둘"]


def test_out_of_range_and_duplicate_numbers_are_ignored(nc, monkeypatch):
    response = "\n".join([
        "1. TITLE: 첫 번째",
        "   DESC: 하나",
        "1. TITLE: 중복 번호는 무시",
        "   DESC: 무시",
        "7. TITLE: 범위 밖 번호",
        "   DESC: 무시",
    ])
    monkeypatch.setattr(nc, "chat_completion", _stub(response))

    out = nc.batch_translate(_articles(2))

    assert out[0]["title"] == "첫 번째"
    assert out[1]["title"] == "English title 1"


def test_duplicate_title_within_batch_reverts_later_item(nc, monkeypatch):
    response = "\n".join([
        "1. TITLE: 같은 제목",
        "   DESC: 하나",
        "2. TITLE: 같은 제목",
        "   DESC: 둘",
    ])
    monkeypatch.setattr(nc, "chat_completion", _stub(response))

    out = nc.batch_translate(_articles(2))

    assert out[0]["title"] == "같은 제목"
    assert out[1]["title"] == "English title 1"   # 남의/중복 제목보다 원문이 낫다


def test_title_and_desc_in_one_line_are_split(nc, monkeypatch):
    response = "1. TITLE: 한 줄 제목 DESC: 한 줄 설명"
    monkeypatch.setattr(nc, "chat_completion", _stub(response))

    out = nc.batch_translate(_articles(1))

    assert out[0]["title"] == "한 줄 제목"
    assert out[0]["description"] == "한 줄 설명"


def test_title_starting_with_digit_is_preserved(nc, monkeypatch):
    """AIK24-COLLECTOR-TITLE-FIX 회귀 방지 — 번호 매핑 경로에서도 숫자는 보존."""
    response = "\n".join([
        "1. TITLE: 6개국에서 제미나이 무료 사용 가능",
        "   DESC: 설명",
    ])
    monkeypatch.setattr(nc, "chat_completion", _stub(response))

    out = nc.batch_translate(_articles(1))

    assert out[0]["title"] == "6개국에서 제미나이 무료 사용 가능"


def test_response_without_numbers_uses_only_exact_count(nc, monkeypatch):
    """번호가 없는 응답은 개수가 정확히 맞을 때만 순서대로 쓴다."""
    exact = "\n".join([
        "TITLE: 첫 번째",
        "DESC: 하나",
        "TITLE: 두 번째",
        "DESC: 둘",
    ])
    monkeypatch.setattr(nc, "chat_completion", _stub(exact))
    out = nc.batch_translate(_articles(2))
    assert [a["title"] for a in out] == ["첫 번째", "두 번째"]

    short = "\n".join([
        "TITLE: 하나뿐인 제목",
        "DESC: 하나뿐인 설명",
    ])
    monkeypatch.setattr(nc, "chat_completion", _stub(short))
    out2 = nc.batch_translate(_articles(3))
    assert [a["title"] for a in out2] == [
        "English title 0", "English title 1", "English title 2",
    ]
