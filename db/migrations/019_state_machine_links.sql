-- NovelOS 状态机写门：章节↔审查绑定列（对抗审查封旁路补丁）。
--
-- 背景：chapters 表此前无 review 关联列，章节接受可绕开审查直改
-- （novel-writing SKILL 裸 SQL `UPDATE chapters SET status='accepted'`），
-- 机器痕迹缺失。本迁移给 chapters 增加 review_id 外键列：
-- 接受路径由门工具 novelos_accept_chapter 强制校验 approved review
-- 并写入本列，形成「哪条审查接受了本章」的可追溯绑定。
--
-- SQLite ADD COLUMN 支持带 REFERENCES 的可空列（默认 NULL），只增列不重建表。
-- 存量行 review_id 保持 NULL——历史已接受章节不回填（回填须经重审走门工具）。
-- 生产库 data/novelos-v2.db 不由本仓库手工执行；迁移只在测试内存库
-- （经 db/migrations/schema.sql 重生成基线）与未来真实运行时经门生效。

ALTER TABLE chapters ADD COLUMN review_id TEXT REFERENCES reviews(id);
