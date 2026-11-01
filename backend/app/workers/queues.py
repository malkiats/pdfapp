"""RQ queues, one per egress profile (ADR-0001), and the worker roles that consume them.

Job payloads hold only `job_id`, `tool_slug` and validated options: never file bytes,
filenames or URLs in clear. No tool jobs exist in Phase 1.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from pdfapp.backend.app.core.config import Settings

QUEUE_DOCS: Final = "docs"
QUEUE_WEB: Final = "web"
QUEUE_AI: Final = "ai"


class Role(StrEnum):
    WORKER_DOCS = "worker-docs"
    WORKER_WEB = "worker-web"
    WORKER_AI = "worker-ai"
    SWEEPER = "sweeper"


WORKER_ROLES: Final = (Role.WORKER_DOCS, Role.WORKER_WEB, Role.WORKER_AI)


def queues_for(role: Role, settings: Settings) -> list[str]:
    """Queue names a worker role consumes, in priority order (e.g. `docs-paid`, `docs`)."""
    mapping = {
        Role.WORKER_DOCS: settings.queues.docs,
        Role.WORKER_WEB: settings.queues.web,
        Role.WORKER_AI: settings.queues.ai,
    }
    if role not in mapping:
        raise ValueError("role has no queues")
    return list(mapping[role])
