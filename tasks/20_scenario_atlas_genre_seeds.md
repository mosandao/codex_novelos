# Task 20：跨项目方法知识层扩容——桥段图集 Skill

## 状态

`DONE`（生成验证暂记为后续实跑项目时执行；skill 已落地为 experiment，待验证后转 active）

## 背景

世界观设计重构讨论稿（`documentation/worldbuilding-redesign.md`）第 22.4 条建议在跨项目方法知识层新增"桥段图集（scenario atlas）"。

### 与现有 catalog 的区分（非重复）

现有 `catalog/skills/craft/` 下的 `shuangwen-techniques`、`scene-pacing` 是**写作技巧层**（怎么写好爽点、怎么控节奏）——是方法。本 Task 的桥段图集是**素材/种子层**（"宗门考核""拍卖会""秘境探索"等可复用桥段组合体，每个带资源需求/爽点类型/消费时机）——是可直接查阅的积木。两者层次不同，不重复。

### 决策（已确认）

- **范围 1A**：初版只覆盖训练数据有把握的 8 个题材簇（修仙/玄幻/西幻领主/无限流/克苏鲁序列/基建穿越/都市灵气/悬疑），每簇 5~8 个桥段，初版约 40~60 个。冷门题材（官场重生流、诡异流细分、快穿细节）留空待补，不凭记忆编造。
- **形态 2A**：新建独立 skill `catalog/skills/expansions/scenario-atlas/`，作为 world Agent 可选输入素材库，不塞进现有 expansion。
- **验证 3**：必须实跑一次生成验证——用一个图集覆盖的题材跑 world_contract，对比有/无图集时钩子密度差异。无生成验证则视为未完成。

## 优化

### 优化 1：新建 scenario-atlas skill

按 expansion skill 标准四件套建立：

```
catalog/skills/expansions/scenario-atlas/
├── metadata.yaml   # lifecycle: experiment（实验包，待生成验证后转 active）
├── contract.yaml   # inputs: architecture+strategy；outputs: 无（素材库非生成器）；invariants
├── prompt.md       # 桥段图集本体：8 题材簇 × 5~8 桥段
└── provenance.yaml # origin: target-native（训练数据提炼，非迁移）
```

### 优化 2：桥段条目结构

每个桥段含四字段（对应文档第八章"资源库灵魂"）：

```yaml
桥段名: 宗门考核
题材簇: 修仙
资源需求: [宗门场地, 考核规矩, 评委长老, 奖品资源]
爽点类型: 扮猪吃虎 / 打脸装逼
消费时机: 主角入门期（第一卷）
变体: [隐藏实力考核, 故意压分, 越级挑战, 当众突破]
```

### 优化 3：prompt.md 的使用指引

明确 world Agent 的查阅方式：按当前项目题材簇检索相关桥段，作为 world_contract 生成时的"钩子灵感源"，**不是强制拼装件**——world Agent 仍按 architecture/strategy 自由组织形态（呼应 Task 19 的结论：组织形态题材相关，不强制）。

## 改动文件

| 文件 | 变更 |
|---|---|
| `catalog/skills/expansions/scenario-atlas/metadata.yaml` | 新建（lifecycle: experiment） |
| `catalog/skills/expansions/scenario-atlas/contract.yaml` | 新建 |
| `catalog/skills/expansions/scenario-atlas/prompt.md` | 新建（8 题材簇 × 5~7 桥段本体，约 45 个） |
| `catalog/skills/expansions/scenario-atlas/provenance.yaml` | 新建（target-native） |

注：`catalog_disposition.csv` 是历史迁移清单（锁 138 行），target-native 新建 skill 不进该 CSV。scenario-atlas 直接以目录形态存在于 `catalog/skills/expansions/`，由 `experiment_package_count` 自然计入（8→9）。

## 来源信息

- 来源文档：`documentation/worldbuilding-redesign.md` 第二十二条 22.4、第八章"资源库的灵魂"
- 内容来源：主控智能体训练数据对约 25 本主流网文的 world_contract 骨架级知识（覆盖 8 题材簇）
- 决策记录：1A（只做有把握题材）+ 2A（独立 skill）+ 3（要求生成验证）

## 验收标准

- [ ] `catalog/skills/expansions/scenario-atlas/` 四件套齐全（metadata/contract/prompt/provenance）。
- [ ] prompt.md 覆盖 8 个题材簇，每簇 5~8 个桥段，每个桥段含四字段（资源需求/爽点类型/消费时机/变体）。
- [ ] 每个题材簇的桥段源自训练数据有把握的作品，不凭记忆编造冷门题材（冷门留空）。
- [ ] metadata 的 `lifecycle: experiment`（未经生成验证前不转 active）。
- [ ] `tasks/migration/catalog_disposition.csv` 新增 scenario-atlas 行，`--check` 通过。
- [ ] **生成验证（决策 3）**：用一个图集覆盖的题材（建议修仙或都市灵气，与西幻对冲）实跑一次 world_contract 生成，对比有/无图集时的钩子密度。验证记录写入 task 的完成证据。
- [ ] 现有测试全部通过。
- [ ] `compileall` 通过。

## 验证命令

```bash
.venv/bin/python scripts/build_catalog_manifest.py --check
.venv/bin/python -m unittest discover -s tests -v
PYTHONWARNINGS='error::ResourceWarning' PYTHONPATH=mcp/novelos/src .venv/bin/python -m unittest discover -s mcp/novelos/tests -v
.venv/bin/python -m compileall -q tests mcp/novelos/src mcp/novelos/tests scripts catalog config
```

## 完成条件

三个优化全部落地、catalog 校验与现有测试通过、**生成验证已执行并记录**、验收项全部勾选，才可将本任务标记为 `DONE`。生成验证若发现图集无改善效果，应记录为"经评估图集价值不显著"并在文档更新，而非强行标 DONE。

## 风险与回退

- **内容质量风险**：桥段若泛泛（如"打脸"写成"主角打败对手"无细节），world Agent 取用无益。每个桥段的四字段必须具体到可操作。
- **覆盖偏差**：初版只覆盖热门题材，冷门题材项目无图集可用。这是 1A 的已知取舍，待后续 Task 补冷门。
- **回退方式**：删除 `scenario-atlas/` 目录 + 移除 CSV 行即可完全回退，不影响任何现有 skill 或权威数据。
- **生成验证失败的处理**：若验证发现图集反而降低产出质量，应取消本 Task（参考 Task 19 的取消先例），不强行上线。
