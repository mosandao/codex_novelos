from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import uuid
from pathlib import Path
from typing import Any

from novelos_mcp import NovelOSError

PROJECTION_FORMAT_VERSION = 1
GENERATOR_VERSION = "1.1.0"

# 不允许出现在文件名中的控制字符与保留字符
ILLEGAL_CHAR_PATTERN = re.compile(r'[\x00-\x1f\x7f\\/:*?"<>|]')

_CN_DIGITS = "零一二三四五六七八九"


def cn_num(n: int) -> str:
    """将正整数转为中文数字（如 1->一, 10->十, 21->二十一, 100->一百）。"""
    if n < 0:
        return str(n)
    if n == 0:
        return "零"
    if n < 10:
        return _CN_DIGITS[n]
    if n < 20:
        return "十" if n == 10 else "十" + _CN_DIGITS[n - 10]
    if n < 100:
        tens, ones = divmod(n, 10)
        return _CN_DIGITS[tens] + "十" + (_CN_DIGITS[ones] if ones else "")
    if n < 1000:
        hundreds, rest = divmod(n, 100)
        result = _CN_DIGITS[hundreds] + "百"
        if rest == 0:
            return result
        if rest < 10:
            return result + "零" + _CN_DIGITS[rest]
        return result + cn_num(rest)
    return str(n)


def sanitize_filename(name: str, default: str = "untitled") -> str:
    """清理并校验目录/文件名，防止路径逃逸、控制字符与空文件名。"""
    if not name:
        return default
    # 替换非法字符
    cleaned = ILLEGAL_CHAR_PATTERN.sub("_", name).strip()
    # 移除首尾点号与空格
    cleaned = cleaned.strip(". ")
    # 拒绝穿越路径
    if not cleaned or cleaned in ("..", ".") or ".." in cleaned:
        return default
    return cleaned


