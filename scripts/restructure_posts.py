#!/usr/bin/env python3
"""
Phase 34: 블로그 포스트 구조 재구성
- frontmatter 다음, 첫 H2 이전에 도입단락 추가
- 도입단락 = 첫 H2 직후의 첫 단락 (빈 줄까지)
- 메타 도입문 패턴(26개 확장) 매칭 시 해당 문장 제거
- 메타 도입문 제거 후 단락이 비면: 다음 단락 사용
- description = 도입단락의 첫 문장 (Phase 32 로직 유지)
- yaml.dump() 기반 frontmatter 재작성 (기존 로직 유지)
"""
import os
import re
import sys
import yaml
from datetime import datetime
from pathlib import Path

# 프로젝트 루트 설정
PROJECT_DIR = Path(__file__).parent.parent
BLOG_DIR = PROJECT_DIR / "src" / "content" / "blog"

# 26개 메타 도입문 패턴 (확장판)
META_INTRO_PATTERNS = [
    # 기본 패턴들
    r'본\s+포스트에서는\s+[^.!?]*[.!?]',
    r'본\s+글에서는\s+[^.!?]*[.!?]',
    r'이번\s+포스트에서는\s+[^.!?]*[.!?]',
    r'이번\s+글에서는\s+[^.!?]*[.!?]',
    r'이번\s+글에서\s+[^.!?]*[.!?]',
    r'이\s+글에서는\s+[^.!?]*[.!?]',
    r'이\s+포스트에서는\s+[^.!?]*[.!?]',
    # 동사 변형들
    r'살펴보겠습니다[.!?]',
    r'살펴보도록\s+하겠습니다[.!?]',
    r'알아보겠습니다[.!?]',
    r'알아보도록\s+하겠습니다[.!?]',
    r'다루겠습니다[.!?]',
    r'다루도록\s+하겠습니다[.!?]',
    r'논의하겠습니다[.!?]',
    r'분석하겠습니다[.!?]',
    r'설명드리겠습니다[.!?]',
    r'소개해\s+드리겠습니다[.!?]',
    r'들여다보겠습니다[.!?]',
    r'짚어보겠습니다[.!?]',
    r'정리해\s+보겠습니다[.!?]',
    r'살펴봅니다[.!?]',
    r'알아봅니다[.!?]',
    r'다룹니다[.!?]',
    # 미래형/종결형 변형
    r'살펴볼\s+것입니다[.!?]',
    r'알아볼\s+것입니다[.!?]',
    r'다룰\s+것입니다[.!?]',
]

# 컴파일된 패턴 (성능 최적화)
_COMPILED_META_PATTERNS = [re.compile(p, re.IGNORECASE) for p in META_INTRO_PATTERNS]

# 한국어 문장 종결어미 패턴 (description 추출용)
_KOREAN_SENTENCE_ENDINGS = (
    r'(?<!\d)[.!?](?!\d)|'
    r'(?:'
    r'습니다|입니다|했습니다|'
    r'합니다|있습니다|였습니다|됩니다|'
    r'봅니다|듣습니다|옵니다|갑니다|줍니다|삽니다|팝니다|만듭니다|'
    r'생각합니다|느낍니다|알고 있습니다|모릅니다|'
    r'임|음|이다|한다|했다|'
    r'요|함'
    r')(?=[\s\.\!\?]|$)'
)
_KOR_END_PATTERN = re.compile(_KOREAN_SENTENCE_ENDINGS)


