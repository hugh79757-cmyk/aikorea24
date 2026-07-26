#!/usr/bin/env python3
"""
빈 H2 감지 스크립트 (detect_empty_h2.py)

3가지 패턴 감지:
- Pattern 1: H2 → 빈 줄 → H2 (공백 라인만)
- Pattern 2: H2 → H2 (공백 라인 없음, 바로 다음 헤딩)
- Pattern 3: H2 → 비-텍스트 콘텐츠만(이미지/인용/코드블록) → H2

출력: 파일명, 빈 H2 텍스트, 다음 H2 텍스트, 주변 5라인 컨텍스트
"""
import re
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
BLOG_DIR = PROJECT_DIR / "src" / "content" / "blog"


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """MD 파일에서 frontmatter와 body 분리"""
    delim_positions = []
    for m in re.finditer(r'^---$', content, re.MULTILINE):
        delim_positions.append(m.start())
    
    if len(delim_positions) < 2:
        return {}, content
    
    first_delim = delim_positions[0]
    if first_delim > 0 and content[:first_delim].strip():
        return {}, content
    
    for i in range(1, len(delim_positions)):
        second_delim = delim_positions[i]
        fm_str = content[first_delim + 3:second_delim].strip()
        body = content[second_delim + 3:].lstrip('\n')
        try:
            import yaml
            fm = yaml.safe_load(fm_str)
            if fm and isinstance(fm, dict) and 'title' in fm and 'date' in fm:
                return fm, body
        except Exception:
            continue
    
    second_delim = delim_positions[1]
    fm_str = content[first_delim + 3:second_delim].strip()
    body = content[second_delim + 3:].lstrip('\n')
    return {}, body


def find_all_h2_positions(body: str) -> list[tuple[int, int, str]]:
    """본문에서 모든 H2 헤딩의 위치와 텍스트 반환: [(start, end, text), ...]"""
    h2_list = []
    for match in re.finditer(r'^##\s+(.+)$', body, re.MULTILINE):
        h2_list.append((match.start(), match.end(), match.group(1).strip()))
    return h2_list


def get_context(body: str, pos: int, lines: int = 5) -> str:
    """지정된 위치 주변의 컨텍스트 라인 반환"""
    lines_before = body[:pos].split('\n')
    lines_after = body[pos:].split('\n')
    
    context_before = lines_before[-lines:] if len(lines_before) > lines else lines_before
    context_after = lines_after[:lines+1]
    
    return '\n'.join(context_before + context_after)


def is_text_content(text: str) -> bool:
    """일반 텍스트 단락인지 확인 (한글/영문/숫자 포함)"""
    stripped = text.strip()
    if not stripped:
        return False
    # 마크다운 이미지, 인용, 코드블록, 수평선 제외
    if stripped.startswith('![') or stripped.startswith('>') or stripped.startswith('```') or re.match(r'^[-*]{3,}$', stripped):
        return False
    # 한글, 영문, 숫자가 하나라도 있으면 텍스트로 간주
    return bool(re.search(r'[가-힣a-zA-Z0-9]', stripped))


