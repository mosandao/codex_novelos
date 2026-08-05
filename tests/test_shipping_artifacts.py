from __future__ import annotations

import json
import os
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCUMENTATION = ROOT / "documentation"


class ShippingArtifactsTest(unittest.TestCase):
    def test_required_docs_exist_and_conditional_docs_are_not_fabricated(self) -> None:
        expected = {
            "architecture.md",
            "flows.md",
            "permissions.md",
            "variables.md",
            "tests.md",
            "automation.md",
            "worldbuilding-redesign.md",
        }
        self.assertEqual(expected, {path.name for path in DOCUMENTATION.glob("*.md")})
        architecture = (DOCUMENTATION / "architecture.md").read_text(encoding="utf-8")
        for name in expected - {"architecture.md"}:
            self.assertIn(f"./{name}", architecture)
        self.assertIn("没有独立 HTTP/Web 前端、账号体系、网络服务、邮件、定时任务或公开 SEO 页面", architecture)
        self.assertIn("ui://novelos/project-wizard-v3.html", architecture)

    def test_new_runner_targets_only_unified_mcp_and_pins_authorized_seed(self) -> None:
        runner = (ROOT / "scripts" / "run_novelos_mcp.sh").read_text(encoding="utf-8")
        self.assertIn("-m novelos_mcp.server", runner)
        self.assertIn("data/novelos-v2.db", runner)
        self.assertIn("catalog/skills", runner)
        self.assertIn("config/agents.yaml", runner)
        self.assertIn("NOVELOS_SEED_DB_PATH", runner)
        self.assertIn("NOVELOS_SEED_INVENTORY_PATH", runner)
        self.assertIn("mcp/novelos/resources/seed.db", runner)
        self.assertIn("mcp/novelos/resources/seed-inventory.json", runner)
        self.assertNotIn("novelos.mcp.memory_server", runner)
        for variable in ("NOVELOS_SEED_DB_PATH", "NOVELOS_SEED_INVENTORY_PATH"):
            with self.subTest(variable=variable):
                environment = dict(os.environ)
                environment.pop("NOVELOS_SEED_DB_PATH", None)
                environment.pop("NOVELOS_SEED_INVENTORY_PATH", None)
                environment[variable] = "/not/authorized/value"
                result = subprocess.run(
                    ["bash", str(ROOT / "scripts" / "run_novelos_mcp.sh")],
                    cwd=ROOT,
                    env=environment,
                    text=True,
                    capture_output=True,
                    timeout=5,
                    check=False,
                )
                self.assertEqual(64, result.returncode)
                self.assertIn("拒绝环境变量覆盖", result.stderr)

    def test_restore_manifest_proves_logical_identity(self) -> None:
        manifest = json.loads(
            (ROOT / "tasks" / "migration" / "schema12_restore_drill.json").read_text(encoding="utf-8")
        )
        self.assertEqual("passed", manifest["restore_drill"])
        snapshot = manifest["logical_snapshot"]
        self.assertEqual("ok", snapshot["quick_check"])
        self.assertEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13], snapshot["schema_versions"])
        self.assertRegex(snapshot["logical_hash"], r"^sha256:[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
