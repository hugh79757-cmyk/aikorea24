#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
"""
smoke_test_chain.py — 무료 LLM 폴백 체인 스모크 테스트
config/models.yaml의 16개 무료 tier를 각각 1회 호출해 성공/실패 매트릭스 출력.
용도: 체인 도입 전 각 모델의 API 키/엔드포인트/한국어 응답 가능 여부 확인.
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))  # 프로젝트 루트

from scripts.threads.v3.model_router import (
    CHAIN_CONFIG, _call_tier_once, _log_to_file
)

TEST_PROMPT = "한국어로 한 문장으로 인사하고, 오늘 날씨가 어떤지 상상해서 짧게 말해줘."

def main():
    if not CHAIN_CONFIG:
        print('❌ CHAIN_CONFIG 없음 — config/models.yaml 확인')
        sys.exit(1)

    tier_order = CHAIN_CONFIG['tier_order']
    models_cfg = CHAIN_CONFIG['models']
    free_tiers = [t for t in tier_order if t != 'default']

    print(f'=== 무료 체인 스모크 테스트: {len(free_tiers)}개 모델 ===')
    print()

    results = []
    for tier in free_tiers:
        tier_cfg = models_cfg.get(tier)
        if not tier_cfg:
            print(f'  {tier}: ⚠️ 설정 없음 (models.yaml 확인)')
            results.append((tier, False, '설정 없음', 0))
            continue

        provider = tier_cfg['provider']
        model = tier_cfg['model']
        prov_cfg = CHAIN_CONFIG['providers'][provider]
        api_key = os.environ.get(prov_cfg['api_key_env'], '')
        if not api_key:
            print(f'  {tier} ({provider}/{model}): ❌ API 키 없음 ({prov_cfg["api_key_env"]})')
            results.append((tier, False, 'API 키 없음', 0))
            continue

        start = time.time()
        try:
            text = _call_tier_once(
                tier, tier_cfg,
                [{'role': 'user', 'content': TEST_PROMPT}],
                temperature=0.3,
                max_tokens=200,
                response_format=None,
                extra_body=None,
            )
            elapsed = time.time() - start
            if text:
                preview = text.replace('\n', ' ')[:50]
                print(f'  {tier} ({provider}/{model}): ✅ ({elapsed:.1f}s) {preview}')
                results.append((tier, True, text[:50], elapsed))
            else:
                print(f'  {tier} ({provider}/{model}): ❌ 빈 응답 ({elapsed:.1f}s)')
                results.append((tier, False, '빈 응답', elapsed))
        except Exception as e:
            elapsed = time.time() - start
            status = getattr(e, 'status_code', '?')
            print(f'  {tier} ({provider}/{model}): ❌ HTTP {status} {type(e).__name__}: {str(e)[:100]} ({elapsed:.1f}s)')
            results.append((tier, False, f'HTTP {status} {type(e).__name__}', elapsed))

        time.sleep(1)  # rate limit 완화

    print()
    ok_count = sum(1 for r in results if r[1])
    print(f'=== 결과: {ok_count}/{len(free_tiers)} 성공 ===')
    if ok_count < 10:
        print('⚠️ 10개 미만 — API 키/엔드포인트 점검 필요')
        sys.exit(2)
    print('✅ 스모크 테스트 통과 기준 충족 (10개 이상)')


if __name__ == '__main__':
    main()