def detect_empty_h2_patterns(body: str) -> list[dict]:
    """빈 H2 패턴 3가지 모두 감지"""
    h2_list = find_all_h2_positions(body)
    results = []
    
    for i, (h2_start, h2_end, h2_text) in enumerate(h2_list):
        if i + 1 >= len(h2_list):
            # 마지막 H2는 다음 H2가 없어서 패턴 1,2 해당 안됨
            # 패턴 3만 확인 가능
            after_h2 = body[h2_end:]
            # 선행 공백 스킵
            j = 0
            while j < len(after_h2) and after_h2[j] in '\n\r ':
                j += 1
            if j < len(after_h2):
                next_content = after_h2[j:]
                # 다음 H2 전까지의 내용 확인
                next_h2_match = re.search(r'^##\s+.+$', next_content, re.MULTILINE)
                if next_h2_match:
                    content_between = next_content[:next_h2_match.start()].strip()
                    if content_between and not is_text_content(content_between):
                        results.append({
                            'pattern': 3,
                            'empty_h2': h2_text,
                            'next_h2': None,
                            'context': get_context(body, h2_start),
                            'non_text_content': content_between[:200]
                        })
            continue
        
        next_h2_start, next_h2_end, next_h2_text = h2_list[i + 1]
        
        # 두 H2 사이의 내용
        between = body[h2_end:next_h2_start]
        
        # Pattern 1: H2 → 빈 줄(들)만 → H2
        stripped_between = between.strip()
        if not stripped_between:
            # 공백만 있음 (빈 줄들)
            results.append({
                'pattern': 1,
                'empty_h2': h2_text,
                'next_h2': next_h2_text,
                'context': get_context(body, h2_start),
                'between_content': repr(between[:100])
            })
            continue
        
        # Pattern 2: H2 → 바로 H2 (공백 라인 없음)
        if not between.strip('\n\r ') and '\n\n' not in between:
            # 공백 문자도 거의 없음
            results.append({
                'pattern': 2,
                'empty_h2': h2_text,
                'next_h2': next_h2_text,
                'context': get_context(body, h2_start),
                'between_content': repr(between[:100])
            })
            continue
        
        # Pattern 3: H2 → 비-텍스트 콘텐츠만 → H2
        # between의 각 단락이 텍스트가 아닌지 확인
        paragraphs = re.split(r'\n\s*\n', between.strip())
        all_non_text = True
        non_text_contents = []
        for p in paragraphs:
            p = p.strip()
            if p and is_text_content(p):
                all_non_text = False
                break
            if p:
                non_text_contents.append(p[:100])
        
        if all_non_text and non_text_contents:
            results.append({
                'pattern': 3,
                'empty_h2': h2_text,
                'next_h2': next_h2_text,
                'context': get_context(body, h2_start),
                'non_text_content': ' | '.join(non_text_contents[:3])
            })
    
    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description='빈 H2 감지')
    parser.add_argument('--all', action='store_true', help='전체 블로그 포스트 검사')
    parser.add_argument('--file', type=str, help='특정 파일만 검사')
    args = parser.parse_args()
    
    if args.file:
        files = [BLOG_DIR / args.file]
    elif args.all:
        files = sorted(BLOG_DIR.glob("*.md"))
    else:
        # 기본 테스트 파일
        test_files = [
            "2026-07-25-009-코그니션의-포크-인수-ai-개성이-경쟁-우위가-된-이유를-분석합니다.md",
            "2026-07-25-011-알파폴드-ai가-유전자-편집-단백질을-더-안전하게-재설계하는-방법과-미래-전망.md",
        ]
        files = [BLOG_DIR / f for f in test_files if (BLOG_DIR / f).exists()]
    
    print(f"검사 대상: {len(files)}개 파일\n")
    
    total_pattern1 = 0
    total_pattern2 = 0
    total_pattern3 = 0
    all_results = []
    
    for fpath in files:
        if not fpath.exists():
            continue
        
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        fm, body = parse_frontmatter(content)
        detections = detect_empty_h2_patterns(body)
        
        if detections:
            for d in detections:
                d['file'] = fpath.name
                all_results.append(d)
                
                if d['pattern'] == 1:
                    total_pattern1 += 1
                elif d['pattern'] == 2:
                    total_pattern2 += 1
                elif d['pattern'] == 3:
                    total_pattern3 += 1
    
    # 출력
    print(f"{'='*60}")
    print(f"빈 H2 감사 결과")
    print(f"{'='*60}")
    print(f"총 감지 건수: {len(all_results)}건")
    print(f"  Pattern 1 (H2 → 공백 → H2): {total_pattern1}건")
    print(f"  Pattern 2 (H2 → H2, 공백 없음): {total_pattern2}건")
    print(f"  Pattern 3 (H2 → 비텍스트 → H2): {total_pattern3}건")
    print(f"{'='*60}\n")
    
    # 상세 출력
    for r in all_results:
        print(f"📄 {r['file']}")
        print(f"   Pattern {r['pattern']}: 빈 H2 = \"{r['empty_h2']}\"")
        if r['next_h2']:
            print(f"   다음 H2 = \"{r['next_h2']}\"")
        if r.get('between_content'):
            print(f"   사이 내용: {r['between_content']}")
        if r.get('non_text_content'):
            print(f"   비텍스트 내용: {r['non_text_content']}")
        print(f"   컨텍스트:")
        for line in r['context'].split('\n')[:10]:
            print(f"     {line}")
        print()
    
    # 코그니션 포스트(009) 포함 여부 확인
    cognition_found = any('009' in r['file'] and '코그니션' in r['file'] for r in all_results)
    print(f"코그니션 포스트(009) 감지 여부: {'포함됨 ✅' if cognition_found else '포함되지 않음 ❌'}")
    
    # 요약 통계
    print(f"\n{'='*60}")
    print(f"요약: Pattern 1={total_pattern1}, Pattern 2={total_pattern2}, Pattern 3={total_pattern3}, 합계={len(all_results)}")


if __name__ == '__main__':
    main()