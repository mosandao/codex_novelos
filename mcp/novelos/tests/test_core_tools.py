from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from novelos_mcp import NovelOSError, NovelOSService
from agent_test_support import complete_review_run


class CoreToolsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary.name) / "novelos.db"
        self.service = NovelOSService(self.database)
        self.project = self.service.create_project("核心工具", metadata={"owner": "author"})
        self.trace = self.service.start_trace("core-tools", self.project["id"])
        self.book = self.service.create_book(self.project["id"], "第一部", "书说明")
        self.volume = self.service.create_volume(self.book["id"], 1, "第一卷", "卷说明")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_hierarchy_create_get_list_and_pagination(self) -> None:
        self.assertEqual("author", self.service.get_project(self.project["id"])["metadata"]["owner"])
        self.assertEqual([self.project["id"]], [item["id"] for item in self.service.list_projects()])
        self.assertEqual(self.book["id"], self.service.get_book(self.book["id"])["id"])
        self.assertEqual([self.book["id"]], [item["id"] for item in self.service.list_books(self.project["id"])])
        self.assertEqual(self.volume["id"], self.service.get_volume(self.volume["id"])["id"])
        self.assertEqual([self.volume["id"]], [item["id"] for item in self.service.list_volumes(self.book["id"])])
        with self.assertRaisesRegex(NovelOSError, "invalid_pagination"):
            self.service.list_projects(limit=0)
        with self.assertRaisesRegex(NovelOSError, "not_found"):
            self.service.get_book("book:not-found")

    def test_duplicate_volume_rolls_back(self) -> None:
        with self.assertRaisesRegex(NovelOSError, "conflict"):
            self.service.create_volume(self.book["id"], 1, "重复卷")
        self.assertEqual(1, len(self.service.list_volumes(self.book["id"])))

    def test_duplicate_chapter_rolls_back_new_resource(self) -> None:
        self.service.create_chapter_draft(self.volume["id"], 1, "第一章", "第一版正文")
        with self.service.database.read() as connection:
            before = connection.execute("SELECT COUNT(*) FROM resources").fetchone()[0]
        with self.assertRaisesRegex(NovelOSError, "conflict"):
            self.service.create_chapter_draft(self.volume["id"], 1, "重复第一章", "不应保留的正文")
        with self.service.database.read() as connection:
            after = connection.execute("SELECT COUNT(*) FROM resources").fetchone()[0]
        self.assertEqual(before, after)
        self.assertEqual(1, len(self.service.list_chapters(self.volume["id"])))

    def test_two_clients_cannot_update_same_draft_version(self) -> None:
        draft = self.service.create_chapter_draft(self.volume["id"], 1, "第一章", "第一版")
        other = NovelOSService(self.database)
        changed = other.update_chapter_draft(draft["id"], draft["version"], "第二版")
        self.assertEqual(2, changed["version"])
        with self.assertRaisesRegex(NovelOSError, "stale_version"):
            self.service.update_chapter_draft(draft["id"], draft["version"], "冲突版本")

    def test_accepted_chapter_is_immutable_and_can_be_superseded(self) -> None:
        draft = self.service.create_chapter_draft(self.volume["id"], 1, "第一章", "正文")
        _, review = complete_review_run(
            self.service,
            self.trace["id"],
            "chapter",
            draft["id"],
            draft["subject_hash"],
            "prose-v1",
            evidence_refs=[draft["resource_ref"]],
        )
        self.assertEqual(review["id"], self.service.get_review(review["id"])["id"])
        accepted = self.service.accept_chapter(
            draft["id"], review["id"], draft["version"], self.trace["id"]
        )
        with self.assertRaisesRegex(NovelOSError, "invalid_state"):
            self.service.update_chapter_draft(accepted["id"], accepted["version"], "非法修改")
        superseded = self.service.supersede_chapter(accepted["id"], accepted["version"])
        self.assertEqual("superseded", superseded["status"])

    def test_superseded_chapter_number_can_be_reused(self) -> None:
        # supersede 释放 (volume_id, number) 槽位，支持重写已接受章节。
        first = self.service.create_chapter_draft(self.volume["id"], 1, "第一章", "旧版正文")
        _, review = complete_review_run(
            self.service,
            self.trace["id"],
            "chapter",
            first["id"],
            first["subject_hash"],
            "prose-v1",
            evidence_refs=[first["resource_ref"]],
        )
        accepted = self.service.accept_chapter(first["id"], review["id"], first["version"], self.trace["id"])
        self.service.supersede_chapter(accepted["id"], accepted["version"])

        # 同号重建 draft 应成功（不再 conflict）
        rewritten = self.service.create_chapter_draft(self.volume["id"], 1, "第一章", "重写正文")
        self.assertEqual("draft", rewritten["status"])
        self.assertNotEqual(accepted["subject_hash"], rewritten["subject_hash"])

        # list_chapters 返回两条（1 superseded + 1 draft）
        chapters = self.service.list_chapters(self.volume["id"])
        self.assertEqual(2, len(chapters))
        statuses = {ch["status"] for ch in chapters}
        self.assertEqual({"superseded", "draft"}, statuses)

        # 两个 draft 同号仍应冲突（部分唯一索引保证 draft/accepted 互斥）
        with self.assertRaisesRegex(NovelOSError, "conflict"):
            self.service.create_chapter_draft(self.volume["id"], 1, "再次重复", "第三版正文")

    def test_accepted_chapter_can_be_revised_and_reaccepted(self) -> None:
        # 完整循环：draft → accept → revise → update → review → accept
        draft = self.service.create_chapter_draft(self.volume["id"], 1, "第一章", "原始正文")
        _, review = complete_review_run(
            self.service,
            self.trace["id"],
            "chapter",
            draft["id"],
            draft["subject_hash"],
            "prose-v1",
            evidence_refs=[draft["resource_ref"]],
        )
        accepted = self.service.accept_chapter(draft["id"], review["id"], draft["version"], self.trace["id"])
        self.assertEqual("accepted", accepted["status"])
        self.assertEqual(2, accepted["version"])

        # revise：accepted → draft，保留 chapter_id
        revised = self.service.revise_chapter(accepted["id"], accepted["version"], self.trace["id"], reason="局部措辞调整")
        self.assertEqual("draft", revised["status"])
        self.assertEqual(3, revised["version"])
        self.assertEqual(accepted["id"], revised["id"])

        # 局部修改内容（subject_hash 随之变化）
        updated = self.service.update_chapter_draft(revised["id"], revised["version"], "修订后正文")
        self.assertEqual(4, updated["version"])
        self.assertNotEqual(accepted["subject_hash"], updated["subject_hash"])

        # 旧 review 因 hash 不匹配失效；新 review 绑定新 hash
        _, review2 = complete_review_run(
            self.service,
            self.trace["id"],
            "chapter",
            updated["id"],
            updated["subject_hash"],
            "prose-v1",
            evidence_refs=[updated["resource_ref"]],
        )
        reaccepted = self.service.accept_chapter(updated["id"], review2["id"], updated["version"], self.trace["id"])
        self.assertEqual("accepted", reaccepted["status"])
        self.assertEqual(5, reaccepted["version"])
        self.assertEqual(accepted["id"], reaccepted["id"])

    def test_only_accepted_chapter_can_be_revised(self) -> None:
        # draft 状态不可 revise
        draft = self.service.create_chapter_draft(self.volume["id"], 1, "第一章", "正文")
        with self.assertRaisesRegex(NovelOSError, "invalid_state"):
            self.service.revise_chapter(draft["id"], draft["version"], self.trace["id"])

        # accept → supersede 后也不可 revise
        _, review = complete_review_run(
            self.service,
            self.trace["id"],
            "chapter",
            draft["id"],
            draft["subject_hash"],
            "prose-v1",
            evidence_refs=[draft["resource_ref"]],
        )
        accepted = self.service.accept_chapter(draft["id"], review["id"], draft["version"], self.trace["id"])
        superseded = self.service.supersede_chapter(accepted["id"], accepted["version"])
        with self.assertRaisesRegex(NovelOSError, "invalid_state"):
            self.service.revise_chapter(superseded["id"], superseded["version"], self.trace["id"])

    def test_revise_requires_running_trace_in_same_project(self) -> None:
        draft = self.service.create_chapter_draft(self.volume["id"], 1, "第一章", "正文")
        _, review = complete_review_run(
            self.service,
            self.trace["id"],
            "chapter",
            draft["id"],
            draft["subject_hash"],
            "prose-v1",
            evidence_refs=[draft["resource_ref"]],
        )
        accepted = self.service.accept_chapter(draft["id"], review["id"], draft["version"], self.trace["id"])

        # 另一个项目的 trace
        other_project = self.service.create_project("其他项目")
        other_trace = self.service.start_trace("other", other_project["id"])
        with self.assertRaisesRegex(NovelOSError, "trace_project_mismatch"):
            self.service.revise_chapter(accepted["id"], accepted["version"], other_trace["id"])
        self.service.finish_trace(other_trace["id"], "completed")

        # 已结束的 trace
        self.service.finish_trace(self.trace["id"], "completed")
        new_trace = self.service.start_trace("revise-after-finish", self.project["id"])
        accepted_v2 = self.service.get_chapter(accepted["id"])
        self.service.finish_trace(new_trace["id"], "completed")
        with self.assertRaisesRegex(NovelOSError, "invalid_state"):
            self.service.revise_chapter(accepted_v2["id"], accepted_v2["version"], new_trace["id"])

    def test_delete_project_requires_no_active_trace_and_removes_projection(self) -> None:
        with self.assertRaisesRegex(NovelOSError, "运行中的 Trace"):
            self.service.delete_project(self.project["id"], self.project["version"], output_root=str(Path(self.temporary.name) / "projections"))

        project = self.service.create_project("待删除项目")
        book = self.service.create_book(project["id"], "第一部")
        volume = self.service.create_volume(book["id"], 1, "第一卷")
        self.service.create_chapter_draft(volume["id"], 1, "第一章", "待删除正文")
        output_root = Path(self.temporary.name) / "projections"
        rendered = self.service.render_project_projection(project["id"], output_root=str(output_root))

        deleted = self.service.delete_project(project["id"], project["version"], output_root=str(output_root))

        self.assertTrue(deleted["deleted"])
        self.assertEqual(1, deleted["deleted_records"]["books"])
        self.assertEqual(1, deleted["deleted_records"]["volumes"])
        self.assertEqual(1, deleted["deleted_records"]["chapters"])
        self.assertTrue(deleted["projection"]["removed"])
        self.assertFalse(Path(rendered["output_directory"]).exists())
        with self.assertRaisesRegex(NovelOSError, "not_found"):
            self.service.get_project(project["id"])


if __name__ == "__main__":
    unittest.main()
