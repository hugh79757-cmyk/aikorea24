#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
"""
pitch_evaluator.py — 피치 품질 평가 게이트
- GPT-4o-mini가 피치의 품질을 0~5점 평가
- 3점 미만이면 폐기
"""
import os, json, re
from datetime import datetime

THREADS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS_DIR = os.path.join(THREADS_DIR, 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f'[{ts}] {msg}')
    with open(os.path.join(LOGS_DIR, datetime.now().strftime('%Y-%m-%d') + '.log'), 'a', encoding='utf-8') as f:
        f.write(f'[{ts}] [eval] {msg}\n')

EVAL_SYSTEM_PROMPT = """당신은 피치 품질 평가자입니다.

아래 기준으로 0~5점을 매기고, 3점 이상만 통과시킵니다.

[평가 기준]
1. 상식충돌: "상식적으로 A였어야 하는데 실제로는 B" 구조가 명확한가? (0~2점)
   - 2점: 독자가 "어? 몰랐다" 할 충돌
   - 1점: 어느 정도 알려진 이야기
   - 0점: 충돌 없음, 단순 사실 나열

2. 구체성: 숫자/인물/기업명이 포함되어 있는가? (0~2점)
   - 2점: 구체적 숫자 + 인물/기업명 모두 있음
   - 1점: 하나만 있음
   - 0점: 추상적 표현뿐

3. 연결성: 2개 이상의 서로 다른 기사가 연결되었는가? (0~1점)
   - 1점: 2개 이상 다른 출처 기사
   - 0점: 단일 기사 또는 같은 출처

[출력 형식]
{"score": 0~5, "passed": true/false, "reason": "평가 이유 한 줄"}"""

def evaluate_pitch(pitch):
    """피치 품질 평가 → 통과 여부"""
    from v3.model_router import chat_completion

    pitch_json = json.dumps(pitch, ensure_ascii=False)
    try:
        resp = chat_completion(
            system_prompt=EVAL_SYSTEM_PROMPT,
            messages=[{'role': 'user', 'content': f'평가할 피치:\n{pitch_json}'}],
            temperature=0.3,
            max_tokens=300,
        )
        # JSON 파싱
        m = re.search(r'\{[^}]+\}', resp)
        if m:
            result = json.loads(m.group(0))
            score = result.get('score', 0)
            passed = result.get('passed', False)
            reason = result.get('reason', '')
            log(f'  평가: {score}점/{"" if passed else "불"}통과 ({reason})')
            return passed, score, reason
    except Exception as e:
        log(f'  ⚠️ 평가 오류: {e}')

    # fallback: 기본 통과
    ids = pitch.get('article_ids', [])
    hook = pitch.get('hook', '')
    if len(ids) >= 2 and len(hook) <= 18:
        return True, 3, 'fallback 통과'
    return False, 0, 'fallback 실패'


def filter_pitches(pitches):
    """여러 피치 중 품질 통과하는 첫 번째 피치 반환"""
    for p in pitches:
        passed, score, reason = evaluate_pitch(p)
        if passed:
            log(f'  ✅ 피치 통과: {score}점')
            return p
        log(f'  ❌ 피치 불통: {score}점 - {reason}')
    return None
