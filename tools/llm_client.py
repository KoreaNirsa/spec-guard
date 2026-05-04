from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Iterable, Iterator
from dataclasses import dataclass


class LLMConfigError(RuntimeError):
    pass


class LLMRequestError(RuntimeError):
    pass


@dataclass(frozen=True)
class LLMConfig:
    api_key: str
    model: str
    endpoint: str
    timeout: int


class OpenAIResponsesClient:
    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    @classmethod
    def from_env(cls, model: str | None = None) -> "OpenAIResponsesClient":
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("SPECGUARD_LLM_API_KEY")
        if not api_key:
            raise LLMConfigError("Missing OPENAI_API_KEY or SPECGUARD_LLM_API_KEY for --llm mode.")

        resolved_model = model or os.getenv("SPECGUARD_LLM_MODEL") or "gpt-5.1"
        endpoint = os.getenv("SPECGUARD_LLM_ENDPOINT") or "https://api.openai.com/v1/responses"
        timeout = int(os.getenv("SPECGUARD_LLM_TIMEOUT", "60"))
        return cls(LLMConfig(api_key=api_key, model=resolved_model, endpoint=endpoint, timeout=timeout))

    def generate_text(self, instructions: str, input_text: str, max_output_tokens: int = 2500) -> str:
        payload = {
            "model": self.config.model,
            "instructions": instructions,
            "input": input_text,
            "max_output_tokens": max_output_tokens,
        }
        request = urllib.request.Request(
            self.config.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise LLMRequestError(f"LLM request failed with HTTP {exc.code}: {body}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise LLMRequestError(f"LLM request failed: {exc}") from exc

        text = _extract_response_text(data)
        if not text:
            raise LLMRequestError("LLM response did not contain text output.")
        return text.strip()

    def stream_text(self, instructions: str, input_text: str, max_output_tokens: int = 2500) -> Iterator[str]:
        payload = {
            "model": self.config.model,
            "instructions": instructions,
            "input": input_text,
            "max_output_tokens": max_output_tokens,
            "stream": True,
        }
        request = urllib.request.Request(
            self.config.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        emitted = False
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout) as response:
                for delta in _iter_response_text_deltas(response):
                    emitted = True
                    yield delta
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise LLMRequestError(f"LLM stream failed with HTTP {exc.code}: {body}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise LLMRequestError(f"LLM stream failed: {exc}") from exc

        if not emitted:
            raise LLMRequestError("LLM stream did not contain text output.")


def _extract_response_text(data: dict[str, object]) -> str:
    output_text = data.get("output_text")
    if isinstance(output_text, str):
        return output_text

    chunks: list[str] = []
    output = data.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, dict):
                    continue
                text = part.get("text")
                if isinstance(text, str):
                    chunks.append(text)
    return "\n".join(chunks)


def _iter_sse_events(lines: Iterable[bytes | str]) -> Iterator[tuple[str | None, str]]:
    event_type: str | None = None
    data_parts: list[str] = []

    for raw_line in lines:
        line = raw_line.decode("utf-8", errors="replace") if isinstance(raw_line, bytes) else raw_line
        line = line.rstrip("\r\n")

        if not line:
            if data_parts:
                yield event_type, "\n".join(data_parts)
            event_type = None
            data_parts = []
            continue

        if line.startswith(":"):
            continue

        field, separator, value = line.partition(":")
        if not separator:
            continue
        if value.startswith(" "):
            value = value[1:]

        if field == "event":
            event_type = value
        elif field == "data":
            data_parts.append(value)

    if data_parts:
        yield event_type, "\n".join(data_parts)


def _iter_response_text_deltas(lines: Iterable[bytes | str]) -> Iterator[str]:
    for event_type, data in _iter_sse_events(lines):
        if data == "[DONE]":
            break

        try:
            event = json.loads(data)
        except json.JSONDecodeError as exc:
            raise LLMRequestError(f"LLM stream returned invalid JSON: {data}") from exc

        if not isinstance(event, dict):
            continue

        resolved_type = event.get("type") or event_type
        if resolved_type == "response.output_text.delta":
            delta = event.get("delta")
            if isinstance(delta, str):
                yield delta
            continue

        if resolved_type == "error":
            error = event.get("error")
            if isinstance(error, dict):
                message = error.get("message") or error.get("type") or "unknown error"
            else:
                message = error or "unknown error"
            raise LLMRequestError(f"LLM stream returned an error: {message}")
