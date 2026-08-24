# NovelOS Viewer · 产品架构与原型说明

> 产品定位：NovelOS 权威库的**纯只读可视化工作台**——DSH ui-panel 插件形态，浏览器内 sql.js(WASM) 直读 `data/novelos-v2.db`，全 JS 渲染，零 Python 参与视图链。
> 设计原则继承自对抗审查报告（`docs/plugin-feasibility-adversarial-review.md`）：快照制新鲜度 / 物理只读 / 零写路径 / 零 argv / 单渲染器。

---

## 一、产品架构图

```mermaid
flowchart TB
    subgraph DSH["DSH Web GUI (127.0.0.1:50876)"]
        CONV["对话区\n(主控 agent · 主模型可切换)"]
        PANEL["dsh-novelos-viewer 面板\n(ui-panel 路由页)"]

        subgraph CLIENT["插件 Client Bundle（纯 JS）"]
            SQLJS["sql.js (SQLite→WASM)\n内存只读打开"]
            VIEWS["视图渲染器×6\n总览/卷纲/章节/人物/世界/连续性"]
            ROLES["模型分工配置卡\n角色→provider/model 映射"]
        end

        subgraph HOST["插件 Host（Node）"]
            R1["GET /db-bytes\n整库文件字节流(唯一数据出口)"]
            R2["GET /manifest\nmtime+大小+schema版本"]
        end
    end

    subgraph NOVELOS["NovelOS 仓库（既有资产，零改动）"]
        DB[("data/novelos-v2.db\n权威库 25 表")]
        PY["legacy-python/scripts/novelos_*.py\n写路径校验门(过渡期,R2后JS化)"]
        MCP["SQLite MCP\nmcp-novelos-sqlite"]
        AGENTSK[".agents/skills/novel-*\n六个操作层技能"]
    end

    CONV -- "@项目 / 快照路径" --> PANEL
    PANEL -- "fetch 字节流" --> R1
    PANEL -- "新鲜度轮询" --> R2
    R1 -- "readFileSync 只读" --> DB
    R2 -- "stat()" --> DB
    SQLJS -- "new Database(bytes)" --> VIEWS

    CONV -- "读库查询" --> MCP --> DB
    CONV -- "落库(唯一写路径)" --> PY --> DB
    AGENTSK --> CONV

    style CLIENT fill:#1a1814,color:#e8e0d0,stroke:#b03a2e
    style DB fill:#232019,color:#e8e0d0,stroke:#8a7a52
    style HOST fill:#1a1814,color:#e8e0d0,stroke:#8a7a52
```

### 关键边界（红队整改项逐一落实）

| 边界 | 设计 |
|---|---|
| **物理只读** | sql.js 将 db 全量载入内存，WASM 实例无任何回写 API——面板结构上不可能污染权威库 |
| **零子进程** | 视图链无 Python spawn → cp936 编码雷 / 退出码歧义 / 僵尸进程三类 P0 整体消失 |
| **零参数注入面** | host 路由无任何入参，repoRoot 编译期常量——F3 路径穿越无从谈起 |
| **单渲染器** | HTML(JS) 是唯一人类视图；md 投影退役；模型侧走 SQLite MCP——无双实现漂移 |
| **快照新鲜度** | 页面常驻显示 db 文件 mtime+体积；「刷新」= 重拉字节流重建 WASM 实例 |
| **已知遗留（中危）** | db 字节经 50876 无鉴权可下载——本地单人使用可接受，后续可加 Host 校验 |

## 二、Agent 多模型分工架构

```mermaid
flowchart LR
    USER["用户"] --> ORCH["主控 Agent\n(编排·不写作)"]
    ORCH --> W["写作代理\n强创意模型\n如 deepseek-chat"]
    ORCH --> RV["审查代理\n异构厂商模型\n对抗性互查"]
    ORCH --> CTX["记忆/连续性代理\n快速廉价模型"]
    W & RV & CTX -- "结构化产出" --> GATE["Python 校验门\njsonschema + 事务\n(模型无关的兜底)"]
    GATE --> DB[("novelos-v2.db")]

    CONF["模型分工配置卡\n(设置卡 JSON)"] -.分配.-> ORCH
```

- 分配规则存于设置卡（角色→provider/model），改配置不改代码；
- 校验门在脚本层不依赖模型自觉——换弱模型只会 FAIL 阻断，不会脏库；
- 审查端刻意用异构厂商模型，利用「不同模型盲区不同」提升审查多样性。

## 三、信息架构（面板六视图）

1. **总览**——书卡（卷数/章数/字数/进度条）+ 各资产状态徽章（candidate/locked/stale 计数）
2. **卷纲**——卷型时间轴：每卷高潮门位置、单元编排、线弧跨度
3. **章节流**——按卷分组的状态流水（draft/review/accepted），点开看正文只读预览
4. **人物**——名册卡（席位/状态活死/出场卷分布）
5. **世界**——规则条目 + 势力/地点/物品索引
6. **连续性**——六账本候选与晋升状态 + 人物状态史审计

## 四、原型图

高保真交互原型见 [novelos-viewer-prototype.html](./novelos-viewer-prototype.html)（双击浏览器打开即可，内嵌模拟数据，布局即开发规格）。
