# Task 31: 创建链路衔接缺陷修复（跨事务/跨步骤状态一致性）

**状态**: `DONE`

**范围**: Task 30 全链路落地后的漏洞分析复查（逐项落到代码验证）发现：单步内的不变式靠得住，但**步骤之间**的状态一致性靠人记。本任务修复六处衔接缺口，不改变任何架构决策（内核双层/裁决制/一书一分身全部不动）。

## 缺陷登记（分析结论 → 修复方案）

| # | 缺陷 | 严重度 | 修复 |
|---|---|---|---|
| 1 | 单次调用 `--payload --kernel-candidate --candidate`（create 模式）在内核落库后于 `validate_candidate` 裸崩 KeyError（`ak["kernel_version_id"]`），留孤儿内核 + traceback | 高 | 建核后**内存缝合** select 形态（`_stitch_bound_payload`），单次调用走通全链，落库快照与两段式完全一致；`--dry-run` 组合给明确提示 |
| 2 | 内核去重只有 display_name 精确匹配：换名重试 = 近重复内核进 roster；失败尝试留孤儿无提示 | 高 | create 模式入口校验增两条 WARN：与既有内核建核素材 Jaccard 相似度 ≥0.8（防近重复）；库中未被任何项目绑定的内核清单（防孤儿堆积） |
| 3 | character_status 账本 INSERT 与注册表 `--status-update` 两步写无配对校验，漏跑即静默漂移（canon 读注册表）；单对象接口一章多迁移要多次调用 | 高 | `--status-update` 支持数组（单事务批量）；新增 `--pending-status` 对账——promoted 候选集每人物**最新** character_status vs 注册表现状，漂移非零退出；novel-continuity SKILL 收尾必跑 |
| 4 | 内核修订零自动传播是裁决制有意设计，但三层可见性全缺：select 绑旧版无 WARN、修订落库不列受影响项目 | 中 | select 绑定非最新版本 → 入口校验 WARN；revise 落库后打印仍绑旧版的项目清单与裁决指引 |
| 5 | 人物契约重锁删掉的人物永远留在注册表保持 active，无对账 | 中 | `--roster` 重锁对账：曾在旧 roster（state_json 带 arc_role）但不在新 roster 的人物 WARN（退役走 --status-update，不自动改状态） |
| 6 | 复活/回滚机械可行但留半截痕迹（exit_type 置 NULL 而 exit_chapter_id COALESCE 粘滞）；状态 UPDATE 覆盖式无审计 | 中 | 非退场状态（active/peripheral）整体清空 exit 字段且禁止携带 exit_type；每次迁移在 state_json.状态史 追加审计记录（from/to/exit_type/chapter_id/at） |

## 排除项（查证后确认非缺陷）

- `_slot_kernel_full` 按 binding 的 `kernel_version_id` 钉死版本注入——persona 与创作链永远消费同一内核版本，不存在「分身 v1 + 内核 v2」混注。
- 逐字复制检查方向正确（禁止 persona 照抄内核 identity 条目，防偷懒），与「表达层重新长出」自洽。
- revise 的 growth_log 追加校验保证内核修订内容必变，不会产生同 hash 空版本。
- 旧 v2 项目（无 kernel binding）`has_kernel=False`，内核条件模块不注入，完全不受影响。

## 任务项

- **31-1** `novelos_create_project.py`：#1 内存缝合 + #2 双 WARN + #4 旧版 WARN/受影响项目清单
- **31-2** `novelos_register_characters.py`：#3 数组化 + `--pending-status` + #5 roster 对账 + #6 退场痕迹对称/状态史
- **31-3** 文档同步：novel-continuity SKILL（收尾对账步骤）、AGENTS.md 工作流第 5 条、flows.md 人物生命周期（对账入状态机）
- **31-4** 测试补齐 + 四命令验证 + 验收记录

## 追溯体系

同 Task 30：状态只用 `TODO`/`IN PROGRESS`/`DONE`/`BLOCKED`；commit message 带 `[T31-x-y]`；四命令全绿才 DONE。

