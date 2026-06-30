#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
"""
기존 src/content/tools/*.md 파일에 tasks, updated 필드 자동 채우기 (GPT 호출 없음)
scripts/task_config.py의 40개 태스크 vocabulary 기반 키워드 매칭

사용법:
  python3 scripts/backfill_tasks.py           # 실제 수정
  python3 scripts/backfill_tasks.py --dry-run # 결과만 미리보기
  python3 scripts/backfill_tasks.py --verbose # 상세 로그
"""
import os, re, sys
from datetime import datetime

from pipeline.infra import project_root; PROJECT_DIR = project_root()

from pipeline.infra.logger import get_scrubbed_logger
logger = get_scrubbed_logger(__name__)

TOOLS_DIR = os.path.join(PROJECT_DIR, 'src/content/tools')

# ============================================
# task_config.py import
# ============================================
sys.path.insert(0, os.path.join(PROJECT_DIR, 'scripts'))
from task_config import TASKS

ALL_SLUGS = set(TASKS.keys())
TODAY = datetime.now().strftime('%Y-%m-%d')

# ============================================
# 매핑 규칙 (GPT 없이 heuristic 매칭)
# ============================================

# 1. 태그명 → 태스크 슬러그 (직접 매칭)
TAG_TO_TASKS = {
    '챗봇': ['챗봇-구축', '글쓰기'],
    '글쓰기': ['글쓰기', '카피라이팅', '블로그-작성', '이메일-작성'],
    '만능': ['글쓰기', '요약', '번역'],
    '코딩': ['코딩', '코드-리뷰'],
    '번역': ['번역'],
    '문서분석': ['요약', '논문-요약', 'pdf-요약'],
    '요약': ['요약', 'pdf-요약', '유튜브-요약', '회의-요약', '논문-요약'],
    '이미지생성': ['이미지-생성', '이미지-생성-무료'],
    '이미지': ['이미지-생성', '이미지-생성-무료'],
    '일러스트': ['이미지-생성'],
    '디자인': ['이미지-생성', '로고-디자인', '썸네일-제작', '배경-제거'],
    '아트': ['이미지-생성'],
    '영상': ['영상-제작', '영상-편집'],
    '음성': ['음성-변환', '텍스트-음성', '더빙'],
    '음악': ['음악-생성'],
    '자막': ['자막-생성'],
    '데이터': ['데이터-분석'],
    '엑셀': ['엑셀-자동화'],
    '자동화': ['업무-자동화'],
    '회의': ['회의-요약'],
    '일정': ['일정-관리'],
    'sns': ['sns-콘텐츠'],
    'SNS': ['sns-콘텐츠'],
    'seo': ['seo-최적화'],
    'SEO': ['seo-최적화'],
    '광고': ['광고-카피'],
    '블로그': ['블로그-작성'],
    '리서치': ['리서치'],
    '학습': ['영어-학습', '요약'],
    '논문': ['논문-요약', 'pdf-요약'],
    '노코드': ['노코드'],
    '카피': ['카피라이팅', '광고-카피'],
    '이력서': ['이력서'],
    '맞춤법': ['맞춤법-교정'],
    '보고서': ['보고서-작성'],
    'ppt': ['ppt-발표'],
    'PPT': ['ppt-발표'],
    '프레젠테이션': ['ppt-발표'],
    '썸네일': ['썸네일-제작'],
    '배경': ['배경-제거'],
    '로고': ['로고-디자인'],
    '카피라이팅': ['카피라이팅'],
    '인포그래픽': ['인포그래픽'],
}

