"""Simple multipart form data parser for file uploads."""

from __future__ import annotations

import re


def parse_multipart(body: bytes, content_type: str) -> dict[str, list[bytes] | str]:
    """Parse multipart form data. Returns {field_name: [file_bytes, ...] | json_string}."""
    # Extract boundary from Content-Type header
    match = re.search(r'boundary=([^\s;]+)', content_type)
    if not match:
        raise ValueError("No boundary in Content-Type")

    boundary = match.group(1).strip('"')
    if not boundary:
        raise ValueError("Empty boundary")

    # Split by boundary
    parts = body.split(f'--{boundary}'.encode())
    result: dict[str, list[bytes] | str] = {}

    for part in parts[1:-1]:  # Skip first (empty) and last (closing)
        if not part.strip():
            continue

        # Split headers from body
        header_end = part.find(b'\r\n\r\n')
        if header_end == -1:
            header_end = part.find(b'\n\n')
            if header_end == -1:
                continue
            data_start = header_end + 2
        else:
            data_start = header_end + 4

        headers = part[:header_end].decode('utf-8', errors='ignore')
        data = part[data_start:]

        # Strip trailing CRLLN
        if data.endswith(b'\r\n'):
            data = data[:-2]
        elif data.endswith(b'\n'):
            data = data[:-1]

        # Extract field name
        name_match = re.search(r'name="([^"]+)"', headers)
        if not name_match:
            continue

        field_name = name_match.group(1)

        # Check if it's a file or form field
        if 'filename=' in headers:
            # File: add to list
            if field_name not in result:
                result[field_name] = []
            files_list = result[field_name]
            if isinstance(files_list, list):
                files_list.append(data)
        else:
            # Form field: store as string
            result[field_name] = data.decode('utf-8', errors='ignore')

    return result
