"""
format_selector.py — 피치/기사 특성에 따라 A/B/C/D 형식 선택
- LLM 1회 호출로 판단
- 실패 시 D (기본값) 반환
"""
import os, re, json
from datetime import datetime

THREADS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS_DIR = os.path.join(THREADS_DIR, 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f'[{ts}] {msg}')
    with open(os.path.join(LOGS_DIR, datetime.now().strftime('%Y-%m-%d') + '.log'), 'a', encoding='utf-8') as f:
        f.write(f'[{ts}] [selector] {msg}\n')

SELECTOR_PROMPT = """당신은 AI 뉴스 기사에 가장 적합한 쓰레드 형식을 선택하는 편집자입니다.

아래 4가지 형식 중 피치와 기사에 가장 적합한 하나를 골라 JSON으로 출력하세요.

## 형식 A — 실험형 (5개 카드 + 링크)
조건: 실험 중인 형식. 특정 조건 없이 모든 주제에 시도 가능.
- 선택 우선순위는 유지: A 조건 충족 시 A 선택, 아니면 하위 형식 순.

## 형식 B — 구조 분석형 (8개 카드)
조건 (하나라도 해당):
- 정부/기관의 정책 발표나 규제 변화
- 산업 구조, 시장 점유율, 경쟁 구도 분석
- 복수 기업/국가 간 비교가 핵심
- 데이터/통계/숫자가 스토리의 중심
- "A처럼 보이지만 실제로는 B" 구조

## 형식 C — X 쓰레드형 (7개 트윗)
조건 (하나라도 해당):
- 짧은 뉴스 브리핑 / 긴급 속보
- 단순한 제품 출시나 서비스 발표
- 깊은 분석이나 반전 구조가 필요 없는 단순 메시지

## 형식 D — 펀치 브리핑형 (5개 카드) ← 기본값
조건:
- 위 A/B/C 중 어느 것에도 명확히 해당하지 않음
- 상식충돌 구조는 있지만 인물 행동이 중심이 아님
- 숫자/데이터가 풍부하고 punch-style 훅에 적합
- A/B/C 조건이 두 개 이상 섞여 있음

## 선택 우선순위
A > B > C > D (A 조건이 가장 강력, D는 fallback)

## 출력 형식 (JSON만)
{"format": "A/B/C/D", "reason": "선택 이유 한 줄"}"""


def select_format(pitch, all_articles):
    """
    피치 + 기사 메타데이터를 보고 가장 적합한 형식 반환
    
    Returns:
        tuple: (format_letter, reason)
    """
    from v3.model_router import chat_completion

    # 피치 정보 요약
    hook = pitch.get('hook', '')[:100]
    narrative = pitch.get('narrative', '')[:200]
    twist = pitch.get('twist', '')[:100]
    emotion = pitch.get('emotion', '')
    
    # 관련 기사 정보 요약
    article_ids = pitch.get('article_ids', [])
    article_summaries = []
    for a in all_articles:
        aid = a.get('id')
        if aid in article_ids or str(aid) in [str(x).lstrip('#').strip() for x in article_ids]:
            title = a.get('title', '')[:80]
            desc = (a.get('description', '') or '')[:200]
            source = a.get('source', '')
            article_summaries.append(f"제목: {title}\n출처: {source}\n요약: {desc}")
    
    articles_text = '\n---\n'.join(article_summaries) if article_summaries else '(기사 정보 없음)'

    user_prompt = f"""아래 피치와 기사 정보를 보고 가장 적합한 형식을 선택하세요.

=== 피치 ===
훅: {hook}
내러티브: {narrative}
반전: {twist}
감정: {emotion}

=== 관련 기사 ===
{articles_text}

=== 선택 기준 요약 ===
A: 인물의 구체적 행동 + 감정 + 갈등 (모두 필요)
B: 데이터/정책/산업 구조 분석 중심
C: 짧은 브리핑/속보/단순 발표
D: 위 셋 중 명확한 것이 없거나 혼합 (기본값)

출력: {{"format": "A/B/C/D", "reason": "선택 이유 한 줄"}}"""

    try:
        resp = chat_completion(
            system_prompt=SELECTOR_PROMPT,
            messages=[{'role': 'user', 'content': user_prompt}],
            temperature=0.2,
            max_tokens=200,
        )
        if not resp:
            log(f'  ⚠️ selector: 응답 없음 → D')
            return 'D', 'selector 무응답'

        m = re.search(r'\{[^}]*\}', resp)
        if m:
            result = json.loads(m.group(0))
            fmt = result.get('format', 'D').upper().strip()
            reason = result.get('reason', '').strip()
            if fmt not in ('A', 'B', 'C', 'D'):
                log(f'  ⚠️ selector: 알 수 없는 형식 "{fmt}" → D')
                return 'D', f'알 수 없는 형식: {fmt}'
            log(f'  ✅ 형식 선택: {fmt} — {reason}')
            return fmt, reason
        else:
            log(f'  ⚠️ selector: JSON 파싱 실패 → D')
            return 'D', 'JSON 파싱 실패'
    except Exception as e:
        log(f'  ⚠️ selector 오류: {e} → D')
        return 'D', f'오류: {e}'
