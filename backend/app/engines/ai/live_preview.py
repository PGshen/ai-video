import re
import shutil
import sys
import time
import unicodedata
import uuid
from collections import deque
from typing import TextIO


_ANSI_ESCAPE = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def _clean(value: object) -> str:
    """Keep model-controlled text from emitting terminal control sequences."""
    return _ANSI_ESCAPE.sub("", str(value)).replace("\r", "")


def _display_width(value: str) -> int:
    width = 0
    for char in value:
        if unicodedata.combining(char):
            continue
        width += 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1
    return width


def _clip_head(value: str, width: int) -> str:
    result: list[str] = []
    used = 0
    for char in value:
        char_width = _display_width(char)
        if used + char_width > width:
            break
        result.append(char)
        used += char_width
    return "".join(result)


def _clip_tail(value: str, width: int) -> str:
    result: list[str] = []
    used = 0
    for char in reversed(value):
        char_width = _display_width(char)
        if used + char_width > width:
            break
        result.append(char)
        used += char_width
    return "".join(reversed(result))


class LiveLLMPreview:
    """Render one LLM request in a fixed five-line stdout viewport.

    The response viewport is redrawn with a carriage return as tokens arrive.
    This remains safe when application loggers write to the same terminal and
    emits at most four newline-delimited rows per request.
    """

    max_lines = 5
    response_lines = 3

    def __init__(
        self,
        *,
        provider: str,
        model: str,
        messages: list[dict],
        stream: TextIO | None = None,
    ) -> None:
        self.stream = stream or sys.stdout
        self.provider = provider
        self.model = model
        self.request_id = uuid.uuid4().hex[:8]
        self.started = time.monotonic()
        self._last_rendered_at = 0.0
        self._closed = False
        self._width = max(
            40,
            min(shutil.get_terminal_size(fallback=(120, 24)).columns, 160),
        )
        self._rows: deque[str] = deque([""], maxlen=self.response_lines)
        self._request_preview = self._format_request(messages)
        self._render("connecting", force=True, initial=True)

    def _format_request(self, messages: list[dict]) -> str:
        content = " | ".join(
            f"{message.get('role', '?')}: {_clean(message.get('content', ''))}"
            for message in messages
        ).replace("\n", " ↵ ")
        available = max(8, self._width - _display_width("request: "))
        if _display_width(content) > available:
            content = "…" + _clip_tail(content, available - 1)
        return content

    def append(self, content: str) -> None:
        if self._closed or not content:
            return
        row_width = max(8, self._width - _display_width("response: "))
        for char in _clean(content):
            if char == "\n":
                self._rows.append("")
                continue
            current = self._rows[-1]
            if _display_width(current) + _display_width(char) > row_width:
                self._rows.append(char)
            else:
                self._rows[-1] = current + char
        self._render("streaming")

    def finish(self, *, chunks: int, content_len: int) -> None:
        elapsed = time.monotonic() - self.started
        self._render(
            f"done {elapsed:.2f}s chunks={chunks} chars={content_len}",
            force=True,
        )
        self._close()

    def fail(self, error: BaseException) -> None:
        elapsed = time.monotonic() - self.started
        message = _clean(error).replace("\n", " ")
        available = max(8, self._width - 30)
        if _display_width(message) > available:
            message = _clip_head(message, available - 1) + "…"
        self._render(
            f"failed {elapsed:.2f}s {type(error).__name__}: {message}",
            force=True,
        )
        self._close()

    def _render(self, status: str, *, force: bool = False, initial: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._last_rendered_at < 0.08:
            return
        self._last_rendered_at = now
        header = _clip_head(
            f"[LLM {self.request_id}] {self.provider}/{self.model} {status}",
            self._width,
        )
        request = _clip_head(
            f"request: {self._request_preview}",
            self._width,
        )
        rows = list(self._rows)[-self.response_lines :]
        rows = ["response: " + row for row in rows]
        rows.extend(["response: "] * (self.response_lines - len(rows)))

        if initial:
            self.stream.write(f"{header}\n{request}\nresponse: ")
        else:
            tail = " ↵ ".join(row.removeprefix("response: ") for row in rows)
            line = _clip_head(f"response: {tail}", self._width)
            padding = " " * max(0, self._width - _display_width(line))
            self.stream.write(f"\r{line}{padding}")
            if force and not initial:
                self.stream.write(f"\n{header}\n")
        self.stream.flush()

    def _close(self) -> None:
        if self._closed:
            return
        self._closed = True
