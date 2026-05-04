from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path


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


@dataclass(frozen=True)
class LLMSettings:
    mode: str
    model: str | None = None
    endpoint: str = "https://api.openai.com/v1/responses"
    timeout: int = 60
    api_key: str | None = None
    api_key_env: str = "OPENAI_API_KEY"
    codex_command: str = "codex"
    codex_profile: str | None = None


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

    @classmethod
    def from_settings(cls, settings: LLMSettings, model: str | None = None) -> "OpenAIResponsesClient":
        api_key = settings.api_key or os.getenv(settings.api_key_env) or os.getenv("SPECGUARD_LLM_API_KEY")
        if not api_key:
            raise LLMConfigError(
                f"Missing OpenAI API key. Set {settings.api_key_env}, run specguard auth setup --mode openai, "
                "or use local Codex mode."
            )

        resolved_model = model or settings.model or os.getenv("SPECGUARD_LLM_MODEL") or "gpt-5.1"
        endpoint = os.getenv("SPECGUARD_LLM_ENDPOINT") or settings.endpoint
        timeout = int(os.getenv("SPECGUARD_LLM_TIMEOUT", str(settings.timeout)))
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


class CodexExecClient:
    def __init__(self, settings: LLMSettings, root: Path, model: str | None = None) -> None:
        self.settings = settings
        self.root = root
        self.model = model or settings.model
        self.command = _resolve_codex_command(settings.codex_command)
        if not self.command:
            raise LLMConfigError("Local Codex CLI was not found. Install Codex or choose OpenAI Platform mode.")

    def _base_command(self) -> list[str]:
        command = [
            self.command,
            "exec",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            "--color",
            "never",
        ]
        if self.model:
            command.extend(["--model", self.model])
        if self.settings.codex_profile:
            command.extend(["--profile", self.settings.codex_profile])
        return command

    def generate_text(self, instructions: str, input_text: str, max_output_tokens: int = 2500) -> str:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as output_file:
            output_path = Path(output_file.name)

        command = self._base_command() + ["--output-last-message", str(output_path), "-"]
        prompt = _build_prompt(instructions, input_text, max_output_tokens)
        try:
            completed = subprocess.run(
                command,
                input=prompt,
                text=True,
                capture_output=True,
                cwd=self.root,
                timeout=self.settings.timeout,
            )
            if completed.returncode != 0:
                message = (completed.stderr or completed.stdout or "unknown Codex error").strip()
                raise LLMRequestError(f"Codex request failed: {message}")
            text = output_path.read_text(encoding="utf-8").strip() if output_path.exists() else ""
            if not text:
                text = completed.stdout.strip()
            if not text:
                raise LLMRequestError("Codex response did not contain text output.")
            return text
        except subprocess.TimeoutExpired as exc:
            raise LLMRequestError("Codex request timed out.") from exc
        finally:
            output_path.unlink(missing_ok=True)

    def stream_text(self, instructions: str, input_text: str, max_output_tokens: int = 2500) -> Iterator[str]:
        command = self._base_command() + ["--json", "-"]
        prompt = _build_prompt(instructions, input_text, max_output_tokens)
        emitted = False
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=self.root,
            )
            assert process.stdin is not None
            assert process.stdout is not None
            process.stdin.write(prompt)
            process.stdin.close()

            for line in process.stdout:
                delta = _extract_codex_event_text(line, delta_only=True)
                if delta:
                    emitted = True
                    yield delta

            stderr = process.stderr.read() if process.stderr else ""
            return_code = process.wait(timeout=self.settings.timeout)
            if return_code != 0:
                raise LLMRequestError(f"Codex stream failed: {stderr.strip() or 'unknown Codex error'}")
        except subprocess.TimeoutExpired as exc:
            process.kill()
            raise LLMRequestError("Codex stream timed out.") from exc

        if not emitted:
            text = self.generate_text(instructions, input_text, max_output_tokens=max_output_tokens)
            yield text


def config_path(root: Path) -> Path:
    return root / ".specguard" / "config.json"


