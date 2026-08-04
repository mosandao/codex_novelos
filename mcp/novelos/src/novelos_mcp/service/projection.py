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


class ProjectionMixin:

    def get_projection_snapshot(
        self, project_id: str, include_candidates: bool = True, include_all_outputs: bool = True
    ) -> dict[str, Any]:
        with self.database.read() as connection:
            # 显式开启只读事务以获得快照隔离：整个读取期间所有 SELECT
            # 看到事务开始时的数据库快照，并发写不会穿插进来造成混合版本。
            connection.execute("BEGIN")
            try:
                return self._read_projection_snapshot(
                    connection, project_id, include_candidates=include_candidates, include_all_outputs=include_all_outputs
                )
            finally:
                connection.rollback()

    def render_project_projection(
        self,
        project_id: str,
        output_root: str = "novels",
        include_candidates: bool = True,
        include_all_outputs: bool = True,
    ) -> dict[str, Any]:
        from novelos_mcp.projection import ProjectionEngine

        engine = ProjectionEngine(root_dir=output_root)
        return engine.render(
            self,
            project_id,
            include_candidates=include_candidates,
            include_all_outputs=include_all_outputs,
        )

    def verify_project_projection(self, project_directory: str) -> dict[str, Any]:
        """逐文件校验已生成的投影目录，校验其 manifest 中记录的内容 Hash 与来源 Hash。"""
        from novelos_mcp.projection import ProjectionEngine

        return ProjectionEngine.verify_manifest(project_directory)
