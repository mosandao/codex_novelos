from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from novelos.config import Settings


class SettingsTest(unittest.TestCase):
    def test_defaults(self) -> None:
        settings = Settings.from_file(None)
        self.assertEqual(settings.database_path, "data/novelos.db")
        self.assertEqual(settings.model_provider, "local")

    def test_file_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.toml"
            path.write_text(
                '[app]\ndatabase_path = "custom.db"\ncontext_chapter_limit = 8\n'
                '[model]\nprovider = "openai"\n'
            )
            settings = Settings.from_file(path)
        self.assertEqual(settings.database_path, "custom.db")
        self.assertEqual(settings.context_chapter_limit, 8)
        self.assertEqual(settings.model_provider, "openai")


if __name__ == "__main__":
    unittest.main()

