#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
"""
validator.py — 쓰레드 품질 검증 (8개 항목)
"""
import re

def validate_thread(content):
    """
    반환: (bool, list)  # 합격 여부, 실패 사유 리스트
    """
    failures = []
    cards = [c.strip() for c in content.split('---') if c.strip()]

    if not cards:
        return False, ['카드 없음']

    # 1. 카드 수
    if len(cards) != 8:
        failures.append(f'카드 수: {len(cards)}/8')

    # 2. 레이블 금지
    label_pattern = r'^\(?(훅|데이터|구조|비교|반전|압축|결론|CTA)\)?'
    for i, card in enumerate(cards):
        first_line = card.strip().split('\n')[0].strip()
        if re.search(label_pattern, first_line):
            failures.append(f'카드 {i+1}: 레이블 발견 ("{first_line[:20]}")')

    # 3. 1번 카드 길이 (2줄 이상)
    if len(cards) >= 1:
        lines1 = cards[0].strip().split('\n')
        if len(lines1) < 2:
            failures.append(f'1번 카드: {len(lines1)}줄/2')

    # 4. 각 카드 길이 (2~7번, 2줄 이상)
    for i, card in enumerate(cards[1:7], 2):
        if i <= len(cards):
            lines = card.strip().split('\n')
            if len(lines) < 2:
                failures.append(f'카드 {i}: {len(lines)}줄/2')

    # 5. 8번 카드 (최소 2줄)
    if len(cards) >= 8:
        lines8 = cards[7].strip().split('\n')
        if len(lines8) < 2:
            failures.append(f'8번 카드: {len(lines8)}줄 (최소 2줄)')

    # 6. 출처 확인 (어느 카드든 출처 포함)
    all_text_joined = ' '.join(cards)
    has_source = '출처' in all_text_joined or 'http' in all_text_joined
    if not has_source:
        failures.append('출처 없음')

    # 7. 숫자 포함 (최소 1개)
    numbers = re.findall(r'\d+[억만]?[원%달러]|\d+조|\d{1,3}(?:,\d{3})+|[0-9]+\s*[만천백]', all_text_joined)
    if len(numbers) < 1:
        failures.append(f'전체 숫자: {len(numbers)}개/1')

    # 8. 중복 단어 체크 (10회 이상만)
    word_counts = {}
    for card in cards:
        words = set(re.findall(r'[가-힣a-zA-Z]{2,}', card))
        for w in words:
            word_counts[w] = word_counts.get(w, 0) + 1
    heavy_dupes = [w for w, c in word_counts.items() if c >= 10]
    if heavy_dupes:
        failures.append(f'중복 단어: {heavy_dupes[:3]}')

    return len(failures) == 0, failures


if __name__ == '__main__':
    import glob
    drafts = sorted(glob.glob('/Users/twinssn/Projects/aikorea24/scripts/threads/logs/drafts/*.txt'))
    if drafts:
        latest = drafts[-1]
        with open(latest, 'r', encoding='utf-8') as f:
            content = f.read()
        passed, failures = validate_thread(content)
        print(f'초안: {latest}')
        print(f'결과: {"✅ 합격" if passed else "❌ 불합격"}')
        if failures:
            for f in failures:
                print(f'  - {f}')
    else:
        print('검증할 초안 없음')
