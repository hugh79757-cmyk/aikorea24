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
    """validate_final_cards: 엣지 케이스"""

    def test_validate_final_cards_empty(self):
        """빈 리스트 → (False, issues), issues 비어 있지 않음"""
        valid, issues = validate_final_cards([])
        assert valid is False
        assert len(issues) > 0

    def test_validate_final_cards_no_source(self):
        """단일 카드, 링크 없음 → '출처 링크' 오류 (마지막 카드가 유일 카드이므로)"""
        cards = [
            "단일 카드 내용임.\n링크가 없으므로 출처 검증에 실패해야 함.",
        ]
        valid, issues = validate_final_cards(cards)
        assert valid is False
        assert any("출처 링크" in issue for issue in issues)
