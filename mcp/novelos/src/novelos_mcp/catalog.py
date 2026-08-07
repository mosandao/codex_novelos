from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from novelos_mcp.errors import NovelOSError
from novelos_mcp.hashing import content_hash


REQUIRED_METADATA = {"name", "description", "stage", "asset", "capability", "lifecycle", "version", "output_contract"}
ALLOWED_METADATA = REQUIRED_METADATA | {
    "display_name", "pipeline", "genres", "risk", "scope", "output_contract",
    "output_schema", "use_when", "avoid_when", "context_inputs", "artifact_inputs",
    "artifact_outputs", "requires", "produces", "invariants", "tags", "priority",
}
LIFECYCLES = {"active", "experiment", "deprecated", "disabled"}
OUTPUT_CONTRACTS = {"free_text", "document", "typed_result"}
PROVENANCE_FIELDS = {
    "origin", "source_repository", "source_path", "source_commit", "source_hash", "license", "migration_note"
}
PROVENANCE_OPTIONAL_FIELDS = {"additional_sources"}
ADDITIONAL_SOURCE_FIELDS = {"source_repository", "source_path", "source_commit", "source_hash", "license"}


@dataclass(frozen=True, slots=True)
class CatalogPackage:
    root: Path
    metadata: dict[str, Any]
    provenance: dict[str, Any]
    package_hash: str

    @property
    def name(self) -> str:
        return str(self.metadata["name"])


