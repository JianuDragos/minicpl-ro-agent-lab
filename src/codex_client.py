"""Codex CLI client for true dual-agent debate runs."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CodexResult:
    response: str
    ok: bool
    command: list[str]
    output_path: Path
    stdout: str = ""
    stderr: str = ""
    error: str | None = None


class CodexClient:
    def __init__(
        self,
        root: Path,
        executable: str = "codex",
        timeout_seconds: int = 600,
    ) -> None:
        self.root = root
        self.executable = executable
        self.timeout_seconds = timeout_seconds

    def exec(self, prompt: str, output_path: Path) -> CodexResult:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        primary = [
            self.executable,
            "exec",
            "--sandbox",
            "workspace-write",
            "--ask-for-approval",
            "on-request",
            "--output-last-message",
            str(output_path),
            "--cd",
            str(self.root),
            "-",
        ]
        result = self._run(primary, prompt, output_path)
        if result.ok or not self._looks_like_unsupported_approval_flag(result):
            return result

        fallback = [
            self.executable,
            "exec",
            "--sandbox",
            "workspace-write",
            "-c",
            'approval_policy="on-request"',
            "--output-last-message",
            str(output_path),
            "--cd",
            str(self.root),
            "-",
        ]
        return self._run(fallback, prompt, output_path)

    def _run(self, command: list[str], prompt: str, output_path: Path) -> CodexResult:
        try:
            completed = subprocess.run(
                command,
                input=prompt,
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return CodexResult(
                response="",
                ok=False,
                command=command,
                output_path=output_path,
                error=str(exc),
            )

        response = ""
        if output_path.exists():
            response = output_path.read_text(encoding="utf-8", errors="replace").strip()
        if not response:
            response = completed.stdout.strip()

        return CodexResult(
            response=response,
            ok=completed.returncode == 0 and bool(response),
            command=command,
            output_path=output_path,
            stdout=completed.stdout,
            stderr=completed.stderr,
            error=None if completed.returncode == 0 else completed.stderr.strip(),
        )

    def _looks_like_unsupported_approval_flag(self, result: CodexResult) -> bool:
        text = f"{result.stderr}\n{result.stdout}\n{result.error or ''}".lower()
        return "--ask-for-approval" in text or "unexpected argument" in text
