"""ForgeUE Enum Cross-Reference Fence — static drift detector.

Sits adjacent to ``/forgeue:change-doc-sync``;校验 ``tools/`` 下声明的
``frozenset`` 枚举常量(canonical source of truth)与文档(``CLAUDE.md`` /
``docs/ai_workflow/forgeue_integrated_ai_workflow.md``)中以 ``<name> ∈ {…}``
形式描述的枚举字面值是否同步。

Background:``forgeue_finish_gate.py`` L199 NOTE 明确把 enum cross-reference
fence 标为 P2+ deferred follow-on,本工具落地该项。

Detection 流程:

- **canonical** = ``tools/*.py`` 中形如
  ``_VALID_X: frozenset[str] = frozenset({...})`` 或
  ``_X_VALUES = frozenset({...})`` 的 module-level 赋值,通过 ``ast.parse``
  解析,只取所有元素都是 string literal 的 set。
- **mapped canonical** = 名字在 ``_ENUM_MAPPING`` 显式注册表里的 canonical;
  仅对这些做 cross-ref(其余跳过 + ``[WARN]`` advisory)。
- **doc occurrence** = doc 白名单里所有 ``<name> ∈ {…}`` regex 匹配;
  ``<name>`` 必须是 lowercase Python identifier。
- **DRIFT** = mapped canonical 字面值集合 != doc occurrence 字面值集合
  (set equality;order-insensitive)。
- **advisory ``[WARN]`` (exit 0)**:
  1. canonical 在 ``_ENUM_MAPPING`` 注册但所有 doc target 都没出现对应
     ``<name> ∈ {…}`` 行 → 提示考虑文档化
  2. canonical 未在 ``_ENUM_MAPPING`` 注册 → 提示工具默认跳过 cross-ref
  3. doc 出现 ``<name> ∈ {…}`` 但没有任何 mapped canonical → docs-only
     enum,提示考虑升格

Exit codes:

- ``0`` — 无 DRIFT(可有 advisory ``[WARN]``)
- ``2`` — 至少一个 DRIFT
- ``1`` — 解析 / IO 异常

Output:ASCII-only(``[OK]`` / ``[DRIFT]`` / ``[WARN]`` / ``[FAIL]``);
Windows GBK stdout 安全。
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# 显式映射:canonical frozenset 名 -> 文档中字段名
# ---------------------------------------------------------------------------
# 沿 ``tools/forgeue_finish_gate.py`` 现存声明 + ``CLAUDE.md`` /
# ``docs/ai_workflow/forgeue_integrated_ai_workflow.md`` 文字。
#
# 未列入的 canonical(即使匹配 ``_VALID_*`` 命名模式)会进 advisory WARN,
# 不算 drift。这样保留扩展空间:加新 frozenset 时若想纳管,在表里登记一行
# 即可;不想纳管(如内部分类常量、嵌套字段类型)则不动。
_ENUM_MAPPING: dict[str, str] = {
    "_AUTONOMY_DECISION_VALUES": "autonomy_decision",
    "_SUBAGENT_STYLE_DISPATCH_VALUES": "triggered_by_command",
    "_TASK_GRANULARITY_VALUES": "task_granularity",
    "_VALID_WORKTREE_CONSENT_OUTCOMES": "worktree_consent_outcome",
    "_VALID_WORKTREE_MODES": "worktree_mode",
    # 已知未映射(advisory only;非 drift):
    # _VALID_CODEX_REVIEW_REF_TYPES — codex_review_ref.evidence_type 嵌套字段,
    #                                  doc 没有 `<name> ∈ {…}` 行表述
    # _IMPLEMENTATION_EV_TYPES      — 集合包含语义,非顶层 enum 字段
    # _CROSS_CHECK_TYPES            — 内部分类常量
    # _WORKTREE_FENCE_TRIGGER_COMMANDS — 与 _SUBAGENT_STYLE_DISPATCH_VALUES 重叠
    # _WORKTREE_REQUIRED_COMMANDS   — 空 frozenset(ADR-013 D-RestoreConsentGate 退役)
}

# 默认扫描目录(canonical)
_DEFAULT_TOOLS_SUBDIR = "tools"

# 默认扫描文档(B1 scope:仅 2 份 live contract;archived openspec 冻结历史不扫)
_DEFAULT_DOC_TARGETS: tuple[str, ...] = (
    "CLAUDE.md",
    "docs/ai_workflow/forgeue_integrated_ai_workflow.md",
)

# 文档 enum 提取 regex
# 匹配如:
#   `task_granularity` ∈ {phase, per-file, sub-task}
#   worktree_mode ∈ {`in_place`, `skill_worktree`, `wrapper_worktree`}
#   triggered_by_command ∈ {change-apply-subagent, change-apply-parallel}
#
# `<name>` 必填(≥ 1 字符 [a-z_][a-z0-9_]*),前后允许可选 backtick;
# `∈` 是 Unicode literal U+2208;
# `{…}` 内容用 [^}]+ 捕,允许 backtick / 引号 / 空格 / 连字符 / 下划线;
# 末尾 negative lookahead `(?!_[a-z])` 排除 ``{a,b}_suffix`` 简写形态
# (如 ``mode ∈ {skill,wrapper}_worktree`` 是文字简写,不是规范枚举声明)。
_DOC_ENUM_RE = re.compile(
    r"`?(?P<name>[a-z_][a-z0-9_]*)`?\s*∈\s*\{(?P<values>[^}]+)\}(?!_[a-z])"
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class CanonicalEnum:
    """一条 ``frozenset`` 字面声明。"""

    constant: str  # 常量名,如 ``_VALID_WORKTREE_MODES``
    file: str      # 相对 repo root 的 POSIX 路径
    line: int      # 行号
    values: frozenset[str]
    doc_field: str | None  # 映射后的 doc field 名(None = 未映射)


@dataclass
class DocOccurrence:
    """一条文档中 ``<name> ∈ {…}`` 出现。"""

    name: str
    file: str
    line: int
    values: frozenset[str]


@dataclass
class Drift:
    """一条 canonical vs doc 不一致。"""

    enum_name: str
    canonical_constant: str
    canonical_file: str  # 含行号 ``foo.py:123``
    doc_file: str
    doc_line: int
    canonical_values: frozenset[str]
    doc_values: frozenset[str]
    missing_in_doc: frozenset[str]   # canonical - doc
    extra_in_doc: frozenset[str]     # doc - canonical


@dataclass
class CrossRefReport:
    canonical: list[CanonicalEnum] = field(default_factory=list)
    doc_occurrences: list[DocOccurrence] = field(default_factory=list)
    drifts: list[Drift] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)        # actionable warnings
    unmapped_warnings: list[str] = field(default_factory=list)  # 已知有意未映射(--show-all 才打)


# ---------------------------------------------------------------------------
# Canonical extraction (AST)
# ---------------------------------------------------------------------------


def _extract_frozenset_literal(value: ast.expr) -> set[str] | None:
    """如果 ``value`` 是 ``frozenset({...})`` 字面调用,返回 string set;否则 None。

    接受形态:
        frozenset({"a", "b"})       — set literal 参数
        frozenset(["a", "b"])       — list literal 参数
        frozenset(("a", "b"))       — tuple literal 参数
        frozenset()                  — 空,返回 set()
    """
    if not isinstance(value, ast.Call):
        return None
    func = value.func
    if not (isinstance(func, ast.Name) and func.id == "frozenset"):
        return None
    if not value.args:
        return set()  # frozenset() 空构造
    arg = value.args[0]
    if not isinstance(arg, (ast.Set, ast.List, ast.Tuple)):
        return None
    out: set[str] = set()
    for elt in arg.elts:
        # 含非 string literal / 非 Constant(如 ** 解包、变量引用)→ 跳过整体
        if not isinstance(elt, ast.Constant) or not isinstance(elt.value, str):
            return None
        out.add(elt.value)
    return out


def _extract_canonical_enums(tools_dir: Path, repo_root: Path) -> list[CanonicalEnum]:
    """``ast.parse`` 扫 ``tools_dir`` 下所有 ``*.py``(跳过 ``_*.py``);
    抓 module-level ``_VALID_*`` / ``*_VALUES`` / ``*_TYPES`` / ``*_COMMANDS``
    赋值,值是 ``frozenset({…字符串字面…})`` 时纳入。

    跳过空 frozenset(如 ADR-013 退役的 ``_WORKTREE_REQUIRED_COMMANDS``);
    """
    out: list[CanonicalEnum] = []
    for py in sorted(tools_dir.rglob("*.py")):
        # 跳过 ``_common.py`` / ``__init__.py`` 等下划线起手的辅助模块
        if py.name.startswith("_"):
            continue
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except (SyntaxError, OSError) as exc:  # pragma: no cover
            raise RuntimeError(f"cannot parse {py}: {exc}") from exc
        for node in tree.body:
            target: str | None = None
            value: ast.expr | None = None
            # 形态 1:annotated assignment(``_VALID_X: frozenset[str] = frozenset(...)``)
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                target = node.target.id
                value = node.value
            # 形态 2:plain assignment(``_CROSS_CHECK_TYPES = frozenset(...)``)
            elif (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
            ):
                target = node.targets[0].id
                value = node.value
            if target is None or value is None:
                continue
            # 名字模式守门:仅认 4 类常见 enum 命名后缀
            if not (
                target.startswith("_VALID_")
                or target.endswith("_VALUES")
                or target.endswith("_TYPES")
                or target.endswith("_COMMANDS")
            ):
                continue
            literals = _extract_frozenset_literal(value)
            if literals is None:
                continue
            if not literals:
                # 空 frozenset(如退役的 _WORKTREE_REQUIRED_COMMANDS)无 cross-ref 意义
                continue
            try:
                rel = py.relative_to(repo_root).as_posix()
            except ValueError:
                rel = py.as_posix()
            out.append(
                CanonicalEnum(
                    constant=target,
                    file=rel,
                    line=node.lineno,
                    values=frozenset(literals),
                    doc_field=_ENUM_MAPPING.get(target),
                )
            )
    return out


# ---------------------------------------------------------------------------
# Doc occurrence extraction (regex)
# ---------------------------------------------------------------------------


def _parse_doc_values(raw: str) -> frozenset[str]:
    """把 ``{a, b, c}`` 中括号内文本切成 string set。

    支持:
        ``{a, b, c}`` — 普通逗号分隔
        ``{a,b,c}`` — 无空格
        ``{`a`, `b`, `c`}`` — 反引号包裹
        ``{"a", "b"}`` — 双引号包裹
        ``{'a', 'b'}`` — 单引号包裹

    每个 token 依次去 backtick / 单双引号 / whitespace。
    """
    out: set[str] = set()
    for token in raw.split(","):
        cleaned = token.strip().strip("`").strip("'\"").strip()
        if cleaned:
            out.add(cleaned)
    return frozenset(out)


def _extract_doc_occurrences(
    repo_root: Path, doc_targets: tuple[str, ...]
) -> list[DocOccurrence]:
    """扫文档白名单,regex 抓 ``<name> ∈ {…}`` 出现。"""
    out: list[DocOccurrence] = []
    for rel in doc_targets:
        p = repo_root / rel
        if not p.is_file():
            # 文件不存在 → 静默跳过(B1 scope 的 doc 不应缺失,缺失本身不是
            # cross-ref 工具的职责;forgeue_doc_sync_check 已守 doc 完整性)
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        for m in _DOC_ENUM_RE.finditer(text):
            line_no = text[: m.start()].count("\n") + 1
            out.append(
                DocOccurrence(
                    name=m.group("name"),
                    file=rel.replace("\\", "/"),
                    line=line_no,
                    values=_parse_doc_values(m.group("values")),
                )
            )
    return out


# ---------------------------------------------------------------------------
# Drift computation
# ---------------------------------------------------------------------------


def _compute_drift(
    canonical: list[CanonicalEnum],
    occurrences: list[DocOccurrence],
) -> tuple[list[Drift], list[str], list[str]]:
    """diff canonical vs doc occurrences;返回 (drifts, actionable_warnings,
    unmapped_warnings)。

    - actionable_warnings:mapped canonical 缺 doc 出现 + docs-only enum
      (这两类是 user 应该决策的信号)
    - unmapped_warnings:canonical 未在 _ENUM_MAPPING 注册(故意跳过 cross-ref
      的内部常量;每次 baseline 都喷会噪;默认抑制,``--show-all`` 才打)
    """
    drifts: list[Drift] = []
    actionable: list[str] = []
    unmapped: list[str] = []

    # 索引:doc field name -> canonical(只索引 mapped canonical)
    by_doc_field: dict[str, CanonicalEnum] = {
        c.doc_field: c for c in canonical if c.doc_field
    }
    occurrence_names = {o.name for o in occurrences}

    # 1) canonical 已 mapped 但 docs 完全无 ``∈ {…}`` 出现 → actionable WARN
    for c in canonical:
        if c.doc_field and c.doc_field not in occurrence_names:
            actionable.append(
                f"canonical {c.constant} ({c.file}:{c.line}) mapped to "
                f"`{c.doc_field}` but no `{c.doc_field} ∈ {{…}}` occurrence "
                f"in any doc target — consider documenting"
            )
        elif c.doc_field is None:
            unmapped.append(
                f"canonical {c.constant} ({c.file}:{c.line}) has no "
                f"_ENUM_MAPPING entry — skipped from cross-ref"
            )

    # 2) docs 出现但无 mapped canonical → docs-only actionable WARN
    #    (可能是未升格 enum,或 short-form 文字本来就不该被 fence 管;不 fail)
    for o in occurrences:
        if o.name not in by_doc_field:
            actionable.append(
                f"docs-only enum `{o.name} ∈ {{…}}` at {o.file}:{o.line} — "
                f"no canonical _VALID_* frozenset; consider promotion or this "
                f"may be a non-canonical narrative reference"
            )

    # 3) hard drift:mapped canonical 字面值集合 != doc occurrence 字面值集合
    for o in occurrences:
        c = by_doc_field.get(o.name)
        if c is None:
            continue
        if c.values != o.values:
            drifts.append(
                Drift(
                    enum_name=o.name,
                    canonical_constant=c.constant,
                    canonical_file=f"{c.file}:{c.line}",
                    doc_file=o.file,
                    doc_line=o.line,
                    canonical_values=c.values,
                    doc_values=o.values,
                    missing_in_doc=c.values - o.values,
                    extra_in_doc=o.values - c.values,
                )
            )

    return drifts, actionable, unmapped


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _format_set(values: frozenset[str]) -> str:
    if not values:
        return "{}"
    return "{" + ", ".join(sorted(values)) + "}"


def _format_report(report: CrossRefReport, *, show_all: bool = False) -> str:
    """ASCII-only 报告,Windows GBK stdout 安全。

    ``show_all=False``(默认):只展示 actionable WARN(``warnings``);
    ``show_all=True``:也展示 unmapped canonical 的诊断 WARN(``unmapped_warnings``)。
    """
    lines: list[str] = []
    lines.append("[ENUM CROSS-REF CHECK]")
    lines.append(f"  canonical frozensets discovered : {len(report.canonical)}")
    mapped = sum(1 for c in report.canonical if c.doc_field)
    lines.append(f"  mapped to doc field             : {mapped}")
    lines.append(f"  doc occurrences                 : {len(report.doc_occurrences)}")
    lines.append(f"  drifts                          : {len(report.drifts)}")
    lines.append(f"  actionable warnings             : {len(report.warnings)}")
    if show_all:
        lines.append(f"  unmapped advisories (--show-all): {len(report.unmapped_warnings)}")
    else:
        lines.append(
            f"  unmapped advisories             : {len(report.unmapped_warnings)} "
            "(suppressed; pass --show-all to see)"
        )
    lines.append("")

    if report.drifts:
        lines.append("DRIFTS:")
        for d in report.drifts:
            lines.append(
                f"  [DRIFT] enum={d.enum_name}  canonical={d.canonical_constant}\n"
                f"          canonical {d.canonical_file} = {_format_set(d.canonical_values)}\n"
                f"          doc       {d.doc_file}:{d.doc_line} = {_format_set(d.doc_values)}\n"
                f"          missing-in-doc = {_format_set(d.missing_in_doc)}\n"
                f"          extra-in-doc   = {_format_set(d.extra_in_doc)}"
            )
        lines.append("")

    if report.warnings:
        lines.append("ACTIONABLE WARNINGS (advisory, exit 0 OK):")
        for w in report.warnings:
            lines.append(f"  [WARN] {w}")
        lines.append("")

    if show_all and report.unmapped_warnings:
        lines.append("UNMAPPED ADVISORIES (canonical 故意未 cross-ref):")
        for w in report.unmapped_warnings:
            lines.append(f"  [WARN] {w}")
        lines.append("")

    if report.drifts:
        lines.append("[FAIL] enum cross-ref drift detected — fix docs OR canonical frozenset")
    else:
        lines.append("[OK] no enum cross-ref drift detected")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run(
    repo_root: Path,
    *,
    tools_subdir: str = _DEFAULT_TOOLS_SUBDIR,
    doc_targets: tuple[str, ...] = _DEFAULT_DOC_TARGETS,
) -> CrossRefReport:
    """跑一次 cross-ref 检查,返回 ``CrossRefReport``。"""
    tools_dir = repo_root / tools_subdir
    canonical = _extract_canonical_enums(tools_dir, repo_root)
    occurrences = _extract_doc_occurrences(repo_root, doc_targets)
    drifts, actionable, unmapped = _compute_drift(canonical, occurrences)
    return CrossRefReport(
        canonical=canonical,
        doc_occurrences=occurrences,
        drifts=drifts,
        warnings=actionable,
        unmapped_warnings=unmapped,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "ForgeUE enum cross-reference fence — verify _VALID_* frozenset "
            "(canonical) agrees with `<name> ∈ {…}` doc occurrences."
        )
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repo root (default: parent of tools/)",
    )
    parser.add_argument(
        "--tools-subdir",
        default=_DEFAULT_TOOLS_SUBDIR,
        help=f"canonical scan dir relative to repo-root (default: {_DEFAULT_TOOLS_SUBDIR})",
    )
    parser.add_argument(
        "--doc",
        action="append",
        dest="doc_targets",
        default=None,
        help=(
            "doc target relpath (repeatable; default: 2 core docs "
            "CLAUDE.md + docs/ai_workflow/forgeue_integrated_ai_workflow.md)"
        ),
    )
    parser.add_argument(
        "--show-all",
        action="store_true",
        help=(
            "also print unmapped canonical advisories(默认抑制;诊断时打开,"
            "看哪些 frozenset 故意没纳管 cross-ref)"
        ),
    )
    args = parser.parse_args(argv)
    doc_targets: tuple[str, ...] = (
        tuple(args.doc_targets) if args.doc_targets else _DEFAULT_DOC_TARGETS
    )

    try:
        report = run(
            args.repo_root,
            tools_subdir=args.tools_subdir,
            doc_targets=doc_targets,
        )
    except Exception as exc:  # noqa: BLE001
        # parse / IO 异常 → exit 1(沿 forgeue_doc_sync_check 的异常退出码)
        print(f"[FAIL] enum cross-ref check raised: {exc}", file=sys.stderr)
        return 1

    print(_format_report(report, show_all=args.show_all))
    # exit 2 = drift(沿 forgeue_doc_sync_check.py / forgeue_finish_gate.py 的 blocker 退出码)
    return 2 if report.drifts else 0


if __name__ == "__main__":
    sys.exit(main())