# 2. 카테고리 → 기본 태스크 그룹
CATEGORY_TO_TASKS = {
    '글쓰기·챗봇': ['글쓰기', '이메일-작성', '카피라이팅', '보고서-작성', '챗봇-구축', '이력서', '맞춤법-교정'],
    '이미지 생성': ['이미지-생성', '이미지-생성-무료', '배경-제거', '썸네일-제작', '로고-디자인', 'ppt-발표', '인포그래픽'],
    '영상·음성': ['영상-제작', '영상-편집', '자막-생성', '음성-변환', '더빙', '음악-생성', '텍스트-음성'],
    '업무·생산성': ['회의-요약', '일정-관리', '데이터-분석', '엑셀-자동화', '업무-자동화'],
    '코딩·개발': ['코딩', '코드-리뷰', '노코드'],
    '디자인': ['이미지-생성', '이미지-생성-무료', '로고-디자인', 'ppt-발표', '인포그래픽', '배경-제거'],
    '번역·학습': ['번역', '영어-학습', '논문-요약', '요약'],
    '영상·이미지': ['영상-제작', '영상-편집', '이미지-생성', '이미지-생성-무료', '썸네일-제작'],
    '음성': ['음성-변환', '텍스트-음성', '더빙'],
    '영상': ['영상-제작', '영상-편집', '자막-생성', '음성-변환'],
    '이미지': ['이미지-생성', '이미지-생성-무료', '배경-제거'],
    '코딩': ['코딩', '코드-리뷰'],
    '개발·코딩': ['코딩', '코드-리뷰'],
    '생산성': ['데이터-분석', '엑셀-자동화', '업무-자동화', '회의-요약'],
    '생산성·업무': ['데이터-분석', '엑셀-자동화', '업무-자동화', '회의-요약'],
    '검색': ['리서치'],
    '음악': ['음악-생성'],
    '프레젠테이션': ['ppt-발표'],
}

