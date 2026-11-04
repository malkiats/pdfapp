"""R2 settings (un-prefixed env names) and the opportunistic sweep, on moto (no network)."""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

import boto3  # noqa: TID251 - test fixtures talk to moto directly
import pytest
from moto import mock_aws
from pdfapp.backend.app.core.config import R2Config, Settings
from pdfapp.backend.app.core.upload_ids import hour_bucket
from pdfapp.backend.app.storage.r2 import R2Store, UploadKeys, safe_filename
from pydantic import SecretStr, ValidationError

R2_VARS = (
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_ACCOUNT_ID",
    "R2_BUCKET_NAME",
    "R2_ENDPOINT",
    "R2_PRESIGN_EXPIRES",
    "R2_PREFIX",
)


@pytest.fixture(autouse=True)
def _clean_r2_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in R2_VARS:
        monkeypatch.delenv(name, raising=False)


def _set_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "placeholder-key-id")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "placeholder-secret")
    monkeypatch.setenv("R2_BUCKET_NAME", "placeholder-bucket")
    monkeypatch.setenv("R2_ACCOUNT_ID", "abc123")


# ------------------------------------------------------------------ config
def test_unset_means_disabled() -> None:
    settings = Settings()
    assert settings.r2() is None
    assert settings.large_files_enabled is False
    assert settings.r2_presign_expires == 900


def test_unprefixed_env_names_enable_r2(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required(monkeypatch)
    cfg = Settings().r2()
    assert cfg is not None
    assert cfg.endpoint == "https://abc123.r2.cloudflarestorage.com"
    assert cfg.bucket == "placeholder-bucket"
    assert cfg.prefix == "pdfapp"
    assert isinstance(cfg.secret_access_key, SecretStr)
    assert "placeholder" not in repr(cfg)
    assert "placeholder-secret" not in repr(Settings())


@pytest.mark.parametrize("missing", ["R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET_NAME"])
def test_any_required_var_missing_disables(monkeypatch: pytest.MonkeyPatch, missing: str) -> None:
    _set_required(monkeypatch)
    monkeypatch.setenv(missing, "")
    assert Settings().large_files_enabled is False


def test_endpoint_wins_over_account_and_needs_one_of_them(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required(monkeypatch)
    monkeypatch.setenv("R2_ENDPOINT", "https://abc123def.r2.cloudflarestorage.com/")
    cfg = Settings().r2()
    assert cfg is not None
    assert cfg.endpoint == "https://abc123def.r2.cloudflarestorage.com"
    monkeypatch.delenv("R2_ENDPOINT")
    monkeypatch.delenv("R2_ACCOUNT_ID")
    assert Settings().r2() is None


@pytest.mark.parametrize(
    "endpoint", ["http://example.com", "ftp://x", "https://x.example/bucket", "https://x?y=1"]
)
def test_endpoint_rejected(monkeypatch: pytest.MonkeyPatch, endpoint: str) -> None:
    monkeypatch.setenv("R2_ENDPOINT", endpoint)
    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("", 900), ("   ", 900), ("30", 60), ("600", 600), ("99999", 3600)],
)
def test_presign_expires(monkeypatch: pytest.MonkeyPatch, raw: str, expected: int) -> None:
    monkeypatch.setenv("R2_PRESIGN_EXPIRES", raw)
    assert Settings().r2_presign_expires == expected


def test_presign_expires_garbage_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("R2_PRESIGN_EXPIRES", "soon")
    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.parametrize(
    ("raw", "expected"), [("/pdfapp/", "pdfapp"), ("pdfapp/b", "pdfapp/b"), ("", "pdfapp")]
)
def test_prefix(monkeypatch: pytest.MonkeyPatch, raw: str, expected: str) -> None:
    monkeypatch.setenv("R2_PREFIX", raw)
    assert Settings().r2_prefix == expected


def test_prefix_rejects_traversal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("R2_PREFIX", "../etc")
    with pytest.raises(ValidationError):
        Settings()


def test_large_limits_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_LIMITS__MAX_LARGE_FILE_BYTES", "1234")
    monkeypatch.setenv("APP_LIMITS__MAX_LARGE_PAGES", "50")
    settings = Settings()
    assert settings.limits.max_large_file_bytes == 1234
    assert settings.limits.max_large_pages == 50
    assert settings.limits.max_large_total_bytes == 250 * 1024 * 1024


