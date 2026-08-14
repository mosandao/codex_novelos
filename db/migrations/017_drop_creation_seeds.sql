-- NovelOS：删除创作种子表（creation_seeds）。
--
-- 背景：创作种子自 migration 013 建表以来从未获得写入通路——向导 JSON
-- (novelos.project.create.v1) 不含种子字段，任何 SKILL/流程也不写它，
-- 全库为空。用户原始意图的权威入口是向导「创作资料」(reference_material，
-- 上限 1 万字)，由方向智能体提炼消费（见 story-direction prompt）。
-- 保留空表 + 空投影文件 + prompt 死引用属于「无入口孤儿」，按 B 方案清除。
--
-- 表为空，DROP 零数据损失。

DROP TABLE IF EXISTS creation_seeds;
