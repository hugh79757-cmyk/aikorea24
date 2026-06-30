"""
test_characterization_validate_final_cards.py — validate_final_cards() 특성 테스트

Phase 4 모놀리스 분할 전 현재 동작을 포착하는 특성 테스트(캐릭터라이제이션 테스트).
Strangler Fig 패턴에서 리팩토링 후 동작 보존을 확인하는 회귀 게이트 역할을 함.
외부 의존성(D1, 네트워크, API) 없이 완전히 밀폐된(hermetic) 환경에서 실행됨.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts/threads"))

from main_v3 import validate_final_cards

# INSTRUCTION_PATTERNS는 v3.writer_v3에 정의되어 있음
# import 실패 시 테스트용 값으로 대체 (소스 코드에서 추출)
try:
    from v3.writer_v3 import INSTRUCTION_PATTERNS
except ImportError:
    INSTRUCTION_PATTERNS = [
        "다음 Threads 쓰레드의 AI 말투를",
        "[원본]",
        "[출력 규칙]",
        "수정된 쓰레드만 출력",
        "--- 구분자 정확히 유지",
        "내용(사실, 수치, 고유명사)은 절대 변경",
        "반말체(~임, ~했음, ~있음) 그대로 유지",
        "구분자 정확히 유지",
    ]


class TestValidateFinalCardsValid:
    """정상 입력이 (True, [])를 반환하는지 확인"""

    def test_valid_cards(self):
        """5개 정상 카드 — 모든 검증 통과, (True, []) 반환"""
        cards = [
            (
                "AI 산업이 빠르게 성장하고 있음.\n"
                "올해 글로벌 AI 시장 규모가 1조 달러를 돌파했음.\n"
                "이 성장의 중심에는 생성형 AI 기술이 있음."
            ),
            (
                "오픈AI가 새로운 추론 모델을 출시했음.\n"
                "이 모델은 수학과 코딩에서 뛰어난 성능을 보여줌.\n"
                "전문가들은 이 모델이 업계를 변화시킬 것이라고 예상함!"
            ),
            (
                "구글 딥마인드가 단백질 구조 예측 모델을 공개했음.\n"
                "생물학 연구의 패러다임이 완전히 바뀌고 있음.\n"
                "과연 이 기술이 신약 개발을 가속화할 수 있을까?"
            ),
            (
                "엔비디아의 데이터센터 매출이 사상 최대를 기록했음.\n"
                "AI 칩 수요가 공급을 초과하여 생산 라인이 확대됨.\n"
                "대기 기간이 6개월에 달하고 있음."
            ),
            (
                "한국 AI 스타트업들의 글로벌 시장 진출이 가속화됨.\n"
                "🔗 https://example.com/ai-news"
            ),
        ]
        valid, issues = validate_final_cards(cards)
        assert valid is True
        assert issues == []


class TestValidateFinalCardsInstructionPattern:
    """프롬프트 명령어 누출 검증"""

    def test_instruction_pattern_detected(self):
        """INSTRUCTION_PATTERNS 접두사가 포함된 카드 → '프롬프트 명령어 포함' 오류"""
        pattern = INSTRUCTION_PATTERNS[0]  # "다음 Threads 쓰레드의 AI 말투를"
        cards = [
            (
                "정상적인 첫 번째 카드임.\n"
                "아무 문제가 없음."
            ),
            (
                f"{pattern}자연스럽게 다듬어라.\n"
                "수정된 내용만 출력하라."
            ),
            (
                "세 번째 카드 내용임.\n"
                "문제가 전혀 없음."
            ),
            (
                "네 번째 카드도 정상임.\n"
                "통과되어야 함."
            ),
            (
                "마지막 카드로 출처를 포함함.\n"
                "🔗 https://example.com/news"
            ),
        ]
        valid, issues = validate_final_cards(cards)
        assert valid is False
        assert any("프롬프트 명령어 포함" in issue for issue in issues)


class TestValidateFinalCardsEmptyCard:
    """빈 카드 검증"""

    def test_empty_card(self):
        """빈 문자열 카드 → '빈 카드' 오류"""
        cards = [
            "정상적인 첫 번째 카드 내용임.\n문제가 없음.",
            "",  # 빈 카드
            "세 번째 카드는 정상 내용임.\n출처 링크가 있음.",
            "네 번째 카드도 정상임.\n통과되어야 함.",
            "마지막 카드로 출처를 포함함.\n🔗 https://example.com/news",
        ]
        valid, issues = validate_final_cards(cards)
        assert valid is False
        assert any("빈 카드" in issue for issue in issues)


class TestValidateFinalCardsLength:
    """500자 초과 검증"""

    def test_length_violation(self):
        """510자 카드 → '500자 초과' 오류"""
        # 510자 카드 생성 ('a' 1자 + 공백 1자 = 2자 → 255회 반복)
        long_content = "a " * 255  # 510자
        cards = [
            "정상적인 첫 번째 카드임.\n아무 문제가 없음.",
            long_content,
            "세 번째 카드는 정상 내용임.",
            "네 번째 카드도 정상임.",
            "마지막 카드 출처 포함.\n🔗 https://example.com/news",
        ]
        valid, issues = validate_final_cards(cards)
        assert valid is False
        assert any("500자 초과" in issue for issue in issues)


class TestValidateFinalCardsSourceLink:
    """출처 링크 검증"""

    def test_missing_source_link(self):
        """마지막 카드에 http/🔗 없음 → '출처 링크 없음' 오류"""
        cards = [
            "첫 번째 카드 내용임.\n정상적인 내용.",
            "두 번째 카드 내용임.\n정상적인 내용.",
            "세 번째 카드 내용임.\n정상적인 내용.",
            "네 번째 카드 내용임.\n정상적인 내용.",
            "마지막 카드인데 링크가 없음.\n문제가 발생해야 함.",
        ]
        valid, issues = validate_final_cards(cards)
        assert valid is False
        assert any("출처 링크 없음" in issue for issue in issues)


class TestValidateFinalCardsIncompleteSentence:
    """미완결 문장 검증"""

    def test_incomplete_sentence(self):
        """마지막 줄이 구두점(. ! ?) 없이 끝남 → '미완결 문장' 오류"""
        cards = [
            "정상적인 첫 번째 카드 내용임.\n문제가 전혀 없음.",
            (
                "이 카드는 마지막 줄이 완결되지 않았음.\n"
                "갑자기 끝나버림"
            ),
            "세 번째 카드는 정상적인 내용임.\n끝에 마침표가 있음.",
            "네 번째 카드도 정상 내용임.\n문제가 전혀 없음.",
            "마지막 카드로 출처 링크를 포함함.\n🔗 https://example.com/news",
        ]
        valid, issues = validate_final_cards(cards)
        assert valid is False
        assert any("미완결 문장" in issue for issue in issues)


class TestValidateFinalCardsDuplicateContent:
    """내용 중복 검증"""

    def test_duplicate_content(self):
        """인접 카드 단어 집합 85% 이상 중복 → '내용 유사' 오류"""
        duplicate_text = (
            "AI 산업이 빠르게 성장하고 있음 올해 글로벌 시장 규모가 확대됨.\n"
            "이 기술은 많은 분야에서 혁신을 만들고 있음.\n"
            "기업들의 투자가 계속해서 증가하고 있음."
        )
        cards = [
            "정상적인 첫 번째 카드임.\n내용이 충분히 다름.",
            duplicate_text,
            duplicate_text,  # 카드 2와 완전히 동일 → 100% 중복
            "네 번째 카드는 정상적인 내용임.\n중복 검사는 인접 카드만 비교함.",
            "마지막 카드로 출처 링크를 포함함.\n🔗 https://example.com/news",
        ]
        valid, issues = validate_final_cards(cards)
        assert valid is False
        assert any("내용 유사" in issue for issue in issues)


class TestValidateFinalCardsKoreanEnglishSpacing:
    """한글+영어 붙어쓰기 검증"""

    def test_korean_english_spacing(self):
        """한글에 3글자 이상 영어가 공백 없이 붙어있음 → '한글+영어 붙어쓰기' 오류"""
        cards = [
            "정상적인 첫 번째 카드 내용임.\n문제가 전혀 없음.",
            (
                "개발자는OpenAI API를 사용하고 있음.\n"
                "이 기술은 매우 혁신적임."
            ),
            "세 번째 카드는 정상임.\n아무 문제가 없음.",
            "네 번째 카드도 정상임.\n통과되어야 함.",
            "마지막 카드로 출처를 포함함.\n🔗 https://example.com/news",
        ]
        valid, issues = validate_final_cards(cards)
        assert valid is False
        assert any("한글+영어 붙어쓰기" in issue for issue in issues)
