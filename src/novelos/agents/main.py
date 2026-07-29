from __future__ import annotations

from novelos.agents.context_builder import ContextBuilderAgent
from novelos.agents.reviewer import ReviewAgent
from novelos.agents.runtime import AgentRuntime
from novelos.domain import ContinuationRequest, ContinuationResult
from novelos.ports import MemoryGateway
from novelos.skills import MemorySkill, ReviewSkill, WritingSkill


class MainAgent:
    """The only long-lived Agent: plans, routes, and assembles results."""

    def __init__(
        self,
        gateway: MemoryGateway,
        memory_skill: MemorySkill,
        writing_skill: WritingSkill,
        review_skill: ReviewSkill,
        runtime: AgentRuntime | None = None,
        spawn_context_builder_after: int = 20,
    ) -> None:
        self.gateway = gateway
        self.memory_skill = memory_skill
        self.writing_skill = writing_skill
        self.review_skill = review_skill
        self.runtime = runtime or AgentRuntime()
        self.spawn_context_builder_after = spawn_context_builder_after

    def continue_chapter(self, request: ContinuationRequest) -> ContinuationResult:
        start_event = len(self.runtime.events)
        if self.memory_skill.chapter_count() >= self.spawn_context_builder_after:
            builder = ContextBuilderAgent(self.memory_skill)
            with self.runtime.spawn("context-builder", builder) as agent:
                context = agent.build(request.goal)
        else:
            context = self.memory_skill.build_context(request.goal)

        chapter = self.writing_skill.draft(request, context)

        if request.deep_review:
            reviewer = ReviewAgent(self.review_skill)
            with self.runtime.spawn("review", reviewer) as agent:
                review = agent.review(chapter, context, request.goal)
        else:
            review = self.review_skill.review(chapter, context, request.goal)

        saved = review.approved
        if saved:
            self.gateway.save_chapter(chapter)

        return ContinuationResult(
            chapter=chapter,
            review=review,
            saved=saved,
            runtime_events=tuple(self.runtime.events[start_event:]),
        )

