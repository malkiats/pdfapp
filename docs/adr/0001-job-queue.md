# ADR-0001: Job queue: RQ on Redis

Status: superseded by [ADR-0006](0006-synchronous-processing-on-vercel.md) on 2026-11-01 (all-Vercel, synchronous design) · Date: 2026-10-31

## Context
Heavy work (PDF ops, LibreOffice, Tesseract, LLM calls, URL fetches) must run outside the API in isolated workers. Most jobs are CPU-bound or run external subprocesses. They need a hard timeout, and must not leave document data in memory between jobs. The team is small, so ops cost matters more than throughput features. Redis is already needed for job state and rate limiting.

## Options

| | Celery | RQ | arq | Dramatiq |
|---|---|---|---|---|
| Broker | Redis/RabbitMQ | Redis | Redis | Redis/RabbitMQ |
| Execution model | prefork pool (long-lived children) | **fork per job** | asyncio, one process | long-lived processes + threads |
| Hard timeout | soft/hard time limits (pool-dependent) | parent kills work-horse | asyncio cancel (cannot stop CPU-bound code) | thread interrupt (cannot stop C code or subprocesses) |
| Memory isolation between jobs | no (configurable max-tasks-per-child) | **yes** | no | no |
| Ops / config surface | large | small | small | small |
| Fit for CPU/subprocess work | good | good | poor without process pools | good |
| Maintenance | active | active | low activity | active |

## Decision
Use **RQ** (2.x) on Redis/Valkey, with one queue per egress profile: `docs`, `web`, `ai`. Each worker service consumes exactly one queue.
- Job timeouts and result TTLs are set per job from settings.
- `on_failure` and `on_success` callbacks call the TempFileManager (ADR-0002). Job payloads hold only `job_id`, the tool `slug` and validated options. **Never file bytes, filenames or URLs in clear**: the URLs for web compare are stored in the workspace, not in the queue payload.
- RQ retention hygiene: `result_ttl` and `failure_ttl` are short (minutes) and never exceed the workspace hard TTL (ADR-0002). Exceptions stored by RQ are reduced to the exception class name, since messages and tracebacks can contain paths or content. Secrets (job tokens, API keys, credentials) are never placed in job args or kwargs.
- Scheduling: the sweeper is a dedicated process with a loop and a Redis lock. It does not depend on a queue scheduler.

## Consequences
- (+) Fork per job gives crash and memory isolation and a reliable kill on timeout, with very little config.
- (+) The same Redis serves the queue, job state and rate limits, so there is one managed dependency.
- (−) Fork overhead (~10–50 ms) per job. This is negligible next to document work.
- (−) RQ is sync. The API enqueues through a threadpool call, which is cheap.
- (−) No native priorities beyond separate queues. Paid users get priority through queue order: `rq worker docs-paid docs`.
- (−) A Redis restart drops queued jobs. This is accepted: users re-submit, and the sweeper cleans up orphans.

## Rejected
- **Celery**: too much config and operational surface for this team. Long-lived children keep data in memory unless tuned.
- **arq**: asyncio does not suit CPU-bound work, timeouts cannot preempt C extensions, and maintenance has slowed.
- **Dramatiq**: a good library, but time limits cannot kill native code or subprocesses and there is no per-job process isolation. It would be the fallback if RQ stops being maintained.
