#!/usr/bin/env python3
"""Unit tests for ``tools/forgeue_preflight_wrapper.py``(W1 preflight wrapper)。

合约源(spec):
    openspec/changes/enhance-workflow-automation-executable-enforcement/specs/
        examples-and-acceptance/spec.md  ``Requirement: Preflight wrapper receipt JSON contract``

设计文档:
    openspec/changes/enhance-workflow-automation-executable-enforcement/design.md
        ``D-W1-ReceiptSchema`` + ``D-DispatchWrapperBoundary``

18 fence(P0.3 tasks.md):

base 6 ——
    - test_wrapper_self_manages_worktree_and_writes_receipt_with_13_fields
    - test_receipt_json_well_formed
    - test_worktree_path_absolute
    - test_cascade_exit_code_zero
    - test_wrapper_stdout_outputs_relative_path
    - test_default_receipts_dir_when_unset
    - test_worktree_action_enum_in_created_or_reused

failure path 6 ——
    - test_cascade_check_fail_exit_5
    - test_wrong_cwd_exit_6_stderr_contains_isolated_worktree
    - test_dirty_worktree_exit_6_stderr_contains_dirty
    - test_git_not_repo_exit_6
    - test_receipt_dir_not_writable_exit_7
    - test_unknown_skill_exit_5

reuse 3(D-OQ-1)——
    - test_reuse_if_clean_returns_reused_action
    - test_reuse_if_clean_dirty_tree_rejects
    - test_different_branch_or_orphaned_worktree_handled

CLI smoke 2 ——
    - test_cli_help_exit_0
    - test_cli_minimal_invocation_smoke

(总 18:6 base + 6 fail + 3 reuse + 2 CLI + 1 happy-path = 18,prompt 计入说明)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# repo / tool / module wiring(沿 tests/unit/test_skill_cascade_check.py 模式)
# ---------------------------------------------------------------------------

_REPO = Path(__file__).resolve().parents[2]
_TOOLS = _REPO / "tools"
WRAPPER = _TOOLS / "forgeue_preflight_wrapper.py"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


# 假 SKILL.md(无 ## Integration 段 → cascade check 自动 exit 0;沿
# tests/unit/test_skill_cascade_check.py SAMPLE_NO_INTEGRATION)
_SAMPLE_NO_INTEGRATION = """\
---
name: dummy-leaf
description: dummy
---

# Dummy Leaf

## When to Use

