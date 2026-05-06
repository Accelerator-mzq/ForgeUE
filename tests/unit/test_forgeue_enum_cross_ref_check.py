"""Unit tests for ``tools/forgeue_enum_cross_ref_check.py``.

覆盖:
- 真实 repo baseline → 0 drift exit 0(回归保护:有人改文档或常量值导致
  drift 时,这条会立刻 fail)
- canonical 提取:annotated assignment / plain assignment / 多种 frozenset
  字面参数形态 / 跳过非字符串 / 跳过空 frozenset / 跳过下划线起手文件
- doc occurrence regex:正常形态 / 反引号包裹 / 引号包裹 / 排除
  ``{a,b}_suffix`` 简写
- drift 检测:counts 字符串 set 不一致(missing-in-doc + extra-in-doc 双向)
- actionable vs unmapped advisory 分类
- ``_compute_drift`` set equality 顺序无关
- CLI exit code 协议:0 = 无 drift,2 = drift 存在,1 = parse exception
- ``--show-all`` flag 输出 unmapped advisory
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_TOOLS = _REPO / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import forgeue_enum_cross_ref_check as fec  # noqa: E402

TOOL = _TOOLS / "forgeue_enum_cross_ref_check.py"


# ---------------------------------------------------------------------------
# Baseline regression — 真实 repo 应保持 0 drift
# ---------------------------------------------------------------------------


def test_real_repo_baseline_no_drift():
    """如果有人改了 docs 或 frozenset 一边没同步另一边,这条立刻 fail。"""
    report = fec.run(_REPO)
    assert report.drifts == [], (
        f"unexpected drift in real repo:\n"
        + "\n".join(f"  {d}" for d in report.drifts)
    )


def test_real_repo_baseline_canonical_count_at_least_5_mapped():
    """守门已 mapped 的 5 个核心 enum 不被误删。"""
    report = fec.run(_REPO)
    mapped = [c for c in report.canonical if c.doc_field]
    mapped_names = {c.constant for c in mapped}
    expected_at_least = {
        "_AUTONOMY_DECISION_VALUES",
        "_SUBAGENT_STYLE_DISPATCH_VALUES",
        "_TASK_GRANULARITY_VALUES",
        "_VALID_WORKTREE_CONSENT_OUTCOMES",
        "_VALID_WORKTREE_MODES",
    }
    missing = expected_at_least - mapped_names
    assert not missing, f"core mapped canonical missing: {missing}"


# ---------------------------------------------------------------------------
# _extract_frozenset_literal — AST 层
# ---------------------------------------------------------------------------


def _parse_value(src: str):
    import ast

    return ast.parse(src, mode="eval").body


def test_frozenset_set_literal_extracted():
    v = _parse_value('frozenset({"a", "b", "c"})')
    assert fec._extract_frozenset_literal(v) == {"a", "b", "c"}


def test_frozenset_list_literal_extracted():
    v = _parse_value('frozenset(["x", "y"])')
    assert fec._extract_frozenset_literal(v) == {"x", "y"}


def test_frozenset_tuple_literal_extracted():
    v = _parse_value('frozenset(("p", "q"))')
    assert fec._extract_frozenset_literal(v) == {"p", "q"}


def test_frozenset_empty_returns_empty_set():
    v = _parse_value("frozenset()")
    assert fec._extract_frozenset_literal(v) == set()


def test_frozenset_with_non_string_returns_none():
    """含 int / 变量引用 / 解包等 → 跳过整体(返回 None)。"""
    v = _parse_value("frozenset({1, 2, 3})")
    assert fec._extract_frozenset_literal(v) is None


def test_non_frozenset_call_returns_none():
    v = _parse_value('set(["a", "b"])')
    assert fec._extract_frozenset_literal(v) is None


# ---------------------------------------------------------------------------
# _extract_canonical_enums — 从合成 tools 目录提取
# ---------------------------------------------------------------------------


def _make_tools_dir(tmp_path: Path, content: str) -> Path:
    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "sample.py").write_text(content, encoding="utf-8")
    return tools


def test_extract_canonical_annotated_and_plain(tmp_path):
    src = """