def extract_first_sentence(text: str, max_len: int = 300) -> str:
    """텍스트에서 첫 번째 완전한 문장만 추출"""
    if not text:
        return ""
    
    # 마크다운 헤딩, 링크, 수평선 제거
    text = re.sub(r"^(\s*[-*]{3,}\s*)+", "", text)
    text = re.sub(r"^##?\s*(서론|들어가며|시작하며|개요)\s*[:：]?\s*", "", text)
    text = re.sub(r"^##?\s+[^\n]+\n\s*", "", text)
    text = re.sub(r"^(\s*\[.*?\]\([^)]+\)\s*)+", "", text)
    text = re.sub(r"[#*>\n\s]+", " ", text).strip()
    
    if not text:
        return ""
    
    # 첫 번째 종결어미 찾기
    m = _KOR_END_PATTERN.search(text)
    if m:
        end_pos = m.end()
        sentence_text = text[:end_pos]
        
        # 문장 시작점 찾기
        last_boundary = -1
        for pattern in ['. ', '! ', '? ', '\n']:
            idx = sentence_text.rfind(pattern)
            if idx > last_boundary:
                last_boundary = idx
        for ending in ['다 ', '요 ', '함 ', '습니다 ', '입니다 ', '했습니다 ', '합니다 ', '있습니다 ', '였습니다 ', '됩니다 ']:
            idx = sentence_text.rfind(ending)
            if idx > last_boundary:
                last_boundary = idx + len(ending) - 1
        
        if last_boundary > 0:
            start = last_boundary + 1
        else:
            start = 0
        
        first_sentence = sentence_text[start:end_pos].strip()
        if len(first_sentence) < 10:
            m2 = _KOR_END_PATTERN.search(text)
            if m2:
                return text[:m2.end()].strip()
        
        if len(first_sentence) > max_len:
            return first_sentence[:max_len].strip()
        return first_sentence
    
    # 종결어미 못 찾으면 max_len에서 공백 기준 자름
    last_space = text.rfind(' ', 0, max_len)
    if last_space > 0:
        return text[:last_space].strip()
    
    return text[:max_len].strip()


def remove_meta_intro(paragraph: str) -> str:
    """단락에서 메타 도입문 패턴 제거"""
    if not paragraph:
        return paragraph
    
    result = paragraph
    for pattern in _COMPILED_META_PATTERNS:
        result = pattern.sub('', result)
    
    # 연속된 공백 정리
    result = re.sub(r'\s+', ' ', result).strip()
    return result


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """MD 파일에서 frontmatter와 body 분리 (표준 frontmatter: 첫 번째 --- ~ 두 번째 ---, 필수 필드 포함된 것 우선)"""
    # --- 구분자 위치 모두 찾기 (줄 시작에서)
    delim_positions = []
    for m in re.finditer(r'^---$', content, re.MULTILINE):
        delim_positions.append(m.start())
    
    if len(delim_positions) < 2:
        return {}, content
    
    # 첫 번째 ---는 반드시 파일 시작(또는 공백 후)에 있어야 함
    first_delim = delim_positions[0]
    if first_delim > 0 and content[:first_delim].strip():
        # 파일 시작이 ---가 아님
        return {}, content
    
    # 두 번째 ---부터 시도하며 유효한 frontmatter 찾기 (title, date 등 필수 필드 포함)
    for i in range(1, len(delim_positions)):
        second_delim = delim_positions[i]
        fm_str = content[first_delim + 3:second_delim].strip()
        body = content[second_delim + 3:].lstrip('\n')
        
        try:
            fm = yaml.safe_load(fm_str)
            if fm and isinstance(fm, dict) and 'title' in fm and 'date' in fm:
                return fm, body
        except Exception:
            continue
    
    # 필수 필드 있는 것 못 찾으면 첫 번째 쌍 사용 (폴백)
    second_delim = delim_positions[1]
    fm_str = content[first_delim + 3:second_delim].strip()
    body = content[second_delim + 3:].lstrip('\n')
    
    try:
        fm = yaml.safe_load(fm_str)
        if fm is None:
            fm = {}
    except Exception:
        fm = {}
        for line in fm_str.split('\n'):
            line = line.strip()
            if not line or ':' not in line:
                continue
            key, _, val = line.partition(':')
            key = key.strip()
            val = val.strip()
            if val.startswith('[') and val.endswith(']'):
                items = []
                for item in re.findall(r'"([^"]*?)"', val):
                    items.append(item)
                fm[key] = items
            elif val in ('true', 'false'):
                fm[key] = val == 'true'
            elif val.isdigit():
                fm[key] = int(val)
            else:
                fm[key] = val.strip('"').strip("'")
    return fm, body


