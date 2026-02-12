#!/usr/bin/env python3
"""
프로젝트 코드 백업 스크립트 v2 (압축 강화)
- 핵심 코드만 추출
- 민감 정보 완전 제거
- 중복/보일러플레이트 제거
- 목표: 100KB 이하
"""
import os
import re
from datetime import datetime
from pathlib import Path
import argparse

# ========================================
# 설정값 (더 엄격한 제한)
# ========================================
MAX_FILE_SIZE = 10 * 1024      # 10KB 초과 스킵
MAX_LINES_PER_FILE = 150       # 파일당 최대 150줄
MAX_TOTAL_SIZE = 100 * 1024    # 전체 최대 100KB

# 제외할 폴더
EXCLUDE_DIRS = {
    'venv', '.venv', 'env', 'node_modules', 'vendor',
    '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache',
    'dist', 'build', '.next', '.nuxt', 'out', 'target',
    '.git', '.svn', '.idea', '.vscode',
    'data', 'logs', 'log', 'tmp', 'temp', 'cache',
    'backups', 'backup', 'tests', 'test', '__tests__',
    'htmlcov', 'coverage', '.coverage',
    'migrations', 'static', 'media', 'assets',
}

# 제외할 파일 패턴
EXCLUDE_PATTERNS = [
    'test_', '_test.', '.test.', 'backup', '.bak', 'backup1', 'backup2',
    '.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg', '.webp',
    '.mp3', '.mp4', '.wav', '.avi', '.mov', '.webm',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt',
    '.zip', '.tar', '.gz', '.rar', '.7z',
    '.sqlite', '.db', '.pkl', '.pickle',
    '.log', '.lock', '.cache', '.map',
    'credentials', 'secret', '.pem', '.key', '.crt',
    '.DS_Store', 'Thumbs.db', 'desktop.ini',
    '.pyc', '.pyo', '.so', '.dll', '.exe', '.o',
    'package-lock', 'yarn.lock', 'poetry.lock',
    'LICENSE', 'CHANGELOG', 'CONTRIBUTING',
    '.eslintrc', '.prettierrc', 'tsconfig',
]

# 핵심 파일만 포함
PRIORITY_FILES = {
    'run.py', 'main.py', 'app.py', 'gui.py', 'cli.py',
    'settings.py', 'config.py', '__init__.py',
    'requirements.txt', '.env.example', '__version__.py',
    'Dockerfile', 'docker-compose.yml',
}

# 핵심 확장자
ALLOWED_EXT = {'.py', '.yaml', '.yml', '.sh'}

# 민감 키워드 (완전 마스킹)
SENSITIVE_KEYS = [
    'api_key', 'apikey', 'api-key', 'secret', 'token',
    'password', 'passwd', 'pwd', 'credential', 'private',
    'client_id', 'client_secret', 'auth', 'bearer',
    'database_url', 'db_pass', 'aws_', 'azure_', 'gcp_',
    'access_key', 'refresh_token', 'app_password',
]

# 제거할 코드 패턴 (보일러플레이트)
REMOVE_PATTERNS = [
    r'^\s*#\s*-{3,}.*$',           # --- 주석 구분선
    r'^\s*#\s*={3,}.*$',           # === 주석 구분선
    r'^\s*"""[\s\S]*?"""',          # 독스트링 (여러 줄)
    r"^\s*'''[\s\S]*?'''",          # 독스트링 (여러 줄)
    r'^\s*logging\.debug\(.*\)$',   # debug 로그
    r'^\s*logger\.debug\(.*\)$',    # debug 로그
    r'^\s*print\(.*\)$',            # print 문
    r'^\s*pass\s*$',                # pass만 있는 줄
]


