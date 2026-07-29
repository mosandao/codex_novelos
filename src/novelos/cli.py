from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

from novelos.application import build_main_agent
from novelos.config import Settings
from novelos.domain import Chapter, ContinuationRequest, Entity
from novelos.mcp import InProcessMemoryGateway, MemoryMCPService


def _gateway(settings: Settings) -> InProcessMemoryGateway:
    gateway = InProcessMemoryGateway(MemoryMCPService(settings.database_path))
    gateway.initialize()
    return gateway


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="novelos")
    parser.add_argument("--config", help="TOML configuration file")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("init", help="Initialize storage")

    chapter = commands.add_parser("add-chapter", help="Store a canonical chapter")
    chapter.add_argument("number", type=int)
    chapter.add_argument("title")
    chapter.add_argument("content_file", type=Path)
    chapter.add_argument("--summary", default="")

    entity = commands.add_parser("add-entity", help="Store canonical entity state")
    entity.add_argument("kind")
    entity.add_argument("name")
    entity.add_argument("description")
    entity.add_argument("--state", default="{}", help="JSON object")

    memory = commands.add_parser("add-memory", help="Store a plot fact or thread")
    memory.add_argument("category")
    memory.add_argument("label")
    memory.add_argument("content")
    memory.add_argument("--chapter", type=int)

    context = commands.add_parser("context", help="Build a context packet")
    context.add_argument("topic")

    continuation = commands.add_parser("continue", help="Draft, review, and save a chapter")
    continuation.add_argument("number", type=int)
    continuation.add_argument("goal")
    continuation.add_argument("--title", default="")
    continuation.add_argument("--pov", default="")
    continuation.add_argument("--tone", default="")
    continuation.add_argument("--words", type=int, default=2000)
    continuation.add_argument("--direct-review", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    settings = Settings.from_file(args.config)
    gateway = _gateway(settings)

    if args.command == "init":
        print(json.dumps({"initialized": True, "database": settings.database_path}))
        return
    if args.command == "add-chapter":
        gateway.save_chapter(
            Chapter(args.number, args.title, args.content_file.read_text(), args.summary)
        )
        print(json.dumps({"saved": True, "chapter": args.number}))
        return
    if args.command == "add-entity":
        state = json.loads(args.state)
        if not isinstance(state, dict):
            raise ValueError("--state must be a JSON object")
        gateway.upsert_entity(Entity(args.kind, args.name, args.description, state))
        print(json.dumps({"saved": True, "entity": args.name}, ensure_ascii=False))
        return
    if args.command == "add-memory":
        memory_id = gateway.add_memory(
            args.category, args.label, args.content, args.chapter
        )
        print(json.dumps({"saved": True, "memory_id": memory_id}))
        return
    if args.command == "context":
        agent = build_main_agent(settings)
        packet = agent.memory_skill.build_context(args.topic)
        print(packet.to_prompt())
        return
    if args.command == "continue":
        agent = build_main_agent(settings)
        result = agent.continue_chapter(
            ContinuationRequest(
                chapter_number=args.number,
                goal=args.goal,
                title=args.title,
                point_of_view=args.pov,
                tone=args.tone,
                target_words=args.words,
                deep_review=not args.direct_review,
            )
        )
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

