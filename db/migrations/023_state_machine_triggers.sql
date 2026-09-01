-- 023_state_machine_triggers.sql（R9 P0-5 / M7 状态机纸面化收口）
--
-- 背景：R9 红队 B 组判定——27 表零 TRIGGER，锁定/接受/裁决互锁只有 gate.mjs 单层防线，
-- 裸 SQL 直写（sql-reference.md 通道）全部绕过（免审锁定/免审接受/accepted 直改/裁决期
-- 锁定四个实验 VERIFIED）。本迁移把四条状态机约束下沉为 DB 层 TRIGGER 第二防线：
-- gate 是第一层（友好报错+事务语义），TRIGGER 是第二层（任何 UPDATE 通道都拦）。
--
-- 作用面声明（有意收窄）：只拦 UPDATE 翻转，不拦 INSERT——存量数据/导入/回填工具
-- 需要直插 locked/accepted 行的能力（019「存量不回填」先例）；新建行走
-- candidate/draft → gate → locked/accepted 是唯一正道，INSERT 期伪造锁定由
-- 资源链与 review 关联审计兜底。此残余面在 tasks/R9-redteam-fullchain.md 留痕。
--
-- 生产库应用照 021/022 先例：备份 → 单事务应用 + 版本登记 23 → integrity_check
-- → 攻防双验（免审路径 MUST ABORT；gate 正道 MUST PASS）。未获用户裁决前不落生产库。

-- T1 锁定须绑定 approved 且 subject 相符的回执（封免审锁定 B-1 + rejected/错绑回执绑定 B-5）
CREATE TRIGGER trg_planning_assets_lock_review
BEFORE UPDATE OF status, locked_review_id ON planning_assets
WHEN NEW.status = 'locked' AND OLD.status IS NOT 'locked'
BEGIN
    SELECT RAISE(ABORT,
        'trg_planning_assets_lock_review: 锁定被拒——locked 资产必须绑定 verdict=approved 且 subject_ref 相符的回执（R9 M7；正道 = gate lock-asset）')
    WHERE NOT EXISTS (
        SELECT 1 FROM reviews r
        WHERE r.id = NEW.locked_review_id
          AND r.verdict = 'approved'
          AND r.subject_ref = NEW.id
    );
END;

-- T2 章节接受须 review_id 留痕且 approved 相符（封免审接受 B-2）
CREATE TRIGGER trg_chapters_accept_review
BEFORE UPDATE OF status, review_id ON "chapters"
WHEN NEW.status = 'accepted' AND OLD.status IS NOT 'accepted'
BEGIN
    SELECT RAISE(ABORT,
        'trg_chapters_accept_review: 接受被拒——accepted 章节必须绑定 verdict=approved 且 subject_ref 相符的回执（R9 M7；正道 = gate accept-chapter）')
    WHERE NOT EXISTS (
        SELECT 1 FROM reviews r
        WHERE r.id = NEW.review_id
          AND r.verdict = 'approved'
          AND r.subject_ref = NEW.id
    );
END;

-- T3 已接受章节保持 accepted 时禁止换内容/版本（封免审直改 B-2；
--    合法修订路径 = 降级 draft → 改 → 重审 → 重接受，降级本触发器不拦）
CREATE TRIGGER trg_chapters_accepted_immutable
BEFORE UPDATE OF content_resource_id, version ON "chapters"
WHEN OLD.status = 'accepted' AND NEW.status = 'accepted'
    AND (NEW.content_resource_id IS NOT OLD.content_resource_id
         OR NEW.version IS NOT OLD.version)
BEGIN
    SELECT RAISE(ABORT,
        'trg_chapters_accepted_immutable: 已接受章节不得免审直改内容——降级 draft → 修改 → 重审 → 重接受（AGENTS.md 状态机约束；R9 M7）');
END;

-- T4a/T4b 裁决互锁下沉 DB 层（022 的互锁原只是 gate 查询逻辑——直写可绕过，B-3/C+E-4）
CREATE TRIGGER trg_adjudication_interlock_planning
BEFORE UPDATE OF status ON planning_assets
WHEN NEW.status = 'locked' AND OLD.status IS NOT 'locked'
BEGIN
    SELECT RAISE(ABORT,
        'trg_adjudication_interlock_planning: 该 subject 存在 open 裁决单——互锁期禁止锁定（R8/A5；先 resolve-adjudication）')
    WHERE EXISTS (
        SELECT 1 FROM adjudications a
        WHERE a.status = 'open' AND a.subject_ref = NEW.id
    );
END;

CREATE TRIGGER trg_adjudication_interlock_chapters
BEFORE UPDATE OF status ON "chapters"
WHEN NEW.status = 'accepted' AND OLD.status IS NOT 'accepted'
BEGIN
    SELECT RAISE(ABORT,
        'trg_adjudication_interlock_chapters: 该 subject 存在 open 裁决单——互锁期禁止接受（R8/A5；先 resolve-adjudication）')
    WHERE EXISTS (
        SELECT 1 FROM adjudications a
        WHERE a.status = 'open' AND a.subject_ref = NEW.id
    );
END;