def rebuild_frontmatter(fields: dict) -> str:
    """frontmatter dict를 YAML 문자열로 변환 (키 순서 유지, yaml.dump 사용)"""
    # 키 순서 유지 (기존 순서 우선)
    ordered_keys = ['title', 'description', 'date', 'category', 'tags', 'draft', 'image']
    
    # 순서대로 정렬된 dict 생성
    ordered_fields = {}
    for key in ordered_keys:
        if key in fields:
            ordered_fields[key] = fields[key]
    for key, val in fields.items():
        if key not in ordered_keys:
            ordered_fields[key] = val
    
    # yaml.dump로 안전하게 직렬화 (기본 스타일: block for lists)
    yaml_str = yaml.dump(ordered_fields, allow_unicode=True, sort_keys=False, default_flow_style=False)
    return '---\n' + yaml_str + '---'


def find_first_h2(body: str) -> tuple[int, int] | None:
    """본문에서 첫 번째 H2 헤딩의 위치(시작, 끝) 반환"""
    # ## 로 시작하는 첫 줄 찾기 (공백 허용)
    for match in re.finditer(r'^##\s+.+$', body, re.MULTILINE):
        return match.start(), match.end()
    return None


def extract_first_paragraph_after_h2(body: str, h2_end: int) -> tuple[str, int, int] | None:
    """첫 H2 직후의 첫 번째 단락 추출 (빈 줄까지). 반환: (단락텍스트, 시작위치, 끝위치)"""
    # H2 이후부터 검색
    after_h2 = body[h2_end:]
    
    # 선행 공백/줄바꿈 스킵
    i = 0
    while i < len(after_h2) and after_h2[i] in '\n\r ':
        i += 1
    
    if i >= len(after_h2):
        return None
    
    # 첫 단락: 빈 줄(\n\n) 또는 다음 헤딩(##, ###) 또는 끝까지
    paragraph_start = i
    paragraph_end = i
    
    while paragraph_end < len(after_h2):
        # 빈 줄(두 번 연속 개행) 감지
        if paragraph_end + 1 < len(after_h2) and after_h2[paragraph_end] == '\n' and after_h2[paragraph_end + 1] == '\n':
            break
        # 다음 헤딩 감지
        if after_h2[paragraph_end] == '\n' and paragraph_end + 2 < len(after_h2):
            if after_h2[paragraph_end + 1] == '#' or (after_h2[paragraph_end + 1] == '#' and after_h2[paragraph_end + 2] == '#'):
                break
        paragraph_end += 1
    
    paragraph = after_h2[paragraph_start:paragraph_end].strip()
    
    if not paragraph:
        return None
    
    # 절대 위치로 변환
    abs_start = h2_end + paragraph_start
    abs_end = h2_end + paragraph_end
    
    return paragraph, abs_start, abs_end


def find_next_paragraph(body: str, start_pos: int) -> tuple[str, int, int] | None:
    """주어진 위치 이후의 다음 단락 찾기"""
    after = body[start_pos:]
    
    # 선행 공백/줄바꿈 스킵
    i = 0
    while i < len(after) and after[i] in '\n\r ':
        i += 1
    
    if i >= len(after):
        return None
    
    paragraph_start = i
    paragraph_end = i
    
    while paragraph_end < len(after):
        if paragraph_end + 1 < len(after) and after[paragraph_end] == '\n' and after[paragraph_end + 1] == '\n':
            break
        if after[paragraph_end] == '\n' and paragraph_end + 2 < len(after):
            if after[paragraph_end + 1] == '#' or (after[paragraph_end + 1] == '#' and after[paragraph_end + 2] == '#'):
                break
        paragraph_end += 1
    
    paragraph = after[paragraph_start:paragraph_end].strip()
    if not paragraph:
        return None
    
    abs_start = start_pos + paragraph_start
    abs_end = start_pos + paragraph_end
    return paragraph, abs_start, abs_end


