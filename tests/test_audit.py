"""Audit logic tests: three-way classification, health score, determinism."""

from __future__ import annotations

import unittest

from dotenvelope.audit import audit, health_score, render
from dotenvelope.scanner import scan_tree

from _harness import fresh_dir, write_tree


DEMO_TREE = {
    "app/main.py": (
        "import os\n"
        'DB = os.environ.get("DB_URL", "sqlite:///dev.db")\n'
        "TOKEN = os.getenv('API_TOKEN', 'dev')\n"
        "SECRET = os.environ['SECRET_KEY']\n"
    ),
    "web/server.js": (
        "const port = process.env.PORT || '8080';\n"
        "const host = process.env.HOST;\n"
    ),
    ".env.example": (
        "DB_URL=postgres://localhost/app\n"
        "API_TOKEN=dev\n"
        "PORT=8080\n"
        "OLD_FLAG=true\n"
    ),
}


class ClassifyTest(unittest.TestCase):
    def test_three_way_classification(self):
        root = fresh_dir("cls")
        write_tree(root, DEMO_TREE)
        report = audit(root)
        self.assertEqual(report.undocumented, ["HOST", "SECRET_KEY"])
        self.assertEqual(report.zombie, ["OLD_FLAG"])
        self.assertEqual(report.risky, ["HOST", "SECRET_KEY"])

    def test_clean_project_no_problems(self):
        root = fresh_dir("clean")
        write_tree(root, {
            "app.py": (
                "import os\n"
                "DB = os.environ.get('DB_URL', 'sqlite:///dev.db')\n"
                "T = os.getenv('TOKEN', 'x')\n"
            ),
            ".env.example": "DB_URL=postgres://x\nTOKEN=\n",
        })
        report = audit(root)
        self.assertEqual(report.undocumented, [])
        self.assertEqual(report.zombie, [])
        self.assertEqual(report.risky, [])
        self.assertEqual(health_score(report), 100)

    def test_missing_example_everything_undocumented(self):
        root = fresh_dir("no-example")
        write_tree(root, {
            "app.py": "import os\nX = os.getenv('X', 'd')\n",
        })
        report = audit(root)
        self.assertFalse(report.example_present)
        self.assertEqual(report.undocumented, ["X"])
        self.assertEqual(report.zombie, [])
        self.assertEqual(report.risky, [])


class HealthScoreTest(unittest.TestCase):
    def test_formula_penalties(self):
        root = fresh_dir("hc")
        write_tree(root, DEMO_TREE)
        report = audit(root)
        # undocumented=2 (-12 each), zombie=1 (-4), risky=2 (-6 each)
        self.assertEqual(health_score(report), 100 - 24 - 4 - 12)

    def test_floor_at_zero(self):
        root = fresh_dir("floor")
        write_tree(root, {
            "a.py": "\n".join(f"X{i} = os.environ['V{i}']" for i in range(12)),
        })
        report = audit(root)
        self.assertEqual(len(report.undocumented), 12)
        self.assertEqual(health_score(report), 0)

    def test_cap_deterministic_integer(self):
        root = fresh_dir("det-hc")
        write_tree(root, DEMO_TREE)
        r1 = audit(root)
        r2 = audit(root)
        self.assertEqual(health_score(r1), health_score(r2))
        self.assertIsInstance(health_score(r1), int)


class DeterminismTest(unittest.TestCase):
    def test_render_identical_across_runs(self):
        root = fresh_dir("rdr")
        write_tree(root, DEMO_TREE)
        self.assertEqual(render(audit(root)), render(audit(root)))

    def test_render_contains_all_sections_and_score(self):
        root = fresh_dir("rdr2")
        write_tree(root, DEMO_TREE)
        text = render(audit(root))
        for needle in ("缺文档变量", "僵尸变量", "默认值缺失风险", "健康分: 60/100"):
            self.assertIn(needle, text)


if __name__ == "__main__":
    unittest.main()