# ------------------------------------------------------------------ store
BUCKET = "sweep-bucket"


@pytest.fixture
def store() -> Iterator[tuple[R2Store, Any]]:
    with mock_aws():
        client = boto3.client(
            "s3",
            region_name="us-east-1",
            aws_access_key_id="testing",
            aws_secret_access_key="testing",
        )
        client.create_bucket(Bucket=BUCKET)
        cfg = R2Config(
            access_key_id="testing",
            secret_access_key=SecretStr("testing"),
            bucket=BUCKET,
            endpoint="https://unused.invalid",
            prefix="pdfapp",
            presign_expires=900,
        )
        yield R2Store(cfg, client=client), client


def _keys(client: Any) -> set[str]:
    return {o["Key"] for o in client.list_objects_v2(Bucket=BUCKET).get("Contents", [])}


def test_sweep_deletes_only_stale_hour_buckets(store: tuple[R2Store, Any]) -> None:
    r2, client = store
    now = int(time.time())
    stale = hour_bucket(now - 3 * 3600)
    recent = hour_bucket(now - 30 * 60)
    current = hour_bucket(now)
    put = [
        f"pdfapp/{stale}/u1/in/000",
        f"pdfapp/{stale}/u1/out/result.pdf",
        f"pdfapp/{stale}/u2/in/000",
        f"pdfapp/{recent}/u3/in/000",
        f"pdfapp/{current}/u4/in/000",
        "pdfapp/not-an-hour/keep",
        "pdfapp/keep-at-root",
        f"other/{stale}/keep",
    ]
    for key in put:
        client.put_object(Bucket=BUCKET, Key=key, Body=b"x")
    deleted = r2.sweep_stale(now=now, min_age_seconds=3600, time_budget=5)
    assert deleted == 3
    assert _keys(client) == set(put[3:])


def test_sweep_boundary(store: tuple[R2Store, Any]) -> None:
    r2, client = store
    now = 1_700_000_000 // 3600 * 3600 + 120  # 2 minutes past an hour
    two_hours_ago = hour_bucket(now - 2 * 3600)  # ended 62 minutes ago => stale
    one_hour_ago = hour_bucket(now - 3600)  # ended 2 minutes ago => keep
    client.put_object(Bucket=BUCKET, Key=f"pdfapp/{two_hours_ago}/a/in/000", Body=b"x")
    client.put_object(Bucket=BUCKET, Key=f"pdfapp/{one_hour_ago}/b/in/000", Body=b"x")
    r2.sweep_stale(now=now, min_age_seconds=3600, time_budget=5)
    assert _keys(client) == {f"pdfapp/{one_hour_ago}/b/in/000"}


def test_sweep_swallows_errors(store: tuple[R2Store, Any]) -> None:
    r2, _ = store
    r2.bucket = "does-not-exist"
    assert r2.sweep_stale(now=int(time.time()), min_age_seconds=3600, time_budget=1) == 0


def test_delete_prefix_refuses_outside_prefix(store: tuple[R2Store, Any]) -> None:
    r2, _ = store
    for bad in ("other/x/", "pdfapp", "pdfapp/x"):
        with pytest.raises(ValueError, match="outside"):
            r2.delete_prefix(bad)


def test_delete_prefix_batches(store: tuple[R2Store, Any]) -> None:
    r2, client = store
    for i in range(1005):
        client.put_object(Bucket=BUCKET, Key=f"pdfapp/2020010100/u/in/{i:04d}", Body=b"")
    client.put_object(Bucket=BUCKET, Key="pdfapp/2020010100/v/in/000", Body=b"")
    assert r2.delete_prefix("pdfapp/2020010100/u/") == 1005
    assert _keys(client) == {"pdfapp/2020010100/v/in/000"}


def test_key_layout_has_no_user_data() -> None:
    from pdfapp.backend.app.core.upload_ids import new_upload_id

    upload = new_upload_id(1_700_000_000, 2)
    layout = UploadKeys.for_upload("pdfapp", upload)
    assert layout.input(1) == f"pdfapp/2023111422/{upload.value}/in/001"
    assert layout.output("pdf") == f"pdfapp/2023111422/{upload.value}/out/result.pdf"


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("remove-pages-result.pdf", "remove-pages-result.pdf"),
        ('a"b\r\n.pdf', "a_b__.pdf"),
        ("", "result"),
    ],
)
def test_safe_filename(name: str, expected: str) -> None:
    assert safe_filename(name) == expected