def is_h2_empty(body: str, h2_start: int, h2_end: int) -> bool:
    """첫 H2가 빈 H2인지 확인 (H2 다음에 일반 텍스트 단락 없이 바로 다음 H2가 오거나 끝까지 비어있음)"""
    after_h2 = body[h2_end:]
    
    # 선행 공백/줄바꿈 스킵
    i = 0
    while i < len(after_h2) and after_h2[i] in '\n\r ':
        i += 1
    
    if i >= len(after_h2):
        # H2 다음에 아무것도 없음
        return True
    
    # 다음 문자가 #으로 시작하면 (다음 H2/H3) 빈 H2
    if after_h2[i] == '#':
        return True
    
    # 일반 텍스트가 있으면 빈 H2가 아님
    return False


def remove_empty_first_h2(body: str) -> str:
    """첫 번째 H2가 빈 H2이면 제거하고 본문 반환"""
    h2_pos = find_first_h2(body)
    if not h2_pos:
        return body
    
    h2_start, h2_end = h2_pos
    
    if is_h2_empty(body, h2_start, h2_end):
        # 빈 H2 라인 제거 (해당 줄 전체 삭제)
        # 줄 시작부터 줄 끝까지 찾기
        line_start = body.rfind('\n', 0, h2_start) + 1
        line_end = body.find('\n', h2_end)
        if line_end == -1:
            line_end = len(body)
        
        # 빈 H2 줄 삭제
        new_body = body[:line_start] + body[line_end:]
        
        # 연속된 빈 줄 정규화 (최대 1개)
        new_body = re.sub(r'\n{3,}', '\n\n', new_body)
        
        return new_body.lstrip('\n')
    
    return body


