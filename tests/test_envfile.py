""".env.example parser unit tests."""

from __future__ import annotations

import unittest

from dotenvelope.envfile import as_map, ordered_keys, parse_dotenv


class ParseDotenvTest(unittest.TestCase):
    def test_parse_basic_entries(self):
        text = "A=1\nB=hello world\nC=\n"
        entries = parse_dotenv(text)
        self.assertEqual([e.key for e in entries], ["A", "B", "C"])
        self.assertEqual(as_map(entries), {"A": "1", "B": "hello world", "C": ""})
        self.assertEqual(entries[2].line, 3)

    def test_comments_blank_export_quotes(self):
        text = (
            "# leading comment\n"
            "\n"
            "  \n"
            "export EXPORTED=val\n"
            'QUOTED="with spaces"\n'
            "SINGLE='s'\n"
        )
        entries = parse_dotenv(text)
        self.assertEqual([e.key for e in entries], ["EXPORTED", "QUOTED", "SINGLE"])
        self.assertEqual(as_map(entries), {
            "EXPORTED": "val",
            "QUOTED": "with spaces",
            "SINGLE": "s",
        })

    def test_duplicate_keys_last_wins_map_first_seen_order(self):
        text = "DUP=first\nDUP=second\n"
        entries = parse_dotenv(text)
        self.assertEqual(as_map(entries), {"DUP": "second"})
        self.assertEqual(ordered_keys(entries), ["DUP"])

    def test_malformed_line_without_equals_is_ignored(self):
        entries = parse_dotenv("GOOD=1\nTHIS_IS_BROKEN\n")
        self.assertEqual([e.key for e in entries], ["GOOD"])

    def test_utf8_bom_is_stripped(self):
        entries = parse_dotenv("\ufeffFIRST=1\nSECOND=2\n")
        self.assertEqual([e.key for e in entries], ["FIRST", "SECOND"])


if __name__ == "__main__":
    unittest.main()