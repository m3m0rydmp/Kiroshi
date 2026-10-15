import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from dashboard.install_tools import MODULES, install_missing


class ToolSetupTests(unittest.TestCase):
    def test_ready_installation_never_runs_a_package_manager(self):
        with patch("dashboard.install_tools.subprocess.run") as run, patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(install_missing([dict(adapter=True, installed=True, runnable=True)]), 0)
            run.assert_not_called()

    def test_dry_run_uses_fixed_official_modules_without_writes(self):
        with tempfile.TemporaryDirectory() as temporary, patch("dashboard.install_tools.Path.home", return_value=Path(temporary)), patch("dashboard.install_tools.subprocess.run") as run, patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(install_missing([dict(name="httpx", adapter=True, installed=False)], dry_run=True), 0)
            self.assertIn(MODULES["httpx"], output.getvalue())
            run.assert_not_called()
            self.assertFalse((Path(temporary) / ".local").exists())

    def test_incompatible_existing_tools_are_not_silently_replaced(self):
        with patch("dashboard.install_tools.subprocess.run") as run, patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(install_missing([dict(name="httpx", adapter=True, installed=True, runnable=False)]), 1)
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
