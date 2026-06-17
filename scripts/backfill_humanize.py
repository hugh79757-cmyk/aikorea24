#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
"""
기존 75개 MD 파일에 humanize_md 일괄 적용 (GPT 호출 없음)
- description: ~다 → ~니다 체 변환
- useCases: 각 항목 humanize  
- 본문(body): humanize_md 재적용
- updated: 오늘 날짜로 갱신

사용법:
  python3 scripts/backfill_humanize.py           # 실제 수정
  python3 scripts/backfill_humanize.py --dry-run # 미리보기
"""
import os, re, sys
from datetime import datetime

PROJECT_DIR = '/Users/twinssn/Projects/aikorea24'
TOOLS_DIR = os.path.join(PROJECT_DIR, 'src/content/tools')
sys.path.insert(0, os.path.join(PROJECT_DIR, 'scripts'))

# tools_collector.py에서 humanize_md import
sys.path.insert(0, PROJECT_DIR)
import importlib.util
spec = importlib.util.spec_from_file_location(
    "tools_collector",
    os.path.join(PROJECT_DIR, "scripts/tools_collector.py")
)
tc = importlib.util.module_from_spec(spec)
# humanize_md 의존성 최소한만 정의
import re as _re
from datetime import datetime as _dt

# humanize_md 함수를 직접 정의 (tools_collector import 없이)
def humanize_md(text: str) -> str:
    """tools_collector.py의 humanize_md와 동일한 규칙"""
    if not text:
        return text
    replacements = [
        # A-1: ~에 대해(서) → ~를
        (r'(?<=[가-힣])(\s*)에 대해(서)?(?=\s|[.。]|$)', r'\1를'),
        # A-2: ~를 통해 → ~로
        (r'(?<=[가-힣])(을|를) 통해', r'로'),
        # A-3: ~에 있어(서) → ~에서
        (r'(?<=[가-힣])(\s*)에 있어(서)?(?=\s|[.。]|$)', r'\1에서'),
        # A-5: ~와 관련하여 → ~에
        (r'(?<=[가-힣])(과|와) 관련하여', r''),
        # A-6: ~에 기반하여/바탕으로 → ~로
        (r'(?<=[가-힣])(\s*)에 기반하여', r'\1로'),
        (r'(?<=[가-힣])(\s*)을 바탕으로', r'\1을 보고'),
        # A-7: ~을/를 가지고 있다 → 있다
        (r'([가-힣]+)을/를 가지고 있다', r'\1이 있다'),
        (r'([가-힣]+)을/를 갖추고 있다', r'\1을 갖췄다'),
        # A-9: ~에 의해 → ~가
        (r'(?<=[가-힣])(\s*)에 의해 생성', r'\1가 만든'),
        (r'(?<=[가-힣])(\s*)에 의해 제공', r'\1가 제공'),
        # A-10: ~할 수 있다 남발
        (r'을 제공할 수 있습니다', r'을 제공합니다'),
        (r'을 지원할 수 있습니다', r'을 지원합니다'),
        (r'을 사용할 수 있습니다', r'을 사용합니다'),
        (r'을 활용할 수 있습니다', r'을 활용합니다'),
        (r'을 찾아볼 수 있다', r'을 찾을 수 있다'),
        (r'를 찾아볼 수 있다', r'를 찾을 수 있다'),
        (r'할 수 있도록 돕', r'하는 데 도움이 되'),
        (r'도와준다', r'도움이 됩니다'),
        (r'돕는다', r'도움이 됩니다'),
        (r'수행할 수 있다', r'수행합니다'),
        (r'처리할 수 있다', r'처리합니다'),
        (r'제공할 수 있는', r'제공하는'),
        (r'지원할 수 있는', r'지원하는'),
        (r'활용할 수 있는', r'활용하는'),
        (r'사용할 수 있는', r'사용하는'),
        # A-11: ~을 위해 → ~려고
        (r'([가-힣]+)을 위해 ', r'\1하려고 '),
        (r'([가-힣]+)를 위해 ', r'\1하려고 '),
        # D-1: 결론적/시사/주목 삭제
        (r'결론적으로,?\s*', ''),
        (r'시사하는 바가 크(다|습니다)', '의미가 큽니다'),
        (r'주목할 만한 (점은|것은)\s*', ''),
        # D-4: hype 어휘
        (r'혁신적인', '새로운'),
        (r'획기적인', ''),
        (r'강력한 ', ''),
        (r'파격적인', ''),
        # C-11: 연결어미 뒤 쉼표 제거
        (r'(하고|하며|지만|면서|면서도|아서|어서),', lambda m: m.group(1) + ''),
        # C-5: 본문 이모지 제거
        (r'(?<![💰🇰🇷📊🔗⭐📂])[💡⚠️📌✅❌🔍📱💻🎯🚀🔥💪🧠⚡🔧📈💬🎨📝✨],?', ''),
        # E-2: ~고 있다 → ~합니다
        (r'([가-힣]+)고 있다\b', lambda m: m.group(1) + '니다'),
        # 평서체(~다) → 정중체(~니다)
        (r'([가-힣]+)합니다\.', lambda m: m.group(0)),
        (r'([가-힣]+)습니다\.', lambda m: m.group(0)),
        (r'([가-힣]+)이다\.', lambda m: m.group(1) + '입니다.'),
        (r'([가-힣]+)한다\.', lambda m: m.group(1) + '합니다.'),
        (r'툴이다\.', '툴입니다.'),
        (r'도구다\.', '도구입니다.'),
    ]
    for pattern, replacement in replacements:
        try:
            text = _re.sub(pattern, replacement, text)
        except Exception:
            pass
    return text


