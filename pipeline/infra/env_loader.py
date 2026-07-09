"""
환경 변수 로더 — .env 및 ~/.env.common 통합 로딩

Usage:
    config = EnvConfig()
    api_key = config.get('OPENAI_API_KEY')
    debug = config.getbool('DEBUG', False)
    config.load_to_environ()  # os.environ 동기화 (필요시)

우선순위:
    1. 프로젝트 .env (최우선 — common 덮어쓰기)
    2. ~/.env.common (fallback — setdefault 의미)

Strangler Fig: Phase 2에서 기존 load_env() 호출을 대체 예정.
Python 3.14 stdlib only — no python-dotenv.
"""

import os
import re
from pathlib import Path
from typing import Optional


class EnvConfig:
    """환경 변수 설정 관리자.

    .env 파일과 ~/.env.common 파일을 로드하여 통합된 환경 변수 맵을 제공.
    모듈 임포트 시 부수 효과(side effect) 없음 — load_to_environ()은 명시적 호출 필요.
    """

    def __init__(self, project_dir: Optional[Path] = None):
        """EnvConfig 초기화.

        Args:
            project_dir: 프로젝트 루트 디렉터리 (기본값: 이 파일 위치에서 상위 3단계)
        """
        self._vars: dict[str, str] = {}

        if project_dir is not None:
            self._project_dir = Path(project_dir).resolve()
        else:
            # pipeline/infra/env_loader.py → pipeline/infra/ → pipeline/ → 프로젝트 루트
            self._project_dir = Path(__file__).resolve().parent.parent.parent

        self._load()

    @property
    def project_dir(self) -> Path:
        """프로젝트 루트 디렉터리 경로."""
        return self._project_dir

    # ── 파일 로딩 ────────────────────────────────────────────

    def _load(self) -> None:
        """모든 env 소스 로드 (순서대로, 나중에 로드된 값이 우선)."""
        # 1. ~/.env.common (fallback — setdefault 의미)
        self._load_file(Path.home() / ".env.common", setdefault=True)
        # 2. 프로젝트 .env (최우선 — 기존 값 덮어쓰기)
        self._load_file(self._project_dir / ".env", setdefault=False)

    @staticmethod
    def _parse_line(line: str) -> Optional[tuple[str, str]]:
        """한 줄의 env 정의를 파싱.

        지원 형식:
            - KEY=VALUE
            - export KEY=VALUE
            - KEY="VALUE"
            - export KEY="VALUE"

        건너뛰는 줄:
            - 빈 줄
            - # 으로 시작하는 주석
            - source 로 시작하는 shell 지시문

        Returns:
            (key, value) 튜플 또는 None (파싱 불가능한 줄)
        """
        stripped = line.strip()

        # 빈 줄 / 주석 / shell source 지시문
        if not stripped or stripped.startswith("#") or stripped.startswith("source"):
            return None

        # export 접두사 제거
        if stripped.startswith("export "):
            stripped = stripped[7:].strip()

        # KEY=VALUE 분할 (첫 번째 = 만 split)
        if "=" not in stripped:
            return None
        key, value = stripped.split("=", 1)
        key = key.strip()

        if not key:
            return None

        # 따옴표 제거
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]

        return (key, value)

    def _load_file(self, path: Path, setdefault: bool = False) -> None:
        """env 파일을 읽어 self._vars 에 로드.

        Args:
            path: env 파일 경로
            setdefault: True면 이미 존재하는 키를 덮어쓰지 않음 (fallback 의미)
        """
        if not path.exists():
            return

        with open(path, encoding="utf-8") as f:
            for line in f:
                parsed = self._parse_line(line)
                if parsed is None:
                    continue
                key, value = parsed
                if setdefault:
                    # 이미 존재하는 키는 건너뛰기
                    if key not in self._vars:
                        self._vars[key] = value
                else:
                    self._vars[key] = value

    # ── 조회 메서드 ──────────────────────────────────────────

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """환경 변수 값을 반환.

        Args:
            key: 환경 변수 이름
            default: 키가 없을 때 반환할 기본값

        Returns:
            환경 변수 값 또는 default
        """
        return self._vars.get(key, default)

    def getint(self, key: str, default: int = 0) -> int:
        """환경 변수를 정수로 변환하여 반환.

        Args:
            key: 환경 변수 이름
            default: 변환 실패 시 기본값

        Returns:
            정수 값
        """
        value = self.get(key)
        if value is None:
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    def getbool(self, key: str, default: bool = False) -> bool:
        """환경 변수를 불리언으로 변환하여 반환.

        True로 간주하는 값 (대소문자 무관): 'true', '1', 'yes', 'on'
        그 외 모든 값은 False.

        Args:
            key: 환경 변수 이름
            default: 키가 없을 때 반환할 기본값

        Returns:
            불리언 값
        """
        value = self.get(key)
        if value is None:
            return default
        return value.strip().lower() in ("true", "1", "yes", "on")

    # ── os.environ 동기화 ────────────────────────────────────

    def load_to_environ(self) -> None:
        """로드된 모든 변수를 os.environ 에 설정.

        명시적 호출이 필요함 — 모듈 임포트 시 자동 실행되지 않음.
        프로젝트 .env 값을 os.environ에 반영 (기존값 덮어씀).
        """
        for key, value in self._vars.items():
            os.environ[key] = value