# ------------------------------------------------------------------ fix round
class _FakeS3:
    """Minimal client double: a fixed listing and a scripted delete_objects response."""

    def __init__(self, listing: list[str], delete_response: dict[str, Any]) -> None:
        self.listing = listing
        self.delete_response = delete_response
        self.delete_calls = 0

    def list_objects_v2(self, **kwargs: Any) -> dict[str, Any]:
        if kwargs.get("Delimiter"):
            return {"CommonPrefixes": [{"Prefix": "pdfapp/2020010100/"}]}
        return {"Contents": [{"Key": k} for k in self.listing]}

    def delete_objects(self, **_: Any) -> dict[str, Any]:
        self.delete_calls += 1
        return self.delete_response


def _cfg() -> R2Config:
    return R2Config(
        access_key_id="testing",
        secret_access_key=SecretStr("testing"),
        bucket=BUCKET,
        endpoint="https://unused.invalid",
        prefix="pdfapp",
        presign_expires=900,
    )


def test_quiet_delete_errors_raise() -> None:
    from pdfapp.backend.app.storage.r2 import R2Unavailable

    fake = _FakeS3(
        ["pdfapp/2020010100/u/in/000"], {"Errors": [{"Key": "x", "Code": "AccessDenied"}]}
    )
    store = R2Store(_cfg(), client=fake)
    with pytest.raises(R2Unavailable, match="DeleteFailed"):
        store.delete_keys(["pdfapp/2020010100/u/in/000"])
    with pytest.raises(R2Unavailable, match="DeleteFailed"):
        store.delete_prefix("pdfapp/2020010100/u/")


def test_delete_prefix_detects_no_progress() -> None:
    from pdfapp.backend.app.storage.r2 import R2Unavailable

    fake = _FakeS3(["pdfapp/2020010100/u/in/000"], {})  # "succeeds" but objects stay
    with pytest.raises(R2Unavailable, match="DeleteFailed"):
        R2Store(_cfg(), client=fake).delete_prefix("pdfapp/2020010100/u/")
    assert fake.delete_calls == 1


def test_sweep_stops_without_progress() -> None:
    fake = _FakeS3(["pdfapp/2020010100/u/in/000"], {})
    store = R2Store(_cfg(), client=fake)
    assert store.sweep_stale(now=int(time.time()), min_age_seconds=3600, time_budget=5) == 1
    assert fake.delete_calls == 1  # second identical page => stop, no busy loop


def test_lock_is_one_shot(store: tuple[R2Store, Any]) -> None:
    r2, client = store
    assert r2.create_once("pdfapp/2020010100/u/run.lock") is True
    assert r2.create_once("pdfapp/2020010100/u/run.lock") is False
    r2.delete_prefix("pdfapp/2020010100/u/")
    assert _keys(client) == set()


def test_download_bytes_caps(store: tuple[R2Store, Any]) -> None:
    from pdfapp.backend.app.storage.r2 import ObjectTooLarge

    r2, client = store
    client.put_object(Bucket=BUCKET, Key="pdfapp/k", Body=b"x" * 3000)
    assert r2.download_bytes("pdfapp/k", 3000) == b"x" * 3000
    with pytest.raises(ObjectTooLarge):
        r2.download_bytes("pdfapp/k", 2999)
    with pytest.raises(FileNotFoundError):
        r2.download_bytes("pdfapp/missing", 10)


@pytest.mark.parametrize("env", ["dev", "prod"])
@pytest.mark.parametrize(
    "endpoint",
    [
        "https://evil.example.com",
        "https://abc.r2.cloudflarestorage.com:8443",
        "https://user:pw@abc.r2.cloudflarestorage.com",
        "http://127.0.0.1:9000",
        "https://abc.r2.cloudflarestorage.com.evil.com",
    ],
)
def test_deployed_endpoint_must_be_r2(
    monkeypatch: pytest.MonkeyPatch, env: str, endpoint: str
) -> None:
    monkeypatch.setenv("APP_ENVIRONMENT", env)
    monkeypatch.setenv("R2_ENDPOINT", endpoint)
    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://abc123.r2.cloudflarestorage.com",
        "https://abc123.eu.r2.cloudflarestorage.com",
        "https://abc123.fedramp.r2.cloudflarestorage.com",
    ],
)
def test_deployed_endpoint_r2_hosts_ok(monkeypatch: pytest.MonkeyPatch, endpoint: str) -> None:
    monkeypatch.setenv("APP_ENVIRONMENT", "prod")
    monkeypatch.setenv("R2_ENDPOINT", endpoint)
    assert Settings().r2_endpoint == endpoint