Standalone skill, no deps.
"""


def _write_skill(root: Path, skill_name: str, body: str = _SAMPLE_NO_INTEGRATION) -> Path:
    """在 root 下创建 ``<skill_name>/SKILL.md`` fixture(沿 cascade check 测试模式)。"""
    bare = skill_name.split(":")[-1]
    skill_dir = root / bare
    skill_dir.mkdir(parents=True, exist_ok=True)
    md = skill_dir / "SKILL.md"
    md.write_text(body, encoding="utf-8")
    return md


def _init_repo(repo: Path) -> None:
    """初始化 git 仓库 + 一个 commit(worktree add 需要 HEAD 指向 commit)。"""
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=test@test", "-c", "user.name=test",
         "commit", "--allow-empty", "-m", "init"],
        cwd=str(repo), check=True, capture_output=True,
    )


@pytest.fixture
def temp_git_repo(tmp_path: Path) -> Path:
    """空 git 仓库 + 一个 commit。"""
    repo = tmp_path / "repo"
    _init_repo(repo)
    return repo


@pytest.fixture
def fake_skill_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """在 tmp_path 下放一个 fake skill,设 ``FORGEUE_SKILL_ROOT`` env var 指向它,
    返回该 skill 名(供 ``--skill`` 参数使用)。

    cascade check subprocess 继承父进程 env → 子进程通过 FORGEUE_SKILL_ROOT 找到
    fake SKILL.md → 无 Integration 段 → exit 0。
    """
    skills_root = tmp_path / "fake-skills"
    skill_name = "superpowers:dummy-leaf"
    _write_skill(skills_root, skill_name)
    monkeypatch.setenv("FORGEUE_SKILL_ROOT", str(skills_root))
    return skill_name


def _invoke_wrapper(
    *,
    change_id: str,
    cwd: Path,
    worktrees_root: Path,
    skill: str,
    receipts_dir: Path | None = None,
    extra: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """跑 wrapper subprocess + 返回 result(env 由调用方通过 monkeypatch 设置)。"""
    cmd = [
        sys.executable, str(WRAPPER),
        "--change", change_id,
        "--cwd", str(cwd),
        "--worktrees-root", str(worktrees_root),
        "--skill", skill,
    ]
    if receipts_dir is not None:
        cmd.extend(["--receipts-dir", str(receipts_dir)])
    if extra:
        cmd.extend(extra)
    return subprocess.run(cmd, capture_output=True, text=True)


def _two_step_setup(
    repo: Path,
    change_id: str,
    skill: str,
) -> tuple[Path, subprocess.CompletedProcess[str], subprocess.CompletedProcess[str]]:
    """完整 W1 流:wrapper 第一次在 main repo 调用 → 创建 worktree + exit 6;
    第二次在 worktree 内调用 → 写 receipt + exit 0。返回 (target_worktree, first_run, second_run)。
    """
    worktrees_root = repo / ".worktrees"
    target = (worktrees_root / change_id).resolve()

    first = _invoke_wrapper(
        change_id=change_id,
        cwd=repo,
        worktrees_root=worktrees_root,
        skill=skill,
    )
    second = _invoke_wrapper(
        change_id=change_id,
        cwd=target,
        worktrees_root=worktrees_root,
        skill=skill,
    )
    return target, first, second


# ---------------------------------------------------------------------------
# Base fence #1 — 主 happy-path:wrapper 自管 worktree + 13 字段 receipt
# ---------------------------------------------------------------------------


def test_wrapper_self_manages_worktree_and_writes_receipt_with_13_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """W1 wrapper 自管 isolated worktree(git worktree subprocess)+ 13 字段 receipt。"""
    repo = tmp_path / "repo"
    _init_repo(repo)

    # fake skill fixture(避免依赖真实 SKILL.md;cascade check 自动 exit 0)
    skills_root = tmp_path / "fake-skills"
    skill_name = "superpowers:dummy-leaf"
    _write_skill(skills_root, skill_name)
    monkeypatch.setenv("FORGEUE_SKILL_ROOT", str(skills_root))

    change_id = "test-change"
    target, first, second = _two_step_setup(repo, change_id, skill_name)

    # 第一次:从 main repo 调用 → wrapper 创建 worktree + exit 6 wrong-cwd
    assert first.returncode == 6, (
        f"first invoke from main repo should exit 6 (wrong-cwd);\n"
        f"stdout={first.stdout}\nstderr={first.stderr}"
    )
    assert target.exists(), "worktree directory must be created on first invoke"
    assert "isolated worktree" in first.stderr.lower()

    # 第二次:从 worktree 内调用 → 应成功
    assert second.returncode == 0, (
        f"second invoke from inside worktree should succeed;\n"
        f"stdout={second.stdout}\nstderr={second.stderr}"
    )

    # stdout 应输出 receipt 相对路径
    receipt_rel_path = second.stdout.strip()
    receipt_abs_path = target / "openspec" / "changes" / change_id / receipt_rel_path
    assert receipt_abs_path.exists(), f"receipt not found at {receipt_abs_path}"

    payload = json.loads(receipt_abs_path.read_text(encoding="utf-8"))
    expected_fields = {
        "receipt_id", "change_id", "protocol_version",
        "worktree_path", "is_isolated_worktree", "worktree_action",
        "base_sha", "base_branch", "cwd_at_invocation",
        "skill_cascade_check", "created_at", "wrapper_version",
    }
    assert expected_fields.issubset(set(payload.keys())), (
        f"missing 13-field schema keys: {expected_fields - set(payload.keys())}"
    )
    assert payload["protocol_version"] == "v2"
    assert payload["change_id"] == change_id
    assert payload["is_isolated_worktree"] is True
    assert payload["worktree_action"] in {"created", "reused"}
    assert payload["skill_cascade_check"]["exit_code"] == 0


# ---------------------------------------------------------------------------
# Base fence #2 — receipt JSON well-formed
# ---------------------------------------------------------------------------


def test_receipt_json_well_formed(
    temp_git_repo: Path,
    fake_skill_env: str,
):
    """receipt 写出后是合法 JSON;字段类型符合 schema(string / bool / int / dict)。"""
    target, _, second = _two_step_setup(
        temp_git_repo, "json-shape-change", fake_skill_env
    )
    assert second.returncode == 0, second.stderr

    receipt_rel = second.stdout.strip()
    receipt_abs = target / "openspec" / "changes" / "json-shape-change" / receipt_rel
    text = receipt_abs.read_text(encoding="utf-8")
    payload = json.loads(text)  # 不抛 = well-formed

    assert isinstance(payload["receipt_id"], str)
    assert isinstance(payload["change_id"], str)
    assert isinstance(payload["protocol_version"], str)
    assert isinstance(payload["worktree_path"], str)
    assert isinstance(payload["is_isolated_worktree"], bool)
    assert isinstance(payload["worktree_action"], str)
    assert isinstance(payload["cwd_at_invocation"], str)
    assert isinstance(payload["skill_cascade_check"], dict)
    assert isinstance(payload["skill_cascade_check"]["exit_code"], int)
    assert isinstance(payload["created_at"], str)
    assert isinstance(payload["wrapper_version"], str)


# ---------------------------------------------------------------------------
# Base fence #3 — worktree_path 是绝对路径
# ---------------------------------------------------------------------------


def test_worktree_path_absolute(
    temp_git_repo: Path,
    fake_skill_env: str,
):
    """receipt.worktree_path 必须是绝对路径(spec.md scenario 4)。"""
    target, _, second = _two_step_setup(
        temp_git_repo, "abs-path-change", fake_skill_env
    )
    assert second.returncode == 0
    receipt_rel = second.stdout.strip()
    receipt_abs = target / "openspec" / "changes" / "abs-path-change" / receipt_rel
    payload = json.loads(receipt_abs.read_text(encoding="utf-8"))
    assert os.path.isabs(payload["worktree_path"]), (
        f"worktree_path must be absolute, got {payload['worktree_path']}"
    )


# ---------------------------------------------------------------------------
# Base fence #4 — cascade exit_code 嵌入 receipt 必须 0
# ---------------------------------------------------------------------------


def test_cascade_exit_code_zero(
    temp_git_repo: Path,
    fake_skill_env: str,
):
    """receipt.skill_cascade_check.exit_code 必须 0(spec.md scenario 4)。"""
    target, _, second = _two_step_setup(
        temp_git_repo, "cascade-zero-change", fake_skill_env
    )
    assert second.returncode == 0
    receipt_rel = second.stdout.strip()
    receipt_abs = target / "openspec" / "changes" / "cascade-zero-change" / receipt_rel
    payload = json.loads(receipt_abs.read_text(encoding="utf-8"))
    assert payload["skill_cascade_check"]["exit_code"] == 0
    assert payload["skill_cascade_check"]["skill_invoked"] == fake_skill_env


# ---------------------------------------------------------------------------
# Base fence #5 — wrapper stdout 输出 receipt 相对路径
# ---------------------------------------------------------------------------


def test_wrapper_stdout_outputs_relative_path(
    temp_git_repo: Path,
    fake_skill_env: str,
):
    """wrapper 成功时 stdout 输出 ``preflight_receipts/<receipt_id>.json`` 相对路径,
    供命令模板 capture 写到 evidence frontmatter。
    """
    _target, _, second = _two_step_setup(
        temp_git_repo, "stdout-rel-change", fake_skill_env
    )
    assert second.returncode == 0
    rel = second.stdout.strip()
    assert rel.startswith("preflight_receipts/"), (
        f"stdout should be relative path under preflight_receipts/; got {rel!r}"
    )
    assert rel.endswith(".json")
    # 不应是绝对路径(命令模板拿这个 relative 写 evidence)
    assert not os.path.isabs(rel)


# ---------------------------------------------------------------------------
# Base fence #6 — default receipts_dir(unset)→ 落 worktree 内 openspec/changes/
# ---------------------------------------------------------------------------


def test_default_receipts_dir_when_unset(
    temp_git_repo: Path,
    fake_skill_env: str,
):
    """没传 ``--receipts-dir`` 时 receipt 落 worktree 内
    ``openspec/changes/<change>/preflight_receipts/`` 默认路径。
    """
    target, _, second = _two_step_setup(
        temp_git_repo, "default-dir-change", fake_skill_env
    )
    assert second.returncode == 0
    receipts_dir = target / "openspec" / "changes" / "default-dir-change" / "preflight_receipts"
    assert receipts_dir.is_dir()
    files = list(receipts_dir.glob("*.json"))
    assert len(files) == 1, f"expected 1 receipt file, got {len(files)}: {files}"


# ---------------------------------------------------------------------------
# Base fence #7 — worktree_action enum
# ---------------------------------------------------------------------------


def test_worktree_action_enum_in_created_or_reused(
    temp_git_repo: Path,
    fake_skill_env: str,
):
    """成功时 worktree_action 必须 ∈ {created, reused}(spec.md scenario 4)。"""
    target, _, second = _two_step_setup(
        temp_git_repo, "action-enum-change", fake_skill_env
    )
    assert second.returncode == 0
    receipt_rel = second.stdout.strip()
    receipt_abs = target / "openspec" / "changes" / "action-enum-change" / receipt_rel
    payload = json.loads(receipt_abs.read_text(encoding="utf-8"))
    assert payload["worktree_action"] in {"created", "reused"}


# ---------------------------------------------------------------------------
# Failure path #1 — cascade check fail → exit 5
# ---------------------------------------------------------------------------


def test_cascade_check_fail_exit_5(
    temp_git_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """skill 含 ## Integration + REQUIRED dep 但 wrapper 只 invoke 主 skill(不带 deps),
    cascade check exit 5;wrapper 也 exit 5。

    实现细节:wrapper subprocess 调 ``--invoked <skill>`` 只传主 skill 自己;若
    SKILL.md 声明 REQUIRED dep ≠ 自己,cascade check 找到 missing dep → exit 5。
    """
    skills_root = tmp_path / "skills-with-deps"
    skill_name = "superpowers:has-deps"
    body_with_required = """\
