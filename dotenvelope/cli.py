"""Command-line interface: ``audit`` / ``sync``.

Exit codes: 0 = healthy / done, 1 = findings or recoverable error, 2 = usage.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .audit import EXAMPLE_FILENAME, audit, render
from .envfile import ordered_keys, parse_dotenv
from .scanner import scan_tree

_COMMANDS = {}


class DataError(Exception):
    """Recoverable input problem -> exit code 1."""


def _reconfigure_stdio() -> None:
    """Force UTF-8 stdio so legacy consoles (e.g. GBK) never crash the CLI."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


def _command(name):
    def register(func):
        _COMMANDS[name] = func
        return func

    return register


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dotenvelope",
        description="比对 .env.example 与代码实际读取的环境变量: 缺文档 / 僵尸 / 默认值缺失 + 健康分 0-100。",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    sub = parser.add_subparsers(
        dest="command", required=True, metavar="{audit,sync}"
    )

    p_audit = sub.add_parser("audit", help="审计项目: 三类问题清单 + 健康分")
    p_audit.add_argument("--path", default=".", help="目标项目路径（默认当前目录）")

    p_sync = sub.add_parser(
        "sync", help="把代码里缺文档的变量补进 .env.example"
    )
    p_sync.add_argument("--path", default=".", help="目标项目路径（默认当前目录）")
    p_sync.add_argument(
        "--yes", action="store_true", help="跳过确认直接写入"
    )
    return parser


def _load_root(value: str) -> Path:
    root = Path(value)
    if not root.exists():
        raise DataError(f"路径不存在: {root}")
    if not root.is_dir():
        raise DataError(f"不是目录: {root}")
    return root


@_command("audit")
def _cmd_audit(args) -> int:
    root = _load_root(args.path)
    report = audit(root)
    print(render(report))
    problems = len(report.undocumented) + len(report.zombie) + len(report.risky)
    return 0 if problems == 0 else 1


@_command("sync")
def _cmd_sync(args) -> int:
    root = _load_root(args.path)
    example_path = root / EXAMPLE_FILENAME
    present = example_path.is_file()
    entries = (
        parse_dotenv(example_path.read_text("utf-8", errors="replace")) if present else []
    )
    documented = set(ordered_keys(entries))

    scan = scan_tree(root)
    missing = sorted(v for v in scan.by_var if v not in documented)

    if not missing:
        print(f"已同步: 代码读取的变量都已记录在 {EXAMPLE_FILENAME}。")
        return 0

    print(f"以下 {len(missing)} 个变量在代码中被读取但 {EXAMPLE_FILENAME} 未记录:")
    for var in missing:
        print(f"  + {var}")

    if not args.yes:
        try:
            answer = input(f"是否写入 {EXAMPLE_FILENAME}? [y/N] ")
        except EOFError:
            answer = ""
        if answer.strip().lower() not in ("y", "yes"):
            print("已取消，未修改任何文件。")
            return 1

    lines = ["", "# added by dotenvelope sync (missing in .env.example)"]
    lines.extend(f"{var}=" for var in missing)
    chunk = "\n".join(lines) + "\n"

    if present:
        raw = example_path.read_bytes()
        if raw and not raw.endswith(b"\n"):
            raw += b"\n"
        example_path.write_bytes(raw + chunk.encode("utf-8"))
    else:
        header = f"# .env.example for {root.name}\n"
        example_path.write_bytes((header + chunk).encode("utf-8"))

    print(f"完成: {len(missing)} 个变量已写入 {example_path} (值为空, 请自行填写)。")
    return 0


def main(argv=None) -> int:
    """CLI entry point; returns the process exit code."""
    _reconfigure_stdio()
    parser = _build_parser()
    args = parser.parse_args(argv)  # usage errors -> argparse exits 2
    handler = _COMMANDS[args.command]
    try:
        return handler(args)
    except DataError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1