class CatalogStore:
    def __init__(self, root: str | Path | None) -> None:
        self.root = Path(root).resolve() if root else None

    def _packages(self) -> dict[str, CatalogPackage]:
        if self.root is None or not self.root.is_dir():
            raise NovelOSError("catalog_unavailable", "未配置可用的 Skill Catalog")
        packages: dict[str, CatalogPackage] = {}
        for metadata_path in sorted(self.root.rglob("metadata.yaml")):
            try:
                metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
                provenance_path = metadata_path.parent / "provenance.yaml"
                provenance = yaml.safe_load(provenance_path.read_text(encoding="utf-8"))
            except FileNotFoundError as exc:
                raise NovelOSError("invalid_catalog", "Catalog 包缺少 provenance.yaml", {"path": str(metadata_path.parent)}) from exc
            except yaml.YAMLError as exc:
                raise NovelOSError("invalid_catalog", "Catalog YAML 解析失败", {"path": str(metadata_path.parent)}) from exc
            self._validate_metadata(metadata, metadata_path)
            self._validate_provenance(provenance, provenance_path)
            if metadata["output_contract"] == "typed_result" and not (metadata_path.parent / "schema.json").is_file():
                raise NovelOSError("invalid_catalog", "typed_result Skill 缺少 schema.json", {"path": str(metadata_path.parent)})
            if metadata["name"] != metadata_path.parent.name:
                raise NovelOSError(
                    "invalid_catalog",
                    "Catalog Skill 名称必须与目录名一致",
                    {"name": metadata["name"], "directory": metadata_path.parent.name},
                )
            contract_path = metadata_path.parent / "contract.yaml"
            if contract_path.is_file():
                try:
                    contract_data = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
                except yaml.YAMLError as exc:
                    raise NovelOSError("invalid_catalog", "Catalog YAML 解析失败", {"path": str(contract_path)}) from exc
                self._validate_contract(contract_data, contract_path)
            package = CatalogPackage(metadata_path.parent, metadata, provenance, self._package_hash(metadata_path.parent))
            if package.name in packages:
                raise NovelOSError("invalid_catalog", "Catalog Skill 名称重复", {"name": package.name})
            packages[package.name] = package
        return packages

    def search(
        self,
        stage: str | None = None,
        asset: str | None = None,
        capability: str | None = None,
        genres: list[str] | None = None,
        lifecycle: str = "active",
        scope: str | None = None,
    ) -> dict[str, Any]:
        packages = self._packages()
        candidates = []
        for package in packages.values():
            metadata = package.metadata
            if metadata["lifecycle"] != lifecycle:
                continue
            if stage is not None and metadata["stage"] != stage:
                continue
            if asset is not None and metadata["asset"] != asset:
                continue
            if capability is not None and metadata["capability"] != capability:
                continue
            package_scope = metadata.get("scope")
            if scope is not None and package_scope not in {None, scope}:
                continue
            package_genres = set(metadata.get("genres") or [])
            if genres and package_genres and not package_genres.intersection(genres):
                continue
            candidates.append(self._summary(package))
        candidates.sort(
            key=lambda item: (
                0 if scope is not None and item["scope"] == scope else 1,
                item["priority"],
                item["name"],
            )
        )
        snapshot_hash = self._snapshot_hash(candidates)
        return {"snapshot_hash": snapshot_hash, "candidates": candidates}

    def get(self, name: str) -> dict[str, Any]:
        package = self._get_package(name)
        resources = {}
        for artifact, filename in (
            ("prompt", "prompt.md"),
            ("contract", "contract.yaml"),
            ("input_schema", "input_schema.json"),
            ("schema", "schema.json"),
        ):
            if (package.root / filename).is_file():
                resources[artifact] = f"novelos://catalog/{name}/{artifact}"
        examples = package.root / "examples"
        if examples.is_dir():
            resources["examples"] = sorted(path.name for path in examples.iterdir() if path.is_file())
        clusters = package.root / "clusters"
        if clusters.is_dir():
            resources["clusters"] = sorted(path.name for path in clusters.iterdir() if path.is_file())
        return {
            "metadata": package.metadata,
            "provenance": package.provenance,
            "package_hash": package.package_hash,
            "resources": resources,
        }

    def validate_selection(self, selected_names: list[str], candidate_names: list[str], snapshot_hash: str) -> dict[str, Any]:
        if len(selected_names) != len(set(selected_names)) or len(candidate_names) != len(set(candidate_names)):
            raise NovelOSError("invalid_selection", "Skill 名称不得重复")
        if not set(selected_names).issubset(candidate_names):
            raise NovelOSError("invalid_selection", "选择包含候选快照之外的 Skill")
        packages = self._packages()
        if not set(candidate_names).issubset(packages):
            raise NovelOSError("stale_catalog", "候选 Skill 已不存在")
        summaries = [self._summary(packages[name]) for name in candidate_names]
        actual_hash = self._snapshot_hash(summaries)
        if actual_hash != snapshot_hash:
            raise NovelOSError("stale_catalog", "Catalog 候选快照已变化", {"expected": snapshot_hash, "actual": actual_hash})
        return {"valid": True, "snapshot_hash": actual_hash, "selected_names": selected_names}

    def validate_output(self, name: str, payload: Any) -> dict[str, Any]:
        package = self._get_package(name)
        output_contract = package.metadata.get("output_contract")
        if output_contract in {"free_text", "document"}:
            valid = isinstance(payload, str) and bool(payload.strip())
            return {
                "valid": valid,
                "output_contract": output_contract,
                "errors": [] if valid else [{"path": "$", "message": "输出必须是非空字符串"}],
            }
        if output_contract != "typed_result":
            raise NovelOSError("invalid_catalog", "Skill 缺少有效 output_contract", {"name": name})
        schema_path = package.root / "schema.json"
        if not schema_path.is_file():
            raise NovelOSError("invalid_catalog", "typed_result Skill 缺少 schema.json", {"name": name})
        errors = self._schema_errors(schema_path, payload, name)
        return {"valid": not errors, "output_contract": output_contract, "errors": errors}

    def validate_input(self, name: str, payload: Any) -> dict[str, Any]:
        package = self._get_package(name)
        schema_path = package.root / "input_schema.json"
        if not schema_path.is_file():
            raise NovelOSError("invalid_catalog", "Skill 没有结构化 input schema", {"name": name})
        errors = self._schema_errors(schema_path, payload, name)
        return {"valid": not errors, "errors": errors}

    def get_resource(self, name: str, artifact: str) -> str:
        package = self._get_package(name)
        filenames = {
            "prompt": "prompt.md",
            "contract": "contract.yaml",
            "input_schema": "input_schema.json",
            "schema": "schema.json",
        }
        if artifact not in filenames:
            raise NovelOSError("not_found", "Catalog Resource 类型不存在", {"artifact": artifact})
        path = package.root / filenames[artifact]
        if not path.is_file():
            raise NovelOSError("not_found", "Catalog Resource 不存在", {"name": name, "artifact": artifact})
        return path.read_text(encoding="utf-8")

    def list_cluster_files(self, name: str) -> dict[str, Any]:
        package = self._get_package(name)
        clusters_dir = package.root / "clusters"
        files = sorted(path.name for path in clusters_dir.iterdir() if path.is_file()) if clusters_dir.is_dir() else []
        return {"name": name, "clusters": files}

    def get_cluster_file(self, name: str, filename: str) -> str:
        # 受控目录读取：filename 只允许单层 .md 文件名，禁止任何路径穿越
        if not isinstance(filename, str) or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9._-]*\.md", filename):
            raise NovelOSError("invalid_argument", "cluster 文件名必须是单层 .md 文件名（不含路径分隔符、不以点开头）", {"filename": filename})
        package = self._get_package(name)
        path = package.root / "clusters" / filename
        if not path.is_file():
            raise NovelOSError("not_found", "Catalog cluster 文件不存在", {"name": name, "filename": filename})
        return path.read_text(encoding="utf-8")

    def _get_package(self, name: str) -> CatalogPackage:
        package = self._packages().get(name)
        if package is None:
            raise NovelOSError("not_found", "Catalog Skill 不存在", {"name": name})
        return package

    @staticmethod
    def _validate_metadata(metadata: Any, path: Path) -> None:
        if not isinstance(metadata, dict):
            raise NovelOSError("invalid_catalog", "metadata 必须是对象", {"path": str(path)})
        missing = sorted(REQUIRED_METADATA - metadata.keys())
        unknown = sorted(metadata.keys() - ALLOWED_METADATA)
        if missing or unknown:
            raise NovelOSError("invalid_catalog", "metadata 字段不合法", {"path": str(path), "missing": missing, "unknown": unknown})
        if metadata["lifecycle"] not in LIFECYCLES:
            raise NovelOSError("invalid_catalog", "metadata lifecycle 非法", {"path": str(path)})
        for field in REQUIRED_METADATA - {"lifecycle"}:
            if not isinstance(metadata[field], str) or not metadata[field].strip():
                raise NovelOSError("invalid_catalog", "metadata 必填字段必须是非空字符串", {"path": str(path), "field": field})
        for field in ("genres", "use_when", "avoid_when", "context_inputs", "artifact_inputs", "artifact_outputs", "requires", "produces", "invariants", "tags"):
            if field in metadata and not isinstance(metadata[field], list):
                raise NovelOSError("invalid_catalog", "metadata 列表字段类型错误", {"path": str(path), "field": field})
            if field in metadata and any(not isinstance(item, str) or not item.strip() for item in metadata[field]):
                raise NovelOSError("invalid_catalog", "metadata 列表字段必须包含非空字符串", {"path": str(path), "field": field})
        if metadata["output_contract"] not in OUTPUT_CONTRACTS:
            raise NovelOSError("invalid_catalog", "metadata output_contract 非法", {"path": str(path)})
        if "priority" in metadata and (isinstance(metadata["priority"], bool) or not isinstance(metadata["priority"], int)):
            raise NovelOSError("invalid_catalog", "metadata priority 必须是整数", {"path": str(path)})

    @staticmethod
    def _validate_provenance(provenance: Any, path: Path) -> None:
        if (
            not isinstance(provenance, dict)
            or not PROVENANCE_FIELDS.issubset(provenance)
            or not set(provenance).issubset(PROVENANCE_FIELDS | PROVENANCE_OPTIONAL_FIELDS)
        ):
            raise NovelOSError("invalid_catalog", "provenance 字段不完整", {"path": str(path)})
        if provenance["origin"] not in {"target-native", "adapted", "migrated"}:
            raise NovelOSError("invalid_catalog", "provenance origin 非法", {"path": str(path)})
        for field in ("license", "migration_note"):
            if not isinstance(provenance[field], str) or not provenance[field].strip():
                raise NovelOSError("invalid_catalog", "provenance 必填字段不能为空", {"path": str(path), "field": field})
        source_fields = ("source_repository", "source_path", "source_commit", "source_hash")
        additional_sources = provenance.get("additional_sources", [])
        if not isinstance(additional_sources, list):
            raise NovelOSError("invalid_catalog", "additional_sources 必须是数组", {"path": str(path)})
        if provenance["origin"] == "target-native":
            if any(provenance[field] is not None for field in source_fields) or additional_sources:
                raise NovelOSError("invalid_catalog", "target-native 包不能伪造来源", {"path": str(path)})
            return
        CatalogStore._validate_source_record(provenance, path)
        for source in additional_sources:
            if not isinstance(source, dict) or set(source) != ADDITIONAL_SOURCE_FIELDS:
                raise NovelOSError("invalid_catalog", "additional source 字段不完整", {"path": str(path)})
            CatalogStore._validate_source_record(source, path)

    @staticmethod
    def _validate_source_record(source: dict[str, Any], path: Path) -> None:
        for field in ADDITIONAL_SOURCE_FIELDS:
            if not isinstance(source[field], str) or not source[field].strip():
                raise NovelOSError("invalid_catalog", "迁移包必须记录完整来源", {"path": str(path), "field": field})
        if not re.fullmatch(r"[0-9a-f]{40}", source["source_commit"]):
            raise NovelOSError("invalid_catalog", "迁移包 source_commit 非法", {"path": str(path)})
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", source["source_hash"]):
            raise NovelOSError("invalid_catalog", "迁移包 source_hash 非法", {"path": str(path)})

    @staticmethod
    def _validate_contract(contract: Any, path: Path) -> None:
        if not isinstance(contract, dict):
            raise NovelOSError("invalid_catalog", "contract 必须是对象", {"path": str(path)})
        expected_fields = {"contract_version", "inputs", "outputs", "invariants", "forbidden_actions"}
        if set(contract.keys()) != expected_fields:
            missing = sorted(expected_fields - contract.keys())
            unknown = sorted(contract.keys() - expected_fields)
            raise NovelOSError("invalid_catalog", "contract 字段不合法", {"path": str(path), "missing": missing, "unknown": unknown})
        version = contract["contract_version"]
        if isinstance(version, bool) or version != 1:
            raise NovelOSError("invalid_catalog", "contract contract_version 非法", {"path": str(path)})
        inputs = contract["inputs"]
        if not isinstance(inputs, list):
            raise NovelOSError("invalid_catalog", "contract inputs 必须是列表", {"path": str(path)})
        allowed_cardinalities = {"one", "zero_or_one", "one_or_more", "zero_or_more", "exactly_two", "three_or_more"}
        for item in inputs:
            if not isinstance(item, dict) or set(item.keys()) != {"contract", "cardinality"}:
                raise NovelOSError("invalid_catalog", "contract input 项字段不合法", {"path": str(path)})
            if not isinstance(item["contract"], str) or not item["contract"].strip():
                raise NovelOSError("invalid_catalog", "contract input 必须包含非空 contract 名称", {"path": str(path)})
            if item["cardinality"] not in allowed_cardinalities:
                raise NovelOSError("invalid_catalog", "contract input cardinality 非法", {"path": str(path)})
        for field in ("outputs", "invariants", "forbidden_actions"):
            arr = contract[field]
            if not isinstance(arr, list):
                raise NovelOSError("invalid_catalog", f"contract {field} 必须是列表", {"path": str(path)})
            if any(not isinstance(x, str) or not x.strip() for x in arr):
                raise NovelOSError("invalid_catalog", f"contract {field} 元素必须是非空字符串", {"path": str(path)})
            if len(arr) != len(set(arr)):
                raise NovelOSError("invalid_catalog", f"contract {field} 存在重复字符串", {"path": str(path)})

    @staticmethod
    def _package_hash(root: Path) -> str:
        digest_input = bytearray()
        for path in sorted(item for item in root.rglob("*") if item.is_file() and "__pycache__" not in item.parts):
            digest_input.extend(path.relative_to(root).as_posix().encode("utf-8"))
            digest_input.extend(b"\0")
            digest_input.extend(path.read_bytes())
            digest_input.extend(b"\0")
        return content_hash(bytes(digest_input))

    @staticmethod
    def _schema_errors(schema_path: Path, payload: Any, name: str) -> list[dict[str, str]]:
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
        except (json.JSONDecodeError, SchemaError) as exc:
            raise NovelOSError("invalid_catalog", "Catalog JSON Schema 非法", {"name": name}) from exc
        return [
            {
                "path": "$" + "".join(f"[{part}]" if isinstance(part, int) else f".{part}" for part in error.path),
                "message": error.message,
            }
            for error in sorted(Draft202012Validator(schema).iter_errors(payload), key=lambda item: list(item.path))
        ]

    @staticmethod
    def _snapshot_hash(candidates: list[dict[str, Any]]) -> str:
        canonical = sorted(candidates, key=lambda item: item["name"])
        return content_hash(json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")))

    @staticmethod
    def _summary(package: CatalogPackage) -> dict[str, Any]:
        metadata = package.metadata
        return {
            "name": package.name,
            "version": metadata["version"],
            "description": metadata["description"],
            "stage": metadata["stage"],
            "asset": metadata["asset"],
            "capability": metadata["capability"],
            "genres": metadata.get("genres") or [],
            "scope": metadata.get("scope"),
            "use_when": metadata.get("use_when") or [],
            "avoid_when": metadata.get("avoid_when") or [],
            "priority": int(metadata.get("priority", 100)),
            "package_hash": package.package_hash,
        }
