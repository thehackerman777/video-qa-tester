"""Core types for the Video QA Tester."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TestStatus(Enum):
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    TIMEOUT = "timeout"


class ActionType(Enum):
    NAVIGATE = "navigate"
    PLAY = "play"
    PAUSE = "pause"
    RESUME = "resume"
    SEEK = "seek"
    LIKE = "like"
    SUBSCRIBE = "subscribe"
    LOGIN = "login"
    WAIT = "wait"
    FULLSCREEN = "fullscreen"
    CAPTURE = "capture_snapshot"


@dataclass
class Metadata:
    """Testing metadata — marks all traffic as internal QA."""
    traffic_type: str = "internal_testing"
    test_run_id: str = ""
    scenario: str = ""
    worker: str = ""
    environment: str = "qa"

    def __post_init__(self):
        from datetime import datetime
        import uuid
        if not self.test_run_id:
            self.test_run_id = f"test-{uuid.uuid4().hex[:8]}"
        self.timestamp = datetime.utcnow().isoformat()


@dataclass
class ActionResult:
    action_type: ActionType
    status: str  # success, failure, timeout
    duration_ms: float = 0
    details: dict = field(default_factory=dict)


@dataclass
class TestResult:
    video_url: str
    status: TestStatus
    actions: list[ActionResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    watch_time_seconds: float = 0
    duration_ms: float = 0
    metadata: Optional[Metadata] = None
    view_count_before: int = 0
    view_count_after: int = 0


@dataclass
class ChannelVideo:
    video_id: str
    title: str
    url: str
    view_count: int = 0
    duration: str = ""


@dataclass
class TestConfig:
    """Test configuration."""
    headless: bool = True
    viewport: tuple = (1920, 1080)
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    locale: str = "en-US"
    timeout: int = 30000
    video_wait_seconds: int = 35  # YouTube view threshold
    persist_session: bool = True
    session_dir: str = "sessions"


@dataclass
class LoadTestConfig:
    """Load test configuration."""
    users: int = 100
    ramp_up_seconds: int = 30
    duration_seconds: int = 120
    watch_time_seconds: int = 40  # Per user
    max_concurrent_browsers: int = 10