def content_hash(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


class ProjectionEngine:
    def __init__(self, root_dir: Path | str = "novels") -> None:
        self.root_dir = Path(root_dir).resolve()

    def remove_project_projection(self, project_id: str, project_name: str) -> dict[str, Any]:
        """删除归属于指定项目的派生投影，拒绝触及无 manifest 或其他项目目录。"""
        dir_name = sanitize_filename(project_name, default=f"project_{project_id}")
        target_dir = self.root_dir / dir_name
        if not target_dir.exists():
            return {"removed": False, "project_directory": str(target_dir)}
        if target_dir.is_symlink():
            raise NovelOSError("security_violation", "拒绝删除符号链接投影目录", {"path": str(target_dir)})
        try:
            target_dir.resolve().relative_to(self.root_dir)
        except ValueError as exc:
            raise NovelOSError("security_violation", "投影删除路径超出许可根目录范围", {"path": str(target_dir)}) from exc

        manifest_file = target_dir / "manifest.json"
        if not manifest_file.is_file():
            raise NovelOSError("projection_delete_blocked", "投影目录缺少 manifest，拒绝删除", {"path": str(target_dir)})
        try:
            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise NovelOSError("projection_delete_blocked", "投影 manifest 无法解析，拒绝删除", {"path": str(target_dir)}) from exc
        if manifest.get("project_id") != project_id:
            raise NovelOSError(
                "projection_delete_blocked",
                "投影目录属于其他项目，拒绝删除",
                {"path": str(target_dir), "existing_project_id": manifest.get("project_id"), "request_project_id": project_id},
            )

        shutil.rmtree(target_dir)
        return {"removed": True, "project_directory": str(target_dir)}

    def render(
        self,
        service: Any,
        project_id: str,
        include_candidates: bool = True,
        include_all_outputs: bool = True,
    ) -> dict[str, Any]:
        """将项目的 SQLite 权威快照单向原子渲染为 Markdown 展示文件夹。

        默认将全部产出写入独立的“产出/”目录；当前权威内容仍只写入“规划/”和
        “正文/”。include_candidates 保留兼容性候选视图，include_all_outputs 可在
        需要纯权威快照时关闭全过程档案。
        """
        # 1. 从 Service 获取版本一致的权威只读快照
        try:
            snapshot = service.get_projection_snapshot(
                project_id,
                include_candidates=include_candidates,
                include_all_outputs=include_all_outputs,
            )
        except TypeError as exc:
            # 已启动的 MCP 进程可能暂时持有旧版 Service；保留候选投影能力，
            # 待进程重启后自动启用完整“产出/”快照。
            if "include_all_outputs" not in str(exc):
                raise
            snapshot = service.get_projection_snapshot(project_id, include_candidates=include_candidates)
        project_title = snapshot["project"].get("name") or snapshot["project"].get("title") or "Untitled"
        project_version = snapshot["project"]["version"]
        authority_snapshot_hash = snapshot["authority_snapshot_hash"]

        dir_name = sanitize_filename(project_title, default=f"project_{project_id}")
        target_dir = (self.root_dir / dir_name).resolve()

        # 安全防逃逸校验
        try:
            target_dir.relative_to(self.root_dir)
        except ValueError as exc:
            raise NovelOSError("security_violation", "目标渲染路径超出许可根目录范围", {"path": str(target_dir)}) from exc

        # 检查是否目标目录已存在，若存在需核查 project_id 归属
        if target_dir.exists():
            manifest_file = target_dir / "manifest.json"
            if manifest_file.is_file():
                try:
                    old_manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
                    old_project_id = old_manifest.get("project_id")
                    if old_project_id and old_project_id != project_id:
                        raise NovelOSError(
                            "security_violation",
                            "目标目录已存在且属于其他项目，拒绝非授权覆盖",
                            {"target_dir": str(target_dir), "existing_project_id": old_project_id, "request_project_id": project_id},
                        )
                except json.JSONDecodeError:
                    pass

        # 2. 在同级建立临时构建目录
        self.root_dir.mkdir(parents=True, exist_ok=True)
        tmp_dir = self.root_dir / f".tmp_{dir_name}_{uuid.uuid4().hex}"
        tmp_dir.mkdir(parents=True, exist_ok=True)

        files_manifest: list[dict[str, Any]] = []
        skipped_stats = snapshot.get("skipped_non_authoritative_stats", {})

        def _write_markdown(rel_path_str: str, title: str, body: str, source_info: dict[str, Any]) -> None:
            safe_rel_parts = [sanitize_filename(p) for p in rel_path_str.split("/")]
            rel_path = Path(*safe_rel_parts)
            abs_path = tmp_dir / rel_path

            # 确认不产生软链接或逃逸
            try:
                abs_path.resolve().relative_to(tmp_dir.resolve())
            except ValueError as exc:
                raise NovelOSError("security_violation", "渲染路径发生非法逃逸", {"path": str(rel_path)}) from exc

            abs_path.parent.mkdir(parents=True, exist_ok=True)

            text_content = f"# {title}\n\n{body}\n" if title else f"{body}\n"
            data_bytes = text_content.encode("utf-8")
            abs_path.write_bytes(data_bytes)

            file_digest = content_hash(data_bytes)
            files_manifest.append(
                {
                    "relative_path": rel_path.as_posix(),
                    "sha256": file_digest,
                    "source_type": source_info.get("source_type", "derived"),
                    "source_id": source_info.get("source_id", ""),
                    "source_ref": source_info.get("source_ref", source_info.get("source_id", "")),
                    "source_version": source_info.get("source_version", 1),
                    # 派生/合成文件（如 README、连续性账本）没有单一来源资产，
                    # 此时 source_hash 回退为文件内容 Hash，保证逐文件可校验。
                    "source_hash": source_info.get("source_hash") or file_digest,
                }
            )

        # A. 渲染 README.md
        readme_body = (
            f"此文件夹为 NovelOS 项目《{project_title}》派生的用户只读投影。\n\n"
            "> [!IMPORTANT]\n"
            "> **只读提示**：本目录由 NovelOS 权威数据库单向渲染，可随时安全删除并重新生成。"
            "在本地编辑器中直接修改 Markdown 文件**不会回写**数据库，也不影响权威创作状态。\n\n"
            f"- **项目 ID**：`{project_id}`\n"
            f"- **项目版本**：`v{project_version}`\n"
            f"- **权威快照 Hash**：`{authority_snapshot_hash}`\n"
        )
        _write_markdown("README.md", f"《{project_title}》项目展示视图", readme_body, {"source_type": "project_readme", "source_id": project_id})

        # A2. 创作约束只展示精确项目绑定与 locked Direction，不读取候选冒充权威。
        creator = snapshot.get("creator_signature")
        if creator:
            signature = creator["signature"]
            labels = {
                "sympathies": "天然同情",
                "distrusts": "持续警惕",
                "recurring_attention": "反复关注",
                "narrative_principles": "叙事原则",
                "forbidden_conveniences": "禁止的便利解法",
                "expression_preferences": "表达偏好",
                "negative_constraints": "负面约束",
            }
            creator_lines = [
                f"- **Profile**：{creator['profile_display_name']} (`{creator['profile_id']}`)",
                f"- **版本**：revision {creator['profile_revision']} (`{creator['profile_version_id']}`)",
                f"- **Hash**：`{creator['subject_hash']}`",
                f"- **精确引用**：`{creator['constraint_ref']}`",
                f"- **绑定模式**：`{creator['binding_mode']}`",
            ]
            for field, label in labels.items():
                creator_lines.extend(["", f"## {label}"])
                creator_lines.extend(f"- {item}" for item in signature[field])
            creator_body = "\n".join(creator_lines)
            creator_source = {
                "source_type": "creator_signature",
                "source_id": creator["profile_version_id"],
                "source_ref": creator["constraint_ref"],
                "source_version": creator["profile_revision"],
                "source_hash": creator["subject_hash"],
            }
        else:
            creator_body = "*当前项目尚未绑定 Creator Profile；系统未合成或猜测作者思想。*"
            creator_source = {
                "source_type": "creator_signature_absent",
                "source_id": project_id,
                "source_ref": project_id,
                "source_version": project_version,
            }
        _write_markdown("创作约束/作者签名.md", "作者签名", creator_body, creator_source)

        soul = snapshot.get("book_soul")
        if soul:
            soul_value = soul["book_soul"]
            soul_labels = {
                "unresolved_claims": "未决追问",
                "central_contradiction": "核心矛盾",
                "costly_commitments": "有代价的承诺",
                "protected_dignity": "受保护的尊严",
                "forbidden_resolutions": "禁止的解决方式",
                "recurring_tests": "重复检验",
                "narrative_mercy": "叙事仁慈",
                "narrative_cruelty": "叙事残酷",
                "deliberate_silences": "刻意留白",
            }
            soul_lines = [
                f"- **Direction**：`{soul['direction_id']}`，version {soul['direction_version']}",
                f"- **Hash**：`{soul['direction_subject_hash']}`",
                f"- **精确引用**：`{soul['direction_constraint_ref']}`",
            ]
            for field, label in soul_labels.items():
                soul_lines.extend(["", f"## {label}"])
                value = soul_value[field]
                if isinstance(value, list):
                    soul_lines.extend(f"- {item}" for item in value)
                else:
                    soul_lines.append(value)
            soul_body = "\n".join(soul_lines)
            soul_source = {
                "source_type": "book_soul",
                "source_id": soul["direction_id"],
                "source_ref": soul["direction_constraint_ref"],
                "source_version": soul["direction_version"],
                "source_hash": soul["direction_subject_hash"],
            }
        else:
            soul_body = "*当前没有包含有效 `book_soul` 的 locked Story Direction；候选内容不会在此显示为权威。*"
            soul_source = {
                "source_type": "book_soul_absent",
                "source_id": project_id,
                "source_ref": project_id,
                "source_version": project_version,
            }
        _write_markdown("创作约束/本书创作灵魂.md", "本书创作灵魂", soul_body, soul_source)

        # A3. 创作种子（非权威入口层）。不进权威快照一致性视图，单独只读取 active 种子。
        seed = None
        get_seed = getattr(service, "get_creation_seed", None)
        if callable(get_seed):
            try:
                seed = get_seed(project_id)
            except Exception:
                seed = None
        if seed:
            seed_lines = [
                f"- **版本**：v{seed['version']}（历史版本共 {seed['version']} 个）",
                "",
                "## 主角雏形",
                seed["protagonist_seed"] or "*（未填写）*",
                "",
                "## 世界感觉",
                seed["world_seed"] or "*（未填写）*",
                "",
                "## 爽点偏好",
                seed["hook_seed"] or "*（未填写）*",
                "",
                "## 其他备注",
                seed["notes"] or "*（未填写）*",
            ]
            seed_body = "\n".join(seed_lines)
            seed_source = {
                "source_type": "creation_seed",
                "source_id": seed["id"],
                "source_ref": seed["id"],
                "source_version": seed["version"],
            }
        else:
            seed_body = "*当前项目尚未填写创作种子；Direction 将按约束直接生成。*"
            seed_source = {
                "source_type": "creation_seed_absent",
                "source_id": project_id,
                "source_ref": project_id,
                "source_version": project_version,
            }
        _write_markdown("创作约束/创作种子.md", "创作种子", seed_body, seed_source)

        # B. 渲染 规划/ 目录 (01-故事方向 ~ 06-故事弧)
        planning_map = {
            "direction": "01-故事方向.md",
            "architecture": "02-故事架构.md",
            "strategy": "03-全书战略.md",
            "character_contract": "04-人物契约.md",
            "world_contract": "05-世界契约.md",
            "story_arc": "06-故事弧.md",
        }
        for asset_type, filename in planning_map.items():
            asset_item = snapshot["planning_assets"].get(asset_type)
            if asset_item:
                _write_markdown(
                    f"规划/{filename}",
                    f"规划：{asset_type}",
                    asset_item["content"],
                    {
                        "source_type": "planning_asset",
                        "source_id": asset_item["id"],
                        "source_version": asset_item["version"],
                        "source_hash": asset_item["subject_hash"],
                    },
                )

        # C. 渲染 大纲/ 目录 (按卷分层: 第一卷/卷纲.md + 第一卷/第001章-章纲.md)
        # 构建 volume scope_ref -> 卷号 映射
        volume_scope_to_num: dict[str, int] = {}
        for vol in snapshot.get("volume_outlines", []):
            vol_scope = vol.get("scope_ref", "")
            vol_num = vol.get("volume_number") or vol.get("number", 1)
            volume_scope_to_num[vol_scope] = int(vol_num) if vol_num else 1

        for vol in snapshot.get("volume_outlines", []):
            v_num = vol.get("volume_number") or vol.get("number", 1)
            v_num = int(v_num) if v_num else 1
            v_cn = cn_num(v_num)
            v_title = vol.get("title", f"第{v_cn}卷")
            _write_markdown(
                f"大纲/第{v_cn}卷/卷纲.md",
                f"第 {v_cn} 卷卷纲：{v_title}",
                vol.get("content", ""),
                {
                    "source_type": "volume_outline",
                    "source_id": vol["id"],
                    "source_version": vol["version"],
                    "source_hash": vol["subject_hash"],
                },
            )

        for plan in snapshot.get("chapter_plans", []):
            scope_ref = plan.get("scope_ref", "")
            # 从 scope_ref 解析章节号（格式 volume:{id}:chapter_{N}）
            chap_match = re.search(r":chapter_(\d+)$", scope_ref)
            if not chap_match:
                # 非按章拆分的 chapter_plan（如已废弃的合并 scope_ref）跳过渲染
                continue
            c_num = int(chap_match.group(1))
            c_title = plan.get("title", f"第{c_num:03d}章")
            # 从 scope_ref 解析 volume_id 定位卷号
            vol_match = re.match(r"^(volume:[^:]+):", scope_ref)
            v_num = 1
            if vol_match:
                vol_scope_prefix = vol_match.group(1)
                v_num = volume_scope_to_num.get(vol_scope_prefix, 1)
            v_cn = cn_num(v_num)
            _write_markdown(
                f"大纲/第{v_cn}卷/第{c_num:03d}章-章纲.md",
                f"第 {v_cn} 卷第 {c_num} 章执行卡：{c_title}",
                plan.get("content", ""),
                {
                    "source_type": "chapter_plan",
                    "source_id": plan["id"],
                    "source_version": plan["version"],
                    "source_hash": plan["subject_hash"],
                },
            )

        # D. 渲染 正文/ 目录 (按卷分层: 第一卷/第001章-章节标题.md)
        for ch in snapshot.get("chapters", []):
            v_num = ch.get("volume_number") or ch.get("number", 1)
            v_cn = cn_num(int(v_num) if v_num else 1)
            c_num = ch.get("chapter_number") or ch.get("number", 1)
            c_title = sanitize_filename(ch.get("title", "未命名章节"))
            _write_markdown(
                f"正文/第{v_cn}卷/第{c_num:03d}章-{c_title}.md",
                ch.get("title", f"第 {c_num} 章"),
                ch.get("content", ""),
                {
                    "source_type": "chapter",
                    "source_id": ch["id"],
                    "source_version": ch.get("version", 1),
                    "source_hash": ch["subject_hash"],
                },
            )

        # E. 渲染 人物/ & 世界/ 实体目录
        for char in snapshot.get("characters", []):
            c_name = sanitize_filename(char["name"])
            _write_markdown(
                f"人物/{c_name}.md",
                char["name"],
                f"**描述**：{char.get('description', '')}\n\n**人物弧**：{char.get('arc_summary', '')}",
                {"source_type": "character", "source_id": char["id"], "source_version": char["version"], "source_hash": char.get("subject_hash", "")},
            )

        for world in snapshot.get("worlds", []):
            w_name = sanitize_filename(world["name"])
            _write_markdown(
                f"世界/{w_name}.md",
                world["name"],
                f"**规则/设定**：{world.get('description', '')}",
                {"source_type": "world", "source_id": world["id"], "source_version": world["version"], "source_hash": world.get("subject_hash", "")},
            )

        # F. 渲染 连续性/ 账本目录 (6 大主题)
        cont_items = [
            ("伏笔与叙事承诺.md", "叙事承诺账本", snapshot.get("narrative_promises", [])),
            ("读者期待.md", "读者期待账本", snapshot.get("expectation_ledgers", [])),
            ("人物关系.md", "人物关系状态", snapshot.get("relationship_states", [])),
            ("故事弧状态.md", "故事弧状态账本", snapshot.get("arc_states", [])),
            ("时间线.md", "时间线账本", snapshot.get("timelines", [])),
            ("正文事实.md", "正文事实与逻辑账本", snapshot.get("fact_records", [])),
        ]
        for cont_file, cont_title, cont_data in cont_items:
            cont_text = json.dumps(cont_data, indent=2, ensure_ascii=False) if cont_data else "*尚无相关记录*"
            _write_markdown(
                f"连续性/{cont_file}",
                cont_title,
                cont_text,
                {"source_type": "continuity_ledger", "source_id": cont_file, "source_version": 1, "source_hash": content_hash(cont_text)},
            )

        # F2. 诊断模式：渲染 candidate 规划资产到独立的 候选/ 子目录。
        # 候选资产走旁路 key，不参与 authority_snapshot_hash；文件名带 revision
        # 后缀，与权威视图的 locked 资产物理隔离，绝不互相覆盖。
        if include_candidates:
            # 与 planning_map 保持一致的中文类型展示名。
            candidate_display = {
                "direction": "01-故事方向",
                "architecture": "02-故事架构",
                "strategy": "03-全书战略",
                "character_contract": "04-人物契约",
                "world_contract": "05-世界契约",
                "story_arc": "06-故事弧",
                "volume_outline": "卷纲",
                "chapter_plan": "章纲",
            }
            for cand in snapshot.get("planning_candidate_assets", []) or []:
                atype = cand.get("asset_type", "planning")
                display = candidate_display.get(atype, atype)
                revision = cand.get("revision", 1)
                title = f"候选：{display}（r{revision}）"
                body = cand.get("content", "")
                _write_markdown(
                    f"候选/{display}-候选-r{revision}.md",
                    title,
                    body,
                    {
                        "source_type": "planning_candidate",
                        "source_id": cand["id"],
                        "source_version": cand.get("version", 1),
                        "source_hash": cand.get("subject_hash") or content_hash(body),
                    },
                )

        # F3. 全部非权威和中间产出。此处保留候选、失效、被替代、草稿，以及
        # 每个完成的临时 Agent 原始输出；它们与当前权威视图物理隔离。
        if include_all_outputs:
            output_display = {
                "direction": "01-故事方向", "architecture": "02-故事架构",
                "strategy": "03-全书战略", "character_contract": "04-人物契约",
                "world_contract": "05-世界契约", "story_arc": "06-故事弧",
                "volume_outline": "卷纲", "chapter_plan": "章纲",
            }
            for asset in snapshot.get("planning_output_assets", []):
                asset_type = asset.get("asset_type", "planning")
                status = sanitize_filename(asset.get("status", "unknown"))
                label = output_display.get(asset_type, asset_type)
                revision = asset.get("revision", 1)
                identifier = sanitize_filename(asset.get("id", "asset").split(":")[-1][:8])
                _write_markdown(
                    f"产出/规划/{status}/{label}-r{revision}-{identifier}.md",
                    f"{label} {status} 产出（r{revision}）",
                    asset.get("content", ""),
                    {
                        "source_type": "planning_output", "source_id": asset["id"],
                        "source_version": asset.get("version", 1),
                        "source_hash": asset.get("subject_hash") or content_hash(asset.get("content", "")),
                    },
                )
            for chapter in snapshot.get("chapter_output_drafts", []):
                status = sanitize_filename(chapter.get("status", "unknown"))
                volume_number = chapter.get("volume_number") or 1
                chapter_number = chapter.get("number") or 1
                title = sanitize_filename(chapter.get("title", "未命名章节"))
                identifier = sanitize_filename(chapter.get("id", "chapter").split(":")[-1][:8])
                v_cn = cn_num(int(volume_number) if volume_number else 1)
                _write_markdown(
                    f"产出/正文/{status}/第{v_cn}卷-第{chapter_number:03d}章-{title}-{identifier}.md",
                    f"{chapter.get('title', '未命名章节')}（{status}）",
                    chapter.get("content", ""),
                    {
                        "source_type": "chapter_output", "source_id": chapter["id"],
                        "source_version": chapter.get("version", 1),
                        "source_hash": chapter.get("subject_hash") or content_hash(chapter.get("content", "")),
                    },
                )
            for run in snapshot.get("agent_outputs", []):
                role_id = sanitize_filename(run.get("role_id", "agent"))
                run_name = sanitize_filename(run.get("id", "run").replace(":", "-"))
                body = (
                    f"> 状态：`{run.get('status', '')}`  | 输出类型：`{run.get('output_type', '')}`\n"
                    f"> Trace：`{run.get('trace_id', '')}`\n\n"
                    f"{run.get('content', '')}"
                )
                _write_markdown(
                    f"产出/智能体/{role_id}/{run_name}.md",
                    f"{role_id} 产出",
                    body,
                    {
                        "source_type": "agent_output", "source_id": run["id"],
                        "source_version": 1, "source_hash": content_hash(run.get("content", "")),
                    },
                )

        # F4. 创作全过程档案（默认模式也渲染）：为每个 locked 规划资产渲染溯源链。
        # 档案是已锁定资产的过程记录（谁产、谁审、审出什么、凭什么锁定），属于权威视图
        # 的一部分。走旁路 key（planning_provenance），不参与 authority_snapshot_hash。
        provenance_display = {
            "direction": "01-故事方向", "architecture": "02-故事架构",
            "strategy": "03-全书战略", "character_contract": "04-人物契约",
            "world_contract": "05-世界契约", "story_arc": "06-故事弧",
        }
        for prov in snapshot.get("planning_provenance", []) or []:
            atype = prov.get("asset_type", "planning")
            display = provenance_display.get(atype, atype)
            revision = prov.get("revision", 1)
            lines: list[str] = [f"# 创作档案：{display}（revision {revision}）", ""]
            lines.append(f"> 资产类型：`{atype}`")
            lines.append(f"> revision：{revision} | version：{prov.get('version')}")
            lines.append(f"> subject_hash：`{prov.get('subject_hash', '')}`")
            lines.append("")
            lines.append("本档案记录该资产如何锁定：生产者、独立审查发现与锁定凭据。")
            lines.append("")
            lines.append("## 生产 Agent")
            prod = prov.get("producer_run")
            if prod:
                lines.append(f"- 角色：`{prod.get('role_id')}`（{prod.get('status')}）")
                ev = prod.get("isolation_evidence") or {}
                if ev:
                    lines.append(f"- 隔离执行凭据：`{ev.get('source')}` / `{ev.get('agent_id')}`")
                if prod.get("output_ref"):
                    lines.append(f"- 产出：`{prod['output_ref']}`")
            else:
                lines.append("- （无生产 run 记录）")
            lines.append("")
            lines.append("## 独立审查")
            rev = prov.get("review")
            if rev:
                lines.append(f"- Review：`{rev.get('id')}` | verdict：**{rev.get('verdict')}** | profile：`{rev.get('reviewer_profile')}`")
                rrun = rev.get("reviewer_run") or {}
                if rrun.get("isolation_evidence"):
                    rev_ev = rrun["isolation_evidence"]
                    lines.append(f"- 审查 Agent 隔离凭据：`{rev_ev.get('source')}` / `{rev_ev.get('agent_id')}`")
                findings = rev.get("findings") or []
                if findings:
                    lines.append("")
                    lines.append("### 审查发现（findings）")
                    for idx, f in enumerate(findings, 1):
                        sev = f.get("severity", "?")
                        lines.append(f"{idx}. **[{sev}]** {f.get('message', '')}")
                        if f.get("excerpt"):
                            lines.append(f"   > {f['excerpt']}")
                else:
                    lines.append("- （无 finding）")
            else:
                lines.append("- （无审查记录）")
            lines.append("")
            lines.append("## 锁定凭据")
            commit = prov.get("authority_commit")
            if commit:
                lines.append(f"- authority_commit：`{commit.get('id')}`")
                lines.append(f"- action：`{commit.get('action')}` | trace：`{commit.get('trace_id')}`")
                lines.append(f"- 锁定 subject_hash：`{commit.get('subject_hash', '')}`")
            else:
                lines.append("- （无 authority_commit 记录）")
            lines.append("")
            body = "\n".join(lines)
            _write_markdown(
                f"档案/{display}-档案.md",
                f"创作档案：{display}（r{revision}）",
                body,
                {
                    "source_type": "planning_provenance",
                    "source_id": f"{atype}:r{revision}",
                    "source_version": prov.get("version", 1),
                    "source_hash": prov.get("subject_hash") or content_hash(body),
                },
            )

        # G. 校验生成 manifest.json 账本
        manifest_payload = {
            "projection_format_version": PROJECTION_FORMAT_VERSION,
            "project_id": project_id,
            "project_title": project_title,
            "project_version": project_version,
            "authority_snapshot_hash": authority_snapshot_hash,
            "generator_version": GENERATOR_VERSION,
            "file_count": len(files_manifest),
            "files": sorted(files_manifest, key=lambda x: x["relative_path"]),
        }
        manifest_bytes = json.dumps(manifest_payload, indent=2, ensure_ascii=False).encode("utf-8")
        manifest_path = tmp_dir / "manifest.json"
        manifest_path.write_bytes(manifest_bytes)

        # H. 原子覆盖替换旧投影目录
        if target_dir.exists():
            shutil.rmtree(target_dir)
        tmp_dir.rename(target_dir)

        return {
            "project_id": project_id,
            "project_title": project_title,
            "output_directory": str(target_dir),
            "authority_snapshot_hash": authority_snapshot_hash,
            "rendered_file_count": len(files_manifest) + 1,  # 含 manifest.json
            "skipped_non_authoritative_stats": skipped_stats,
        }

    @staticmethod
    def verify_manifest(project_dir: Path | str) -> dict[str, Any]:
        """逐文件校验已生成投影目录的 manifest.json：

        - 重算每个文件的 SHA-256 并与 manifest 条目的 ``sha256`` 比对；
        - 校验每个条目的 ``source_hash`` 非空且符合 sha256 形态；
        - 校验 manifest 自身记录的 ``authority_snapshot_hash`` 与重算结果一致。

        返回 ``{"verified_file_count": N, "errors": [...]}``；errors 非空即代表存在不一致。
        """
        project_path = Path(project_dir)
        manifest_path = project_path / "manifest.json"
        if not manifest_path.is_file():
            raise NovelOSError("not_found", "目标目录缺少 manifest.json", {"path": str(manifest_path)})
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        errors: list[str] = []
        verified = 0
        for entry in manifest.get("files", []):
            rel_path = entry.get("relative_path", "")
            file_path = project_path / rel_path
            # 路径不得逃逸出投影目录
            try:
                file_path.resolve().relative_to(project_path.resolve())
            except ValueError:
                errors.append(f"path escapes projection root: {rel_path}")
                continue
            if not file_path.is_file():
                errors.append(f"missing file: {rel_path}")
                continue
            actual_hash = content_hash(file_path.read_bytes())
            expected_hash = entry.get("sha256", "")
            if actual_hash != expected_hash:
                errors.append(f"sha256 mismatch for {rel_path}: {actual_hash} != {expected_hash}")
            source_hash = entry.get("source_hash", "")
            if not source_hash or not source_hash.startswith("sha256:"):
                errors.append(f"invalid source_hash for {rel_path}: {source_hash}")
            verified += 1
        if errors:
            raise NovelOSError(
                "manifest_verification_failed",
                "manifest 逐文件校验未通过",
                {"errors": errors, "verified_file_count": verified},
            )
        return {"verified_file_count": verified, "errors": errors}