# 3. useCases / description 키워드 → 태스크 슬러그
KEYWORD_TO_TASKS = {
    'pdf': ['pdf-요약'],
    '유튜브': ['유튜브-요약'],
    '블로그': ['블로그-작성', '글쓰기'],
    '이메일': ['이메일-작성'],
    '번역': ['번역'],
    '요약': ['요약', 'pdf-요약', '논문-요약', '회의-요약'],
    '맞춤법': ['맞춤법-교정'],
    '보고서': ['보고서-작성'],
    '이력서': ['이력서'],
    '카피': ['카피라이팅'],
    '이미지': ['이미지-생성', '이미지-생성-무료'],
    '배경': ['배경-제거'],
    '썸네일': ['썸네일-제작'],
    '로고': ['로고-디자인'],
    'ppt': ['ppt-발표'],
    '프레젠테이션': ['ppt-발표'],
    '발표': ['ppt-발표'],
    '인포그래픽': ['인포그래픽'],
    '영상': ['영상-제작', '영상-편집'],
    '비디오': ['영상-제작', '영상-편집'],
    '동영상': ['영상-제작', '영상-편집'],
    '자막': ['자막-생성'],
    '음성': ['음성-변환', '텍스트-음성'],
    '더빙': ['더빙'],
    '음악': ['음악-생성'],
    '노래': ['음악-생성'],
    'tts': ['텍스트-음성'],
    '회의': ['회의-요약'],
    '일정': ['일정-관리'],
    '데이터': ['데이터-분석'],
    '엑셀': ['엑셀-자동화'],
    '자동화': ['업무-자동화'],
    '챗봇': ['챗봇-구축', '글쓰기'],
    '코딩': ['코딩', '코드-리뷰'],
    '코드': ['코딩', '코드-리뷰'],
    '개발': ['코딩', '코드-리뷰'],
    '노코드': ['노코드'],
    '논문': ['논문-요약', 'pdf-요약'],
    '영어': ['영어-학습', '번역'],
    '리서치': ['리서치'],
    'sns': ['sns-콘텐츠'],
    'seo': ['seo-최적화'],
    '광고': ['광고-카피'],
    '면접': ['이력서'],
    '여행': ['글쓰기'],
    '컨셉': ['이미지-생성'],
    '일러스트': ['이미지-생성'],
    '브랜드': ['로고-디자인', '이미지-생성'],
    '코드 리뷰': ['코드-리뷰'],
    '계약서': ['요약', 'pdf-요약'],
    '오디오': ['음악-생성', '음성-변환', '텍스트-음성'],
    '프레젠테이션': ['ppt-발표'],
    '슬라이드': ['ppt-발표'],
    '발표자료': ['ppt-발표'],
    '파워포인트': ['ppt-발표'],
    '비즈니스': ['보고서-작성', '이메일-작성'],
    '회화': ['영어-학습'],
    '발음': ['영어-학습'],
    '교육': ['영어-학습', '요약'],
    '연구': ['리서치', '논문-요약'],
    '학술': ['논문-요약'],
    '문서': ['요약'],
    '검색': ['리서치'],
    '자동완성': ['코딩'],
    '디버깅': ['코드-리뷰'],
    '워크플로우': ['업무-자동화'],
    '3d': ['이미지-생성'],
    '3D': ['이미지-생성'],
    '게임': ['이미지-생성'],
    'ui': ['이미지-생성', '로고-디자인'],
    'UX': ['로고-디자인', '이미지-생성'],
    '프로토타입': ['로고-디자인'],
    '협업': ['업무-자동화', '일정-관리'],
    '웹앱': ['노코드', '코딩'],
    '풀스택': ['코딩'],
    '브라우저': ['코딩', '노코드'],
    '숏폼': ['영상-편집', '영상-제작'],
    '틱톡': ['영상-편집'],
    '유튜브': ['유튜브-요약', '영상-편집'],
    '아바타': ['영상-제작'],
    '립싱크': ['영상-편집', '더빙'],
    '마케팅': ['sns-콘텐츠', '광고-카피'],
    '상품사진': ['이미지-생성'],
    '로컬 실행': ['코딩'],
    '파워유저': ['코딩'],
    '작곡': ['음악-생성'],
    '창작': ['음악-생성', '글쓰기'],
    'ai음악': ['음악-생성'],
    '리믹스': ['음악-생성'],
    '크리에이티브': ['이미지-생성', '영상-편집'],
    '모션': ['영상-편집'],
    '프로젝트관리': ['업무-자동화', '일정-관리'],
    '회의록': ['회의-요약'],
    '음성 인식': ['음성-변환'],
    '자동 요약': ['요약'],
    '출처': ['리서치'],
    '뉴스': ['리서치'],
    '기술 문서': ['요약', '리서치'],
    '클라우드 IDE': ['코딩'],
    'AI 코드 생성': ['코딩'],
    '배포': ['코딩', '노코드'],
    '오픈소스': ['코딩'],
    '카드뉴스': ['이미지-생성', 'sns-콘텐츠'],
    '포스터': ['이미지-생성', '썸네일-제작'],
    '인쇄': ['이미지-생성'],
    '템플릿': ['ppt-발표', '이미지-생성'],
    '한국': ['번역'],
    '일본어': ['번역'],
    '중국어': ['번역'],
    '다국어': ['번역'],
    '문서번역': ['번역'],
    '영문 교정': ['맞춤법-교정', '번역'],
    '문법': ['맞춤법-교정'],
    '학습': ['영어-학습', '요약'],
    '그래프': ['데이터-분석'],
    '통계': ['데이터-분석'],
    '시각화': ['인포그래픽', 'ppt-발표'],
    '다이어그램': ['인포그래픽'],
    '자동생성': ['글쓰기', 'ppt-발표'],
    '올인원': ['글쓰기', '요약'],
    '멀티모달': ['이미지-생성', '글쓰기'],
    'API': ['코딩'],
    '에이전트': ['챗봇-구축', '코딩'],
    '터미널': ['코딩'],
    'CLI': ['코딩'],
    '고급': ['코딩'],
    'Gemini': ['글쓰기', '챗봇-구축'],
    'Anthropic': ['글쓰기'],
    'Google': ['리서치', '요약'],
    '네이버': ['번역'],
    '구글': ['리서치'],
    'xAI': ['글쓰기'],
    '중국AI': ['번역'],
    '유럽AI': ['번역'],
    'AI검색': ['리서치'],
    'AI에이전트': ['챗봇-구축', '코딩'],
    'AI 크리에이티브': ['이미지-생성', '영상-편집'],
    'AI 작곡': ['음악-생성'],
    'AI영상': ['영상-제작', '영상-편집'],
}


def parse_frontmatter(content: str) -> dict:
    """MD frontmatter 파싱 (YAML 라이브러리 없이 regex)"""
    fm = {}
    m = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if not m:
        return fm
    body = m.group(1)
    for line in body.split('\n'):
        line = line.strip()
        if not line or ':' not in line:
            continue
        key, _, val = line.partition(':')
        key = key.strip()
        val = val.strip()
        # 리스트 처리 [...]
        if val.startswith('[') and val.endswith(']'):
            items = []
            for item in re.findall(r'"([^"]*?)"', val):
                items.append(item)
            fm[key] = items
        # 불리언
        elif val in ('true', 'false'):
            fm[key] = val == 'true'
        # 숫자
        elif val.isdigit():
            fm[key] = int(val)
        # 일반 문자열
        else:
            fm[key] = val.strip('"').strip("'")
    return fm


