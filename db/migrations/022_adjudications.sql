-- 022 · TBD 物化（R8-T2，修正案 A5；对抗审查 P4-5 成立判处置）
-- 背景：审查 3 轮未收敛/同因复发/mismatch 升级用户裁决时，流程只「挂起」——
-- 无落盘产物记录卡住的 subject 与各轮 blocking 摘要，下游无感知，理论上可在
-- 未决资产之上继续写下一章（升级=不可恢复状态）。
-- 变更：新增 adjudications 表（一 subject 至多一条 open——部分唯一索引强制）：
--   · open 行 = 未决裁决的库内权威事实（subject + reason + 各轮 blocking 摘要 rounds_json）；
--   · 门互锁：lock-asset / accept-chapter 遇 subject 存在 open 行 → GateFail（先裁决后推进）；
--     commit-review 不拦（裁决期间补审查是合法输入）、propagate-stale 不拦（标记下游
--     恰是裁决影响面的一部分）；
--   · 下游注入可见：composer 槽 open_adjudications（项目内 open 行渲染为警示节）。
-- 存量不回填（照 019/021 先例——本表为纯新增，无存量语义）。
-- 幂等/回滚：单事务应用，任一步失败整体回滚零写入；应用前先复制库文件备份。

CREATE TABLE adjudications (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    subject_type TEXT NOT NULL,
    subject_ref TEXT NOT NULL,
    reason TEXT NOT NULL,
    rounds_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved')),
    resolution TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

-- 同 subject 至多一条 open（重复开单在 DB 层即拒绝，gate 只做友好报错）
CREATE UNIQUE INDEX idx_adjudications_open_subject
    ON adjudications(project_id, subject_type, subject_ref) WHERE status = 'open';

CREATE INDEX idx_adjudications_project ON adjudications(project_id, status);
