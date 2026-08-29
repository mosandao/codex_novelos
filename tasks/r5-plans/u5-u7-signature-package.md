# U5-U7 呈报包：R5 立项签名链（schema v3 草案 + migration 020 草案 + personas 试点选样）

> 状态：`IN PROGRESS`（prepare-only 轮产物，待用户对 U5/U6/U7 裁决后进入 R5 执行轮）
> 上位：`tasks/R5-knowledge-absorption.md` §4 R5 行、§5 U5/U6/U7；蓝图 `tasks/r5-plans/d4-signature-chain.plan.md` + 红方 `d4-signature-chain.redteam.md`（F4/F5/F6/F7/F8/F9/F11/F12/F13/F16 已落进本准备轮，F1 已由裁-1 解决）
> **prepare-only 纪律执行情况**：生产库 `data/novelos-v2.db` 零写入（前后 sha256 一致：`3ef3b9e0…`）；migration 020 未在生产执行（仅 /tmp 副本实测）；personas 未落生产库（仅 /tmp 副本 commit 实测）；personas 原文只落 `data/knowledge/`（gitignore 已覆盖，`git check-ignore` 实测命中）。

## 0. 交付物清单

| 产物 | 性质 | 入 git |
|---|---|---|
| `config/schemas/creator-signature.schema.json` | v3 草案（enum [1,2,3] + style_dna + measured_features + F12 allOf） | 是 |
| `config/schemas/project-create-request.schema.json` | 增 `setup.style_seed` 可选段（镜像 author_kernel 反查；只增段不改既有） | 是 |
| `db/migrations/020_creator_profiles_style_seed.sql` | 草案，照 018 模板表重建，**未执行** | 是 |
| `scripts/novelos-import-personas.mjs` | MySQL→选样→归一化→dry-run/commit（写库函数完整实现，默认 dry-run） | 是 |
| `config/knowledge/personas-alias-map.json` | author_name 归并表（脚本内置规则投影，入 git 裁决材料） | 是 |
| `data/knowledge/personas-pilot.json` | 15 卡归一化试点 JSON + conversion_notes + 归并记录 | 否（gitignore） |
| `catalog/skills/onboarding/creator-signature-fusion/prompt.md` | 增补「第三步：量体」节（不动主干） | 是 |

## 1. U5：schema 变更范围 + 备份时点（020）

**变更范围（两文件，向后兼容已验证）**：

1. `creator-signature.schema.json`：`schema_version` enum `[1,2,3]`；新增可选字段 `style_dna`（corpus_basis{tier A/B/C/D, notes, refs[]} + lexicon_summary(≤400 字) + syntax_patterns(≤5) + punctuation_habits(≤5) + structure_preferences(≤5) + dialogue_style(≤5)）与 `measured_features`（maxItems 16；feature pattern `^(fpr:[A-Za-z0-9]+|style:[a-z0-9-]+)$` 照裁-1；source_ref 逐条必填照红方 F11）；allOf 强制 `tier=D → measured_features maxItems 0`（F12）。根对象 `additionalProperties:false` 保留。**存量 v1/v2 签名不迁移不复验、继续合法**（迷你校验器实测：v1/v2 最小签名 PASS）。
2. `project-create-request.schema.json`：`setup` 增可选 `style_seed` 段（mode none/persona_select；persona_select 须 seed_version_id + seed_subject_hash）；required 数组与 author_kernel 段零改动。库内反查纪律（schema 之外的主控自查）：seed_version_id 存在 + `ownership='style_seed'` + `status='active'` + seed_subject_hash 相符。

**备份命令（照裁-10 口径；在生产库执行 020 前运行）**：

```bash
# ① checkpoint（wal 归并入主库文件后 -wal 恒 0 字节，防备份撕裂）
node -e "const {DatabaseSync}=require('node:sqlite');const db=new DatabaseSync('data/novelos-v2.db');console.log(db.prepare('PRAGMA wal_checkpoint(TRUNCATE)').get());db.close();"
# ② cp 备份（文件名含日期与用途）
cp data/novelos-v2.db "data/novelos-v2.db.bak.r5-u5-$(date +%Y%m%d-%H%M%S)"
# ③ 核对：字节数一致 + checkpoint 后主库 sha256 一致
ls -l data/novelos-v2.db*; shasum -a 256 data/novelos-v2.db
```

**020 执行步骤（U5 批准后，主控受控会话）**：备份（上）→ `node:sqlite` 执行 `db/migrations/020_creator_profiles_style_seed.sql`（`PRAGMA foreign_keys=OFF` 下跑）→ 行数比对（creator_profiles 前后 30 行）+ ownership 抽查 → 下方 schema.sql 再导出 → `schema_migrations` 写入 version=20。

**迁移影响面**：仅 `creator_profiles` 一表（30 行 = 26 system_archetype + 4 user，2026-08-29 只读实测）；`creator_profile_versions`/`project_creator_bindings` 无结构变化（018 已含 kernel 列）；重建零数据损失，id 不变。现网 `author_kernel` 0 行——R5 执行轮冒烟若走 select 内核路径须先建测试内核（红方 F17，属执行轮前置）。

