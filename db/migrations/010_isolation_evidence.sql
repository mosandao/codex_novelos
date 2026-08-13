-- agent_run 必须携带隔离执行凭据（isolation_evidence）才能进入权威提交。
-- 该列可空：普通 run（探索、失败、统计）不需要凭据；只有 producer/reviewer run
-- 在 lock / accept / promote 路径被 _validate_authority_trace 强制要求非空。
-- 凭据是声明性证明（JSON），如 {"source":"codex_task","agent_id":"agent_xxx"}，
-- 用于把"随手自审可锁定"提升为"必须显式提供执行来源"，并留痕便于审计。
-- 真实模型上下文隔离仍由 主控智能体 用独立 Codex Task 创建 sub-agent 兑现。
ALTER TABLE agent_runs ADD COLUMN isolation_evidence TEXT;
