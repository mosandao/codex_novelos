# COMPOSE-PORT-NOTES — 组装器 py → JS 移植对比结论

`legacy-python/scripts/novelos_compose_prompt.py`（1191 行，冻结基线只读）
→ `scripts/novelos-compose-prompt.mjs`（单文件 ESM，Node 22+，仅 node 标准库，零 npm 依赖）。

## 一、函数清单对照（py → JS，全部移植）

| py | JS（scripts/novelos-compose-prompt.mjs） | 说明 |
|---|---|---|
| `_get_field` | `getField(context, fieldPath)` | 点路径取值，取不到 null；用 `Object.hasOwn` 防原型链键 |
| `evaluate_when` | `evaluateWhen(rule, context)` | all/field(not_null,is_null,non_empty,equals)/query(六 op)；未知 op/rule 抛错 |
| `load_manifest` | `loadManifest(skillDir)` | 读 schema 文件保持缺配置同样报错；结构校验走手写等价件 `validateManifestStruct` |
| `select_modules` | `selectModules(skillDir, context)` | manifest 声明序返回 `[id, body]` |
| `_extract_checklist` | `extractChecklist(mainPrompt)` | `^##\s+交付前自检.*$` 节剪切 |
| `_extract_module_checklist` | `extractModuleChecklist(moduleBody)` | `^##\s+附加自检\s*$` 抽正文 |
| `resolve_proposal` | `resolveProposal(skillDir, proposal)` | 未注册 id → exit 1，消息含 skill 目录名 |
| `compose` | `compose(skillDir, context, dataSections, proposalModules)` | U 型组装逐字复刻 |
| `_persona_library_count` | `personaLibraryCount(db)` | |
| `_persona_fingerprints_query` | `personaFingerprintsQuery(db, selectedIds)` | ≤10 全量否则前 10 + selected parent |
| `build_context_direction/fusion/kernel_fusion` | 同名 camelCase | |
| `validate_kernel_fusion_payload` | 同名 | revise 需 base_version 非空串；create 需 setup.author_kernel dict；文案逐字 |
| 17 个 `_slot_*` + `upstream:`/`upstream-reviews:`/`canon_minimal`/`review_feedback`/craft_refs | 同名 slotXxx + `SLOT_REGISTRY` | genre_pack 多收 context 参数（统一五参签名） |
| `resolve_slots` | `resolveSlots(db, skillDir, opts)` | data_slots 声明序 + craft 卡存在性门 |
| `validate_fusion_payload` | `validateFusionPayload(payload)` | **手写结构级校验** `validateFusionPayloadStruct`（见差异 #1） |
| `content_hash` | `contentHash(text)` | `sha256:<hex>`，node:crypto |
| `write_composition_log` | `writeCompositionLog(...)` | ts `%Y%m%d-%H%M%S-%f`（本地，毫秒×1000 补足微秒）、safe_scope 正则同款、`file` 字段 posix 风格两侧一致、index.jsonl 追加 |
| `main` | `main(argv)` | CLI 流程同序；exit 0 |

py 运行时语义等价件：`pyStr`（None/True/False 渲染）、`pyStrip`（不剥 \ufeff）、`pyTruthy`（''/[]/{} 为假）、`pyEq`（bool 视作 int）、`pyJsonDumps`（indent=1 与紧凑 `, `/`: ` 分隔符两种模式）。测试曾揪出并修复两处真实缺陷：①JS `Boolean([])===true` 而 py `bool([])===False`（non_empty 及全部 `if x:` 真值点已换 `pyTruthy`）；②fusion 校验器遇未知根键提前收口导致漏报字段路径（已改为累积收集，必填缺失才提前收口防次生异常）。

## 二、行为差异声明

