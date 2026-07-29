from __future__ import annotations

from novelos.domain import Chapter, ContextPacket, ReviewReport
from novelos.skills import ReviewSkill


class ReviewAgent:
    """Temporary domain reasoning role for a deep chapter review."""

    def __init__(self, review_skill: ReviewSkill) -> None:
        self.review_skill = review_skill

    def review(self, chapter: Chapter, context: ContextPacket, goal: str) -> ReviewReport:
        return self.review_skill.review(chapter, context, goal)

