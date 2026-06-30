"""
로그 스크러빙 — API 키, JWT, 이메일, PII 패턴 기반 자동 redaction

Usage:
    from pipeline.infra.logger import ScrubRegistry, get_scrubbed_logger

    logger = get_scrubbed_logger(__name__)
    logger.info("API key: sk-test1234567890")  # → "API key: ***"

    # 직접 스크러빙
    safe = ScrubRegistry.scrub("secret key is sk-abc...")
"""

import logging
import re
import time
from typing import Optional


# ── 알려진 민감 환경 변수 이름들 ──────────────────────────
# 이 이름들로 시작하는 KEY=VALUE 패턴을 스크럽합니다.
_SENSITIVE_ENV_NAMES: list[str] = [
    "API_KEY",
    "API_TOKEN",
    "ACCESS_KEY",
    "SECRET_KEY",
    "SECRET",
    "TOKEN",
    "PASSWORD",
    "PASS",
    "CLIENT_SECRET",
    "AUTH_SECRET",
    "SESSION_SECRET",
    "AI_API_KEY",
    "WORKERS_AI_API_TOKEN",
    "D1_API_TOKEN",
    "BOT_TOKEN",
    "BEARER",
]


class ScrubRegistry:
    """패턴 기반 민감 정보 스크러빙 레지스트리.

    클래스 수준에서 컴파일된 정규식 패턴 목록을 관리합니다.
    모든 인스턴스가 동일한 패턴 세트를 공유합니다.

    사용법:
        # 기본 패턴으로 스크럽 (생성자에서 자동 등록)
        safe = ScrubRegistry.scrub("my key is sk-test123")

        # 커스텀 패턴 추가
        ScrubRegistry.add_pattern("my_secret", r"my_secret=[a-zA-Z0-9_]+")
    """

    _patterns: list[tuple[str, re.Pattern, str]] = []  # (name, compiled_pattern, replacement)
    _initialized: bool = False

    @classmethod
    def _ensure_defaults(cls) -> None:
        """기본 스크럽 패턴을 한 번만 등록합니다."""
        if cls._initialized:
            return
        cls._initialized = True

        # API 키 패턴 (sk-... 형식) — 하이픈 포함, 짧은 키도 캐치
        cls.add_pattern("openai_key", r"sk-[A-Za-z0-9-]{4,}")

        # GitHub Personal Access Token
        cls.add_pattern("github_token", r"ghp_[A-Za-z0-9]{36,}")

        # GitHub fine-grained token
        cls.add_pattern("github_fine_token", r"github_pat_[A-Za-z0-9]{22,}")

        # Cloudflare API Token
        cls.add_pattern("cf_token", r"cfut_[A-Za-z0-9]{20,}")

        # NVIDIA API Key
        cls.add_pattern("nvidia_key", r"nvapi-[A-Za-z0-9\-]{20,}")

        # Hugging Face Token
        cls.add_pattern("hf_token", r"hf_[A-Za-z0-9]{20,}")

        # Brevo API Key
        cls.add_pattern("brevo_key", r"xkeysib-[A-Za-z0-9\-]{20,}")

        # Upstage API Key
        cls.add_pattern("upstage_key", r"up_[A-Za-z0-9]{20,}")

        # OpenRouter Key
        cls.add_pattern("openrouter_key", r"sk-or-v1-[A-Za-z0-9]{20,}")

        # MiMo API Key
        cls.add_pattern("mimo_key", r"sk-sck[A-Za-z0-9]{20,}")

        # Naver CLOVA Key
        cls.add_pattern("clova_key", r"nv-[A-Za-z0-9\-]{20,}")

        # Zhipu API Key
        cls.add_pattern("zhipu_key", r"[0-9a-f]{32}\.[A-Za-z0-9]{10,}")

        # Data.go.kr key
        cls.add_pattern("data_gokr", r"[0-9a-f]{64}")

        # JWT (세 부분, eyJ 로 시작)
        cls.add_pattern("jwt", r"eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")

        # Bearer token 헤더
        cls.add_pattern("bearer", r"Bearer\s+[A-Za-z0-9\-_.]{20,}")

        # Google OAuth Client Secret
        cls.add_pattern("google_oauth", r"GOCSPX-[A-Za-z0-9\-_]{20,}")

        # Threads Access Token (THA...)
        cls.add_pattern("threads_token", r"TH[Aa][A-Za-z0-9\-_]{20,}")

        # Coupang Secret Key
        cls.add_pattern("coupang_secret", r"[0-9a-f]{32,}")

        # OpenAI project keys (sk-proj-...)
        cls.add_pattern("openai_proj_key", r"sk-proj-[A-Za-z0-9\-_]{20,}")

        # 이메일 주소 (PII)
        cls.add_pattern("email", r"[\w.+-]+@[\w-]+\.[\w.-]+")

    @classmethod
    def add_pattern(cls, name: str, pattern: str, replacement: str = "[REDACTED]") -> None:
        """스크럽 패턴을 등록합니다.

        Args:
            name: 패턴 식별자 (로깅/디버깅용)
            pattern: 정규식 패턴 문자열
            replacement: 대체 문자열 (기본값: '***')
        """
        compiled = re.compile(pattern)
        # 중복 등록 방지 — 같은 이름이면 교체
        for i, (n, _, _) in enumerate(cls._patterns):
            if n == name:
                cls._patterns[i] = (name, compiled, replacement)
                return
        cls._patterns.append((name, compiled, replacement))

    @classmethod
    def scrub(cls, text: str) -> str:
        """텍스트의 모든 민감 패턴을 *** 로 대체합니다.

        Args:
            text: 원본 텍스트

        Returns:
            스크럽된 텍스트
        """
        cls._ensure_defaults()
        result = text
        for _, compiled, replacement in cls._patterns:
            result = compiled.sub(replacement, result)

        # env 이름 기반 KEY=VALUE 스크럽 추가
        result = cls._scrub_env_lines(result)

        return result

    @classmethod
    def _scrub_env_lines(cls, text: str) -> str:
        """KEY=VALUE 패턴에서 VALUE가 민감한 env 이름이면 스크럽.

        KEY=sk-... 형태는 위 패턴에서 이미 걸러지지만,
        KEY=단순문자열 (예: SESSION_SECRET=abc123) 은 추가 처리 필요.
        """
        # KEY=VALUE 패턴에서 KEY가 민감 이름 목록에 포함되면 VALUE 마스킹
        for env_name in _SENSITIVE_ENV_NAMES:
            # export KEY=VALUE 또는 KEY=VALUE 형태
            pattern = re.compile(
                rf'({re.escape(env_name)})=\S+',
                re.IGNORECASE,
            )
            text = pattern.sub(r'\1=[REDACTED]', text)
        return text

    @classmethod
    def from_env_names(cls, names: list[str]) -> None:
        """환경 변수 이름 목록에서 스크럽 패턴을 생성하여 등록합니다.

        각 이름에 대해 'NAME=value' 패턴을 등록합니다.

        Args:
            names: 환경 변수 이름 목록 (예: ['OPENAI_API_KEY', 'DEEPSEEK_API_TOKEN'])
        """
        for name in names:
            pattern = re.escape(name) + r'=\S+'
            cls.add_pattern(f"env_{name}", pattern, f"{name}=***")

    @classmethod
    def list_patterns(cls) -> list[tuple[str, str]]:
        """등록된 모든 패턴 목록을 반환합니다.

        Returns:
            (name, pattern_string) 튜플 목록
        """
        cls._ensure_defaults()
        return [(n, p.pattern) for n, p, _ in cls._patterns]