## 2. schema.sql 再导出（020 执行后动作，红方 F4/裁-11）

`db/migrations/schema.sql` 头注已约定「下次 schema 变更后须从生产库重新导出」。020 落地后：

```bash
node -e "
const {DatabaseSync}=require('node:sqlite');
const db=new DatabaseSync('data/novelos-v2.db',{readOnly:true});
const rows=db.prepare(\"SELECT sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY rootpage\").all();
const out=rows.map(r=>r.sql+';').join('\n\n');
require('node:fs').writeFileSync('db/migrations/schema.sql.new', header + out);
"
# 人工合并头注（版本说明改「schema v20 终态；002..020 增量」）→ mv schema.sql.new schema.sql
# 校验：schema.sql 独立执行建空库 → PRAGMA table_info(creator_profiles) 的 ownership CHECK 含 'style_seed'
```

导出后 grep 断言 `ownership IN ('system_archetype', 'user', 'author_kernel', 'style_seed')` 在场，测试夹具基线随之对齐。

## 3. U6：personas 试点范围（选样名单 + SQL + 归并记录）

**池实测（2026-08-29 MySQL 只读）**：全表 122 行 / 103 作者；q 分布 10×9、9×52、8×58、7×3，**q≥9 池 61 条**；池内 weaknesses 空为 0 条。

**选样 SQL**：

```sql
SELECT id, TRIM(author_name) an, book_source, quality_score,
       CHAR_LENGTH(weaknesses) wlen, CHAR_LENGTH(persona_prompt) plen
FROM kb_author_personas
WHERE quality_score >= 9
ORDER BY quality_score DESC, plen DESC, id;
-- 归并/去重/每作者 ≤2 在脚本内按确定性规则执行（见 conversion_notes 与本节归并记录）
```

**选样规则（脚本 `scripts/novelos-import-personas.mjs` 内置，确定性可复跑）**：q≥9 → weaknesses 非空 → 同作者同书去重（取 q 高、seed_prompt 长者）→ 按题材轴覆盖取卡（女频必取 ≥2）→ 同作者 ≤2 硬约束 → 补足至 15（12-16 区间）。

**选样名单（15 卡，女频 2）**：

| # | 轴 | 作者（归并后）·书 | q | 源 id |
|---|---|---|---|---|
| 1 | 女频（必取） | Priest·有匪 | 9 | 200（trim 归并入池） |
| 2 | 女频（必取） | 海宴·琅琊榜 | 9 | 64 |
| 3 | 科幻 | 刘慈欣·三体2：黑暗森林 | 10 | 84（2/84 同书取密度高者） |
| 4 | 科幻 | 刘慈欣·三体1：地球往事 | 9 | 83 |
| 5 | 仙侠 | 辰东·遮天 | 10 | 166 |
| 6 | 仙侠 | 耳根·仙逆 | 10 | 169 |
| 7 | 历史武侠/权谋 | 猫腻·庆余年 | 10 | 170 |
| 8 | 历史武侠/权谋 | 烽火戏诸侯·雪中悍刀行 | 10 | 171 |
| 9 | 武侠经典 | 金庸·天龙八部 | 10 | 182 |
| 10 | 武侠经典 | 古龙·多情剑客无情剑 | 10 | 183 |
| 11 | 都市诡异 | 爱潜水的乌贼·诡秘之主 | 10 | 199 |
| 12 | 游戏电竞 | 蝴蝶蓝·全职高手 | 9 | 9 |
| 13 | 悬疑 | 紫金陈·无罪之证 | 9 | 22 |
| 14 | 历史向 | 当年明月·明朝那些事儿 | 9 | 24 |
| 15 | 群像参考 | 吹牛者·临高启明 | 9 | 4 |

**归并记录（author_name 预处理，红方 F5）**：

- trim：1 命中——id=200「␣Priest」前导空格（不归并则女频必取判据直接落空）。
- 别名归并表（`config/knowledge/personas-alias-map.json`，内置两条规则）：`^刘慈欣` → 刘慈欣（5 名变体 6 条：刘慈欣 / 刘慈欣风格×2 / 刘慈欣（三体1风格）/ 刘慈欣（三体2风格）/ 刘慈欣·硬科幻风格；q≥9 池内命中 id 2/63/83/84）；`^三九音域\s*\|` → 三九音域（id=116 带后缀脏名，q=8 不在池，防未来混入）。无「无法机械归并」的残留项。
- 同作者同书去重丢弃 8 条：刘慈欣#2（与 84 同书）、耳根#6、蝴蝶蓝#176、忘语#186、天蚕土豆#167、月关#175、辰东#73、天下霸唱#191。
- 同字符串多行 17 组不属别名归并，由「同作者 ≤2」纪律处理（溢出清单 38 作者 38 条见 pilot JSON `stats.merge_log.authorOverflow`，仅记录 id+作者名，无原文）。

