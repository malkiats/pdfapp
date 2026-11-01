"""Local directory backend (shared Docker volume in local dev, CI and single-host setups).

Error contract (shared with every backend): a missing object is ``NotFound`` (or an empty
result for listings), a key that would leave the root is ``PathEscape``, and EVERY other OS
failure (permissions, I/O, full disk, ...) is ``StorageUnavailable`` with a fixed message.
OS error messages are never propagated because they contain paths.
"""

from __future__ import annotations

import contextlib
import os
import secrets
import shutil
from collections.abc import AsyncIterator, Callable
from pathlib import Path, PurePosixPath
from typing import IO, TypeVar

from anyio import to_thread

from pdfapp.backend.app.storage.errors import InputTooLarge, NotFound, PathEscape, StorageUnavailable

_DIR_MODE = 0o700
_FILE_MODE = 0o600
_OPEN_FLAGS = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
_PARTIAL = ".part-"

T = TypeVar("T")


async def _run(func: Callable[[], T], failure: str) -> T:
    """Runs blocking file I/O in a thread, normalising OS errors (FileNotFoundError passes)."""
    try:
        return await to_thread.run_sync(func)
    except (FileNotFoundError, PathEscape, NotFound, InputTooLarge, StorageUnavailable):
        raise
    except OSError as exc:
        raise StorageUnavailable(failure) from exc


