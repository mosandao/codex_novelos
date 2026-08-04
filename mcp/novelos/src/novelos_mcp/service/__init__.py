from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import re
import shutil
import sqlite3
import uuid
import yaml
from types import MappingProxyType
from pathlib import Path
from typing import Any, Iterable

from novelos_mcp.agent_contracts import AgentContractStore
from novelos_mcp.errors import NovelOSError
from novelos_mcp.catalog import CatalogStore
from novelos_mcp.creative_contracts import (
    CreativeContractStore,
    creator_signature_ref,
    planning_constraint_ref,
)
from novelos_mcp.hashing import content_hash
from novelos_mcp.knowledge import KnowledgeStore
from novelos_mcp.storage import Database
from novelos_mcp.system_archetypes import (
    load_system_archetypes_config,
    sync_system_archetypes_to_db,
)
from novelos_mcp.archetype_recommendation import (
    recommend_archetypes,
    generate_derivation_draft,
)

from ._constants import (
    CONTINUITY_OWNERS,
    ENTITY_AUTHORITY_ASSETS,
    PLANNING_PRODUCERS,
    PLANNING_UPSTREAM_TYPES,
)
from ._helpers import _id, _json, _require_sha256, _require_text

# Deprecated compatibility snapshot. Runtime services always query their own AgentContractStore.
PLANNING_REVIEW_PROFILES = MappingProxyType(AgentContractStore().planning_review_profiles())


from ._internals import _ServiceInternals
from .agents import AgentsMixin
from .chapters import ChaptersMixin
from .creators import CreatorsMixin
from .memory import MemoryMixin
from .planning import PlanningMixin
from .projects import ProjectsMixin
from .projection import ProjectionMixin
from .reviews import ReviewsMixin


class NovelOSService(
    _ServiceInternals,
    ProjectsMixin,
    CreatorsMixin,
    PlanningMixin,
    ChaptersMixin,
    ReviewsMixin,
    AgentsMixin,
    MemoryMixin,
    ProjectionMixin,
):
    def __init__(
        self,
        database_path: str | Path,
        seed_database_path: str | Path | None = None,
        catalog_path: str | Path | None = None,
        agent_contract_path: str | Path | None = None,
        seed_inventory_path: str | Path | None = None,
    ) -> None:
        self.database = Database(database_path)
        self.database.initialize()
        self.knowledge = KnowledgeStore(seed_database_path, seed_inventory_path)
        self.catalog = CatalogStore(catalog_path)
        self.agent_contracts = AgentContractStore(agent_contract_path)
        self.creative_contracts = CreativeContractStore()
        self.system_archetypes = load_system_archetypes_config()
        with self.database.transaction() as connection:
            sync_system_archetypes_to_db(connection, self.system_archetypes)


__all__ = [
    "NovelOSService",
    "CONTINUITY_OWNERS",
    "ENTITY_AUTHORITY_ASSETS",
    "PLANNING_PRODUCERS",
    "PLANNING_REVIEW_PROFILES",
    "PLANNING_UPSTREAM_TYPES",
]
