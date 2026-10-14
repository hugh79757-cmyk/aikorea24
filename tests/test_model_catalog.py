"""AIK24-FREE-PIPE-01 작업 2 — diff 감지 테스트.

지시서 완료 기준: "어제 스냅샷 파일을 복사해 1건을 인위 수정(추가/삭제/변경 각 1건)한 뒤
diff가 3건을 정확히 잡아내는 테스트 1회 성공".
"""
import copy
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

from model_catalog import diff  # noqa: E402

YESTERDAY = [
    {"provider": "openrouter", "model_id": "a/free:free", "name": "A", "pricing": {"prompt": 0.0, "completion": 0.0}, "context_length": 8192},
    {"provider": "openrouter", "model_id": "b/free:free", "name": "B", "pricing": {"prompt": 0.0, "completion": 0.0}, "context_length": 16384},
    {"provider": "openrouter", "model_id": "c/free:free", "name": "C", "pricing": {"prompt": 0.0, "completion": 0.0}, "context_length": 32768},
]
# b 는 사라짐, d 는 추가, a 는 컨텍스트 길이 변경 → 3건
TODAY = copy.deepcopy(YESTERDAY)
TODAY[0]["context_length"] = 32768
TODAY.pop(1)
TODAY.append({"provider": "openrouter", "model_id": "d/free:free", "name": "D", "pricing": {"prompt": 0.0, "completion": 0.0}, "context_length": 4096})

# OpenRouter 전체 목록에는 b(유료 base)와 c 가 남아 있다 → b 는 '무료→유료 전환'
ALL_IDS = {"openrouter": {"a/free:free", "b/free", "c/free:free", "d/free:free"}}


def test_diff_catches_one_of_each():
    d = diff(YESTERDAY, TODAY, ALL_IDS)
    assert len(d["added"]) == 1 and d["added"][0]["model_id"] == "d/free:free"
    assert len(d["removed"]) == 1 and d["removed"][0]["model_id"] == "b/free:free"
    assert len(d["changed"]) == 1 and d["changed"][0]["field"] == "context_length"
    assert d["changed"][0]["before"] == 8192 and d["changed"][0]["after"] == 32768


def test_removed_reason_is_upgrade_not_delisting():
    d = diff(YESTERDAY, TODAY, ALL_IDS)
    assert d["removed"][0]["reason"] == "무료→유료 전환"


def test_removed_reason_is_delisting_when_base_gone():
    d = diff(YESTERDAY, TODAY, {"openrouter": {"a/free:free", "c/free:free", "d/free:free"}})
    assert d["removed"][0]["reason"] == "단종/제거"


def test_first_run_marks_everything_as_added():
    """첫 실행(어제 스냅샷 없음)이면 전부 added — 작업 4가 전부 평가해도 되는 이유."""
    assert diff([], YESTERDAY, ALL_IDS)["added"] == YESTERDAY
    assert diff(None, YESTERDAY, ALL_IDS)["added"] == YESTERDAY
    assert diff(None, YESTERDAY, ALL_IDS)["removed"] == []
    assert diff(None, YESTERDAY, ALL_IDS)["changed"] == []


def test_identical_snapshots_are_empty():
    d = diff(YESTERDAY, copy.deepcopy(YESTERDAY), ALL_IDS)
    assert d == {"added": [], "removed": [], "changed": []}


@pytest.mark.parametrize("prev,cur", [(None, None), ([], [])])
def test_empty_inputs(prev, cur):
    assert diff(prev, cur, {}) == {"added": [], "removed": [], "changed": []}