def load_llm_settings(root: Path) -> LLMSettings | None:
    path = config_path(root)
    data: dict[str, object] = {}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise LLMConfigError(f"Invalid SpecGuard LLM config: {path}") from exc
        if isinstance(loaded, dict):
            llm = loaded.get("llm", loaded)
            data = llm if isinstance(llm, dict) else {}

    mode = str(os.getenv("SPECGUARD_LLM_MODE") or data.get("mode") or "").strip().lower()
    if not mode:
        if os.getenv("OPENAI_API_KEY") or os.getenv("SPECGUARD_LLM_API_KEY"):
            mode = "openai"
        else:
            return None

    return LLMSettings(
        mode=mode,
        model=_optional_string(os.getenv("SPECGUARD_LLM_MODEL") or data.get("model")),
        endpoint=str(os.getenv("SPECGUARD_LLM_ENDPOINT") or data.get("endpoint") or "https://api.openai.com/v1/responses"),
        timeout=int(os.getenv("SPECGUARD_LLM_TIMEOUT") or data.get("timeout") or 60),
        api_key=_optional_string(data.get("api_key")),
        api_key_env=str(data.get("api_key_env") or "OPENAI_API_KEY"),
        codex_command=str(os.getenv("SPECGUARD_CODEX_COMMAND") or data.get("codex_command") or "codex"),
        codex_profile=_optional_string(data.get("codex_profile")),
    )


def save_llm_settings(root: Path, settings: LLMSettings) -> Path:
    path = config_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"llm": _settings_to_json(settings)}, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def clear_llm_settings(root: Path) -> bool:
    path = config_path(root)
    if not path.exists():
        return False
    path.unlink()
    return True


def build_llm_client(root: Path, mode: str | None = None, model: str | None = None) -> object:
    settings = load_llm_settings(root)
    if mode:
        base = settings or LLMSettings(mode=mode)
        settings = LLMSettings(
            mode=mode,
            model=model or base.model,
            endpoint=base.endpoint,
            timeout=base.timeout,
            api_key=base.api_key,
            api_key_env=base.api_key_env,
            codex_command=base.codex_command,
            codex_profile=base.codex_profile,
        )
    if settings is None:
        raise LLMConfigError("No LLM provider is configured.")

    if model:
        settings = LLMSettings(
            mode=settings.mode,
            model=model,
            endpoint=settings.endpoint,
            timeout=settings.timeout,
            api_key=settings.api_key,
            api_key_env=settings.api_key_env,
            codex_command=settings.codex_command,
            codex_profile=settings.codex_profile,
        )

    if settings.mode == "openai":
        return OpenAIResponsesClient.from_settings(settings, model=model)
    if settings.mode == "codex":
        return CodexExecClient(settings, root=root, model=model)
    raise LLMConfigError(f"Unsupported LLM mode: {settings.mode}. Use codex or openai.")


def codex_available(command: str = "codex") -> bool:
    return _resolve_codex_command(command) is not None


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


def _build_prompt(instructions: str, input_text: str, max_output_tokens: int) -> str:
    return "\n\n".join([
        instructions.strip(),
        f"Maximum output tokens: {max_output_tokens}",
        "# Input",
        input_text.strip(),
    ]).strip()


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _settings_to_json(settings: LLMSettings) -> dict[str, object]:
    data: dict[str, object] = {
        "mode": settings.mode,
        "model": settings.model,
        "timeout": settings.timeout,
    }
    if settings.mode == "openai":
        data.update({
            "endpoint": settings.endpoint,
            "api_key_env": settings.api_key_env,
        })
        if settings.api_key:
            data["api_key"] = settings.api_key
    if settings.mode == "codex":
        data.update({
            "codex_command": settings.codex_command,
            "codex_profile": settings.codex_profile,
        })
    return {key: value for key, value in data.items() if value is not None}


def _resolve_codex_command(command: str) -> str | None:
    return shutil.which(command) or shutil.which(f"{command}.cmd")


def _extract_codex_event_text(line: str, delta_only: bool = False) -> str:
    stripped = line.strip()
    if not stripped:
        return ""
    try:
        event = json.loads(stripped)
    except json.JSONDecodeError:
        return ""
    if not isinstance(event, dict):
        return ""
    return _extract_text_from_event(event, delta_only=delta_only)


def _extract_text_from_event(event: object, delta_only: bool = False) -> str:
    if isinstance(event, str):
        return "" if delta_only else event
    if isinstance(event, list):
        return "".join(_extract_text_from_event(item, delta_only=delta_only) for item in event)
    if not isinstance(event, dict):
        return ""

    event_type = str(event.get("type") or "")
    if "delta" in event_type:
        for key in ("delta", "text", "content", "message"):
            value = event.get(key)
            if isinstance(value, str):
                return value

    if delta_only:
        for key in ("event", "data", "payload"):
            text = _extract_text_from_event(event.get(key), delta_only=True)
            if text:
                return text
        return ""

    if event_type in {"agent_message", "assistant_message", "final_answer", "message"}:
        for key in ("text", "content", "message"):
            value = event.get(key)
            text = _extract_text_from_event(value, delta_only=False)
            if text:
                return text

    for key in ("event", "data", "payload"):
        text = _extract_text_from_event(event.get(key), delta_only=False)
        if text:
            return text
    return ""
