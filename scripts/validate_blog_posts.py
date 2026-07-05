#!/usr/bin/env python3
"""Pre-build validation: check all blog posts for valid frontmatter and content."""
import os, sys, re

BLOG_DIR = os.path.join(os.path.dirname(__file__), '..', 'src', 'content', 'blog')

def validate_file(fpath):
    """Returns list of issues found."""
    issues = []
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if len(content) < 100:
        issues.append(f"내용 너무 짧음 ({len(content)}자) — 에러 메시지 가능성")
        return issues
    
    lines = content.split('\n')
    if not lines or lines[0].strip() != '---':
        issues.append("frontmatter 시작 --- 없음")
        return issues
    
    # Find closing ---
    closing = None
    for i in range(1, min(len(lines), 50)):
        if lines[i].strip() == '---':
            closing = i
            break
    
    if closing is None:
        issues.append("frontmatter 닫는 --- 없음")
        return issues
    
    fm_lines = lines[1:closing]
    fm_text = '\n'.join(fm_lines)
    
    # Check required fields
    required = {'title', 'description', 'date', 'category'}
    found = set()
    for line in fm_lines:
        for field in required:
            if line.strip().startswith(field + ':'):
                found.add(field)
    
    missing = required - found
    if missing:
        issues.append(f"frontmatter 필드 누락: {', '.join(missing)}")
    
    # Check date format (warn only — ISO 8601 with timezone is also valid)
    for line in fm_lines:
        if line.strip().startswith('date:'):
            date_str = line.split(':', 1)[1].strip().strip('"\'')
            if date_str and not re.match(r'^\d{4}-\d{2}-\d{2}', date_str):
                issues.append(f"date 형식 이상: {date_str}")
    
    return issues


def validate_all():
    """전체 블로그 포스트를 검증. 문제 있으면 False, 정상이면 True."""
    blog_dir = BLOG_DIR
    if not os.path.isdir(blog_dir):
        print(f"블로그 디렉토리 없음: {blog_dir}")
        return False

    failed_files = []
    for fname in sorted(os.listdir(blog_dir)):
        if not fname.endswith('.md'):
            continue
        fpath = os.path.join(blog_dir, fname)
        issues = validate_file(fpath)
        if issues:
            failed_files.append((fname, issues))

    if failed_files:
        print(f"\n⚠️ {len(failed_files)}개 파일에 문제 있음")
        for fname, issues in failed_files:
            print(f"  ❌ {fname}")
            for issue in issues:
                print(f"     - {issue}")
        return False
    else:
        print(f"✅ 모든 블로그 포스트 정상")
        return True


def main():
    ok = validate_all()
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