def should_include(path: Path, root: Path) -> bool:
    """파일 포함 여부 판단 (엄격)"""
    rel_path = path.relative_to(root)
    parts = rel_path.parts
    name = path.name
    name_lower = name.lower()
    
    # 폴더 체크
    for part in parts:
        if part.lower() in {d.lower() for d in EXCLUDE_DIRS}:
            return False
    
    # 제외 패턴 체크
    for pattern in EXCLUDE_PATTERNS:
        if pattern.lower() in name_lower:
            return False
    
    # 우선 파일
    if name in PRIORITY_FILES:
        return True
    
    # 숨김 파일
    if name.startswith('.'):
        return name in {'.gitignore', '.env.example'}
    
    # 확장자 체크
    return path.suffix.lower() in ALLOWED_EXT


def mask_sensitive(content: str) -> str:
    """민감 정보 완전 마스킹"""
    lines = []
    for line in content.split('\n'):
        line_lower = line.lower()
        
        # 민감 키워드 체크
        is_sensitive = any(key in line_lower for key in SENSITIVE_KEYS)
        
        if is_sensitive:
            # = 기준 마스킹
            if '=' in line and not line.strip().startswith('#'):
                key_part = line.split('=')[0]
                lines.append(f"{key_part}=***")
            # : 기준 마스킹 (YAML)
            elif ':' in line and not line.strip().startswith('#') and not line.strip().startswith('-'):
                key_part = line.split(':')[0]
                lines.append(f"{key_part}: ***")
            else:
                lines.append(line)
        else:
            lines.append(line)
    
    return '\n'.join(lines)


def compress_content(content: str) -> str:
    """코드 압축 (불필요한 부분 제거)"""
    lines = content.split('\n')
    result = []
    
    in_docstring = False
    docstring_char = None
    
    for line in lines:
        stripped = line.strip()
        
        # 빈 줄 연속 제거
        if not stripped:
            if result and result[-1].strip() == '':
                continue
            result.append('')
            continue
        
        # 독스트링 시작/끝 감지
        if '"""' in stripped or "'''" in stripped:
            char = '"""' if '"""' in stripped else "'''"
            count = stripped.count(char)
            
            if not in_docstring and count == 1:
                in_docstring = True
                docstring_char = char
                continue
            elif in_docstring and char == docstring_char:
                in_docstring = False
                docstring_char = None
                continue
            elif count >= 2:
                # 한 줄 독스트링
                continue
        
        if in_docstring:
            continue
        
        # 긴 주석 제거 (# --- 등)
        if stripped.startswith('#') and len(stripped) > 3:
            if stripped[1:4] in ['---', '===', '***', '###']:
                continue
        
        # 변경 이력 주석 제거
        if stripped.startswith('#') and any(kw in stripped for kw in ['변경 이력', '변경이력', 'changelog', 'history']):
            continue
        
        result.append(line)
    
    # 끝 빈 줄 제거
    while result and result[-1].strip() == '':
        result.pop()
    
    return '\n'.join(result)


def truncate_content(content: str, max_lines: int) -> tuple:
    """줄 수 제한"""
    lines = content.split('\n')
    if len(lines) <= max_lines:
        return content, False
    
    # 앞부분 + import + 클래스/함수 정의만
    truncated = []
    import_done = False
    
    for i, line in enumerate(lines):
        if i >= max_lines:
            break
        truncated.append(line)
        
        # import 끝나면 좀 더 빨리 자르기
        if not import_done and line.strip() and not line.strip().startswith(('import', 'from', '#')):
            import_done = True
    
    truncated.append(f"\n# ... ({len(lines) - len(truncated)}줄 생략)")
    return '\n'.join(truncated), True


def get_file_priority(path: Path) -> int:
    """파일 우선순위 (낮을수록 중요)"""
    name = path.name
    
    if name in {'run.py', 'main.py', 'app.py'}:
        return 0
    if name in {'settings.py', 'config.py'}:
        return 1
    if name in {'gui.py', 'cli.py'}:
        return 2
    if name == '__init__.py':
        return 3
    if name == 'requirements.txt':
        return 4
    if name.endswith('.yaml') or name.endswith('.yml'):
        return 5
    return 10


