import io

from app.engines.ai.live_preview import LiveLLMPreview


class NonTTY(io.StringIO):
    def isatty(self) -> bool:
        return False


def test_non_tty_preview_emits_at_most_five_lines_and_rolls_response():
    output = NonTTY()
    preview = LiveLLMPreview(
        provider="doubao",
        model="test-model",
        messages=[{"role": "user", "content": "request body"}],
        stream=output,
    )

    for index in range(10):
        preview.append(f"line-{index}\n")
    preview.finish(chunks=10, content_len=70)

    rendered = output.getvalue()
    assert rendered.count("\n") <= 5
    assert "request body" in rendered
    assert "line-9" in rendered
    assert "done" in rendered


def test_preview_strips_model_terminal_control_sequences():
    output = NonTTY()
    preview = LiveLLMPreview(
        provider="doubao",
        model="test-model",
        messages=[{"role": "user", "content": "\x1b[31mrequest"}],
        stream=output,
    )
    preview.append("\x1b[2Jresponse")
    preview.finish(chunks=1, content_len=8)

    rendered = output.getvalue()
    assert "\x1b[31m" not in rendered
    assert "\x1b[2J" not in rendered
