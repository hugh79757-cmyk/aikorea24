"""
test_characterization_pure_functions.py — validate_thread() 및 validate_final_cards() 엣지 케이스 특성 테스트

Phase 4 모놀리스 분할 전 현재 동작을 포착하는 특성 테스트(캐릭터라이제이션 테스트).
8개 카드 쓰레드 검증(validator.py)과 최종 카드 검증(main_v3.py)의 현재 동작을 기록함.
외부 의존성(D1, 네트워크, API) 없이 완전히 밀폐된(hermetic) 환경에서 실행됨.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts/threads"))

from validator import validate_thread
from main_v3 import validate_final_cards


class TestValidateThreadValid:
    """validate_thread: 정상 8개 카드 쓰레드 검증"""

    def test_validate_thread_valid(self):
        """8개 카드, 레이블 없음, 출처 포함, 숫자 포함 → (True, []) 반환"""
        card_template = (
            "{n}번 카드의 첫 번째 줄 내용임.\n"
            "두 번째 줄도 정상적인 내용으로 채워져 있음.\n"
            "세 번째 줄까지 정상임."
        )
        cards_list = [card_template.format(n=i) for i in range(1, 9)]
        # 1번 카드에 숫자 포함 (10만)
        cards_list[0] = (
            "AI 시장 규모가 10만 달러를 돌파했음.\n"
            "매년 2배씩 성장하고 있음.\n"
            "이 추세는 앞으로도 지속될 것임."
        )
        # 8번 카드(마지막)에 출처 포함
        cards_list[-1] = (
            "8번 카드는 마지막 카드임.\n"
            "출처를 반드시 포함해야 함.\n"
            "🔗 https://example.com/news/ai"
        )
        content = '\n---\n'.join(cards_list)
        valid, failures = validate_thread(content)
        assert valid is True
        assert failures == []


class TestValidateThreadInvalidCardCount:
    """validate_thread: 잘못된 카드 수 검증"""

    def test_validate_thread_invalid_card_count(self):
        """5개 카드 → '카드 수' 오류 (8개 필요)"""
        card_template = "{n}번 카드 내용임.\n10만 달러 규모의 시장이 형성됨."
        cards_list = [card_template.format(n=i) for i in range(1, 6)]
        content = '\n---\n'.join(cards_list)
        valid, failures = validate_thread(content)
        assert valid is False
        assert any("카드 수" in f for f in failures)


class TestValidateThreadLabelDetection:
    """validate_thread: 레이블 검증"""

    def test_validate_thread_label_detected(self):
        """카드가 '(훅)' 레이블로 시작 → '레이블 발견' 오류"""
        cards_list = [
            "(훅) 첫 번째 카드의 첫 줄에 레이블이 포함되어 있음.\n두 번째 줄 정상.",
            "두 번째 카드 내용임.\n10만 명이 넘는 사용자가 있음.\n정상 줄.",
            "세 번째 카드 내용임.\n1조 원 규모의 시장이 형성됨.\n정상 줄.",
            "네 번째 카드 내용임.\n정상 줄.",
            "다섯 번째 카드 내용임.\n정상 줄.",
            "여섯 번째 카드 내용임.\n정상 줄.",
            "일곱 번째 카드 내용임.\n정상 줄.",
            "여덟 번째 카드로 출처 포함.\n🔗 https://example.com/news",
        ]
        content = '\n---\n'.join(cards_list)
        valid, failures = validate_thread(content)
        assert valid is False
        assert any("레이블" in f for f in failures)


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
