---
name: novel-writing
description: 根据已锁定 Chapter Plan 和已确认 Canon 上下文起草或修改小说正文。续写完整章节、撰写长场景、调整文风时使用。
---

# 小说写作

通过 node:sqlite 操作数据库（读=只读查询；写=受控直写，插件门工具已退役）。SQL 模板见 `novel-project/sql-reference.md`。

## 工作流

1. 接收已锁定 Chapter Plan（SELECT planning_assets 读取）。写作方法论经组装器一步产出：`node scripts/novelos-compose-prompt.mjs --asset chapter-draft --project <project_id>`——persona 全文 + locked 章纲原文 + canon 最小集（六类账本近端条目）+ 四张 craft 方法卡（形式阈值唯一权威源）+ 频道笔触模块随 setup 自动路由，整段注入 Writer sub agent。修复重试加 `--review-feedback <上轮回执.json> --round <N>`。
2. 组装产物已含 persona（narrative 全文 + anchors：目光/五维/内在矛盾/声音样本/盲区）与 canon 上下文；`$novel-memory` 仅用于组装未覆盖的定制检索（特定人物/时间窗口深挖）。Writer 写到超出这位作者经验边界的场景时，按 persona 的方式处理——绕开、转喻、有限视角（`blindspots.cannot_write` 列出的圈子尤其如此），**禁止切换全知叙述假装在场**。
3. 将已确认上游与 Canon 视为约束。缺少关键材料时返回 context gap。
4. 完整章节由 Main Agent 创建 sub agent（Writer）执行；局部改句可直接处理。
5. 写作时保持人物动机、知识边界、地点规则、时间顺序、伏笔和场景状态变化一致。通过选择和后果表现 `book_soul`、`soul_pressure` 与 `moral_residue`；不要自行创造作者思想。
6. 产出正文后落库为**草稿**（仅允许 `status='draft'`；`accepted` 变更按第 7 步纪律执行）：
   ```sql
   -- 存内容（草稿暂存）
   INSERT INTO resources (id, media_type, content, content_hash) VALUES (?, 'text/markdown', CAST(? AS BLOB), ?);
   -- 创建/更新章节（draft 专用）
   INSERT INTO chapters (id, volume_id, number, title, status, content_resource_id, summary, metadata_json, version)
   VALUES (?, ?, ?, ?, 'draft', ?, ?, ?, 1);
   -- 改已有草稿章节：直接更新
   UPDATE chapters SET content_resource_id = ?, summary = ?, version = version + 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?;
   ```
   content_hash 格式 `'sha256:'+sha256(内容 UTF-8 字节的 hex)`，用 node:crypto 计算（`crypto.createHash('sha256').update(content,'utf8')`）。
   落库前跑 `node scripts/novelos-prose-fingerprint.mjs --text-file <草稿>` 预筛自查（只报事实不判级，命中不阻断落库），screen 摘要写入章节 metadata_json 的 `prescreen` 字段；修订轮 UPDATE 分支重跑预筛并更新 prescreen——预筛候选是审查侧证伪线索，不是写作方的整改清单。
7. 交给 `$novel-review` 审查：回执按 sql-reference.md「审查」模板以受控 SQL 落库。审查通过后接受：单事务内先核对回执为 approved 且 subject_ref=该章节，再 `UPDATE chapters SET status='accepted', review_id=? ...`（写 `chapters.review_id` 机器痕迹，模板见 sql-reference.md）。交审查时预筛候选清单由主控手工附审查注入尾部并标注「仅供证伪，须逐条 confirm（`fpr:<ID>`）或 deny（`fpr-deny:<ID>`）+理由」；修订分支（重开 draft）按第 6 步口径重跑预筛并更新 metadata_json.prescreen。

修改已接受章节：免审直改禁止——必须重开 draft（降级操作 UPDATE status='draft'）→ 改稿 → `$novel-review` 重审（落新回执）→ 按第 7 步接受 SQL 重新接受。唯一例外是幂等确认：对已 accepted 章节重复接受且内容 hash 未变时，允许零写入确认；内容已变必须重审。

Writer 不接受、锁定或晋升任何结果——这些都是主控的职责。

## 用户打断

写作或修复进行中用户提出修改：立即停止当前生成，按 AGENTS.md「用户实时打断与修改」协议分流（setup 级/资产级/章内级），先呈报影响面再动。
