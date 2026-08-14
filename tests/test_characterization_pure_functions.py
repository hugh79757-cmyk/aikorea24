"""
test_characterization_pure_functions.py — validate_final_cards() 엣지 케이스 특성 테스트

Phase 4 모놀리스 분할 전 현재 동작을 포착하는 특성 테스트(캐릭터라이제이션 테스트).
외부 의존성(D1, 네트워크, API) 없이 완전히 밀폐된(hermetic) 환경에서 실행됨.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts/threads"))

from main_v3 import validate_final_cards


class TestValidateFinalCardsEdgeCases:
    """validate_final_cards: 엣지 케이스 (FORMAT_D: 5카드, 링크 카드 별도 반환 — 출처 링크 검증 미도입)"""

    def test_validate_final_cards_empty(self):
        """빈 리스트 → validate_final_cards는 카드 수 검증을 호출 전에 수행하므로
        빈 리스트도 (True, []) 반환 (이슈 없음). 카드 수 부족은 상위에서 Rejection."""
        valid, issues = validate_final_cards([])
        assert valid is True
        assert issues == []

    def test_validate_final_cards_no_source(self):
        """단일 카드 — validate_final_cards는 출처 링크 검증 미도입.
        INSTRUCTION_PATTERNS/길이/미완결 문장만 검사. 단일 카드는 통과 가능."""
        cards = [
            "단일 카드 내용임. 충분한 길이를 확보했음.",
        ]
        valid, issues = validate_final_cards(cards)
        # 출처 링크 검증 없음 — 빈 카드도 아니고, 프롬프트도 없고, 길이도 500 이하
        assert valid is True
        assert issues == []
