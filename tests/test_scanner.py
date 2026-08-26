"""Scanner unit tests: pattern detection, defaults, exclusions, GBK, determinism."""

from __future__ import annotations

import unittest

from dotenvelope.scanner import scan_tree

from _harness import fresh_dir, write_bytes, write_tree


class ScanPythonTest(unittest.TestCase):
    def test_py_environ_get_detected(self):
        root = fresh_dir("py-get")
        write_tree(root, {
            "app.py": 'import os\nDB = os.environ.get("DB_URL")\n',
        })
        scan = scan_tree(root)
        self.assertIn("DB_URL", scan.variables())
        occ = scan.occurrences("DB_URL")
        self.assertEqual(len(occ), 1)
        self.assertEqual(occ[0].file, "app.py")
        self.assertEqual(occ[0].line, 2)
        self.assertFalse(occ[0].has_default)  # bare .get() -> no fallback

    def test_py_getenv_with_and_without_default(self):
        root = fresh_dir("py-getenv")
        write_tree(root, {
            "app.py": "import os\nA = os.getenv('A')\nB = os.getenv('B', 'fallback')\n",
        })
        scan = scan_tree(root)
        self.assertFalse(scan.occurrences("A")[0].has_default)
        self.assertTrue(scan.occurrences("B")[0].has_default)

    def test_py_environ_item_never_has_default(self):
        root = fresh_dir("py-item")
        write_tree(root, {
            "app.py": "import os\nX = os.environ['X']\n",
        })
        scan = scan_tree(root)
        self.assertIn("X", scan.variables())
        self.assertFalse(scan.occurrences("X")[0].has_default)

    def test_py_all_defaults_helper(self):
        root = fresh_dir("py-all")
        write_tree(root, {
            "app.py": (
                "import os\n"
                "A = os.getenv('A', 'x')\n"
                "B = os.environ.get('B')\n"
                "B = os.getenv('B', 'y')\n"
            ),
        })
        scan = scan_tree(root)
        self.assertTrue(scan.all_defaults("A"))
        self.assertFalse(scan.all_defaults("B"))  # one site lacks a default


class ScanJsTest(unittest.TestCase):
    def test_js_process_env_dot_with_or_default(self):
        root = fresh_dir("js-dot")
        write_tree(root, {
            "server.js": (
                "const port = process.env.PORT || '8080';\n"
                "const host = process.env.HOST;\n"
                "const db = process.env.DB_URL ?? 'local';\n"
            ),
        })
        scan = scan_tree(root)
        self.assertEqual(sorted(scan.variables()), ["DB_URL", "HOST", "PORT"])
        self.assertTrue(scan.occurrences("PORT")[0].has_default)
        self.assertFalse(scan.occurrences("HOST")[0].has_default)
        self.assertTrue(scan.occurrences("DB_URL")[0].has_default)

    def test_js_bracket_notation(self):
        root = fresh_dir("js-bracket")
        write_tree(root, {
            "app.ts": "const t = process.env['TOKEN'];\n",
        })
        scan = scan_tree(root)
        self.assertIn("TOKEN", scan.variables())
        self.assertFalse(scan.occurrences("TOKEN")[0].has_default)


class ScanScopeTest(unittest.TestCase):
    def test_skips_excluded_dirs(self):
        root = fresh_dir("skip-dirs")
        write_tree(root, {
            "lib/a.py": "import os\nA = os.getenv('REAL')\n",
            "node_modules/pkg/index.js": "const x = process.env.HIDDEN1;\n",
            "pkg/.venv/lib/site/x.py": "import os\nB = os.getenv('HIDDEN2')\n",
            "src/__pycache__/m.pyc": "import os\nC = os.getenv('HIDDEN3')\n",
            ".hidden/src/h.py": "import os\nD = os.getenv('HIDDEN4')\n",
        })
        scan = scan_tree(root)
        self.assertEqual(scan.variables(), ["REAL"])

    def test_ignores_non_source_files(self):
        root = fresh_dir("skip-nonsrc")
        write_tree(root, {
            "README.md": "import os\nX = os.getenv('NOT_A_SOURCE')\n",
            "config.ini": "os.environ.get('INI')\n",
            "notes.txt": "process.env.TXT\n",
        })
        scan = scan_tree(root)
        self.assertEqual(scan.variables(), [])

    def test_gbk_encoded_source_never_crashes(self):
        root = fresh_dir("gbk")
        write_bytes(
            root,
            "app.py",
            "# 中文注释（GBK 编码）\nimport os\nKEY = os.getenv('KEY_OK')\n".encode("gbk"),
        )
        scan = scan_tree(root)  # must not raise
        self.assertIn("KEY_OK", scan.variables())
        self.assertEqual(scan.files_scanned, 1)

    def test_deterministic_scan(self):
        root = fresh_dir("det")
        write_tree(root, {
            "b.py": "import os\nY = os.getenv('Y')\n",
            "a.py": "import os\nX = os.getenv('X')\n",
        })
        first = scan_tree(root)
        second = scan_tree(root)
        self.assertEqual(first.variables(), second.variables())
        self.assertEqual(
            [occ.file for occ in first.occurrences("Y")],
            [occ.file for occ in second.occurrences("Y")],
        )


if __name__ == "__main__":
    unittest.main()