TODAY = datetime.now().strftime('%Y-%m-%d')


def parse_frontmatter(content: str) -> dict:
    """MD frontmatter 파싱"""
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
    return fm


def rebuild_frontmatter(fields: dict) -> str:
    """수정된 frontmatter → YAML 문자열"""
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


def process_file(filepath: str, dry_run: bool = False) -> dict:
    """MD 파일 humanize → 결과"""
    filename = os.path.basename(filepath)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # frontmatter 분리
    m = re.match(r'^(---\s*\n.*?\n---)\n(.*)$', content, re.DOTALL)
    if not m:
        return {'file': filename, 'status': 'error', 'reason': 'frontmatter 파싱 실패'}

    fm_yaml = m.group(1)
    body = m.group(2)
    fm = parse_frontmatter(content)

    name = fm.get('name', filename)
    changes = []

    # 1. description humanize
    old_desc = fm.get('description', '')
    new_desc = humanize_md(old_desc)
    if new_desc != old_desc:
        changes.append(f'description: humanize 적용')

    # 2. useCases 각 항목 humanize
    old_uc = fm.get('useCases', [])
    new_uc = [humanize_md(uc) for uc in old_uc]
    if new_uc != old_uc:
        changes.append(f'useCases: {len(old_uc)}건 humanize')

    # 3. body humanize
    new_body = humanize_md(body)
    body_changed = new_body != body
    if body_changed:
        changes.append('body: humanize 적용')

    # 4. updated 갱신
    old_updated = fm.get('updated', '')
    new_updated = TODAY

    if dry_run:
        if changes or old_updated != new_updated:
            return {
                'file': filename, 'name': name, 'status': 'dry-run',
                'changes': changes, 'desc_before': old_desc[:80],
                'desc_after': new_desc[:80],
            }
        return {'file': filename, 'name': name, 'status': 'skip', 'reason': '변경 없음'}

    # 실제 수정
    fm['description'] = new_desc
    fm['useCases'] = new_uc
    fm['updated'] = new_updated

    new_fm_yaml = rebuild_frontmatter(fm)
    new_content = new_fm_yaml + '\n' + new_body

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

    status = 'updated' if changes else 'nochange'
    return {
        'file': filename, 'name': name, 'status': status,
        'changes': changes,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description='MD 파일 humanize 일괄 적용')
    parser.add_argument('--dry-run', action='store_true', help='미리보기')
    args = parser.parse_args()

    if not os.path.isdir(TOOLS_DIR):
        print(f"에러: {TOOLS_DIR} 없음")
        sys.exit(1)

    md_files = sorted([f for f in os.listdir(TOOLS_DIR) if f.endswith('.md')])
    print(f"대상 파일: {len(md_files)}개\n")

    results = []
    for fname in md_files:
        fpath = os.path.join(TOOLS_DIR, fname)
        result = process_file(fpath, dry_run=args.dry_run)
        results.append(result)

        if result['status'] == 'skip':
            if args.dry_run:
                print(f"  ⏭️  {result['name']:30s} → {result.get('reason', '')}")
        elif result['status'] == 'dry-run':
            print(f"  🔍 {result['name']:30s}")
            for ch in result.get('changes', []):
                print(f"     {ch}")
            print(f"     desc: {result.get('desc_before','')}…")
            print(f"       →  {result.get('desc_after','')}…")
        elif result['status'] == 'updated':
            print(f"  ✅ {result['name']:30s} → {', '.join(result.get('changes', ['humanize']))}")
        elif result['status'] == 'nochange':
            print(f"  ⏭️  {result['name']:30s} → 변경 없음")
        else:
            print(f"  ❌ {result['name']:30s} → {result.get('reason', '오류')}")

    updated = [r for r in results if r['status'] == 'updated']
    dry_run_r = [r for r in results if r['status'] == 'dry-run']

    print(f"\n{'='*55}")
    if args.dry_run:
        print(f"🔍 DRY RUN — 수정 대상: {len(dry_run_r)}개")
    else:
        print(f"✅ humanize 완료: {len(updated)}개 파일")


if __name__ == '__main__':
    main()