---
name: has-deps
description: dummy
---

## Integration

**Required workflow skills:**
- **superpowers:some-other-skill** - REQUIRED: prereq must be invoked first
"""
    _write_skill(skills_root, skill_name, body=body_with_required)
    monkeypatch.setenv("FORGEUE_SKILL_ROOT", str(skills_root))

    # 第一次跑(在 main repo)创建 worktree + exit 6 wrong-cwd
    worktrees_root = temp_git_repo / ".worktrees"
    target = (worktrees_root / "cascade-fail-change").resolve()
    first = _invoke_wrapper(
        change_id="cascade-fail-change",
        cwd=temp_git_repo,
        worktrees_root=worktrees_root,
        skill=skill_name,
    )
    assert first.returncode == 6  # wrong-cwd

    # 第二次跑(在 worktree)→ cascade check 应找到 missing dep → exit 5
    second = _invoke_wrapper(
        change_id="cascade-fail-change",
        cwd=target,
        worktrees_root=worktrees_root,
        skill=skill_name,
    )
    assert second.returncode == 5, (
        f"cascade check fail should map to exit 5;\n"
        f"stdout={second.stdout}\nstderr={second.stderr}"
    )
    assert "cascade" in second.stderr.lower()


# ---------------------------------------------------------------------------
# Failure path #2 — wrong-cwd → exit 6 + stderr "isolated worktree"
# ---------------------------------------------------------------------------


def test_wrong_cwd_exit_6_stderr_contains_isolated_worktree(
    temp_git_repo: Path,
    fake_skill_env: str,
):
    """wrapper 在 main repo 调用 → 创建 worktree 但 cwd 校验 fail → exit 6 +
    stderr 含 "isolated worktree"(spec.md Scenario "wrapper 拒绝 wrong-cwd")。
    """
    worktrees_root = temp_git_repo / ".worktrees"
    first = _invoke_wrapper(
        change_id="wrong-cwd-change",
        cwd=temp_git_repo,
        worktrees_root=worktrees_root,
        skill=fake_skill_env,
    )
    assert first.returncode == 6
    assert "isolated worktree" in first.stderr.lower()


# ---------------------------------------------------------------------------
# Failure path #3 — dirty worktree → exit 6 + stderr "dirty"
# ---------------------------------------------------------------------------


def test_dirty_worktree_exit_6_stderr_contains_dirty(
    temp_git_repo: Path,
    fake_skill_env: str,
):
    """已存在 worktree 但 dirty → wrapper exit 6 + stderr 含 "dirty"
    (spec.md Scenario "wrapper 拒绝 dirty worktree")。
    """
    worktrees_root = temp_git_repo / ".worktrees"
    target = (worktrees_root / "dirty-change").resolve()

    # 第一次跑创建 worktree(在 main repo,exit 6 wrong-cwd 但 worktree 已建)
    first = _invoke_wrapper(
        change_id="dirty-change",
        cwd=temp_git_repo,
        worktrees_root=worktrees_root,
        skill=fake_skill_env,
    )
    assert first.returncode == 6
    assert target.exists()

    # 在 worktree 里写一个 untracked 文件 → dirty
    (target / "dirty_file.txt").write_text("uncommitted change", encoding="utf-8")

    # 再跑 wrapper(从 worktree 内调用)→ dirty → exit 6 + stderr "dirty"
    second = _invoke_wrapper(
        change_id="dirty-change",
        cwd=target,
        worktrees_root=worktrees_root,
        skill=fake_skill_env,
    )
    assert second.returncode == 6
    assert "dirty" in second.stderr.lower()


# ---------------------------------------------------------------------------
# Failure path #4 — git not repo → exit 6
# ---------------------------------------------------------------------------


def test_git_not_repo_exit_6(
    tmp_path: Path,
    fake_skill_env: str,
):
    """cwd 不在任何 git 仓库内 → wrapper exit 6(``not inside a git repository``)。"""
    no_repo = tmp_path / "no-git-here"
    no_repo.mkdir()
    worktrees_root = no_repo / ".worktrees"

    proc = _invoke_wrapper(
        change_id="no-repo-change",
        cwd=no_repo,
        worktrees_root=worktrees_root,
        skill=fake_skill_env,
    )
    assert proc.returncode == 6
    assert "git" in proc.stderr.lower()


# ---------------------------------------------------------------------------
# Failure path #5 — receipt dir 不可写 → exit 7
# ---------------------------------------------------------------------------


def test_receipt_dir_not_writable_exit_7(
    temp_git_repo: Path,
    fake_skill_env: str,
    tmp_path: Path,
):
    """``--receipts-dir`` 指向不可写路径(把它指向已存在的文件)→ wrapper exit 7。

    Windows 下 read-only 目录权限语义不可靠,改用"目录路径上有冲突文件" 触发
    OSError(``mkdir`` 在路径含已存在文件时抛 FileExistsError / NotADirectoryError,
    都是 OSError 子类)。

    blocking_file 落在 worktree 之**外**(避免污染 dirty check)。
    """
    worktrees_root = temp_git_repo / ".worktrees"
    target = (worktrees_root / "receipt-fail-change").resolve()

    # 第一次跑创建 worktree(在 main repo)
    first = _invoke_wrapper(
        change_id="receipt-fail-change",
        cwd=temp_git_repo,
        worktrees_root=worktrees_root,
        skill=fake_skill_env,
    )
    assert first.returncode == 6  # wrong-cwd 但 worktree 已建

    # 在 worktree 之外创建一个文件,把 receipts-dir 指向它 →
    # ``mkdir(parents=True, exist_ok=True)`` 在路径已是文件时
    # 抛 FileExistsError(POSIX)/ NotADirectoryError(尝试在文件下创建子目录)→ exit 7
    blocking_file = tmp_path / "blocked-as-receipts-dir"
    blocking_file.write_text("not a directory", encoding="utf-8")
    fake_receipts_dir = blocking_file / "child"  # 指向 file 下的"子目录"

    second = _invoke_wrapper(
        change_id="receipt-fail-change",
        cwd=target,
        worktrees_root=worktrees_root,
        skill=fake_skill_env,
        receipts_dir=fake_receipts_dir,
    )
    assert second.returncode == 7, (
        f"receipt write fail should exit 7;\n"
        f"stdout={second.stdout}\nstderr={second.stderr}"
    )


# ---------------------------------------------------------------------------
# Failure path #6 — unknown skill → exit 5
# ---------------------------------------------------------------------------


def test_unknown_skill_exit_5(
    temp_git_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """``--skill <unknown>`` cascade check 找不到 SKILL.md → exit 5。"""
    # 设一个空的 skills root,完全不放任何 SKILL.md
    empty_skills = tmp_path / "empty-skills"
    empty_skills.mkdir()
    monkeypatch.setenv("FORGEUE_SKILL_ROOT", str(empty_skills))
    # 同时清掉 plugin cache / codex 的副作用(指向空 fake home)
    fake_home = tmp_path / "fake-home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("USERPROFILE", str(fake_home))  # Windows
    monkeypatch.delenv("CODEX_HOME", raising=False)

    worktrees_root = temp_git_repo / ".worktrees"
    target = (worktrees_root / "unknown-skill-change").resolve()

    first = _invoke_wrapper(
        change_id="unknown-skill-change",
        cwd=temp_git_repo,
        worktrees_root=worktrees_root,
        skill="superpowers:no-such-skill-anywhere",
    )
    assert first.returncode == 6  # wrong-cwd

    second = _invoke_wrapper(
        change_id="unknown-skill-change",
        cwd=target,
        worktrees_root=worktrees_root,
        skill="superpowers:no-such-skill-anywhere",
    )
    assert second.returncode == 5, (
        f"unknown skill should exit 5;\n"
        f"stdout={second.stdout}\nstderr={second.stderr}"
    )


# ---------------------------------------------------------------------------
# Reuse #1(D-OQ-1)— --reuse-if-clean + clean tree → reused action
# ---------------------------------------------------------------------------


def test_reuse_if_clean_returns_reused_action(
    temp_git_repo: Path,
    fake_skill_env: str,
):
    """已存在 clean worktree → 第二次 wrapper 调用返回 ``worktree_action: reused``。

    spec 实际上 wrapper 总是 reuse if clean(spec.md scenario 1 默认行为);
    ``--reuse-if-clean`` 是 advisory flag(D-OQ-1)。
    """
    worktrees_root = temp_git_repo / ".worktrees"
    target, _, second = _two_step_setup(
        temp_git_repo, "reuse-clean-change", fake_skill_env
    )
    assert second.returncode == 0
    receipt_rel = second.stdout.strip()
    receipt_abs = target / "openspec" / "changes" / "reuse-clean-change" / receipt_rel
    payload_first = json.loads(receipt_abs.read_text(encoding="utf-8"))
    # 第一次 second 调用:worktree 上一步刚创建 → reused(因为已在 list 中了)
    assert payload_first["worktree_action"] == "reused"

    # 再调一次(同样在 clean worktree 内)→ 仍 reused
    third = _invoke_wrapper(
        change_id="reuse-clean-change",
        cwd=target,
        worktrees_root=worktrees_root,
        skill=fake_skill_env,
        extra=["--reuse-if-clean"],
    )
    assert third.returncode == 0
    rel3 = third.stdout.strip()
    abs3 = target / "openspec" / "changes" / "reuse-clean-change" / rel3
    payload3 = json.loads(abs3.read_text(encoding="utf-8"))
    assert payload3["worktree_action"] == "reused"


# ---------------------------------------------------------------------------
# Reuse #2(D-OQ-1)— --reuse-if-clean + dirty tree → reject
# ---------------------------------------------------------------------------


def test_reuse_if_clean_dirty_tree_rejects(
    temp_git_repo: Path,
    fake_skill_env: str,
):
    """已存在 worktree 但 dirty + --reuse-if-clean → 仍然 exit 6 + stderr "dirty"
    (clean 才能 reuse;dirty 强制 reject 沿 spec.md scenario 3)。
    """
    worktrees_root = temp_git_repo / ".worktrees"
    target = (worktrees_root / "reuse-dirty-change").resolve()

    # 第一次跑创建 worktree
    first = _invoke_wrapper(
        change_id="reuse-dirty-change",
        cwd=temp_git_repo,
        worktrees_root=worktrees_root,
        skill=fake_skill_env,
    )
    assert first.returncode == 6  # wrong-cwd 但 worktree 已建
    assert target.exists()

    # 弄脏 worktree
    (target / "uncommitted.txt").write_text("dirty", encoding="utf-8")

    # 带 --reuse-if-clean flag 再跑 → 仍 exit 6
    second = _invoke_wrapper(
        change_id="reuse-dirty-change",
        cwd=target,
        worktrees_root=worktrees_root,
        skill=fake_skill_env,
        extra=["--reuse-if-clean"],
    )
    assert second.returncode == 6
    assert "dirty" in second.stderr.lower()


# ---------------------------------------------------------------------------
# Reuse #3 — orphaned worktree handled(branch 已删 / worktree dir 残留)
# ---------------------------------------------------------------------------


def test_different_branch_or_orphaned_worktree_handled(
    temp_git_repo: Path,
    fake_skill_env: str,
):
    """边界:wrapper-managed worktree 目录残留(被手工 rm -rf;git 仍记录但目录已无)
    → wrapper 应 graceful 处理(用 ``git worktree prune`` 或重新创建)。

    这里我们模拟更轻量的 case:worktree dir 还在 + 已注册到 git worktree list +
    clean → 直接 reuse(沿正常路径,不应崩)。该 fence 兜底 D-OQ-1 reuse 边界。
    """
    worktrees_root = temp_git_repo / ".worktrees"
    target, first, second = _two_step_setup(
        temp_git_repo, "orphan-edge-change", fake_skill_env
    )
    assert first.returncode == 6
    assert second.returncode == 0  # second 调用的 reuse 路径必须工作

    # 校验 receipt 含 base_branch 字段(detached HEAD 时可能是 ``HEAD`` 字符串)
    receipt_rel = second.stdout.strip()
    receipt_abs = target / "openspec" / "changes" / "orphan-edge-change" / receipt_rel
    payload = json.loads(receipt_abs.read_text(encoding="utf-8"))
    assert "base_branch" in payload
    # branch 字段可能 None / "HEAD" / "worktree-orphan-edge-change" — 任一合法
    assert payload["base_branch"] is None or isinstance(payload["base_branch"], str)


# ---------------------------------------------------------------------------
# CLI smoke #1 — --help 退 0
# ---------------------------------------------------------------------------


def test_cli_help_exit_0():
    """``python tools/forgeue_preflight_wrapper.py --help`` 必须 exit 0
    (argparse 标准行为;沿 cascade check 测试模式)。
    """
    proc = subprocess.run(
        [sys.executable, str(WRAPPER), "--help"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0
    assert "preflight wrapper" in proc.stdout.lower() or "wrapper" in proc.stdout.lower()
    assert "--change" in proc.stdout
    assert "--worktrees-root" in proc.stdout


# ---------------------------------------------------------------------------
# CLI smoke #2 — minimal invocation(只 --change + --cwd + --worktrees-root)
# ---------------------------------------------------------------------------


def test_cli_minimal_invocation_smoke(
    temp_git_repo: Path,
    fake_skill_env: str,
):
    """最小调用:仅 ``--change`` + ``--cwd`` + ``--worktrees-root``;wrapper 用
    默认 skill / 默认 receipts-dir;happy path 走完。
    """
    worktrees_root = temp_git_repo / ".worktrees"
    target = (worktrees_root / "minimal-change").resolve()

    # 第一次:main repo → exit 6
    first = subprocess.run(
        [sys.executable, str(WRAPPER),
         "--change", "minimal-change",
         "--cwd", str(temp_git_repo),
         "--worktrees-root", str(worktrees_root),
         "--skill", fake_skill_env],
        capture_output=True, text=True,
    )
    assert first.returncode == 6

    # 第二次:worktree → exit 0
    second = subprocess.run(
        [sys.executable, str(WRAPPER),
         "--change", "minimal-change",
         "--cwd", str(target),
         "--worktrees-root", str(worktrees_root),
         "--skill", fake_skill_env],
        capture_output=True, text=True,
    )
    assert second.returncode == 0, (
        f"minimal invocation should succeed;\n"
        f"stdout={second.stdout}\nstderr={second.stderr}"
    )
    rel = second.stdout.strip()
    assert rel.startswith("preflight_receipts/")


# ---------------------------------------------------------------------------
# ADR-013 codex round 2 plan review F3 writeback(W7-a wrapper bug fix
# regression):_git_repo_root 在 worktree 内调用必须返 main repo 而非 worktree
# 自身,否则 _resolve_target_worktree 算 nested target → ``git worktree add``
# nested fail(本仓库实测 "Filename too long" 链锁失败)。
# ---------------------------------------------------------------------------


def test_git_repo_root_from_inside_worktree_returns_main_repo(
    tmp_path: Path,
):
    """``_git_repo_root(<inside-worktree-cwd>)`` MUST 返回 main repo 路径,**不**返
    worktree 自身路径(原 bug:用 ``git rev-parse --show-toplevel`` 在 worktree 内
    返 worktree 自身 → ``_resolve_target_worktree`` 算 nested target → 创第二
    worktree 失败)。

    本 fence 测 fixed wrapper 用 ``git rev-parse --git-common-dir`` 取共享
    ``.git`` 目录的 parent 作 main repo root,两种调用上下文(main / worktree)
    返同一 main repo 路径。
    """
    # import wrapper 内部 helper(沿 SUT 直接 unit-test)
    sys.path.insert(0, str(_TOOLS))
    try:
        from forgeue_preflight_wrapper import _git_repo_root  # noqa: WPS433
    finally:
        sys.path.pop(0)

    repo = tmp_path / "repo"
    _init_repo(repo)

    # 创 worktree(用 git CLI 直接,不走 wrapper)
    worktree = tmp_path / "wt"
    subprocess.run(
        ["git", "worktree", "add", str(worktree), "-b", "wt-branch"],
        cwd=str(repo), check=True, capture_output=True,
    )

    # 校验:从 main repo 内 cwd 调用 → 返 main repo
    root_from_main = _git_repo_root(repo)
    assert root_from_main is not None
    assert os.path.realpath(root_from_main) == os.path.realpath(repo), (
        f"_git_repo_root from main repo cwd should return main repo;\n"
        f"got {root_from_main!r}, expected {repo!r}"
    )

    # 校验(关键 fence):从 worktree 内 cwd 调用 → 仍返 main repo,**不**返 worktree
    root_from_worktree = _git_repo_root(worktree)
    assert root_from_worktree is not None
    assert os.path.realpath(root_from_worktree) == os.path.realpath(repo), (
        f"_git_repo_root from inside worktree cwd MUST return main repo "
        f"(W7-a bug fix for ADR-013);\n"
        f"got {root_from_worktree!r}, expected {repo!r} (NOT worktree {worktree!r})"
    )
    assert os.path.realpath(root_from_worktree) != os.path.realpath(worktree), (
        f"_git_repo_root from inside worktree MUST NOT return worktree itself "
        f"(this is the original bug — pre-fix used git rev-parse --show-toplevel "
        f"which returns worktree self);\n"
        f"got {root_from_worktree!r}"
    )


def test_wrapper_reuse_path_works_when_invoked_from_existing_worktree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """Regression for ADR-013 codex round 2 plan review F3:wrapper 第二次从已
    创建的 worktree 内调用应走 reuse 路径(exit 0 + receipt 写入),**不**应试图
    nested 创建第二 worktree。

    Pre-fix:``_git_repo_root`` 在 worktree 内返 worktree 自身 →
    ``_resolve_target_worktree`` 算 ``<worktree>/.worktrees/<change>`` nested
    target → ``git worktree add`` 在 nested 路径创 worktree → "Filename too
    long" / branch 已存在 链锁失败(本仓库实测 D:/ClaudeProject/ForgeUE_claude
    路径深度触发 Windows MAX_PATH)。

    Post-fix:_git_repo_root 用 git-common-dir 推断 main repo,target =
    ``<main>/.worktrees/<change>``;`_ensure_worktree` `worktree list` 找到
    existing entry → 走 reused 分支 → exit 0 + receipt OK。
    """
    repo = tmp_path / "repo"
    _init_repo(repo)

    skills_root = tmp_path / "fake-skills"
    skill_name = "superpowers:dummy-leaf"
    _write_skill(skills_root, skill_name)
    monkeypatch.setenv("FORGEUE_SKILL_ROOT", str(skills_root))

    change_id = "wt-reuse-regression"
    target, first, second = _two_step_setup(repo, change_id, skill_name)

    # First: from main repo → exit 6 (worktree created + wrong-cwd warning)
    assert first.returncode == 6
    assert target.exists()

    # Second (key fence): from worktree internal cwd → exit 0 (reuse path works)
    assert second.returncode == 0, (
        f"reuse path from inside worktree MUST succeed (W7-a bug fix);\n"
        f"stdout={second.stdout}\nstderr={second.stderr}"
    )

    # Verify worktree_action == "reused" (not "created" — that would mean
    # wrapper still tried to nested-create instead of reusing)
    receipt_rel = second.stdout.strip()
    receipt_abs = target / "openspec" / "changes" / change_id / receipt_rel
    payload = json.loads(receipt_abs.read_text(encoding="utf-8"))
    assert payload["worktree_action"] == "reused", (
        f"second invoke from worktree MUST reuse existing worktree, not create "
        f"a nested one;\n got worktree_action={payload['worktree_action']!r}"
    )
    # Verify worktree_path is the original worktree, not a nested path
    assert os.path.realpath(payload["worktree_path"]) == os.path.realpath(target), (
        f"worktree_path in receipt MUST point to original worktree;\n"
        f"got {payload['worktree_path']!r}, expected {target!r}"
    )