def export_project(output_name: str = None, root_path: str = None):
    """프로젝트 백업 (압축 강화)"""
    root = Path(root_path) if root_path else Path.cwd()
    project_name = root.name
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    if output_name:
        output_file = root / output_name
    else:
        output_file = root / f'backup_{timestamp}.txt'
    
    files_exported = []
    files_skipped = []
    total_size = 0
    
    # 파일 수집 및 우선순위 정렬
    all_files = []
    for path in sorted(root.rglob('*')):
        if path.is_file() and should_include(path, root):
            rel_path = path.relative_to(root)
            size = path.stat().st_size
            priority = get_file_priority(path)
            all_files.append((rel_path, size, path, priority))
    
    # 우선순위 정렬
    all_files.sort(key=lambda x: (x[3], x[1]))
    
    with open(output_file, 'w', encoding='utf-8') as out:
        # 헤더 (최소화)
        out.write(f"# {project_name} 백업 ({datetime.now().strftime('%Y-%m-%d')})\n")
        out.write(f"# 파일: {len(all_files)}개\n")
        out.write("=" * 50 + "\n\n")
        
        # 파일 목록 (간략)
        out.write("## 파일\n")
        for rel_path, size, _, _ in all_files:
            out.write(f"- {rel_path}\n")
        out.write("\n")
        
        # 파일 내용
        for rel_path, size, path, _ in all_files:
            # 전체 크기 제한
            if total_size > MAX_TOTAL_SIZE:
                files_skipped.append(f"{rel_path} (총량 초과)")
                continue
            
            # 개별 파일 크기 제한
            if size > MAX_FILE_SIZE:
                files_skipped.append(f"{rel_path} (크기 초과)")
                out.write(f"\n{'='*50}\n")
                out.write(f"# {rel_path} [스킵: {size:,}B]\n")
                continue
            
            try:
                content = path.read_text(encoding='utf-8')
                
                # 민감 정보 마스킹
                content = mask_sensitive(content)
                
                # 코드 압축
                content = compress_content(content)
                
                # 줄 수 제한
                content, truncated = truncate_content(content, MAX_LINES_PER_FILE)
                
                out.write(f"\n{'='*50}\n")
                out.write(f"# {rel_path}\n")
                out.write(f"{'='*50}\n")
                out.write(content)
                out.write("\n")
                
                files_exported.append(str(rel_path))
                total_size += len(content)
                
            except UnicodeDecodeError:
                files_skipped.append(f"{rel_path} (인코딩)")
            except Exception as e:
                files_skipped.append(f"{rel_path} ({e})")
        
        # 요약
        out.write(f"\n{'='*50}\n")
        out.write(f"# 완료: {len(files_exported)}개, 스킵: {len(files_skipped)}개\n")
    
    final_size = output_file.stat().st_size
    print(f"✅ 백업 완료: {output_file.name}")
    print(f"   포함: {len(files_exported)}개")
    print(f"   스킵: {len(files_skipped)}개")
    print(f"   크기: {final_size:,} bytes ({final_size/1024:.1f}KB)")
    
    if files_skipped:
        print(f"   스킵 목록: {', '.join(files_skipped[:5])}")
    
    return output_file


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='프로젝트 백업 v2 (압축)')
    parser.add_argument('-o', '--output', help='출력 파일명')
    parser.add_argument('-p', '--path', help='프로젝트 경로')
    parser.add_argument('--max-lines', type=int, default=150, help='파일당 최대 줄')
    parser.add_argument('--max-size', type=int, default=10, help='최대 파일 크기(KB)')
    parser.add_argument('--max-total', type=int, default=100, help='전체 최대 크기(KB)')
    
    args = parser.parse_args()
    
    if args.max_lines:
        MAX_LINES_PER_FILE = args.max_lines
    if args.max_size:
        MAX_FILE_SIZE = args.max_size * 1024
    if args.max_total:
        MAX_TOTAL_SIZE = args.max_total * 1024
    
    export_project(args.output, args.path)
