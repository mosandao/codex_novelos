# Task 27：craft skill 标准补齐（通俗度/开头/钩子强度）

## 状态

`DONE`（prose-webnovel-accessibility craft skill + 三端引用全部落地）

## 背景

外部商业网文评估报告暴露三个审查盲区：通俗度/抽象度完全缺失、开头吸引力完全缺失、钩子强度只有"有无"二值判定。全 catalog skill 搜索"通俗""易懂""抽象度""钩子强度"——零命中。

在 Task 26 完成后的轻流程上补齐标准，让新维度低成本生效。

## 目标 / 优化

### 优化 1：新建 craft skill `prose-webnovel-accessibility`

**目录**：`catalog/skills/craft/prose-webnovel-accessibility/`

三个检查维度：
- **§1 通俗度与抽象修辞节制**：抽象修辞链 ≤1、书面化动词 ≤3、面向 90% 读者
- **§2 开头吸引力**：前 3 段用具体物/动作/对话切入，禁止纯意象开头
- **§3 钩子强度**：强/中/弱三级，开篇章必须强钩子，禁止弱钩子

### 优化 2：三端引用

| 端 | 文件 | 引用方式 |
|---|---|---|
| writer | `catalog/skills/writing/chapter-draft-generation/prompt.md` | 方法素材段追加 |
| reviewer | `catalog/skills/review/prose-quality-review/prompt.md` | 方法素材段 + 检查维度段追加 |
| 章纲 | `catalog/skills/planning/chapter-plan-execution-card/prompt.md` | 钩子段加强度分级 + metadata `hook_strength` |

## 改动文件

| 文件 | 变更 |
|---|---|
| `catalog/skills/craft/prose-webnovel-accessibility/metadata.yaml` | 新建 |
| `catalog/skills/craft/prose-webnovel-accessibility/prompt.md` | 新建 |
| `catalog/skills/craft/prose-webnovel-accessibility/provenance.yaml` | 新建 |
| `catalog/skills/writing/chapter-draft-generation/prompt.md` | 方法素材段追加引用 |
| `catalog/skills/review/prose-quality-review/prompt.md` | 方法素材段 + 检查维度追加 |
| `catalog/skills/planning/chapter-plan-execution-card/prompt.md` | 钩子段加强度分级 |
| `tasks/27_prose_webnovel_accessibility.md` | 本文件 |
| `tasks/README.md` | 登记 |

## 来源信息

- 触发实例：第一章正文外部评估报告（3 份），trace `trace:0f752896`
- 缺口实证：全 catalog skill 搜索"通俗""易懂""抽象度"——零命中

## 验收标准

- [x] prose-webnovel-accessibility 目录下 3 个文件齐全
- [x] chapter-draft-generation 引用新 skill
- [x] prose-quality-review 引用新 skill + 检查维度
- [x] chapter-plan-execution-card 钩子段包含强度分级
- [x] compileall 通过
