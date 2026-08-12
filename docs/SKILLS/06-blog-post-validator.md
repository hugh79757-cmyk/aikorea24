# 블로그 포스트 검증 스킬

> Astro 빌드/배포 전 블로그 포스트의 frontmatter와 내용 품질 검증. 불량 포스트 차단으로 파이프라인 무결성 보장.

---

## 1. 개요

생성된 블로그 포스트가 Astro 콘텐츠 컬렉션 요구사항을 충족하는지 검증하고, 실패 시 파이프라인 중단을 통해 불량 콘텐츠가 배포되는 것을 방지.

**주요 스크립트:** `scripts/validate_blog_posts.py`

**실행 시점:**
- `run_pipeline.py` Step 3 (심층글 저장 직후)
- `deploy.sh` Step 0 (빌드 전)

---

## 2. 검증 항목

### 2.1 필수 Frontmatter 체크

각 `.md` 파일의 frontmatter에 다음이 존재해야 함:

| 필드 | 유형 | 필수 여부 | 비고 |
|------|------|----------|------|
| `title` | string | ✅ 필수 | 빈 문자열 불가 |
| `description` | string | ✅ 필수 | 빈 문자열 불가 |
| `date` | string | ✅ 필수 | YYYY-MM-DD 형식 |
| `draft` | boolean | ✅ 필수 | `true`면 배포 제외 |
| `tags` | array | ✅ 필수 | 최소 1개 |
| `category` | string | ✅ 필수 | 허용값 중 하나 |
| `image` | string | 선택 | 있으면 존재 확인 |

### 2.2 내용 품질 체크

- 본문에 최소 분량 이상의 텍스트 존재
- frontmatter와 본문 구분 명확 (`---` delimiters)
- Markdown 구문 기본 유효성

### 2.3 중복 체크

- 동일한 title의 포스트가 여러 개 존재하는지 확인
- 동일 날짜 + 유사 제목 중복 검출

---

## 3. 실행 방법

### 3.1 단독 실행

```bash
cd /Users/twinssn/Projects/aikorea24
python3 scripts/validate_blog_posts.py
```

출력:
```
✅ 블로그 포스트 검증 통과: N개
또는
❌ 검증 실패: [오류 내용]
```

### 3.2 파이프라인 통합 실행

자동으로 실행됨:
- `run_pipeline.py` Step 3 종료 직후
- `deploy.sh` Step 0

```python
# run_pipeline.py 에서
if results:
    import validate_blog_posts
    log("  🛡️  블로그 frontmatter 최종 검증")
    if not validate_blog_posts.validate_all():
        raise RuntimeError("블로그 포스트 검증 실패: 더 이상 진행하지 않습니다.")
```

### 3.3 반환값

- `validate_all()` → `True` (통과) / `False` (실패)
- 실패 시 `sys.exit(1)` → 파이프라인 중단

---

## 4. 동작 방식

### 4.1 대상 파일 탐색

```python
BLOG_DIR = PROJECT_DIR / "src" / "content" / "blog"
markdown_files = list(BLOG_DIR.glob("*.md"))
```

### 4.2 Frontmatter 파싱

```python
import re

def parse_frontmatter(content):
    match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if not match:
        return None, content  # frontmatter 없음
    fm_text = match.group(1)
    body = content[match.end():]
    # YAML 비슷하지만 간단한 키: 값 파싱
    fm = {}
    for line in fm_text.split('\n'):
        m = re.match(r'^([\w-]+):\s*(.*)$', line)
        if m:
            fm[m.group(1)] = m.group(2).strip()
    return fm, body
```

### 4.3 검증 로직

```python
def validate_post(filepath):
    errors = []
    warnings = []

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    fm, body = parse_frontmatter(content)

    # 필수 필드 체크
    for field in ['title', 'description', 'date', 'draft', 'tags', 'category']:
        if field not in fm:
            errors.append(f"{field} 누락")

    # title/description 빈 값 체크
    if not fm.get('title'):
        errors.append("title이 비어있음")
    if not fm.get('description'):
        errors.append("description이 비어있음")

    # draft 값 체크
    if fm.get('draft') not in ('true', 'false', 'True', 'False'):
        errors.append(f"draft 값 이상: {fm.get('draft')}")

    # date 형식 체크
    if not re.match(r'\d{4}-\d{2}-\d{2}', fm.get('date', '')):
        errors.append(f"date 형식 이상: {fm.get('date')}")

    # image 존재 확인 (있으면)
    if fm.get('image'):
        image_path = PROJECT_DIR / fm['image'].lstrip('/')
        if not image_path.exists():
            warnings.append(f"image 경로 존재 안 함: {fm['image']}")

    # 본문 분량 체크
    if len(body.strip()) < 200:
        warnings.append("본문 분량 부족")

    return errors, warnings
```

### 4.4 결과 집계

```python
def validate_all():
    all_errors = []
    all_warnings = []

    for md_file in BLOG_DIR.glob("*.md"):
        errors, warnings = validate_post(md_file)
        if errors:
            all_errors.append((md_file, errors))
        if warnings:
            all_warnings.append((md_file, warnings))

    if all_errors:
        print("❌ 검증 실패:")
        for filepath, errors in all_errors:
            print(f"  {filepath}:")
            for e in errors:
                print(f"    - {e}")
        return False

    if all_warnings:
        print("⚠️  경고:")
        for filepath, warnings in all_warnings:
            print(f"  {filepath}:")
            for w in warnings:
                print(f"    - {w}")

    print(f"✅ 검증 통과: {len(list(BLOG_DIR.glob('*.md')))}개")
    return True
```

---

## 5. 파일 구조

```
scripts/
└── validate_blog_posts.py       # 검증 스크립트

src/content/blog/                 # 검증 대상
├── 2026-08-07-...md
└── ...
```

---

## 6. 체크리스트

### 최초 설정
- [ ] `python3 scripts/validate_blog_posts.py` 실행
- [ ] 기존 블로그 포스트 모두 통과 확인
- [ ] 실패 시 오류 내용 확인 및 포스트 수정

### 파이프라인 통합
- [ ] `run_pipeline.py` 실행 시 검증 단계 포함 확인
- [ ] 검증 실패 시 파이프라인 중단 확인
- [ ] 배포 전 `deploy.sh`에서도 검증 실행 확인

---

## 7. 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| frontmatter 파싱 실패 | `---` delimiters 누락/손상 | AI 출력 frontmatter 정상화 (auto_deep_article의 normalize_frontmatter) |
| title/description 누락 | AI가 frontmatter 생성 안 함 | normalize_frontmatter() 기본값 채움 |
| draft 값 이상 | AI가 이상한 값 생성 | `\x01` 등 깨진 값 → `false`로 자동 보정 |
| image 경로 없음 | 썸네일 미생성 | auto_thumbnail.py 먼저 실행 |
| 검증 실패로 파이프라인 중단 | 신규 포스트 문제 | 오류 내용 확인 후 포스트 수정 또는 재생성 |

---

*문서 버전: 1.0 | 생성일: 2026-08-07*
