from __future__ import annotations

from novelos.domain import Chapter, ContextPacket, ContinuationRequest
from novelos.ports import TextModel


class WritingSkill:
    SYSTEM_PROMPT = (
        "You are a professional fiction writer. Treat the context packet as canon. "
        "Write only the requested chapter body, without commentary or review notes."
    )

    def __init__(self, model: TextModel) -> None:
        self.model = model

    def draft(self, request: ContinuationRequest, context: ContextPacket) -> Chapter:
        prompt = (
            f"CHAPTER: {request.chapter_number}\n"
            f"TITLE: {request.title or 'Untitled'}\n"
            f"GOAL: {request.goal}\n"
            f"POINT OF VIEW: {request.point_of_view or 'Follow established style'}\n"
            f"TONE: {request.tone or 'Follow established style'}\n"
            f"TARGET WORDS: {request.target_words}\n\n"
            f"CONTEXT PACKET\n{context.to_prompt()}"
        )
        content = self.model.complete(self.SYSTEM_PROMPT, prompt).strip()
        title = request.title or f"Chapter {request.chapter_number}"
        return Chapter(request.chapter_number, title, content)