_VALID_X: frozenset[str] = frozenset({"a", "b"})
_Y_VALUES = frozenset({"c", "d", "e"})
_OTHER_THING = frozenset({"ignored"})  # 非 _VALID_/_VALUES/_TYPES/_COMMANDS 命名 → 跳过
"""
    tools = _make_tools_dir(tmp_path, src)
    canonical = fec._extract_canonical_enums(tools, tmp_path)
    by_name = {c.constant: c for c in canonical}
    assert "_VALID_X" in by_name
    assert by_name["_VALID_X"].values == frozenset({"a", "b"})
    assert "_Y_VALUES" in by_name
    assert by_name["_Y_VALUES"].values == frozenset({"c", "d", "e"})
    assert "_OTHER_THING" not in by_name


def test_extract_canonical_skips_underscore_files(tmp_path):
    """_common.py 等下划线起手文件不扫(辅助模块惯例)。"""
    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "_common.py").write_text(
        '_VALID_HIDDEN: frozenset[str] = frozenset({"x"})', encoding="utf-8"
    )
    canonical = fec._extract_canonical_enums(tools, tmp_path)
    assert canonical == []


def test_extract_canonical_skips_empty_frozenset(tmp_path):
    """空 frozenset 不进 canonical(无 cross-ref 意义)。"""
    src = '_VALID_EMPTY: frozenset[str] = frozenset()'
    tools = _make_tools_dir(tmp_path, src)
    canonical = fec._extract_canonical_enums(tools, tmp_path)
    assert canonical == []


def test_extract_canonical_skips_non_string_literals(tmp_path):
    """含变量引用的 frozenset 不进 canonical(extract 返回 None)。"""
    src = """
_VAR = "x"
_VALID_REF: frozenset[str] = frozenset({_VAR, "y"})
"""
    tools = _make_tools_dir(tmp_path, src)
    canonical = fec._extract_canonical_enums(tools, tmp_path)
    assert canonical == []


def test_extract_canonical_recognises_all_4_naming_patterns(tmp_path):
    src = """