class LocalBackend:
    name = "local"

    def __init__(self, root: Path) -> None:
        # Resolved once (symlinks in the configured path are followed here, never later).
        self._root = root.resolve()

    # ------------------------------------------------------------------ paths
    @property
    def root(self) -> Path:
        return self._root

    def _path(self, key: str) -> Path:
        """Maps a relative key to a path under the root, refusing anything that escapes."""
        pure = PurePosixPath(key)
        if (
            not key
            or pure.is_absolute()
            or "\\" in key
            or "\x00" in key
            or any(part in ("", ".", "..") for part in key.rstrip("/").split("/"))
        ):
            raise PathEscape("key is not a clean relative path")
        candidate = self._root.joinpath(*pure.parts)
        if not candidate.resolve(strict=False).is_relative_to(self._root):
            raise PathEscape("key resolves outside the storage root")
        return candidate

    @staticmethod
    def _mkparents(path: Path) -> None:
        path.parent.mkdir(mode=_DIR_MODE, parents=True, exist_ok=True)

    @staticmethod
    def _unlink_quiet(path: Path) -> None:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(path)

    # ------------------------------------------------------------------ writes
    async def put_stream(self, key: str, chunks: AsyncIterator[bytes], *, max_bytes: int) -> int:
        final = self._path(key)
        partial = final.with_name(final.name + _PARTIAL + secrets.token_hex(4))

        def _open() -> IO[bytes]:
            self._mkparents(final)
            return os.fdopen(os.open(partial, _OPEN_FLAGS, _FILE_MODE), "wb")

        handle = await _run(_open, "write failed")
        written = 0
        try:
            async for chunk in chunks:
                written += len(chunk)
                if written > max_bytes:
                    raise InputTooLarge(max_bytes)
                await _run(lambda c=chunk: handle.write(c), "write failed")  # type: ignore[misc]
            await _run(handle.flush, "write failed")
            handle.close()
            await _run(lambda: os.replace(partial, final), "write failed")
        except BaseException:
            handle.close()
            with contextlib.suppress(OSError):
                await to_thread.run_sync(self._unlink_quiet, partial)
            raise
        return written

    async def put_file(self, key: str, source: Path) -> int:
        final = self._path(key)

        def _copy() -> int:
            self._mkparents(final)
            partial = final.with_name(final.name + _PARTIAL + secrets.token_hex(4))
            fd = os.open(partial, _OPEN_FLAGS, _FILE_MODE)
            try:
                with os.fdopen(fd, "wb") as out, source.open("rb") as src:
                    shutil.copyfileobj(src, out, 1024 * 1024)
                os.replace(partial, final)
            except BaseException:
                self._unlink_quiet(partial)
                raise
            return final.stat().st_size

        try:
            return await _run(_copy, "write failed")
        except FileNotFoundError as exc:
            raise StorageUnavailable("write failed") from exc

    # ------------------------------------------------------------------ reads
    async def get_stream(self, key: str, *, chunk_size: int = 65536) -> AsyncIterator[bytes]:
        path = self._path(key)
        try:
            handle = await _run(lambda: path.open("rb"), "read failed")
        except FileNotFoundError as exc:
            raise NotFound("object not found") from exc
        try:
            while True:
                chunk = await _run(lambda: handle.read(chunk_size), "read failed")
                if not chunk:
                    break
                yield chunk
        finally:
            handle.close()

    async def download_to(self, key: str, dest: Path) -> int:
        source = self._path(key)

        def _copy() -> int:
            fd = os.open(dest, _OPEN_FLAGS, _FILE_MODE)
            with os.fdopen(fd, "wb") as out, source.open("rb") as src:
                shutil.copyfileobj(src, out, 1024 * 1024)
            return dest.stat().st_size

        try:
            return await _run(_copy, "read failed")
        except FileNotFoundError as exc:
            raise NotFound("object not found") from exc

    async def size(self, key: str) -> int | None:
        path = self._path(key)
        try:
            return (await _run(path.stat, "stat failed")).st_size
        except FileNotFoundError:
            return None

    async def list_keys(self, prefix: str) -> list[str]:
        base = self._path(prefix)

        def _walk() -> list[str]:
            if not base.is_dir():
                return []
            keys: list[str] = []

            def _raise(error: OSError) -> None:
                if not isinstance(error, FileNotFoundError):
                    raise error

            for dirpath, _dirnames, filenames in os.walk(base, onerror=_raise):
                for filename in filenames:
                    if _PARTIAL in filename:
                        continue
                    keys.append(Path(dirpath, filename).relative_to(self._root).as_posix())
            return sorted(keys)

        return await _run(_walk, "list failed")

    async def list_children(self, prefix: str) -> list[str]:
        base = self._path(prefix)

        def _list() -> list[str]:
            try:
                with os.scandir(base) as entries:
                    return sorted(e.name for e in entries if e.is_dir(follow_symlinks=False))
            except FileNotFoundError:
                return []

        return await _run(_list, "list failed")

    # ------------------------------------------------------------------ deletes
    async def delete_prefix(self, prefix: str) -> int:
        base = self._path(prefix)

        def _raise(error: OSError) -> None:
            if not isinstance(error, FileNotFoundError):
                raise error

        def _delete() -> int:
            if not base.exists():
                return 0
            deleted = 0
            for dirpath, dirnames, filenames in os.walk(base, topdown=False, onerror=_raise):
                for filename in filenames:
                    try:
                        os.unlink(os.path.join(dirpath, filename))
                    except FileNotFoundError:
                        continue
                    if _PARTIAL not in filename:
                        deleted += 1
                for dirname in dirnames:
                    with contextlib.suppress(FileNotFoundError):
                        os.rmdir(os.path.join(dirpath, dirname))
            with contextlib.suppress(FileNotFoundError):
                os.rmdir(base)
            return deleted

        return await _run(_delete, "delete failed")

    async def ping(self) -> None:
        def _probe() -> None:
            self._root.mkdir(mode=_DIR_MODE, parents=True, exist_ok=True)
            probe = self._root / f".ready-{secrets.token_hex(8)}"
            fd = os.open(probe, _OPEN_FLAGS, _FILE_MODE)
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(b"ok")
                if probe.read_bytes() != b"ok":
                    raise OSError("probe mismatch")
            finally:
                self._unlink_quiet(probe)

        try:
            await _run(_probe, "storage not writable")
        except FileNotFoundError as exc:
            raise StorageUnavailable("storage not writable") from exc