**转换形态**：每卡归一化（JSON 数组/顿号串统一拆数组、`{"score":..,"description":..}` 信封剥壳、persona_prompt 保留为 `seed_prompt` 只进融合 agent 禁入写作侧）+ `conversion_notes` 逐卡记录动作；落库形态 = resources×2（种子卡 BLOB + 全字段溯源快照）→ creator_profiles（ownership='style_seed'）→ creator_profile_versions（revision=1，parent NULL——种子不作 parent）。

**版权边界（裁-5/U12 已裁默认）**：入 git 的只有归并表与本文选样名单；卡片原文（含 persona_prompt 全文）只落 `data/knowledge/personas-pilot.json`（gitignore）与库内 BLOB（`data/*.db` gitignore）；试点 15/122 ≈ 12%，不整表搬运。

## 4. U7：B 级语料授权（随本包捎带呈报）

裁决项：B 级（授权文本）启用条件——①授权来源与范围由用户在向导确认约束时一并声明；②`corpus_basis.notes` 必须含可核验凭证（链接/书证标识），主控抽查；③裁决记录入派生 resource 的 `user_input_snapshot`。未获凭证前 B 级不可用（降 C 级处理，无豁免）。schema 已按此表述（notes description 强制凭证；红方 F8 处置）。

## 5. 回滚步骤

| 层 | 步骤 |
|---|---|
| DB（020 之后发现异常） | 恢复备份 `cp data/novelos-v2.db.bak.r5-u5-<ts> data/novelos-v2.db`（覆盖前二次确认 + 当前文件再备份一份）；020 本身数据零损失，也可仅 `git` 层面无涉 |
| DB（种子数据单独清理） | 按 `ownership='style_seed'` 反查 id 集：先删 `creator_profile_versions`，再删 `creator_profiles`，最后删关联 `resources`（双资源 id 在 derivation/content 引用里）——单事务逆序删，删前备份 |
| git | `git revert` schema×2 / migration 文件 / import 脚本 / alias map / prompt 增补（建议独立 commit，revert 干净） |
| 试点 JSON | 直接删除 `data/knowledge/personas-pilot.json`（gitignore，无追踪负担） |

## 6. 验证记录（prepare-only 轮实测，2026-08-29）

| 项 | 结果 |
|---|---|
| guardrails | **296 passed, 0 failed** |
| compose 测试 | **28 passed, 0 failed**（schema 改动后内核/签名链冒烟不炸） |
| prose-fingerprint | **49 PASS, 0 FAIL** |
| verify-review-evidence | **15 passed, 0 failed** |
| canary（现场汇总） | **exit 0**（screen 误报汇总与基线口径一致） |
| render-projection 测试（附加） | 48 PASS / 0 FAIL |
| schema 迷你校验器（/tmp，17 例） | 全 PASS：v1/v2 最小签名合法（向后兼容）、v3 全量合法、F12 生效（tier=D + 非空 measured_features 被拒）、F11 生效（缺 source_ref 被拒）、裁-1 生效（`fp:dash-density` 被拒、`fpr:L01`/`style:*` 合法）、maxItems 16 顶格、根 additionalProperties:false 保留、pcr style_seed 四态（合法/none/缺 id 拒/未知字段拒）、author_kernel 段零改动 |
| 020 副本实测（/tmp/novelos-r5d4-test.db） | 30 行零损失（26+4）；CHECK 双向生效（bogus 拒绝 / style_seed 放行） |
| import --commit 副本实测 | 15 卡 → 60 行（resources 30 / profiles 15 / versions 15）；content_hash 重算抽查 OK；parent_version_id 全 NULL；种子名册反查 SQL 可查（15 行） |
| import 生产库保护 | `--commit --db data/novelos-v2.db` → REFUSE（硬编码）；`--commit` 无 --db → REFUSE |
| 渲染器抽查（副本含 v3 字段签名探针） | `--verify` 通过（9 文件），v3 字段不崩（防御式复确认） |
| 生产库零写入复核 | sha256 前后一致 `3ef3b9e0500dd47ea99c6380ff29b015464f7a6c30f90384f0a8727e3ef11541` |

## 7. 开放点（执行轮待办，非本轮遗漏）

1. **compose 手写校验器联动**：`scripts/novelos-compose-prompt.mjs` 的 `validateFusionPayloadStruct` 对 setup 未知字段报错——payload 携带 `style_seed` 会在组装器层被拒。须随执行轮的 style_seed 槽三联动（schema/manifest/recipes + compose resolver，红方 F15 口径：槽实现比内核 select 更严）一并放开；本轮白名单不含该文件，未动。
2. **渲染器风格 DNA 段**：当前防御式跳过 style_dna（不崩但不显示）。红方 F14 定为「必须」——执行轮在 `novelos-render-projection.mjs` 签名段增补风格 DNA 渲染（tier + 四列表 + measured_features 表）。
3. **v3 是否强制 style_dna**：本轮按「新字段全部可选」落地（未加 `if schema_version=3 → required style_dna` 的 allOf）；如需收紧（v3 融合产物必须带风格侧）属一行 schema 改动，随 U5 裁决定。
4. R5 执行轮冒烟「select 内核」前置：现网 author_kernel 0 行，须先建测试内核（红方 F17）。
