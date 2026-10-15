import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from dashboard.tools import ROOT, discover


class DetectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.directory = self.home / "custom-bin"
        self.directory.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def executable(self, directory, name, output):
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / name
        path.write_text("#!/bin/sh\nprintf '%s\\n' '" + output + "'\n")
        path.chmod(0o700)
        return str(path)

    def test_fresh_home_missing_tools_is_valid(self):
        with patch("dashboard.tools.Path.home", return_value=self.home), patch.dict(os.environ, {"PATH": str(self.directory)}, clear=True):
            self.assertFalse(any(t["installed"] for t in discover()))

    def test_httpx_name_collision_and_missing_override_fallback(self):
        wrong = self.executable(self.directory, "httpx", "Unrelated Python URL client")
        go = self.executable(self.home / "go/bin", "httpx", "-status-code -no-fallback-scheme")
        with patch("dashboard.tools.Path.home", return_value=self.home), patch.dict(os.environ, {"PATH": str(self.directory)}, clear=True):
            tool = next(t for t in discover({"httpx": str(self.home / 'missing/httpx')}) if t["name"] == "httpx")
            self.assertEqual(tool["path"], go)
            self.assertNotEqual(tool["path"], wrong)
            self.assertEqual(tool["source"], "autodetected")
            self.assertTrue(tool["override_warning"])

    def test_intentional_override_is_machine_local_and_can_be_cleared(self):
        detected = self.executable(self.directory, "ffuf", "-maxtime -noninteractive")
        override = self.executable(self.home, "custom-ffuf", "-maxtime -noninteractive")
        with patch("dashboard.tools.Path.home", return_value=self.home), patch.dict(os.environ, {"PATH": str(self.directory)}, clear=True):
            tool = next(t for t in discover({"ffuf": override}, check=True) if t["name"] == "ffuf")
            self.assertEqual(tool["path"], override)
            self.assertTrue(tool["override_active"])
            tool = next(t for t in discover({}) if t["name"] == "ffuf")
            self.assertEqual(tool["path"], detected)
            self.assertIsNone(tool["configured_path"])


class InstallerTests(unittest.TestCase):
    def test_clean_install_and_start_help_in_path_with_spaces(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            checkout = root / "checkout with spaces"
            checkout.mkdir()
            for name in ("install.sh", "hunt-dashboard"):
                shutil.copy2(ROOT / name, checkout / name)
            shutil.copytree(ROOT / "dashboard", checkout / "dashboard", ignore=shutil.ignore_patterns("__pycache__"))
            commands = root / "commands"
            commands.mkdir()
            for name in ("bash", "readlink", "mkdir", "ln", "dirname", "sed", "tr", "date"):
                (commands / name).symlink_to(shutil.which(name))
            (commands / "python3").symlink_to(sys.executable)
            home = root / "fresh-home"
            home.mkdir()
            binary_dir = root / "launcher directory"
            env = {**os.environ, "HOME": str(home), "PATH": str(commands), "GOBIN": "", "GOPATH": ""}
            args = ["/bin/bash", str(checkout / "install.sh"), "--bin-dir", str(binary_dir)]
            result = subprocess.run(args, env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("0 / 8", result.stdout)
            launcher = binary_dir / "hunt-dashboard"
            self.assertTrue(launcher.is_symlink())
            result = subprocess.run([str(launcher), "--help"], env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("--data-dir", result.stdout)
            self.assertEqual(subprocess.run(args, env=env, capture_output=True, timeout=30).returncode, 0)
            launcher.unlink()
            launcher.write_text("Unrelated launcher")
            result = subprocess.run(args, env=env, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(launcher.read_text(), "Unrelated launcher")


if __name__ == "__main__":
    unittest.main()