# ── 로거 필터 ──────────────────────────────────────────


class ScrubLogFilter(logging.Filter):
    """LogRecord 메시지를 ScrubRegistry 로 스크럽하는 로깅 필터.

    사용법:
        logger.addFilter(ScrubLogFilter())
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """LogRecord 의 메시지를 스크럽합니다."""
        record.msg = ScrubRegistry.scrub(str(record.msg))
        if record.args:
            # args 의 각 항목도 스크럽
            record.args = tuple(
                ScrubRegistry.scrub(str(a)) if isinstance(a, str) else a
                for a in record.args
            )
        return True


def get_scrubbed_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """ScrubLogFilter 가 적용된 로거를 생성합니다.

    생성된 로거의 모든 로그 메시지는 ScrubRegistry 를 통과하여
    API 키, JWT, 이메일 등이 자동으로 *** 처리됩니다.

    Args:
        name: 로거 이름 (보통 __name__)
        level: 로깅 레벨 (기본값: INFO)

    Returns:
        ScrubLogFilter 가 적용된 logging.Logger 인스턴스
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 중복 필터 방지
    has_filter = any(isinstance(f, ScrubLogFilter) for f in logger.filters)
    if not has_filter:
        logger.addFilter(ScrubLogFilter())

    # 핸들러가 없으면 기본 StreamHandler 추가
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        ))
        logger.addHandler(handler)

    return logger


