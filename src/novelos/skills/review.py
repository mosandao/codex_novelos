from __future__ import annotations

import json
import re

from novelos.domain import Chapter, ContextPacket, ReviewFinding, ReviewReport
from novelos.ports import TextModel


class ReviewSkill:
    SYSTEM_PROMPT = (
        "Review fiction against supplied canon. Return JSON only with keys approved and findings. "
        "Each finding must have severity (blocking, warning, or note), message, and excerpt."
    )

    def __init__(self, model: TextModel) -> None:
        self.model = model

    def review(self, chapter: Chapter, context: ContextPacket, goal: str) -> ReviewReport:
        prompt = (
            "REVIEW_REQUEST\n"
            f"GOAL: {goal}\n\n"
            f"CONTEXT\n{context.to_prompt()}\n\n"
            f"DRAFT\n{chapter.content}"
        )
        raw = self.model.complete(self.SYSTEM_PROMPT, prompt)
        payload = self._parse_json(raw)
        findings = tuple(
            ReviewFinding(
                severity=item.get("severity", "warning"),
                message=item.get("message", "Unspecified review finding"),
                excerpt=item.get("excerpt", ""),
            )
            for item in payload.get("findings", [])
        )
        has_blocker = any(item.severity == "blocking" for item in findings)
        return ReviewReport(bool(payload.get("approved", False)) and not has_blocker, findings)

    @staticmethod
    def _parse_json(raw: str) -> dict[str, object]:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return {
                "approved": False,
                "findings": [
                    {
                        "severity": "blocking",
                        "message": "Reviewer returned invalid JSON.",
                        "excerpt": raw[:200],
                    }
                ],
            }
        try:
            value = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {
                "approved": False,
                "findings": [
                    {
                        "severity": "blocking",
                        "message": "Reviewer returned malformed JSON.",
                        "excerpt": raw[:200],
                    }
                ],
            }
        return value if isinstance(value, dict) else {"approved": False, "findings": []}

