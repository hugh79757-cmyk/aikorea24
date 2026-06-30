from dataclasses import dataclass, field
from typing import Optional


@dataclass
class NewsArticle:
    id: int | str
    title: str
    link: str
    description: str
    source: str
    pub_date: str
    original_title: str = ""
    category: str = ""
    cluster: str = ""
    body: str = ""


@dataclass
class BriefingItem:
    news_id: int | str
    sort_order: int
    comment: str
    article: Optional[NewsArticle] = None


@dataclass
class ThreadsPost:
    post_id: Optional[str] = None
    text: str = ""
    media_type: str = "TEXT"
    reply_to_id: Optional[str] = None
    container_id: Optional[str] = None
    status: str = "pending"


@dataclass
class PipelineStepResult:
    step_name: str
    success: bool
    duration_seconds: float
    error: Optional[str] = None
    run_id: Optional[str] = None


@dataclass
class PipelineRun:
    run_id: str
    status: str
    started_at: str
    completed_at: Optional[str] = None
    steps: list[PipelineStepResult] = field(default_factory=list)
