#!/usr/bin/env python3
"""AIK24-COLLECTOR-TITLE-FIX — 배치 번역 제목 파서의 앞자리 숫자 소실 회귀 테스트

배경(2026-11-18):
  `batch_translate()` 파서가 `cleaned.lstrip("0123456789")` 로 TITLE: 뒤의
  앞자리 숫자를 **전부** 지웠다. 그래서 LLM 이 "6개국에서 제미나이…" 로 맞게
  번역해도 "개국에서 제미나이…" 로 발행됐고, "2026년…" · "3분기…" 로 시작하는
  제목도 같은 피해를 입었다. LLM 출력 형식은 "1. TITLE: 번역된 제목" 이므로
  번호는 TITLE: **앞**에 있고, TITLE: 뒤의 숫자는 제목 본문이다.

검증 대상: api_test/news_collector.py::batch_translate()
  · 제목 본문이 숫자로 시작하면 숫자를 보존한다  ("6개국에서…", "2026년…", "3분기…")
  · 번호 잔재(숫자 + '.' 또는 ')')만 제거한다        ("1. 제목", "2) 제목")

D1·네트워크 호출 0회 — chat_completion 을 스텁으로 바꿔 LLM 응답만 주입한다.
사용: pytest tests/test_news_collector_title_number.py -q
"""
import importlib.util
import os

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COLLECTOR_PATH = os.path.join(REPO_ROOT, 'api_test', 'news_collector.py')


@pytest.fixture(scope='module')
def nc():
    """수집기 모듈 로드 (경로 기반 import — api_test 는 패키지가 아니다)."""
    spec = importlib.util.spec_from_file_location('aik24_news_collector_titlefix', COLLECTOR_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _articles(n):
    """>= n 개의 해외 기사 스텁. country='us' 라서 번역 대상이 된다."""
    return [
        {
            "title": f"English title {i}",
            "description": f"English desc {i}",
            "country": "us",
        }
        for i in range(n)
    ]


def _stub_translator(response):
    """chat_completion 스텁 — 고정 응답 1건만 돌려주고 호출 인자를 기록한다."""
    calls = []

    def fake(**kwargs):
        calls.append(kwargs)
        return response

    fake.calls = calls
    return fake


def test_leading_number_in_title_is_preserved(nc, monkeypatch):
    """제목 본문이 숫자로 시작하는 경우 — 숫자를 지우면 안 된다 (이번 사고의 핵심)."""
    response = "\n".join([
        "1. TITLE: 6개국에서 제미나이 '태스크' 기능 무료 사용 가능",
        "   DESC: 구글 제미나이가 6개국에서 무료로 풀렸다.",
        "2. TITLE: 2026년 AI 전망",
        "   DESC: 내년 전망을 정리했다.",
        "3. TITLE: 3분기 실적 발표",
        "   DESC: 실적이 공개됐다.",
    ])
    fake = _stub_translator(response)
    monkeypatch.setattr(nc, "chat_completion", fake)

    out = nc.batch_translate(_articles(3))

    assert [a["title"] for a in out] == [
        "6개국에서 제미나이 '태스크' 기능 무료 사용 가능",
        "2026년 AI 전망",
        "3분기 실적 발표",
    ]
    # 설명은 그대로 살아 있어야 한다(파서 분기 회귀 방지).
    assert out[0]["description"] == "구글 제미나이가 6개국에서 무료로 풀렸다."
    # 한 배치(3건)만 호출하고 끝나야 한다.
    assert len(fake.calls) == 1


def test_list_number_residue_is_stripped(nc, monkeypatch):
    """LLM 이 번호를 TITLE: 뒤에 붙여 보내는 경우 — 번호 잔재만 제거한다."""
    response = "\n".join([
        "1. TITLE: 1. 번호가 붙은 제목",
        "   DESC: 설명 하나",
        "2. TITLE: 2) 괄호 번호가 붙은 제목",
        "   DESC: 설명 둘",
        "3. TITLE:   7)공백 없는 괄호 번호",
        "   DESC: 설명 셋",
    ])
    fake = _stub_translator(response)
    monkeypatch.setattr(nc, "chat_completion", fake)

    out = nc.batch_translate(_articles(3))

    assert [a["title"] for a in out] == [
        "번호가 붙은 제목",
        "괄호 번호가 붙은 제목",
        "공백 없는 괄호 번호",
    ]


def test_number_without_separator_is_not_a_list_number(nc, monkeypatch):
    """숫자 뒤에 '.'/')' 가 없으면 번호가 아니라 본문이다 — 보존한다."""
    response = "\n".join([
        "1. TITLE: 3D 생성 모델 공개",
        "   DESC: 설명 하나",
        "2. TITLE: 100억 파라미터 모델",
        "   DESC: 설명 둘",
        "3. TITLE: 24시간 무료 체험",
        "   DESC: 설명 셋",
    ])
    fake = _stub_translator(response)
    monkeypatch.setattr(nc, "chat_completion", fake)

    out = nc.batch_translate(_articles(3))

    assert [a["title"] for a in out] == [
        "3D 생성 모델 공개",
        "100억 파라미터 모델",
        "24시간 무료 체험",
    ]


def test_original_title_kept_for_translated_rows(nc, monkeypatch):
    """번역된 행은 original_title 에 원문을 보존한다(기존 동작 회귀 방지)."""
    response = "\n".join([
        "1. TITLE: 6개국에서 무료 공개",
        "   DESC: 설명",
    ])
    monkeypatch.setattr(nc, "chat_completion", _stub_translator(response))

    out = nc.batch_translate(_articles(1))

    assert out[0]["original_title"] == "English title 0"
    assert out[0]["title"] == "6개국에서 무료 공개"
