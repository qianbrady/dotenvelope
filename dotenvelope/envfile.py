"""Parse ``.env.example`` files into ordered key/value entries.

Grammar is deliberately close to python-dotenv's loading behaviour:
  * blank lines and whole-line comments (``#``) are ignored
  * an optional ``export `` prefix is stripped
  * the key is everything before the first ``=`` (whitespace-trimmed)
  * matching surrounding quotes on the value are stripped
No variable substitution, no inline-comment handling: values are kept raw.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EnvEntry:
    key: str
    value: str
    line: int  # 1-based line in the original file


def parse_dotenv(text: str) -> list[EnvEntry]:
    """Parse *text* into entries in file order (duplicates repeat)."""
    if text.startswith("\ufeff"):  # strip UTF-8 BOM (common on Windows editors)
        text = text[1:]
    entries: list[EnvEntry] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        if "=" not in line:
            continue  # malformed line: no '='
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        entries.append(EnvEntry(key=key, value=value, line=lineno))
    return entries


def ordered_keys(entries: list[EnvEntry]) -> list[str]:
    """Keys in first-seen order (later duplicates keep the first position)."""
    seen: dict[str, None] = {}
    for e in entries:
        seen.setdefault(e.key, None)
    return list(seen)


def as_map(entries: list[EnvEntry]) -> dict[str, str]:
    """Key -> value, last occurrence wins (like a real dotenv loader)."""
    out: dict[str, str] = {}
    for e in entries:
        out[e.key] = e.value
    return out