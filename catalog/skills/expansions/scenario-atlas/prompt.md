# 桥段图集（Scenario Atlas）

本图集是跨题材的可复用桥段组合体清单，供 World Agent 在生成 `world_contract` 时按当前项目题材检索，作为"钩子灵感源"。**它不是强制拼装件**——World Agent 仍按已锁定的 Architecture 与 Strategy 自由组织世界契约形态（一份大契约 / 切片 / 树形，按题材自选）。

> 本文件是索引。每个题材簇的完整桥段清单、消费时序表与启发式推演提示放在 `clusters/<题材>.md`。簇文件格式规范见 `clusters/README.md`。

## 使用方式

1. 按当前项目的一级题材与二级方向，在下方"题材簇索引"定位对应的簇文件。
2. 打开该簇文件，浏览桥段，挑选与 Architecture 核心引擎、Strategy 阶段目标匹配的作为钩子灵感。
3. 每个桥段的四字段回答："这个桥段需要什么世界资源支撑、产什么爽点、在第几卷消费、有哪些变体"。
4. 阅读簇文件末尾的"启发式推演提示"，按本书差异推导图集未覆盖的衍生桥段。
5. 将选中的桥段按 world-contract 的"结构性消费约束"标注消费时机，融入世界契约。
6. **图集未覆盖的细分题材不要硬套**——遇到未覆盖题材应依靠 Architecture/Strategy 约束直接推导，而非误用不相关桥段。

## 题材簇索引

按"世界观支柱强度"和"网文市场占比"排序。**主流高频题材**（修仙/玄幻/系统流/重生都市）放在前面，作为最常被检索的母题。