def process_file(filepath: Path, dry_run: bool = False) -> dict:
    """단일 MD 파일 처리"""
    filename = filepath.name
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    fm, body = parse_frontmatter(content)
    
    # 첫 H2 찾기
    h2_pos = find_first_h2(body)
    if not h2_pos:
        return {'file': filename, 'status': 'skip', 'reason': 'H2 헤딩 없음'}
    
    h2_start, h2_end = h2_pos
    
    # H2 직후 첫 단락 추출
    first_para_result = extract_first_paragraph_after_h2(body, h2_end)
    
    intro_paragraph = None
    intro_start = None
    intro_end = None
    
    if first_para_result:
        para_text, para_start, para_end = first_para_result
        # 메타 도입문 제거
        cleaned = remove_meta_intro(para_text)
        
        if cleaned.strip():
            intro_paragraph = cleaned
            intro_start = para_start
            intro_end = para_end
        else:
            # 비었으면 다음 단락 찾기
            next_para = find_next_paragraph(body, para_end)
            if next_para:
                next_text, next_start, next_end = next_para
                cleaned_next = remove_meta_intro(next_text)
                if cleaned_next.strip():
                    intro_paragraph = cleaned_next
                    intro_start = next_start
                    intro_end = next_end
    
    if not intro_paragraph:
        return {'file': filename, 'status': 'skip', 'reason': '도입단락 추출 실패'}
    
    # description 생성 (도입단락의 첫 문장)
    new_description = extract_first_sentence(intro_paragraph, 300)
    
    # 본문에서 도입단락 제거
    new_body = body[:intro_start] + body[intro_end:]
    
    # 🔧 핵심 수정: 첫 H2가 빈 H2가 되었는지 확인하고, 그렇다면 제거
    new_body = remove_empty_first_h2(new_body)
    
    # H2 위치 재계산 (단락 제거 + 빈 H2 제거로 위치가 변함)
    new_h2_pos = find_first_h2(new_body)
    if not new_h2_pos:
        return {'file': filename, 'status': 'error', 'reason': 'H2 헤딩 손실'}
    
    new_h2_start, new_h2_end = new_h2_pos
    
    # H2 앞에 도입단락 삽입 (빈 줄 하나 두고)
    # frontmatter 끝난 직후(H2 이전)에 삽입
    before_h2 = new_body[:new_h2_start].rstrip('\n')
    after_h2 = new_body[new_h2_start:]
    
    # 이미 앞부분에 내용이 있으면(보통 frontmatter 바로 뒤) 빈 줄로 구분
    if before_h2.strip():
        new_body = before_h2 + '\n\n' + intro_paragraph + '\n\n' + after_h2
    else:
        new_body = intro_paragraph + '\n\n' + after_h2
    
    # frontmatter 업데이트
    fm['description'] = new_description
    
    new_fm = rebuild_frontmatter(fm)
    new_content = new_fm + '\n' + new_body
    
    if dry_run:
        return {
            'file': filename,
            'status': 'dry-run',
            'intro_preview': intro_paragraph[:100],
            'description': new_description[:100],
        }
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    return {
        'file': filename,
        'status': 'updated',
        'intro_length': len(intro_paragraph),
        'description': new_description[:100],
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description='블로그 포스트 구조 재구성')
    parser.add_argument('--dry-run', action='store_true', help='미리보기만 실행')
    parser.add_argument('--file', type=str, help='특정 파일만 처리 (파일명)')
    parser.add_argument('--all', action='store_true', help='전체 파일 처리')
    args = parser.parse_args()
    
    if not BLOG_DIR.exists():
        print(f"에러: {BLOG_DIR} 없음")
        sys.exit(1)
    
    if args.file:
        files = [BLOG_DIR / args.file]
    elif args.all:
        files = sorted(BLOG_DIR.glob("*.md"))
    else:
        # 기본: 009, 011 테스트 파일만
        test_files = [
            "2026-07-25-009-코그니션의-포크-인수-이유와-데빈-통합-전망-분석.md",
            "2026-07-25-011-알파폴드-ai가-유전자-편집-단백질을-더-안전하게-재설계하는-방법과-미래-전망.md",
        ]
        files = [BLOG_DIR / f for f in test_files if (BLOG_DIR / f).exists()]
    
    print(f"대상 파일: {len(files)}개\n")
    
    results = []
    for fpath in files:
        if not fpath.exists():
            print(f"  ⚠️  {fpath.name}: 파일 없음")
            continue
        result = process_file(fpath, dry_run=args.dry_run)
        results.append(result)
        
        if result['status'] == 'skip':
            print(f"  ⏭️  {result['file']} → {result.get('reason', '')}")
        elif result['status'] == 'dry-run':
            print(f"  🔍 {result['file']}")
            print(f"     도입단락: {result.get('intro_preview', '')}...")
            print(f"     description: {result.get('description', '')}...")
        elif result['status'] == 'updated':
            print(f"  ✅ {result['file']} → 도입단락 {result.get('intro_length', 0)}자, description 갱신")
        elif result['status'] == 'error':
            print(f"  ❌ {result['file']} → {result.get('reason', '')}")
    
    updated = [r for r in results if r['status'] == 'updated']
    dry_run = [r for r in results if r['status'] == 'dry-run']
    errors = [r for r in results if r['status'] == 'error']
    
    print(f"\n{'='*55}")
    if args.dry_run:
        print(f"🔍 DRY RUN — 수정 대상: {len(dry_run)}개, 스킵: {len([r for r in results if r['status']=='skip'])}개, 오류: {len(errors)}개")
    else:
        print(f"✅ 완료: {len(updated)}개 파일 수정, {len(errors)}개 오류")


if __name__ == '__main__':
    main()