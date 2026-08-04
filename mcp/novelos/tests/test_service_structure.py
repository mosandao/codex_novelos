from __future__ import annotations

import inspect
import unittest
from pathlib import Path

import novelos_mcp.service as service_module
from novelos_mcp.service import NovelOSService


class ServiceStructureTest(unittest.TestCase):
    def test_service_is_aggregated_from_package_without_legacy_module(self) -> None:
        self.assertTrue(service_module.__file__.endswith("service/__init__.py"))
        self.assertFalse((Path(service_module.__file__).parent.parent / "service.py").exists())

    def test_constructor_and_container_methods_are_preserved(self) -> None:
        self.assertEqual(
            [
                "database_path",
                "seed_database_path",
                "catalog_path",
                "agent_contract_path",
                "seed_inventory_path",
            ],
            list(inspect.signature(NovelOSService).parameters),
        )
        for name in (
            "create_project",
            "create_book",
            "list_books",
            "create_volume",
            "list_volumes",
            "create_chapter_draft",
            "accept_chapter",
        ):
            self.assertTrue(callable(getattr(NovelOSService, name)), name)


if __name__ == "__main__":
    unittest.main()
