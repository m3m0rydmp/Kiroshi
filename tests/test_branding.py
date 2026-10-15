import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from dashboard.config import default_data_dir, database_path, environment
from dashboard.server import App


class BrandingCompatibilityTests(unittest.TestCase):
    def test_new_installs_use_canonical_data_names(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(default_data_dir(root), root / ".kiroshi-data")
            self.assertEqual(database_path(root), root / "kiroshi.sqlite3")

    def test_existing_data_is_opened_without_moving_or_recreating_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            previous = root / ".hunt-data"
            previous.mkdir()
            old_database = previous / "hunt.sqlite3"
            with sqlite3.connect(old_database) as connection:
                connection.execute("CREATE TABLE records (kind TEXT,id TEXT,body TEXT,PRIMARY KEY(kind,id))")
                connection.execute("INSERT INTO records VALUES (?,?,?)", ("reference", "fixture", json.dumps({"id":"fixture","title":"Retained metadata"})))
            connection.close()
            self.assertEqual(default_data_dir(root), previous)
            self.assertEqual(database_path(previous), old_database)
            app = App(default_data_dir(root))
            try:
                self.assertEqual(app.get("reference", "fixture")["title"], "Retained metadata")
                self.assertFalse((previous / "kiroshi.sqlite3").exists())
            finally:
                app.shutdown()
                app.db.close()

    def test_canonical_environment_takes_precedence_over_legacy_aliases(self):
        with patch.dict("os.environ", {"KIROSHI_USER_AGENT":"new-value","HUNT_USER_AGENT":"old-value"}, clear=True):
            self.assertEqual(environment("USER_AGENT"), "new-value")
        with patch.dict("os.environ", {"HUNT_USER_AGENT":"old-value"}, clear=True):
            self.assertEqual(environment("USER_AGENT"), "old-value")


if __name__ == "__main__":
    unittest.main()
