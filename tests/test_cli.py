"""CLI integration tests: audit/sync exit codes, determinism, GBK smoke."""

from __future__ import annotations

import unittest

from dotenvelope import __version__

from _harness import fresh_dir, run_cli, write_tree


CLEAN_TREE = {
    "app.py": (
        "import os\n"
        "DB = os.environ.get('DB_URL', 'sqlite:///dev.db')\n"
        "T = os.getenv('TOKEN', 'x')\n"
    ),
    ".env.example": "DB_URL=postgres://x\nTOKEN=\n",
}

DIRTY_TREE = {
    "app.py": "import os\nX = os.environ['X']\n",
    ".env.example": "Y=1\n",
}


class AuditCliTest(unittest.TestCase):
    def test_audit_clean_exit_0(self):
        root = fresh_dir("cli-clean")
        write_tree(root, CLEAN_TREE)
        result = run_cli(["audit", "--path", str(root)])
        self.assertEqual(result.returncode, 0)
        self.assertIn("健康分: 100/100", result.stdout)

    def test_audit_findings_exit_1(self):
        root = fresh_dir("cli-dirty")
        write_tree(root, DIRTY_TREE)
        result = run_cli(["audit", "--path", str(root)])
        self.assertEqual(result.returncode, 1)
        self.assertIn("缺文档变量", result.stdout)
        self.assertIn("僵尸变量", result.stdout)
        self.assertIn("默认值缺失风险", result.stdout)

    def test_audit_missing_path_exit_1(self):
        result = run_cli(["audit", "--path", "D:/definitely/not/here"])
        self.assertEqual(result.returncode, 1)
        self.assertIn("错误", result.stderr)

    def test_audit_gbk_project_smoke(self):
        root = fresh_dir("cli-gbk")
        write_tree(root, {"app.py": "import os\nKEY = os.getenv('K')\n"})
        (root / "app.py").write_bytes(
            "# 中文注释（源码混入 GBK）\nimport os\nKEY = os.getenv('K')\n".encode("gbk")
        )
        result = run_cli(["audit", "--path", str(root)])
        self.assertEqual(result.returncode, 1)  # K undocumented
        self.assertEqual(result.stderr, "")
        self.assertIn("K", result.stdout)

    def test_audit_output_deterministic(self):
        root = fresh_dir("cli-det")
        write_tree(root, DIRTY_TREE)
        first = run_cli(["audit", "--path", str(root)])
        second = run_cli(["audit", "--path", str(root)])
        self.assertEqual(first.stdout, second.stdout)


class SyncCliTest(unittest.TestCase):
    def test_sync_yes_appends_missing(self):
        root = fresh_dir("cli-sync-yes")
        write_tree(root, DIRTY_TREE)  # X in code, only Y documented
        result = run_cli(["sync", "--path", str(root), "--yes"])
        self.assertEqual(result.returncode, 0)
        body = (root / ".env.example").read_text("utf-8")
        self.assertIn("X=", body)
        self.assertIn("Y=1", body)  # existing preserved
        # second run: already in sync
        again = run_cli(["sync", "--path", str(root), "--yes"])
        self.assertEqual(again.returncode, 0)
        self.assertIn("已同步", again.stdout)

    def test_sync_declines_without_yes(self):
        root = fresh_dir("cli-sync-no")
        write_tree(root, DIRTY_TREE)
        before = (root / ".env.example").read_text("utf-8")
        result = run_cli(["sync", "--path", str(root)])  # stdin empty -> EOF
        self.assertEqual(result.returncode, 1)
        self.assertIn("已取消", result.stdout)
        self.assertEqual((root / ".env.example").read_text("utf-8"), before)

    def test_sync_creates_example_when_missing(self):
        root = fresh_dir("cli-sync-create")
        write_tree(root, {"app.py": "import os\nA = os.getenv('A')\n"})
        result = run_cli(["sync", "--path", str(root), "--yes"])
        self.assertEqual(result.returncode, 0)
        body = (root / ".env.example").read_text("utf-8")
        self.assertIn("A=", body)


class UsageCliTest(unittest.TestCase):
    def test_no_subcommand_exit_2(self):
        result = run_cli([])
        self.assertEqual(result.returncode, 2)

    def test_unknown_subcommand_exit_2(self):
        result = run_cli(["frobnicate"])
        self.assertEqual(result.returncode, 2)

    def test_version_flag(self):
        result = run_cli(["--version"])
        self.assertEqual(result.returncode, 0)
        self.assertIn(__version__, result.stdout)


if __name__ == "__main__":
    unittest.main()