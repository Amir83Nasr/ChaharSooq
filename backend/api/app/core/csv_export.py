"""Streaming CSV responses for export endpoints."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Iterator, Sequence

from fastapi.responses import StreamingResponse

# Hard ceiling for one export. Counted before streaming so the client gets a
# clear error instead of a silently truncated file.
EXPORT_MAX_ROWS = 50_000

# Flush the buffer roughly every 64k characters; keeps memory flat on big
# exports without a round-trip per row.
_CHUNK_CHARS = 64_000


def _encode_rows(headers: Sequence[str], rows: Iterable[Sequence[str]]) -> Iterator[bytes]:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
        if buffer.tell() >= _CHUNK_CHARS:
            yield buffer.getvalue().encode("utf-8")
            buffer.seek(0)
            buffer.truncate(0)
    if buffer.tell():
        yield buffer.getvalue().encode("utf-8")


def csv_response(
    filename: str,
    headers: Sequence[str],
    rows: Iterable[Sequence[str]],
) -> StreamingResponse:
    """A downloadable UTF-8 CSV (with BOM) that Excel decodes correctly."""

    def body() -> Iterator[bytes]:
        # UTF-8 BOM: without it Excel opens Persian headers as mojibake.
        yield b"\xef\xbb\xbf"
        yield from _encode_rows(headers, rows)

    return StreamingResponse(
        body(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
        },
    )