| 文件 | 题材簇 | 桥段数 | 主要世界观支柱 | 典型代表作 |
|---|---|---|---|---|
| [clusters/xiuxian.md](clusters/xiuxian.md) | 修仙 | 10 | 境界 / 宗门 / 天劫 / 法宝 | 《凡人修仙传》《完美世界》《仙逆》 |
| [clusters/xuanhuan.md](clusters/xuanhuan.md) | 玄幻 | 9 | 血脉 / 学院 / 家族 / 异火 | 《斗破苍穹》《遮天》《武动乾坤》 |
| [clusters/system.md](clusters/system.md) | 系统流 | 9 | 签到 / 任务 / 商城 / 兑换 | 签到 / 任务 / 抽奖类系统文 |
| [clusters/rebirth-urban.md](clusters/rebirth-urban.md) | 重生都市 | 9 | 重生 / 创业 / 文抄 / 金融 | 都市重生经商 / 娱乐圈类 |
| [clusters/wuxia.md](clusters/wuxia.md) | 武侠 | 9 | 江湖 / 武功 / 神兵 / 盟主 | 《天龙八部》《雪中悍刀行》 |
| [clusters/alternate-history.md](clusters/alternate-history.md) | 架空历史 | 9 | 穿越落地 / 攀科技 / 夺嫡 / 称帝 | 《回到明朝当王爷》《唐砖》《赘婿》 |
| [clusters/infinite.md](clusters/infinite.md) | 无限流 | 10 | 主神空间 / 副本 / 兑换 | 《无限恐怖》《轮回乐园》 |
| [clusters/cthulhu.md](clusters/cthulhu.md) | 克苏鲁 / 序列流 | 10 | 序列 / 魔药 / 污染 / 神位 | 《诡秘之主》 |
| [clusters/western-lord.md](clusters/western-lord.md) | 西幻 / 领主 | 10 | 领地 / 封建 / 教会 / 联姻 | 《放开那个女巫》西幻领主经营 |
| [clusters/urban-qi.md](clusters/urban-qi.md) | 都市灵气 | 11 | 觉醒 / 隐秘组织 / 隐世家族 | 都市灵气复苏类 |
| [clusters/downturn.md](clusters/downturn.md) | 末世 / 废土 | 11 | 异变 / 基地 / 人性 / 进化 | 《末日乐园》《全球进化》 |
| [clusters/isekai-build.md](clusters/isekai-build.md) | 基建 / 穿越 | 9 | 科技树 / 种田 / 贸易 / 军事 | 《临高启明》 |
| [clusters/beast-taming.md](clusters/beast-taming.md) | 御兽 / 召唤 | 10 | 契约 / 进化 / 对战 / 图鉴 | 《宠魅》《御兽修仙》 |
| [clusters/game-esports.md](clusters/game-esports.md) | 游戏流 / 电竞 | 10 | 副本 / 公会 / 赛事 / 版本 | 网游 / 电竞类 |
| [clusters/interstellar.md](clusters/interstellar.md) | 星际 / 太空歌剧 | 9 | 跃迁 / 机甲 / 殖民 / 文明 | 《机动风暴》星际网文 |
| [clusters/cyberpunk.md](clusters/cyberpunk.md) | 赛博 / 近未来 | 9 | 义体 / 企业 / 网络 / AI | 赛博朋克类网文 |
| [clusters/tomb-exploration.md](clusters/tomb-exploration.md) | 盗墓 / 探险 | 10 | 古墓 / 风水 / 明器 / 粽子 | 《鬼吹灯》《盗墓笔记》 |
| [clusters/mystery.md](clusters/mystery.md) | 悬疑 | 11 | 案件 / 线索 / 体制 / 侧写 | 《心理罪》《长夜难明》 |
| [clusters/officialdom.md](clusters/officialdom.md) | 官场重生 | 11 | 派系 / 政绩 / 升迁 / 民心 | 体制升迁类 |
| [clusters/horror-rules.md](clusters/horror-rules.md) | 诡异流 / 规则怪谈 | 11 | 规则 / 异常 / 直播 / 串联 | 规则怪谈类 |
| [clusters/quick-transmigration.md](clusters/quick-transmigration.md) | 快穿流 | 11 | 位面 / 系统 / 气运 / 反派 | 快穿位面类 |
| [clusters/female-ancient.md](clusters/female-ancient.md) | 女频古言 | 10 | 嫡庶 / 宅斗 / 宫斗 / 联姻 / 内宅 | 《知否知否应是绿肥红瘦》《庶女攻略》《嫡谋》 |
| [clusters/female-modern.md](clusters/female-modern.md) | 女频现言 | 10 | 甜宠 / 虐恋 / 霸总 / 追妻火葬场 / 年代文 / 娱乐圈 | 《你给我的喜欢》《慈悲城》《三分野》《掌中娇》 |
| [clusters/military.md](clusters/military.md) | 军事 / 谍战 | 11 | 特战 / 兵王 / 谍战 / 战争 / 军旅 | 《特战兵王》《谍影：命令与征服》《刀尖》《伪装者》 |
| [clusters/sports.md](clusters/sports.md) | 体育竞技 | 10 | 球队 / 联赛 / 训练 / 伤病 / 转会 / 战术 | 《篮坛传奇崛起》《冠军教父》《火爆巨星》《球王贝斯特》 |
| [clusters/fanfic.md](clusters/fanfic.md) | 同人 / 综漫 | 11 | 原著借用 / 原著人物 / CP / 原著节点 / 综漫融合 | 综漫同人 / 影视同人 / 四合院系列 / 综英美 |

**总计**：26 题材簇，262 桥段。每簇含"开篇—中段—后段"三段消费时机分布。

## 题材选择指引

当项目题材跨多个簇时，按以下优先级检索：

