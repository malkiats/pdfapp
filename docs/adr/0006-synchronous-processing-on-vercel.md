# ADR-0006: Synchronous, in-request processing on Vercel with no storage

Status: accepted · Date: 2026-11-01 · Supersedes ADR-0001 and ADR-0002 · Revised the same day to the confirmed constraints: 4 MB inline only, no S3, no cron.

## Context
The user confirmed these constraints:
- Frontend and API both run on Vercel, on the Hobby plan as a demo tier.
- Only lightweight pure-Python tools.
- Inputs capped at 4 MB.
- No storage of any kind.

The platform adds its own:
- Request and response bodies are capped at about 4.5 MB.
- `maxDuration` is 60 s.
- `/tmp` persists while an instance is warm, and concurrent requests may share an instance.

## Decision
1. **One synchronous request per tool**: `POST /api/v1/tools/{slug}`.
   - Input: multipart for files, JSON for text or URLs. The whole request must be ≤ 4 MB.
   - Output: the result in the response body, ≤ 4 MB, otherwise `413 output_too_large`.
   - There are no jobs, polling, tickets, tokens, queues, workers, Redis, S3 or cron.
2. **One temp-file helper**, `backend/app/storage/scratch.py`. Every tool must use it, and it is the only module allowed to create files.

```python
class FileKind(StrEnum):  # set by magic-byte sniffing, never by the filename
    PDF = "pdf"; PNG = "png"; JPEG = "jpg"; WEBP = "webp"; TIFF = "tiff"
    TXT = "txt"; MD = "md"; CSV = "csv"; JSON = "json"; ZIP = "zip"

@dataclass(frozen=True)
class Scratch:
    root: Path                                               # /tmp/<secrets.token_hex(16)>, mode 0700
    def input_path(self, index: int, kind: FileKind) -> Path: ...    # root/in/000.pdf
    def output_path(self, kind: FileKind) -> Path: ...               # root/out/result.<ext>
    async def write_input(self, index: int, chunks: AsyncIterator[bytes],
                          *, kind: FileKind, max_bytes: int) -> Path: ...   # raises InputTooLarge
    def read_output(self, path: Path, *, max_bytes: int) -> bytes: ...      # raises OutputTooLarge; path must be inside root

@contextmanager
def scratch() -> Iterator[Scratch]:
    """Creates the directory, yields it, and ALWAYS deletes it (rmtree in finally),
    including on exceptions and timeouts. A failed deletion is logged as
    {event: scratch_cleanup_failed, error_class} only, never with paths."""
```

   Also, when it first starts, an instance deletes any `/tmp/<32-hex>` directories that are older than 5 minutes. These would be leftovers from a killed request.
3. **No shared state**: no module-level content, no caches, no singletons holding request data.
4. **Abuse control**: Vercel Firewall rate-limit rules where the plan allows. Otherwise a best-effort in-process limiter. Groq abuse is bounded by a spend cap on the provider account (ADR-0007).

## Consequences
- (+) Nothing to operate and no user content at rest anywhere we control. This is the strongest privacy posture available.
- (−) Files over 4 MB, heavy tools and per-user quotas are impossible within this design. Adding them means a new ADR (storage and/or workers).
- (−) Untrusted files are parsed in the API process. This is mitigated by caps, the 60 s limit and the absence of high-value secrets before Phase 7.

## Rejected
- S3 large mode with a cron sweep: dropped by user decision (no storage).
- External workers (SQS + Lambda, or RQ + Redis): not needed for lightweight tools.