## 连带发现的存量缺陷（本轮修复）

| # | 缺陷 | 修复 |
|---|---|---|
| 7 | 文档记载的 `--kernel-revise <revise载荷> --kernel-candidate <候选>` 组合从未跑通：revise 信封（`novelos.kernel.revise.v1`）无 `setup` 键，`persist_kernel` 与缝合守卫两处 `payload["setup"]` KeyError（Task 30 冒烟走的是无 payload 路径，未暴露） | `persist_kernel` 对无 setup 的 payload 记录 `kernel_revise` 快照（base_version + kernel_hints）；缝合守卫改防御式取值。库副本 CLI 冒烟全链复验通过 |

## 验收记录

- **T31-1（create_project）**：`test_single_invocation_stitches_before_candidate_gate`（建核+--candidate 同调用：缝合后校验门正常执行不再 KeyError）、`test_candidate_with_create_payload_fails_cleanly`（丢 bound.json 场景给可行动报错）、`test_hints_duplicate_and_orphan_warnings` / `test_hints_distinct_no_duplicate_warning`（相似度 ≥0.80 WARN，不同素材不误报）、`test_select_old_revision_warns`（绑定 r1 时提示最新 r2）、`test_revise_reports_bound_projects`（修订落库后列受影响项目）、`test_kernel_dry_run_with_candidate_hints_limitation`（dry-run 组合明确提示）。
- **T31-2（register_characters）**：`test_array_updates_single_transaction`、`test_status_history_appended`（状态史 from/to/exit_type/chapter_id/at）、`test_revival_clears_exit_traces`（复活后 exit_type 与 exit_chapter_id 同时清空）、`test_nonexit_with_exit_type_rejected`、`test_dropped_character_warns_but_not_auto_retired`（roster 重锁 WARN 且不自动改状态）、`test_status_mismatch_drifts_then_resolves` / `test_unregistered_candidate_drifts` / `test_latest_candidate_wins_no_false_positive`（对账漂移检出/补跑收敛/最新候选优先防误报）。
- **T31-3（文档）**：novel-continuity SKILL 第 6 步改数组形态 + 新增第 7 步收尾必跑 `--pending-status`；AGENTS.md 工作流第 5 条同步；flows.md 人物生命周期状态机增「对账」步（原 5 步 → 6 步）、「立档」步补重锁对账、「状态迁移」步补状态史与复活清痕语义。
- **T31-4（验证）**：四命令全绿——`unittest discover` **135 tests OK**（+16）、`compileall` OK、`check_repository_hygiene --check` 0、`build_catalog_manifest --check` 0。库副本 CLI 冒烟：单次调用全链（内核落库→内存缝合→幽灵 parent 干净 FAIL 无 traceback）、bound payload 完成项目落库、同素材重跑触发「相似度 1.00」WARN、revise 信封全链（原崩溃路径）+ 受影响项目清单、select 绑 r1 提示最新 r2、`--pending-status` 对真实项目对账通过。生产库零写入（kernels=0 不变）。

## 文档变更清单

- `scripts/novelos_create_project.py`：`_stitch_bound_payload`（缝合提纯）+ 建核后内存缝合 + create 模式跑 --candidate 干净报错 + dry-run 组合提示 + `_kernel_hints_dup_warnings`/`_orphan_kernel_warnings` + select 非最新 WARN + revise 落库后受影响项目清单 + `persist_kernel` revise 信封快照容错。
- `scripts/novelos_register_characters.py`：`--status-update` 数组化、`_apply_status_update`（状态史 + 退场痕迹对称）、`check_pending_status`（`--pending-status` 对账）、roster 重锁对账 WARN、非退场状态禁带 exit_type。
- `.agents/skills/novel-continuity/SKILL.md`、`AGENTS.md`、`documentation/flows.md`：对账步骤与状态机语义同步。
- `tests/test_create_v3.py`（+7 用例）、`tests/test_register_characters.py`（+9 用例，夹具扩 resources/continuity_candidate_sets 表）。
