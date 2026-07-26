#!/usr/bin/env python3
"""
Fix broken YAML frontmatter in blog posts.
Handles:
- Duplicate fields (keep last non-empty)
- Unescaped quotes in description
- Duplicated text in description
- Double frontmatter delimiters
- Empty category fields
"""

import re
import yaml
from pathlib import Path

BLOG_DIR = Path("/Users/twinssn/Projects/aikorea24/src/content/blog")


def extract_first_sentence(body: str, max_chars: int = 300) -> str:
    """Extract first complete sentence from body text."""
    # Remove markdown links/images
    text = re.sub(r'!?\[.*?\]\(.*?\)', '', body)
    # Remove markdown formatting
    text = re.sub(r'[#>*`~\[\]]', '', text)
    text = text.strip()
    
    if not text:
        return "AI 관련 최신 소식을 전해드립니다."
    
    # Find first sentence ending with period, question mark, or exclamation
    # Korean sentences typically end with . ? !
    sentences = re.split(r'(?<=[.!?])\s+', text)
    for s in sentences:
        s = s.strip()
        if len(s) > 10:  # Skip very short fragments
            return s[:max_chars]
    
    return text[:max_chars]


def fix_description(desc: str) -> str:
    """Fix corrupted description field."""
    if not desc:
        return ""
    
    # Remove surrounding quotes if present
    desc = desc.strip()
    if desc.startswith('"') and desc.endswith('"'):
        desc = desc[1:-1]
    elif desc.startswith("'") and desc.endswith("'"):
        desc = desc[1:-1]
    
    # Fix duplicated text pattern: "text"text"text" -> "text"
    # Pattern: repeated text with quotes in between
    for _ in range(3):  # Max 3 iterations to handle multiple duplications
        # Match: "text"text"text" or text"text"text
        m = re.match(r'^(.+?)"\1+"(.*)$', desc)
        if m:
            desc = m.group(1) + m.group(2)
        else:
            break
    
    # Also handle: "text""text" (adjacent quotes)
    desc = re.sub(r'^"(.+?)"+"(.*)$', r'"\1"\2', desc)
    
    # Fix unescaped quotes inside: text"text -> text"text (escape the inner)
    # This is tricky - we'll just clean up obvious cases
    # Pattern: Korean text followed by " followed by Korean text
    # e.g. "이 정도면 충분하다"는 느낌이 드신다면 -> "이 정도면 충분하다고 느끼신다면"
    # But this is complex. Let's just truncate at first unescaped quote if it looks broken
    
    # If there are multiple quoted segments, take the first meaningful one
    quotes = re.findall(r'"([^"]+)"', desc)
    if len(quotes) > 1:
        # Take the longest meaningful quote
        desc = max(quotes, key=len)
    elif len(quotes) == 1:
        desc = quotes[0]
    
    # Remove any remaining leading/trailing quotes
    desc = desc.strip('"\'')
    
    # If still empty or too short, return empty
    if len(desc) < 5:
        return ""
    
    return desc


def parse_broken_frontmatter(content: str) -> dict:
    """Parse frontmatter from potentially broken YAML."""
    # Find frontmatter boundaries
    fm_match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if not fm_match:
        return {}
    
    fm_text = fm_match.group(1)
    
    # Handle double frontmatter (--- ... --- ... ---)
    # Take everything up to the second ---
    if '\n---\n' in fm_text:
        fm_text = fm_text.split('\n---\n')[0]
    
    # Parse line by line to handle duplicates
    fields = {}
    for line in fm_text.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        # Match key: value
        m = re.match(r'^(\w+):\s*(.*)$', line)
        if m:
            key = m.group(1)
            value = m.group(2).strip()
            # Remove surrounding quotes
            if value.startswith('"') and value.endswith('"') and len(value) > 1:
                value = value[1:-1]
            elif value.startswith("'") and value.endswith("'") and len(value) > 1:
                value = value[1:-1]
            # Keep last non-empty value for duplicates
            if value:
                fields[key] = value
    
    return fields


def fix_file(filepath: Path) -> tuple[bool, str]:
    """Fix a single broken frontmatter file."""
    content = filepath.read_text(encoding='utf-8')
    
    # Extract body (after frontmatter)
    body_match = re.search(r'^---\n.*?\n---\n(.*)$', content, re.DOTALL)
    if not body_match:
        # Try double frontmatter
        body_match = re.search(r'^---\n.*?\n---\n---\n(.*)$', content, re.DOTALL)
    if not body_match:
        return False, "no valid frontmatter found"
    
    body = body_match.group(1).strip()
    
    # Parse broken frontmatter
    fm = parse_broken_frontmatter(content)
    
    if not fm.get('title'):
        return False, "no title found"
    
    # Fix description
    original_desc = fm.get('description', '')
    fixed_desc = fix_description(original_desc)
    
    # If description is still empty or too short, extract from body
    if not fixed_desc or len(fixed_desc) < 10:
        fixed_desc = extract_first_sentence(body)
    
    # Fix category
    category = fm.get('category', '뉴스')
    if not category or category == '""':
        category = '뉴스'
    
    # Build clean frontmatter
    clean_fm = {
        'title': fm.get('title', ''),
        'description': fixed_desc,
        'date': fm.get('date', ''),
        'category': category,
        'draft': fm.get('draft', False),
    }
    
    # Add optional fields if present
    for key in ['tags', 'image']:
        if key in fm and fm[key]:
            clean_fm[key] = fm[key]
    
    # Serialize with yaml.dump
    new_fm_yaml = yaml.dump(clean_fm, allow_unicode=True, sort_keys=False, default_flow_style=False)
    
    # Reconstruct content
    new_content = f'---\n{new_fm_yaml}---\n{body}\n'
    
    # Write back
    filepath.write_text(new_content, encoding='utf-8')
    
    return True, f"fixed: desc='{original_desc[:40]}...' -> '{fixed_desc[:40]}...'"


def main():
    # Get list of broken files from previous validation
    broken_files = []
    for f in BLOG_DIR.glob("*.md"):
        content = f.read_text(encoding='utf-8')
        try:
            fm_text = content.split('---')[1]
            yaml.safe_load(fm_text)
        except Exception:
            broken_files.append(f)
    
    print(f"Found {len(broken_files)} files with broken frontmatter")
    
    fixed = 0
    failed = 0
    for f in broken_files:
        try:
            success, msg = fix_file(f)
            if success:
                fixed += 1
                print(f"  [FIXED] {f.name}: {msg}")
            else:
                failed += 1
                print(f"  [FAILED] {f.name}: {msg}")
        except Exception as e:
            failed += 1
            print(f"  [ERROR] {f.name}: {e}")
    
    print(f"\nTotal: fixed={fixed}, failed={failed}, total={len(broken_files)}")


if __name__ == '__main__':
    main()