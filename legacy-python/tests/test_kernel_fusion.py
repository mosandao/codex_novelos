from __future__ import annotations

import json
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.novelos_compose_prompt import (
    ASSET_DIRS,
    build_context_kernel_fusion,
    compose,
    resolve_slots,
    validate_kernel_fusion_payload,
)

from tests.test_slot_resolution import _make_db


def _create_payload() -> dict:
    return {
        "request_type": "novelos.project.create.v3",
        "setup": {
            "title": "内核测试书",
            "author_kernel": {
                "mode": "create",
                "kernel_hints": {
                    "taste_anchors": ["低温叙事"],
                    "people_and_scenes": ["基层技术官僚"],
                    "hard_nos": ["圣人视角"],
                    "obsessions": ["秩序的代价"],
                    "core_questions": ["秩序崩坏时普通人靠什么站住"],
                    "knowledge_domains": ["工程审计", "基层官僚运作"],
                },
            },
            "channel": "男频",
        },
    }


def _revise_payload() -> dict:
    return {
        "request_type": "novelos.kernel.revise.v1",
        "base_version": "cpv:k1",
        "kernel_hints": {"hard_nos": ["无代价的宽恕"]},
    }


def _seed_kernel(conn) -> None:
    kernel = {"schema_version": 1,
              "identity": {"display_name": "测试内核", "core_questions": ["秩序的代价"]}}
    conn.execute("INSERT INTO resources VALUES ('res:k1', CAST(? AS BLOB))",
                 (json.dumps(kernel, ensure_ascii=False),))
    conn.execute("INSERT INTO creator_profiles VALUES ('cp:k1', 'author_kernel', '测试内核')")
    conn.execute(
        "INSERT INTO creator_profile_versions VALUES "
        "('cpv:k1', 'cp:k1', NULL, '2026-01-01', 'res:k1', ?)",
        ("sha256:" + "c" * 64,))


class KernelFusionPayload(unittest.TestCase):

    def test_create_and_revise_accepted(self):
        validate_kernel_fusion_payload(_create_payload())
        validate_kernel_fusion_payload(_revise_payload())

    def test_unknown_request_type_rejected(self):
        payload = _create_payload()
        payload["request_type"] = "bogus"
        with self.assertRaises(SystemExit):
            validate_kernel_fusion_payload(payload)

    def test_create_without_author_kernel_rejected(self):
        payload = _create_payload()
        del payload["setup"]["author_kernel"]
        with self.assertRaises(SystemExit):
            validate_kernel_fusion_payload(payload)

    def test_revise_without_base_version_rejected(self):
        payload = _revise_payload()
        del payload["base_version"]
        with self.assertRaises(SystemExit):
            validate_kernel_fusion_payload(payload)


class KernelFusionSlots(unittest.TestCase):

    def test_create_section_order_and_marker(self):
        conn = _make_db()
        payload = _create_payload()
        context = build_context_kernel_fusion(conn, payload)
        self.assertEqual(context["mode"], "create")
        sections = resolve_slots(conn, ASSET_DIRS["kernel-fusion"], payload=payload)
        self.assertEqual(
            [t for t, _ in sections],
            [
                "kernel_hints（内核素材——间接养料，不是照抄的答案）",
                "project_setup v2 快照",
                "kernel_subject（修订基底内核全文）",
                "跨批次比对基准人格",
                "系统原型全库一行式清单（仅作语境：库里还有什么；禁止从清单外原型取材）",
            ],
        )
        self.assertIn("低温叙事", sections[0][1])
        self.assertIn("新建内核", sections[2][1])  # create 无基底 → 占位声明
        out = compose(ASSET_DIRS["kernel-fusion"], context, sections)
        self.assertIn("模式语法：新建内核（create）", out)
        self.assertNotIn("模式语法：修订内核（revise）", out)
        self.assertIn("交付前自检", out)

    def test_revise_reads_base_kernel(self):
        conn = _make_db()
        _seed_kernel(conn)
        payload = _revise_payload()
        context = build_context_kernel_fusion(conn, payload)
        self.assertEqual(context["mode"], "revise")
        sections = resolve_slots(conn, ASSET_DIRS["kernel-fusion"], payload=payload)
        subject = next(b for t, b in sections if t.startswith("kernel_subject"))
        self.assertIn("测试内核", subject)
        self.assertIn("sha256:", subject)
        hints = next(b for t, b in sections if t.startswith("kernel_hints"))
        self.assertIn("无代价的宽恕", hints)
        out = compose(ASSET_DIRS["kernel-fusion"], context, sections)
        self.assertIn("模式语法：修订内核（revise）", out)
        self.assertNotIn("模式语法：新建内核（create）", out)

    def test_revise_unknown_base_stops(self):
        conn = _make_db()
        payload = _revise_payload()
        payload["base_version"] = "creator-profile-version:ghost:9"
        with self.assertRaises(SystemExit):
            resolve_slots(conn, ASSET_DIRS["kernel-fusion"], payload=payload)


if __name__ == "__main__":
    unittest.main()
