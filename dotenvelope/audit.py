"""Three-way audit: ``.env.example`` vs code reads vs (implicit) runtime needs.

Classifications
---------------
undocumented  -- read in code, absent from ``.env.example``: new config was
                 added without documenting it.
zombie        -- documented in ``.env.example``, never read anywhere: the doc
                 misleads new developers.
risky         -- read in code *without a fallback* somewhere
                 (``os.environ['X']``, single-arg ``os.getenv('X')``, bare
                 ``process.env.X``): if the variable is unset at runtime,
                 the program gets a ``KeyError`` / ``None`` / ``undefined``.

Health score (0-100, deterministic)
-----------------------------------
starts at 100; each hit subtracts:
  undocumented  -12        (biggest: real deployment risk)
  zombie         -4        (docentation debt)
  risky          -6        (robustness debt; stackable with undocumented)
clamped to ``[0, 100]``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import __version__
from .envfile import ordered_keys, parse_dotenv
from .scanner import ScanResult, scan_tree

PENALTY_UNDOCUMENTED = 12
PENALTY_ZOMBIE = 4
PENALTY_RISKY = 6

EXAMPLE_FILENAME = ".env.example"


@dataclass
class AuditReport:
    root: Path
    scan: ScanResult
    documented: list[str]  # first-seen doc order
    example_present: bool
    undocumented: list[str]  # sorted
    zombie: list[str]  # doc first-seen order, kept only when unused
    risky: list[str]  # sorted


def health_score(report: AuditReport) -> int:
    score = 100
    score -= PENALTY_UNDOCUMENTED * len(report.undocumented)
    score -= PENALTY_ZOMBIE * len(report.zombie)
    score -= PENALTY_RISKY * len(report.risky)
    return max(0, min(100, score))


def audit(root: Path) -> AuditReport:
    """Scan *root* and classify every environment variable."""
    scan = scan_tree(root)
    example_path = root / EXAMPLE_FILENAME
    example_present = example_path.is_file()
    entries = parse_dotenv(example_path.read_text("utf-8", errors="replace")) if example_present else []
    documented = ordered_keys(entries)
    doc_set = set(documented)
    code_vars = set(scan.by_var)

    undocumented = sorted(code_vars - doc_set)
    zombie = [k for k in documented if k not in code_vars]
    risky = sorted(v for v in code_vars if not scan.all_defaults(v))

    return AuditReport(
        root=root,
        scan=scan,
        documented=documented,
        example_present=example_present,
        undocumented=undocumented,
        zombie=zombie,
        risky=risky,
    )


def _render_occ_list(lines: list[str], report: AuditReport, title: str, vars_: list[str]) -> None:
    lines.append(f"[{title}] {len(vars_)}")
    if not vars_:
        lines.append("  (无)")
        return
    for var in vars_:
        lines.append(f"  {var}")
        for occ in report.scan.occurrences(var):
            lines.append(f"    {occ.file}:{occ.line}  {occ.pattern}")
    lines.append("")


def render(report: AuditReport) -> str:
    """Deterministic text rendering of an audit report."""
    lines: list[str] = []
    lines.append(f"dotenvelope audit v{__version__}")
    lines.append(f"路径: {report.root}")
    example_state = (
        f"存在 ({len(report.documented)} 个变量)"
        if report.example_present
        else "缺失"
    )
    lines.append(
        f"扫描: {report.scan.files_scanned} 个源码文件, "
        f"跳过 {report.scan.dirs_skipped} 个目录"
    )
    lines.append(f".env.example: {example_state}")
    lines.append("")

    _render_occ_list(lines, report, "缺文档变量 undocumented", report.undocumented)
    lines.append(f"[僵尸变量 zombie] {len(report.zombie)}")
    if report.zombie:
        for var in report.zombie:
            lines.append(f"  {var}")
    else:
        lines.append("  (无)")
    lines.append("")
    _render_occ_list(lines, report, "默认值缺失风险 no-default", report.risky)

    problems = len(report.undocumented) + len(report.zombie) + len(report.risky)
    lines.append(f"健康分: {health_score(report)}/100")
    if problems == 0:
        lines.append("总结: 通过 — .env.example 与代码读取一致。")
    else:
        summary = (
            f"发现 {len(report.undocumented)} 个缺文档变量, "
            f"{len(report.zombie)} 个僵尸变量, "
            f"{len(report.risky)} 个默认值缺失"
        )
        lines.append(f"总结: 存在 {problems} 个问题 ({summary})。")
    return "\n".join(lines)