def test_local_allows_loopback_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENVIRONMENT", "local")
    monkeypatch.setenv("R2_ENDPOINT", "http://127.0.0.1:9000")
    assert Settings().r2_endpoint == "http://127.0.0.1:9000"


@pytest.mark.parametrize(("prefix", "ok"), [("pdfapp", True), ("pdfapp/x", True), ("other", False)])
def test_prod_prefix_rule(monkeypatch: pytest.MonkeyPatch, prefix: str, ok: bool) -> None:
    monkeypatch.setenv("APP_ENVIRONMENT", "prod")
    monkeypatch.setenv("R2_PREFIX", prefix)
    if ok:
        assert Settings().r2_prefix == prefix
    else:
        with pytest.raises(ValidationError):
            Settings()


# ------------------------------------------------------------------ hardening round
@pytest.mark.parametrize(
    ("env", "prefix", "ok"),
    [
        ("dev", "other", False),
        ("dev", "pdfapp-evil", False),
        ("dev", "pdfapp/sub", True),
        ("prod", "other", False),
        ("prod", "pdfapp", True),
        ("local", "other", True),  # local/test may point at a private dev bucket
        ("local", "pdfapp", True),
        ("test", "other", True),
    ],
)
def test_prefix_pinned_everywhere(
    monkeypatch: pytest.MonkeyPatch, env: str, prefix: str, ok: bool
) -> None:
    monkeypatch.setenv("APP_ENVIRONMENT", env)
    monkeypatch.setenv("R2_PREFIX", prefix)
    if ok:
        assert Settings().r2_prefix == prefix
    else:
        with pytest.raises(ValidationError):
            Settings()


def test_prefix_pin_applies_with_default_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_ENVIRONMENT", raising=False)
    monkeypatch.setenv("R2_PREFIX", "other")
    with pytest.raises(ValidationError):
        Settings()


class _PrefixIgnoringS3(_FakeS3):
    """A listing that ignores Prefix and returns another product's keys too."""

    def list_objects_v2(self, **kwargs: Any) -> dict[str, Any]:
        if kwargs.get("Delimiter"):
            return {"CommonPrefixes": [{"Prefix": "pdfapp/2020010100/"}]}
        return {"Contents": [{"Key": k} for k in self.listing]}


@pytest.mark.parametrize(
    "foreign", ["other-product/prod/db.dump", "pdfapp/2020010101/u/in/000", "pdfapp-x/a"]
)
def test_deletes_refuse_keys_outside_scope(foreign: str) -> None:
    from pdfapp.backend.app.storage.r2 import R2Unavailable

    fake = _PrefixIgnoringS3(["pdfapp/2020010100/u/in/000", foreign], {})
    store = R2Store(_cfg(), client=fake)
    with pytest.raises(R2Unavailable, match="PrefixViolation"):
        store.delete_prefix("pdfapp/2020010100/u/")
    with pytest.raises(R2Unavailable, match="PrefixViolation"):
        store.delete_keys(["pdfapp/2020010100/u/in/000", foreign], within="pdfapp/2020010100/u/")
    # The sweep swallows the error and deletes nothing.
    assert store.sweep_stale(now=int(time.time()), min_age_seconds=3600, time_budget=2) == 0
    assert fake.delete_calls == 0


def test_delete_keys_defaults_to_configured_prefix() -> None:
    from pdfapp.backend.app.storage.r2 import R2Unavailable

    fake = _FakeS3([], {})
    with pytest.raises(R2Unavailable, match="PrefixViolation"):
        R2Store(_cfg(), client=fake).delete_keys(["elsewhere/x"])
    assert fake.delete_calls == 0


def test_hour_dir_regex_is_ascii_only() -> None:
    from pdfapp.backend.app.storage.r2 import _HOUR_DIR_RE

    assert _HOUR_DIR_RE.fullmatch("2026110412")
    fullwidth = "".join(chr(0xFF10 + int(c)) for c in "2026110412")
    arabic_indic = "".join(chr(0x0660 + int(c)) for c in "2026110412")
    assert not _HOUR_DIR_RE.fullmatch(fullwidth)  # \d would accept these
    assert not _HOUR_DIR_RE.fullmatch(arabic_indic)
