#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
"""
writer_v2.py — 단순화된 GPT-4o 호출 (5개 규칙만)
- 클러스터 + enrichment → 쓰레드
"""
import os, re
from datetime import datetime
from openai import OpenAI

PROJECT_DIR = '/Users/twinssn/Projects/aikorea24'
THREADS_DIR = os.path.join(PROJECT_DIR, 'scripts', 'threads')
LOGS_DIR = os.path.join(THREADS_DIR, 'logs')
DRAFTS_DIR = os.path.join(LOGS_DIR, 'drafts')
os.makedirs(DRAFTS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

def load_env(path):
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    if line.startswith('export '):
                        line = line[7:]
                    k, v = line.split('=', 1)
                    os.environ[k.strip()] = v.strip().strip('"').strip("'")

load_env(os.path.join(PROJECT_DIR, '.env'))
load_env(os.path.join(PROJECT_DIR, 'api_test', '.env.sh'))

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f'[{ts}] {msg}')
    with open(os.path.join(LOGS_DIR, datetime.now().strftime('%Y-%m-%d') + '.log'), 'a', encoding='utf-8') as f:
        f.write(f'[{ts}] {msg}\n')

SYSTEM_PROMPT = """Threads 글쓰기 규칙:
1. 정확히 8개 카드. 1/8 2/8 ... 8/8
2. 각 카드는 --- 로 구분
3. 7번 카드 끝 출처 URL 필수
4. 8번 카드는 8/8 + CTA 3줄만
5. 레이블 금지. 카드 번호만
6. 각 카드 최소 2줄. 1번 카드는 3줄↑
7. 전체에 숫자 1개 이상 포함
8. 문장은 간결하게. 이모지 금지"""

def write_thread_v2(cluster):
    api_key = os.environ.get('OPENAI_API_KEY', '')
    if not api_key:
        log('  ❌ OPENAI_API_KEY 없음')
        return ''

    arts = cluster['articles']
    enrich = cluster.get('enrichment', {})

    # 동적 기사 섹션 생성 (상위 2개만, 짧게)
    article_sections = []
    all_links = []
    for i, art in enumerate(arts[:2], 1):
        title = art.get('title', '')
        desc = (art.get('description', '') or '')[:200]
        source = art.get('source', '')
        link = art.get('link', '')
        if link:
            all_links.append(link)
        section = f"""기사 {i}: {title}
본문: {desc}
출처: {source}
링크: {link}"""
        article_sections.append(section)

    enrichment_text = ''
    e = enrich
    if e.get('background'):
        enrichment_text += f'\n배경: {" ".join(e["background"][:2])}'
    if e.get('twist'):
        enrichment_text += f'\n반전: {" ".join(e["twist"][:2])}'
    if e.get('numbers'):
        enrichment_text += f'\n숫자: {", ".join(e["numbers"][:5])}'

    links_str = ' / '.join(all_links)

    user = f"""아래 기사들로 8개 카드 Threads를 작성하세요.

{' '.join(article_sections)}
{enrichment_text}

출처: {links_str}"""

    from validator import validate_thread

    for attempt in range(3):
        try:
            client = OpenAI(api_key=api_key)
            resp = client.chat.completions.create(
                model='gpt-4o',
                messages=[
                    {'role': 'system', 'content': SYSTEM_PROMPT},
                    {'role': 'user', 'content': user},
                ],
                temperature=0.7,
                max_tokens=2500,
            )
            content = resp.choices[0].message.content.strip()
            content = re.sub(r'^```[a-z]*\n?', '', content)
            content = re.sub(r'\n?```$', '', content)
            content = content.strip()

            passed, failures = validate_thread(content)
            if passed:
                log(f'  GPT-4o: {len(content)}자, 품질 합격')
                return content
            log(f'  재시도 {attempt+2}/3: {failures}')
        except Exception as e:
            log(f'  ❌ GPT 오류: {e}')

    log('  ❌ 3회 재시도 실패')
    return ''

def save_draft(content, cluster):
    now = datetime.now()
    kw = cluster.get('keywords', {})
    label = (kw.get('persons') + kw.get('companies'))[:1]
    label_str = str(label[0]) if label else 'thread'
    safe = re.sub(r'[^a-zA-Z0-9가-힣]', '', label_str)[:15]
    fname = f'{now.strftime("%Y-%m-%d-%H")}-{safe}_v2.txt'
    fpath = os.path.join(DRAFTS_DIR, fname)
    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(content)
    log(f'  💾 초안 저장: {fpath}')
    return fpath

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    from db_reader_v2 import get_clusters
    from scorer_v2 import score_clusters, select_best_cluster
    from enricher import enrich_cluster
    clusters = get_clusters()
    scored = score_clusters(clusters)
    best = select_best_cluster(scored)
    if not best:
        print('선택된 클러스터 없음'); sys.exit(0)
    enriched = enrich_cluster(best)
    content = write_thread_v2(enriched)
    if content:
        print(f'\n{"="*70}\n{content}\n{"="*70}')
        save_draft(content, best)
