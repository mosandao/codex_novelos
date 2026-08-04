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


class ProjectsMixin:

    def create_project(self, name: str, description: str = "", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        project_id = _id("project")
        with self.database.transaction() as connection:
            connection.execute(
                "INSERT INTO projects(id, name, description, metadata_json) VALUES (?, ?, ?, ?)",
                (project_id, _require_text(name, "name"), description, _json(metadata or {})),
            )
            return self._row(self._get(connection, "projects", project_id))

    def get_project(self, project_id: str) -> dict[str, Any]:
        with self.database.read() as connection:
            return self._row(self._get(connection, "projects", project_id))

    def list_projects(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        self._validate_page(limit, offset)
        with self.database.read() as connection:
            rows = connection.execute("SELECT * FROM projects ORDER BY created_at, id LIMIT ? OFFSET ?", (limit, offset)).fetchall()
        return [self._row(row) for row in rows]

    def update_project(
        self,
        project_id: str,
        expected_version: int,
        name: str | None = None,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self.database.transaction() as connection:
            current = self._get(connection, "projects", project_id)
            self._check_version(current, expected_version)
            connection.execute(
                "UPDATE projects SET name=?, description=?, metadata_json=?, version=version+1, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (
                    _require_text(name, "name") if name is not None else current["name"],
                    description if description is not None else current["description"],
                    _json(metadata) if metadata is not None else current["metadata_json"],
                    project_id,
                ),
            )
            return self._row(self._get(connection, "projects", project_id))

    def delete_project(
        self,
        project_id: str,
        expected_version: int,
        output_root: str = "novels",
    ) -> dict[str, Any]:
        """删除无权威提交、无活动 Trace 的项目及其派生投影。"""
        if isinstance(expected_version, bool) or not isinstance(expected_version, int):
            raise NovelOSError("invalid_argument", "expected_version 必须是整数", {"field": "expected_version"})
        if not isinstance(output_root, str) or not output_root.strip():
            raise NovelOSError("invalid_argument", "output_root 必须是非空路径", {"field": "output_root"})

        with self.database.read() as connection:
            current = self._get(connection, "projects", project_id)
            self._check_version(current, expected_version)
            self._assert_project_deletable(connection, project_id)
            project = self._row(current)

        # 投影是可再生的派生视图，因此先在已验证归属后移除；失败时不触及权威数据。
        from novelos_mcp.projection import ProjectionEngine

        projection = ProjectionEngine(output_root).remove_project_projection(project_id, project["name"])

        with self.database.transaction() as connection:
            current = self._get(connection, "projects", project_id)
            self._check_version(current, expected_version)
            self._assert_project_deletable(connection, project_id)
            deleted = self._project_delete_counts(connection, project_id)
            connection.execute("DELETE FROM projects WHERE id=?", (project_id,))

        return {
            "id": project_id,
            "name": project["name"],
            "deleted": True,
            "deleted_records": deleted,
            "projection": projection,
        }

    def create_book(self, project_id: str, title: str, description: str = "") -> dict[str, Any]:
        return self._create_child("books", "book", "project_id", project_id, {"title": _require_text(title, "title"), "description": description})

    def get_book(self, book_id: str) -> dict[str, Any]:
        return self._get_public("books", book_id)

    def list_books(self, project_id: str) -> list[dict[str, Any]]:
        return self._list_children("books", "project_id", project_id)

    def create_volume(self, book_id: str, number: int, title: str, summary: str = "") -> dict[str, Any]:
        if number < 1:
            raise NovelOSError("invalid_argument", "number 必须大于 0", {"field": "number"})
        return self._create_child("volumes", "volume", "book_id", book_id, {"number": number, "title": _require_text(title, "title"), "summary": summary})

    def get_volume(self, volume_id: str) -> dict[str, Any]:
        return self._get_public("volumes", volume_id)

    def list_volumes(self, book_id: str) -> list[dict[str, Any]]:
        return self._list_children("volumes", "book_id", book_id, "number")