1. **jsonschema → 手写结构校验**（任务指定）：manifest 与 create-request 两处 schema 校验为「手写结构级等价，非 schema 全量等价」——锁必填存在性、类型、枚举、长度/数量界、关键 pattern 与 additionalProperties。合法输入两侧一致放行（金样可证）；非法输入 JS 报含字段路径的结构错误（exit 1），py 报 jsonschema 原生 message，文案不逐字相同。
2. **新增 `--db <路径>`**：py 硬编码 `ROOT/data/novelos-v2.db` 无此参数；JS 默认同路径，可指向替代库。
3. **`--review-feedback` 扩展**：py 仅接受文件路径；JS 以 `{`/`[` 开头按内联 JSON 解析，否则按路径读。该槽仅 chapter-draft manifest 声明且需 locked chapter_plan 上游——生产库 planning_assets 为空，本路径当前不可达，未进金样。
4. **stdout 编码**：JS 恒 UTF-8 无 BOM；py 随控制台编码（GBK），重定向必须 `PYTHONUTF8=1` 否则 `UnicodeEncodeError: 'gbk' codec can't encode character '\u2192'`（实测在 direction 输出第 1551 字符处触发）。金样 py 侧一律带 `PYTHONUTF8=1`。
5. **换行**：py 在 Windows 下 stdout 重定向与 `write_text` 均写 CRLF；JS 恒 LF。对比前统一 `\r\n?`→`\n` 归一（归一后逐字节比较）。composition log `.md` 与 index.jsonl 同理。
6. **`_slot_upstream_reviews` 潜在 bug 差异**：py 用 `r["id"]` 按名访问但 `row_factory` 未设（tuple），一旦命中非空回执集必 `TypeError`；生产库 reviews 无关联行、planning_assets 为空，该路径不可达。JS 按 node:sqlite 对象行实现其 evidently-intended 语义（按名取列）。
7. **浮点序列化**：整值浮点 py 渲染 `1.0`、JS 渲染 `1`；≥1e16 或 <1e-4 的指数记法边界不同。现库数据与载荷均为整数/字符串/null，四组金样未触发。
8. **argparse 外观**：JS 手写解析器对齐语义（choices 校验、missing-required、expected-one-argument 均 exit 2），但 usage 文案/程序名（`novelos-compose-prompt.mjs`）不同，且不支持 `--ass` 式缩写。`SystemExit(str)`=exit 1、成功=0 已对齐。
9. **stderr 噪音**：node:sqlite 首次使用打印 ExperimentalWarning（stderr-only，可用 `node --no-warnings` 消除）；py 侧无对应输出。
10. **未捕获异常**：py traceback / JS stack，均 stderr + exit 1。

## 三、金样对比结果（py vs js，同一输入，cmd /c 原始字节重定向，`\r` 归一后比对）

| 金样 | 输入 | 归一后字节数 | sha256(前16) | 结果 |
|---|---|---|---|---|
| direction | 生产项目 `project:fdc0e83f-3cb8-4b7e-8b6d-84e9ea1db589` | 36325 B | `1d92b83dcd79f022` | **MATCH** |
| fusion | `scripts/fixtures/compose-golden/wizard-sample.json`（v3 向导载荷，mode=create） | 42031 B | `38cba98db658237d` | **MATCH** |
| kernel-fusion(revise) | `scripts/fixtures/compose-golden/kernel-revise-sample.json`（base=creator-profile-version:cd4889a7…） | 34947 B | `fabe1fb60b2a483a` | **MATCH** |
| direction+proposal | `scripts/fixtures/compose-golden/proposal-sample.json`（3 提议：1 未命中追加 + 2 规则重复去重） | 37158 B | `5f556bc989805b07` | **MATCH** |

- 审查资产金样不可行的原因：生产库 `planning_assets` 为空（0 行），构造 subject 需向权威库写 planning_assets——裸 SQL 写通道被禁，故按预案以 fusion 家族替代；strategy-review 等审查资产与 subject/upstream/world_lexicon/book_soul/mechanisms/prev_volume_outline/promise_ledger/craft_refs 等槽的降级占位分支为逐字移植，待有锁定资产后可用同法回归。
- 组装日志对齐：默认模式下双端各跑一次 direction，index.jsonl 尾条除 ts/文件名外逐字段相等（content_hash 同为 `sha256:6afd2de4bd1f…`；modules/data_slots/divergence/decision_scope/file 全同）；带 proposal 运行 content_hash 同为 `sha256:ac712dc471d6…`，proposal[].merged 标志一致（false/true/true）。
- 退出码矩阵实测：未知 asset=2、缺 --project=2、fusion 缺 --payload=2、direction-review 缺 --subject=1、成功=0（双端一致）。

## 四、复现方法

```pwsh
# py 侧（过渡解释器 .venv，须 PYTHONUTF8=1 防 GBK 编码崩溃）
$env:PYTHONUTF8="1"
.venv\Scripts\python.exe legacy-python\scripts\novelos_compose_prompt.py --asset direction --project project:fdc0e83f-3cb8-4b7e-8b6d-84e9ea1db589 > py.out.txt
# js 侧
node scripts\novelos-compose-prompt.mjs --asset direction --project project:fdc0e83f-3cb8-4b7e-8b6d-84e9ea1db589 > js.out.txt
# 归一对比（剥 \r 后逐字节）
node -e "const fs=require('fs');const n=p=>fs.readFileSync(p).toString('utf8').replace(/\r\n?/g,'\n');console.log(n('py.out.txt')===n('js.out.txt')?'MATCH':'DIFF')"
```

## 五、测试结果

`node scripts/test-compose-prompt.mjs` → **19 passed, 0 failed**：
①a-d direction 对生产项目（exit 0、主干 H1、输入数据区标记、尾部自检节）；
② 未知 asset 非 0 且含 `invalid choice`；③ direction-review 缺 --subject 报错含提示；
④a-g when 规则纯函数（equals/is_null/not_null/non_empty/all/六 op/未知 op 与未知规则抛错）;
附1-6 pyJsonDumps 双模式、content_hash 标准向量、自检节剪切、附加自检抽取、fusion 载荷结构校验正反例。

注：测试直连生产库只读取项目 ID；组合器本身只读库，日志默认写 gitignored 的 `data/compositions/`。