def rebuild_frontmatter(fields: dict) -> str:
    """frontmatter dict → YAML 문자열"""
    lines = ['---']
    for key in ['name', 'description', 'category', 'price', 'koreanSupport',
                'difficulty', 'url', 'image', 'relatedPost',
                'useCases', 'tags', 'featured', 'order', 'tasks', 'updated']:
        if key not in fields:
            continue
        val = fields[key]
        if key in ('koreanSupport', 'featured'):
            lines.append(f'{key}: {str(val).lower()}')
        elif isinstance(val, list):
            items = ', '.join(f'"{v}"' for v in val)
            lines.append(f'{key}: [{items}]')
        elif isinstance(val, int):
            lines.append(f'{key}: {val}')
        else:
            lines.append(f'{key}: "{val}"')
    lines.append('---')
    return '\n'.join(lines)


def infer_tasks(fm: dict) -> list:
    """frontmatter 정보로 태스크 슬러그 추론"""
    scores = {slug: 0.0 for slug in ALL_SLUGS}

    # --- signal 1: tags (가장 강한 신호, 가중치 3.0) ---
    tags = fm.get('tags', [])
    if isinstance(tags, str):
        tags = [tags]
    for tag in tags:
        tag_key = tag.strip()
        # 태그 매칭: 원본 → 소문자 → 타이틀케이스 순으로 시도
        if tag_key in TAG_TO_TASKS:
            matched = TAG_TO_TASKS[tag_key]
        elif tag_key.lower() in TAG_TO_TASKS:
            matched = TAG_TO_TASKS[tag_key.lower()]
        elif tag_key.title() in TAG_TO_TASKS:
            matched = TAG_TO_TASKS[tag_key.title()]
        else:
            matched = None
        if matched:
            for t in matched:
                scores[t] += 3.0

    # --- signal 2: useCases 키워드 (가중치 2.0) ---
    use_cases = fm.get('useCases', [])
    if isinstance(use_cases, str):
        use_cases = [use_cases]
    uc_text = ' '.join(use_cases)
    uc_lower = uc_text.lower()
    for keyword, task_list in KEYWORD_TO_TASKS.items():
        if keyword.lower() in uc_lower:
            for t in task_list:
                scores[t] += 2.0

    # --- signal 3: category (가중치 1.5) ---
    category = fm.get('category', '')
    if category in CATEGORY_TO_TASKS:
        for t in CATEGORY_TO_TASKS[category]:
            scores[t] += 1.5

    # --- signal 4: description 키워드 (가중치 1.0) ---
    desc = fm.get('description', '')
    desc_lower = desc.lower()
    for keyword, task_list in KEYWORD_TO_TASKS.items():
        if keyword.lower() in desc_lower:
            for t in task_list:
                scores[t] += 1.0

    # --- 결과 정렬 (1~3개 선택) ---
    ranked = [(s, slug) for slug, s in scores.items() if s > 0]
    ranked.sort(reverse=True)

    # 상위 스코어가 0.5 이상 차이나는 것까지만 선택 (최대 3개)
    if not ranked:
        return []
    top_score = ranked[0][0]
    if top_score < 1.0:
        return []

    result = []
    for score, slug in ranked:
        if score >= top_score * 0.5 and len(result) < 3:
            result.append(slug)
    return result


