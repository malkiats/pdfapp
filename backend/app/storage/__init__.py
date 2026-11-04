"""Storage package. The only package allowed to import storage SDKs (ruff TID251).

`r2` is the Cloudflare R2 client used by the large-file flow (/api/v1/uploads).

The ADR-0002 workspace modules (`temp_manager`, `index`, `backends`) were superseded by
ADR-0006 and depend on settings groups that no longer exist; they are no longer
re-exported here so that importing `app.storage.r2` does not pull them in.
"""