_VALID_A: frozenset[str] = frozenset({"a"})
_B_VALUES: frozenset[str] = frozenset({"b"})
_C_TYPES: frozenset[str] = frozenset({"c"})
_D_COMMANDS: frozenset[str] = frozenset({"d"})
_NOT_MATCHING: frozenset[str] = frozenset({"e"})
"""
    tools = _make_tools_dir(tmp_path, src)
    canonical = fec._extract_canonical_enums(tools, tmp_path)
    names = {c.constant for c in canonical}
    assert names == {"_VALID_A", "_B_VALUES", "_C_TYPES", "_D_COMMANDS"}


# ---------------------------------------------------------------------------
# Doc occurrence regex
# ---------------------------------------------------------------------------


def test_doc_regex_basic():
    text = "task_granularity ∈ {phase, per-file, sub-task}"
    m = fec._DOC_ENUM_RE.search(text)
    assert m is not None
    assert m.group("name") == "task_granularity"
    values = fec._parse_doc_values(m.group("values"))
    assert values == frozenset({"phase", "per-file", "sub-task"})


def test_doc_regex_with_backticked_values():
    text = "`worktree_mode` ∈ {`in_place`, `skill_worktree`, `wrapper_worktree`}"
    m = fec._DOC_ENUM_RE.search(text)
    assert m is not None
    assert m.group("name") == "worktree_mode"
    values = fec._parse_doc_values(m.group("values"))
    assert values == frozenset({"in_place", "skill_worktree", "wrapper_worktree"})


def test_doc_regex_with_quoted_values():
    text = 'verdict ∈ {"approve", "needs-attention"}'
    m = fec._DOC_ENUM_RE.search(text)
    assert m is not None
    values = fec._parse_doc_values(m.group("values"))
    assert values == frozenset({"approve", "needs-attention"})


def test_doc_regex_no_spaces():
    text = "x ∈ {a,b,c}"
    m = fec._DOC_ENUM_RE.search(text)
    assert m is not None
    values = fec._parse_doc_values(m.group("values"))
    assert values == frozenset({"a", "b", "c"})


def test_doc_regex_excludes_curly_suffix_shorthand():
    """``mode ∈ {skill,wrapper}_worktree`` 是文字简写,regex 必须不匹配。

    若误匹配会把 ``{skill, wrapper}`` 当 enum,与 _VALID_WORKTREE_MODES
    canonical 比对就会假阳性 drift。negative lookahead `(?!_[a-z])` 守门。
    """
    text = "accepted → mode ∈ {skill,wrapper}_worktree"
    m = fec._DOC_ENUM_RE.search(text)
    assert m is None, f"regex should reject shorthand form, but matched: {m}"


# ---------------------------------------------------------------------------
# _parse_doc_values
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("a, b, c", {"a", "b", "c"}),
        ("a,b,c", {"a", "b", "c"}),
        ("`a`, `b`", {"a", "b"}),
        ('"a", "b"', {"a", "b"}),
        ("'a', 'b'", {"a", "b"}),
        ("  a  ,   b  ", {"a", "b"}),
        ("a", {"a"}),
        ("", set()),  # 空 token 全跳过
        (",,", set()),  # 全空 token
    ],
)
def test_parse_doc_values_variants(raw, expected):
    assert fec._parse_doc_values(raw) == frozenset(expected)


# ---------------------------------------------------------------------------
# _compute_drift
# ---------------------------------------------------------------------------


def _mk_canonical(constant: str, values: set[str], doc_field: str | None) -> fec.CanonicalEnum:
    return fec.CanonicalEnum(
        constant=constant,
        file="tools/sample.py",
        line=1,
        values=frozenset(values),
        doc_field=doc_field,
    )


def _mk_occurrence(name: str, values: set[str], file_: str = "CLAUDE.md", line: int = 1) -> fec.DocOccurrence:
    return fec.DocOccurrence(
        name=name,
        file=file_,
        line=line,
        values=frozenset(values),
    )


def test_compute_drift_no_drift_when_sets_match():
    canonical = [_mk_canonical("_VALID_X", {"a", "b"}, doc_field="x")]
    occurrences = [_mk_occurrence("x", {"b", "a"})]  # 顺序无关
    drifts, actionable, unmapped = fec._compute_drift(canonical, occurrences)
    assert drifts == []
    assert actionable == []  # mapped + occurrence found = no actionable
    assert unmapped == []


def test_compute_drift_detects_missing_in_doc():
    canonical = [_mk_canonical("_VALID_X", {"a", "b", "c"}, doc_field="x")]
    occurrences = [_mk_occurrence("x", {"a", "b"})]
    drifts, _, _ = fec._compute_drift(canonical, occurrences)
    assert len(drifts) == 1
    assert drifts[0].missing_in_doc == frozenset({"c"})
    assert drifts[0].extra_in_doc == frozenset()


def test_compute_drift_detects_extra_in_doc():
    canonical = [_mk_canonical("_VALID_X", {"a"}, doc_field="x")]
    occurrences = [_mk_occurrence("x", {"a", "rogue"})]
    drifts, _, _ = fec._compute_drift(canonical, occurrences)
    assert len(drifts) == 1
    assert drifts[0].missing_in_doc == frozenset()
    assert drifts[0].extra_in_doc == frozenset({"rogue"})


def test_compute_drift_actionable_warning_for_mapped_no_doc():
    canonical = [_mk_canonical("_VALID_X", {"a"}, doc_field="x")]
    occurrences = []  # docs 完全无 ∈ {} 出现
    drifts, actionable, unmapped = fec._compute_drift(canonical, occurrences)
    assert drifts == []
    assert any("no `x ∈ {…}` occurrence" in w for w in actionable)
    assert unmapped == []


def test_compute_drift_unmapped_canonical_goes_to_unmapped_bucket():
    canonical = [_mk_canonical("_VALID_INTERNAL", {"a"}, doc_field=None)]
    occurrences = []
    drifts, actionable, unmapped = fec._compute_drift(canonical, occurrences)
    assert drifts == []
    assert actionable == []
    assert any("_VALID_INTERNAL" in w and "no _ENUM_MAPPING entry" in w for w in unmapped)


def test_compute_drift_actionable_warning_for_docs_only_enum():
    canonical = [_mk_canonical("_VALID_X", {"a"}, doc_field="x")]
    occurrences = [
        _mk_occurrence("x", {"a"}),
        _mk_occurrence("rogue_field", {"u", "v"}),
    ]
    drifts, actionable, _ = fec._compute_drift(canonical, occurrences)
    assert drifts == []
    assert any("docs-only enum `rogue_field" in w for w in actionable)


def test_compute_drift_multiple_doc_occurrences_each_checked():
    """同 enum 在多份 doc 出现:每个 occurrence 独立比对,只 drifted 的报。"""
    canonical = [_mk_canonical("_VALID_X", {"a", "b"}, doc_field="x")]
    occurrences = [
        _mk_occurrence("x", {"a", "b"}, file_="CLAUDE.md", line=10),  # 对
        _mk_occurrence("x", {"a"}, file_="docs.md", line=20),         # drifted
    ]
    drifts, _, _ = fec._compute_drift(canonical, occurrences)
    assert len(drifts) == 1
    assert drifts[0].doc_file == "docs.md"
    assert drifts[0].doc_line == 20
    assert drifts[0].missing_in_doc == frozenset({"b"})


# ---------------------------------------------------------------------------
# End-to-end via tmp_path:tools + docs 合成 → run() 走完整链路
# ---------------------------------------------------------------------------


def _make_synthetic_repo(tmp_path: Path, *, canonical_src: str, doc_text: str) -> Path:
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "sample.py").write_text(canonical_src, encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text(doc_text, encoding="utf-8")
    return tmp_path


def test_run_synthetic_clean(tmp_path, monkeypatch):
    canonical_src = (
        '_VALID_DEMO_FIELD: frozenset[str] = frozenset({"a", "b", "c"})\n'
    )
    doc_text = "demo_field ∈ {a, b, c}\n"
    monkeypatch.setitem(fec._ENUM_MAPPING, "_VALID_DEMO_FIELD", "demo_field")
    repo = _make_synthetic_repo(tmp_path, canonical_src=canonical_src, doc_text=doc_text)
    report = fec.run(repo, doc_targets=("CLAUDE.md",))
    assert report.drifts == []


def test_run_synthetic_drift(tmp_path, monkeypatch):
    canonical_src = (
        '_VALID_DEMO_FIELD: frozenset[str] = frozenset({"a", "b", "c"})\n'
    )
    doc_text = "demo_field ∈ {a, b}\n"  # 缺 c
    monkeypatch.setitem(fec._ENUM_MAPPING, "_VALID_DEMO_FIELD", "demo_field")
    repo = _make_synthetic_repo(tmp_path, canonical_src=canonical_src, doc_text=doc_text)
    report = fec.run(repo, doc_targets=("CLAUDE.md",))
    assert len(report.drifts) == 1
    drift = report.drifts[0]
    assert drift.enum_name == "demo_field"
    assert drift.missing_in_doc == frozenset({"c"})


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _run_cli(*args, repo_root: Path) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(TOOL), "--repo-root", str(repo_root), *args]
    return subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )


def test_cli_real_repo_exit_0():
    """真实 repo CLI 调用应 exit 0(baseline 无 drift)。"""
    res = _run_cli(repo_root=_REPO)
    assert res.returncode == 0, f"stdout:\n{res.stdout}\nstderr:\n{res.stderr}"
    assert "[OK] no enum cross-ref drift detected" in res.stdout


def test_cli_synthetic_drift_exit_2(tmp_path, monkeypatch):
    """合成 repo 制造 drift → CLI exit 2,stdout 含 [DRIFT]。"""
    # 注:CLI subprocess 不继承 monkeypatch,要在源文件直接注入测试 mapping。
    # 改用不需要 mapping 的方案:直接在 ENUM_MAPPING 里有一个内置测试钩子不现实,
    # 所以这里用「内置 5 个 mapped enum 之一」做 drift。
    canonical_src = (
        # 故意写错 canonical 值制造跟 doc 不一致
        '_VALID_WORKTREE_MODES: frozenset[str] = frozenset({"in_place"})\n'
    )
    doc_text = (
        "worktree_mode ∈ {in_place, skill_worktree, wrapper_worktree}\n"
    )
    repo = _make_synthetic_repo(tmp_path, canonical_src=canonical_src, doc_text=doc_text)
    res = _run_cli("--doc", "CLAUDE.md", repo_root=repo)
    assert res.returncode == 2, f"stdout:\n{res.stdout}\nstderr:\n{res.stderr}"
    assert "[DRIFT]" in res.stdout
    assert "worktree_mode" in res.stdout


def test_cli_show_all_includes_unmapped(tmp_path):
    """``--show-all`` 把 unmapped advisory 也打印。"""
    canonical_src = (
        '_VALID_INTERNAL_THING: frozenset[str] = frozenset({"x"})\n'
    )
    doc_text = ""  # docs 啥都没写
    repo = _make_synthetic_repo(tmp_path, canonical_src=canonical_src, doc_text=doc_text)
    # 无 --show-all:unmapped 应被 suppress
    res_quiet = _run_cli("--doc", "CLAUDE.md", repo_root=repo)
    assert res_quiet.returncode == 0
    assert "_VALID_INTERNAL_THING" not in res_quiet.stdout
    assert "(suppressed; pass --show-all to see)" in res_quiet.stdout
    # 加 --show-all:unmapped 应可见
    res_all = _run_cli("--doc", "CLAUDE.md", "--show-all", repo_root=repo)
    assert res_all.returncode == 0
    assert "_VALID_INTERNAL_THING" in res_all.stdout
    assert "UNMAPPED ADVISORIES" in res_all.stdout


def test_cli_help_renders():
    """parser 自身不抛 — sanity check。"""
    cmd = [sys.executable, str(TOOL), "--help"]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    assert res.returncode == 0
    assert "enum cross-reference" in res.stdout.lower()
