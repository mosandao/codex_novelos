from __future__ import annotations

import os


class LocalDemoModel:
    """Deterministic development model; useful for wiring checks, not production prose."""

    def complete(self, system: str, prompt: str) -> str:
        if "REVIEW_REQUEST" in prompt:
            return '{"approved": true, "findings": []}'
        goal = "Continue the story."
        for line in prompt.splitlines():
            if line.startswith("GOAL: "):
                goal = line.removeprefix("GOAL: ")
                break
        return (
            "This is a local demonstration draft.\n\n"
            f"The scene advances with this goal: {goal}\n\n"
            "Configure the OpenAI provider to generate production prose."
        )


class OpenAIResponsesModel:
    """Optional adapter for an explicitly configured OpenAI model."""

    def __init__(self, model: str | None = None) -> None:
        self.model = model or os.environ.get("OPENAI_MODEL", "")
        if not self.model:
            raise ValueError("OPENAI_MODEL must be set when provider=openai")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "OpenAI support is not installed. Run: python3 -m pip install -e '.[openai]'"
            ) from exc
        self.client = OpenAI()

    def complete(self, system: str, prompt: str) -> str:
        response = self.client.responses.create(
            model=self.model,
            instructions=system,
            input=prompt,
        )
        return response.output_text