def process_file(filepath: str, dry_run: bool = False, verbose: bool = False) -> dict:
    """단일 MD 파일 처리 → 결과 dict"""
    filename = os.path.basename(filepath)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # frontmatter 파싱
    fm = parse_frontmatter(content)
    name = fm.get('name', filename)

    # 이미 tasks가 채워져 있으면 skip
    existing_tasks = fm.get('tasks', [])
    if existing_tasks and len(existing_tasks) > 0:
        return {'file': filename, 'name': name, 'status': 'skip', 'reason': '이미 tasks 있음', 'tasks': existing_tasks}

    # 태스크 추론
    inferred = infer_tasks(fm)
    if not inferred:
        return {'file': filename, 'name': name, 'status': 'skip', 'reason': '매칭되는 태스크 없음', 'tasks': []}

    # updated 필드 추가/갱신
    has_updated = 'updated' in fm and fm['updated']
    today = TODAY

    if dry_run:
        changes = []
        changes.append(f"  tasks: [] → {inferred}")
        if not has_updated:
            changes.append(f"  updated: (없음) → {today}")
        return {
            'file': filename, 'name': name, 'status': 'dry-run',
            'tasks': inferred, 'updated': today,
            'changes': changes, 'category': fm.get('category', ''),
            'tags': fm.get('tags', []),
        }

    # 실제 수정
    # frontmatter 영역만 교체
    fm_match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if not fm_match:
        return {'file': filename, 'name': name, 'status': 'error', 'reason': 'frontmatter 파싱 실패'}

    fm_body = fm_match.group(1)
    fm_lines = fm_body.split('\n')

    # tasks 라인 추가/수정
    tasks_str = ', '.join(f'"{t}"' for t in inferred)
    tasks_line = f'tasks: [{tasks_str}]'

    # updated 라인
    updated_line = f'updated: "{today}"'

    new_fm_lines = []
    tasks_added = False
    updated_added = False

    for line in fm_lines:
        stripped = line.strip()
        if stripped.startswith('tasks:'):
            new_fm_lines.append(tasks_line)
            tasks_added = True
        elif stripped.startswith('updated:'):
            new_fm_lines.append(updated_line)
            updated_added = True
        else:
            new_fm_lines.append(line)

    if not tasks_added:
        # tasks가 없던 파일 → order 뒤나 맨 끝에 추가
        new_fm_lines.append(tasks_line)
    if not updated_added:
        new_fm_lines.append(updated_line)

    new_fm_body = '\n'.join(new_fm_lines)
    new_content = content.replace(fm_body, new_fm_body, 1)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

    return {
        'file': filename, 'name': name, 'status': 'updated',
        'tasks': inferred, 'updated': today,
        'category': fm.get('category', ''),
        'tags': fm.get('tags', []),
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description='기존 MD 파일 tasks/updated 필드 백필')
    parser.add_argument('--dry-run', action='store_true', help='실제 수정 없이 결과만 출력')
    parser.add_argument('--verbose', action='store_true', help='상세 로그 출력')
    args = parser.parse_args()

    if not os.path.isdir(TOOLS_DIR):
        print(f"에러: {TOOLS_DIR} 없음")
        sys.exit(1)

    md_files = sorted([f for f in os.listdir(TOOLS_DIR) if f.endswith('.md')])
    print(f"대상 파일: {len(md_files)}개")
    print()

    results = []
    for fname in md_files:
        fpath = os.path.join(TOOLS_DIR, fname)
        result = process_file(fpath, dry_run=args.dry_run, verbose=args.verbose)
        results.append(result)

        if result['status'] == 'skip':
            if args.verbose:
                print(f"  ⏭️  {result['name']:25s} → {result['reason']}")
        elif result['status'] == 'dry-run':
            print(f"  🔍 {result['name']:25s} (cat:{result.get('category','')})")
            for ch in result.get('changes', []):
                print(f"     {ch}")
            print(f"     tags: {result.get('tags', [])}")
        elif result['status'] == 'updated':
            print(f"  ✅ {result['name']:25s} → tasks={result['tasks']}, updated={result['updated']}")
        elif result['status'] == 'error':
            print(f"  ❌ {result['name']:25s} → {result.get('reason', '오류')}")

    # 요약
    print(f"\n{'='*55}")
    updated = [r for r in results if r['status'] == 'updated']
    dry_run = [r for r in results if r['status'] == 'dry-run']
    skipped = [r for r in results if r['status'] == 'skip']
    errors = [r for r in results if r['status'] == 'error']

    if args.dry_run:
        print(f"🔍 DRY RUN — 수정 안 함")
        print(f"   수정 대상: {len(dry_run)}개 파일")
        print(f"   이미 완료: {len(skipped)}개")
    else:
        print(f"✅ 수정 완료: {len(updated)}개 파일")
        print(f"   이미 완료(skip): {len(skipped)}개")
        print(f"   오류: {len(errors)}개")

    if updated:
        print(f"\n--- 수정된 파일 목록 ---")
        for r in updated:
            print(f"  + {r['file']} → {r['tasks']}")


if __name__ == '__main__':
    main()