def scrub_print(*args, **kwargs) -> None:
    """print() 의 드롭인 대체 — 출력 전 ScrubRegistry 로 스크럽.

    Strangler Fig 전환 중 print() 를 직접 사용하는 레거시 코드에서
    민감 정보 누출을 방지하기 위한 임시 함수입니다.

    Usage:
        from pipeline.infra.logger import scrub_print
        scrub_print(f'Token: {new_token}')  # → "Token: ***"
    """
    scrubbed_args = tuple(
        ScrubRegistry.scrub(str(arg)) if isinstance(arg, str) else arg
        for arg in args
    )
    print(*scrubbed_args, **kwargs)


# ── PipelineLogger (structured context + duration) ──────────────

from contextlib import contextmanager
from typing import Generator, Optional


class PipelineLogger(logging.LoggerAdapter):
    """run_id, step_name, duration 컨텍스트를 로그 레코드에 첨부.

    LoggerAdapter 패턴을 사용하여 extra dict를 통해 추가 컨텍스트를 전달.
    ScrubLogFilter는 extra dict를 건드리지 않고 msg만 스크럽하므로
    두 계층이 독립적으로 동작합니다.

    Usage:
        log = PipelineLogger(get_scrubbed_logger(__name__), run_id="run01", step_name="fetch")
        log.info("기사 수집 시작")
        # → "[run_id=run01] [step=fetch] 기사 수집 시작"
    """

    def __init__(
        self,
        logger: logging.Logger,
        run_id: str = "",
        step_name: str = "",
        duration: Optional[float] = None,
    ):
        super().__init__(logger, {"run_id": run_id, "step_name": step_name, "duration": duration})

    def process(self, msg: str, kwargs: dict) -> tuple[str, dict]:
        """로그 메시지에 컨텍스트 프리픽스를 추가."""
        parts = []
        if self.extra["run_id"]:
            parts.append(f"[run_id={self.extra['run_id']}]")
        if self.extra["step_name"]:
            parts.append(f"[step={self.extra['step_name']}]")
        if self.extra.get("duration") is not None:
            parts.append(f"[dur={self.extra['duration']:.1f}s]")
        prefix = " ".join(parts)
        if prefix:
            msg = f"{prefix} {msg}"
        return msg, kwargs


def get_pipeline_logger(
    name: str,
    run_id: str = "",
    step_name: str = "",
    level: int = logging.INFO,
) -> PipelineLogger:
    """PipelineLogger 인스턴스를 생성.

    Args:
        name: 로거 이름 (보통 __name__)
        run_id: 실행 식별자 (예: "run_20260630_120000")
        step_name: 현재 단계 이름 (예: "news_crawl")
        level: 로깅 레벨

    Returns:
        ScrubLogFilter + 컨텍스트가 적용된 PipelineLogger
    """
    logger = get_scrubbed_logger(name, level)
    return PipelineLogger(logger, run_id=run_id, step_name=step_name)


@contextmanager
def log_step(logger: PipelineLogger, step_name: str) -> Generator[PipelineLogger, None, None]:
    """단계 실행 시간을 측정하고 로깅하는 컨텍스트 매니저.

    Usage:
        with log_step(log, "fetch_news") as ctx:
            news = fetch_news()
        # → "[step=fetch_news] [dur=1.2s] fetch_news completed"
    """
    old_step = logger.extra.get("step_name", "")
    logger.extra["step_name"] = step_name
    logger.extra["duration"] = None
    start = time.monotonic()
    try:
        yield logger
    finally:
        elapsed = time.monotonic() - start
        logger.extra["duration"] = elapsed
        logger.info(f"{step_name} completed in {elapsed:.1f}s")
        logger.extra["step_name"] = old_step
