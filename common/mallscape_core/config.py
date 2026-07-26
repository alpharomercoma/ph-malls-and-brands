"""Runtime configuration, read from the environment with working defaults.

Every operational value lives here rather than being written into a module, so
behaviour can be tuned per environment (a CI run, a slow network, a different
data volume) without editing code. Defaults are the values this project runs
with in practice, so the pipeline works with no environment set at all.

Values are read once at import. Invalid values raise immediately with the
offending variable named, because a silently ignored setting is worse than a
crash: it looks like it worked.

Read `.env.example` for the full list with commentary.
"""

from __future__ import annotations

import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _str(name: str, default: str) -> str:
    return os.environ.get(name, default).strip() or default


def _int(name: str, default: int, *, minimum: int | None = None) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got {value}")
    return value


def _float(name: str, default: float, *, minimum: float | None = None) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, got {raw!r}") from exc
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got {value}")
    return value


def _path(name: str, default: Path) -> Path:
    raw = os.environ.get(name)
    return Path(raw).expanduser().resolve() if raw and raw.strip() else default


# --- where data lives --------------------------------------------------------
DATA_DIR: Path = _path("MALLSCAPE_DATA_DIR", _REPO_ROOT / "data")
SITE_DIR: Path = _path("MALLSCAPE_SITE_DIR", _REPO_ROOT / "4_website" / "site")

# --- how the scraper behaves -------------------------------------------------
# 3 req/s is deliberately conservative. SM's WAF issues a temporary site-wide
# 403 at sustained higher rates; see docs/PITFALLS.md.
REQUEST_RATE: float = _float("MALLSCAPE_REQUEST_RATE", 3.0, minimum=0.1)
REQUEST_TIMEOUT: float = _float("MALLSCAPE_REQUEST_TIMEOUT", 30.0, minimum=1.0)
RETRY_ATTEMPTS: int = _int("MALLSCAPE_RETRY_ATTEMPTS", 8, minimum=1)
RETRY_MAX_WAIT: float = _float("MALLSCAPE_RETRY_MAX_WAIT", 300.0, minimum=1.0)
USER_AGENT: str = _str(
    "MALLSCAPE_USER_AGENT",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 mallscape-research/1.0",
)

# --- pagination guards -------------------------------------------------------
# Upper bounds only. They exist to turn a runaway loop into a loud failure
# rather than an infinite one, and are far above any real directory size.
MAX_PAGES: int = _int("MALLSCAPE_MAX_PAGES", 500, minimum=1)

# --- website -----------------------------------------------------------------
SITE_PORT: int = _int("MALLSCAPE_SITE_PORT", 3000, minimum=1)
SITE_TITLE: str = _str("MALLSCAPE_SITE_TITLE", "Philippine Mall Explorer")
SITE_REPO_URL: str = _str(
    "MALLSCAPE_SITE_REPO_URL",
    "https://github.com/alpharomercoma/philippine-mall-explorer",
)


def summary() -> dict[str, object]:
    """Effective configuration, for logging and for the doctor command."""
    return {
        "DATA_DIR": str(DATA_DIR),
        "SITE_DIR": str(SITE_DIR),
        "REQUEST_RATE": REQUEST_RATE,
        "REQUEST_TIMEOUT": REQUEST_TIMEOUT,
        "RETRY_ATTEMPTS": RETRY_ATTEMPTS,
        "RETRY_MAX_WAIT": RETRY_MAX_WAIT,
        "MAX_PAGES": MAX_PAGES,
        "SITE_PORT": SITE_PORT,
        "SITE_TITLE": SITE_TITLE,
    }
