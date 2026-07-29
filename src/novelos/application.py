from __future__ import annotations

from novelos.agents import MainAgent
from novelos.config import Settings
from novelos.mcp import InProcessMemoryGateway, MemoryMCPService
from novelos.models import LocalDemoModel, OpenAIResponsesModel
from novelos.skills import MemorySkill, ReviewSkill, WritingSkill


def build_main_agent(settings: Settings) -> MainAgent:
    service = MemoryMCPService(settings.database_path)
    gateway = InProcessMemoryGateway(service)
    gateway.initialize()
    if settings.model_provider == "local":
        model = LocalDemoModel()
    elif settings.model_provider == "openai":
        model = OpenAIResponsesModel()
    else:
        raise ValueError(f"Unsupported model provider: {settings.model_provider}")
    return MainAgent(
        gateway=gateway,
        memory_skill=MemorySkill(gateway, settings.context_chapter_limit),
        writing_skill=WritingSkill(model),
        review_skill=ReviewSkill(model),
        spawn_context_builder_after=settings.spawn_context_builder_after,
    )

