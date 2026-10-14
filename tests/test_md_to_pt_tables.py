"""AIK24-EMDASH-09 — md_to_pt() 마크다운 표 변환 단위 테스트.

완료 기준 1: 표 2개 포함 마크다운 → table 블록 2개, hasHeaderRow:true, 셀 텍스트·정렬 정확.
             구분선 없는 파이프 나열은 일반 문단으로 남는다 (EMDASH-06 원칙).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

from emdash04_migrate import md_to_pt  # noqa: E402

TWO_TABLES = """## 오늘의 무료 LLM 모델

| 항목 | 값 | 수치 |
|:---|:---:|---:|
| A | `code` | **굵게** |
| B | x | 12 |

| 프로바이더 | 건수 |
|---|---|
| OpenRouter | 14 |
| Kilo | 15 |

GitHub | Pages | Vercel
"""


def _tables(md):
    return [b for b in md_to_pt(md) if b.get("_type") == "table"]


def _cell_text(cell):
    return "".join(s.get("text", "") for s in cell["content"])


def test_two_tables():
    t = _tables(TWO_TABLES)
    assert len(t) == 2


def test_header_rows_and_counts():
    first, second = _tables(TWO_TABLES)
    assert first["hasHeaderRow"] is True
    assert len(first["rows"]) == 3          # 헤더 1 + 데이터 2
    assert len(second["rows"]) == 3         # 헤더 1 + 데이터 2
    assert all(r["cells"][0]["isHeader"] for r in [first["rows"][0], second["rows"][0]])
    assert not any(r["cells"][0]["isHeader"] for r in first["rows"][1:])


def test_alignment_from_delimiter():
    first = _tables(TWO_TABLES)[0]
    aligns = [c.get("textAlign") for c in first["rows"][0]["cells"]]
    assert aligns == ["left", "center", "right"]


def test_cell_texts():
    rows = _tables(TWO_TABLES)[1]["rows"]
    assert [_cell_text(c) for c in rows[0]["cells"]] == ["프로바이더", "건수"]
    assert [_cell_text(c) for c in rows[1]["cells"]] == ["OpenRouter", "14"]
    assert [_cell_text(c) for c in rows[2]["cells"]] == ["Kilo", "15"]


def test_inline_marks_survive_in_cells():
    row = _tables(TWO_TABLES)[0]["rows"][1]
    assert [s.get("marks") for s in row["cells"][1]["content"]] == [["code"]]
    assert [s.get("marks") for s in row["cells"][2]["content"]] == [["strong"]]


def test_pipe_enumeration_without_delimiter_stays_paragraph():
    texts = [b for b in md_to_pt(TWO_TABLES) if b.get("_type") == "block" and b.get("style") == "normal"]
    assert "GitHub | Pages | Vercel" in ["".join(s["text"] for s in b["children"]) for b in texts]


def test_delimiter_without_header_is_not_a_table():
    # 구분선으로 시작하는 표(header 없음)는 인정하지 않는다 — 마크다운 표 스펙에 없다.
    assert _tables("|---|---|\n| a | b |\n") == []


def test_other_blocks_untouched():
    md = "# 제목\n\n> 인용\n\n- 목록\n\n```py\nx = 1\n```\n\n![alt](https://e.com/i.png)\n"
    kinds = [b["_type"] for b in md_to_pt(md)]
    assert kinds == ["block", "block", "block", "code", "image"]
    assert [b.get("style") for b in md_to_pt(md) if b["_type"] == "block"] == ["h1", "blockquote", "normal"]


def test_table_at_end_without_trailing_newline():
    t = _tables("| a | b |\n|---|---|\n| 1 | 2 |")
    assert len(t) == 1 and len(t[0]["rows"]) == 2


def test_ragged_row_is_padded():
    t = _tables("| a | b | c |\n|---|---|---|\n| 1 |\n")[0]
    assert [len(r["cells"]) for r in t["rows"]] == [3, 3]
    assert _cell_text(t["rows"][1]["cells"][2]) == ""