- **一级题材是修仙/仙侠**：主查 `xiuxian.md`，副查 `system.md`（系统流修仙常见）、`xuanhuan.md`（玄幻修仙混血）。
- **一级题材是玄幻**：主查 `xuanhuan.md`，副查 `xiuxian.md`（境界体系混血）、`system.md`。
- **一级题材是都市**：根据二级方向选——`rebirth-urban.md`（重生经商/娱乐圈）、`urban-qi.md`（灵气复苏/隐世家族）、`officialdom.md`（官场）、`game-esports.md`（电竞）、`female-modern.md`（女频现言：甜宠/虐恋/霸总/追妻火葬场/年代文/娱乐圈女频）。
- **一级题材是科幻**：根据二级方向选——`interstellar.md`（太空歌剧）、`cyberpunk.md`（赛博）、`downturn.md`（末世）、`infinite.md`（无限流常被归入科幻）。
- **一级题材是悬疑**：主查 `mystery.md`，副查 `horror-rules.md`（诡异流混血）。
- **一级题材是历史/武侠**：根据二级方向选——`alternate-history.md`（架空历史/穿越改写，主查）、`wuxia.md`（江湖武侠）、`isekai-build.md`（基建种田向的穿越）、`officialdom.md`（古代朝堂/现代体制）、`female-ancient.md`（女频古言：宅斗/宫斗/种田/穿越古言/重生古言）。
- **一级题材是游戏**：主查 `game-esports.md`，副查 `infinite.md`（无限流近似）。
- **一级题材是体育竞技**：主查 `sports.md`（篮球/足球/网球等真实项目），副查 `game-esports.md`（电竞 vs 传统体育的分野见跨簇说明）、`rebirth-urban.md`（重生竞技 vs 重生经商的分野见跨簇说明）。
- **一级题材是同人 / 综漫**：主查 `fanfic.md`（综漫/影视同人/原著偏离/CP），副查 `quick-transmigration.md`（同人穿入原著 vs 快穿位面的分野见跨簇说明）、`infinite.md`（综漫同人 vs 无限流副本的分野见跨簇说明）。
- **一级题材是军事**：主查 `military.md`（特战兵王/谍战/战争/军旅），副查 `alternate-history.md`（古代平乱征战 vs 现代军事的分野见跨簇说明）、`cyberpunk.md`（近未来佣兵/PMC）、`urban-qi.md`（都市兵王/军方介入超凡）。
- **女频题材（主角为女性、爽点为情感/内宅/打脸/撒糖）**：根据时代背景选——`female-ancient.md`（古代：宅斗/宫斗/种田/穿越/重生）、`female-modern.md`（现代：甜宠/虐恋/霸总/追妻火葬场/年代文/娱乐圈）；女频快穿另查 `quick-transmigration.md`。女频与男频共享世界结构但视角与爽点迥异，跨簇说明已标注分野，**勿将男频母题硬套到女频项目**。
- **跨题材无法定位**：先按 Architecture 的核心引擎（升级 / 经营 / 解谜 / 生存 / 博弈）归类，再选对应簇。升级→修仙/玄幻/系统；经营→领主/基建/重生都市；解谜→悬疑/诡异流；生存→末世/无限流/盗墓；博弈→武侠/赛博/星际。

## 覆盖说明

本图集 v0.3.1 覆盖 26 个题材簇共 262 桥段。内容源自主控智能体训练数据对主流网文（约 25 本）的题材共性提炼 + WebSearch 对各题材套路段的素材补充（共 30+ 次查询，提炼读者批评用于反套路小节），非具体作品复制。每个桥段含五字段（资源需求 / 爽点类型 / 消费时机 / 变体 + 消费绑定提示），每个簇另含消费时序表、3+ 个启发式母题、反套路风险、未覆盖子流派推导路径。跨簇相似母题（如攀科技树、制度改革、退婚流、女频古言 vs 男频架空历史、女频年代文 vs 男频重生都市、传统体育 vs 电竞、重生竞技 vs 重生经商、同人穿入原著 vs 快穿位面、综漫同人 vs 无限流副本、现代军事 vs 古代平乱）通过"跨簇说明"字段明确分工，避免 World Agent 误用。v0.3.1 一次性补齐 5 大覆盖缺口：女频古言、女频现言（补齐此前纯男频导向的最大缺口）、军事/谍战、体育竞技、同人/综漫。

World Agent 遇到仍未覆盖的细分题材时，应依靠 Architecture 与 Strategy 的约束直接推导世界契约，不强行套用不相关桥段。簇文件末尾的启发式推演提示就是为了支持这种"从已有母题衍生新桥段"的推导。
