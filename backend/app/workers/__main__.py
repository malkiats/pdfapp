"""Role entrypoint: `python -m app.workers <worker-docs|worker-web|worker-ai|sweeper>`."""

from __future__ import annotations

import asyncio
import sys

from pdfapp.backend.app.core.config import get_settings
from pdfapp.backend.app.core.logging import configure_logging, get_logger
from pdfapp.backend.app.workers.queues import Role

USAGE = "usage: python -m app.workers {worker-docs|worker-web|worker-ai|sweeper}"


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1 or args[0] not in {r.value for r in Role}:
        print(USAGE, file=sys.stderr)
        return 2
    role = Role(args[0])
    settings = get_settings()
    configure_logging(settings.logging.level, json_output=settings.logging.json_output)
    log = get_logger(__name__, role=role.value)
    try:
        if role is Role.SWEEPER:
            from pdfapp.backend.app.workers.sweeper import run_forever

            asyncio.run(run_forever(settings))
            return 0
        from pdfapp.backend.app.workers.runner import run_worker

        return 0 if run_worker(role, settings) else 1
    except RuntimeError as exc:
        # Configuration problems (e.g. no APP_REDIS__URL): one clean line, no traceback.
        log.error("startup_failed", error_class=type(exc).__name__)
        print(f"{role.value}: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - no traceback: it may carry URLs or paths
        log.error("worker_crashed", error_class=type(exc).__name__)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
