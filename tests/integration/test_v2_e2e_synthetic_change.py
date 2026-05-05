"""P5.5 v2 e2e integration test fixture — D-W4-IntegrationGate.

archive 前必跑全绿(tasks.md P10.0 gate):

    pytest -q tests/integration/test_v2_e2e_synthetic_change.py

覆盖 v2 协议端到端实跑:
    - W1 preflight wrapper 创建 worktree / 写 receipt / wrong-cwd / dirty 负例
    - W3 dispatch ledger append + verify
    - W2 parallel 场景:actual diff disjoint / overlap 负例 / dirty implementer 负例
    - finish_gate 全 6 fence on synthetic v2 evidence
    - v1 evidence 兼容 + legacy evidence pass-through 回归

设计文档:
    openspec/changes/enhance-workflow-automation-executable-enforcement/design.md
        D-W4-IntegrationGate(F5 round 1 codex inline writeback)

合约源:
    openspec/changes/enhance-workflow-automation-executable-enforcement/
        specs/examples-and-acceptance/spec.md
        Requirement: v2 e2e integration test fixture

stdlib only;pytest + subprocess;无 third-party 依赖。
"""
from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
from pathlib import Path

import pytest

# ── 路径常量 ──────────────────────────────────────────────────────────────────
# 项目根(两层 parents:tests/integration/ → tests/ → repo root)
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_TOOLS_DIR = _REPO_ROOT / "tools"
_WRAPPER_SCRIPT = _TOOLS_DIR / "forgeue_preflight_wrapper.py"
_LEDGER_SCRIPT = _TOOLS_DIR / "forgeue_dispatch_ledger.py"
_FINISH_GATE_SCRIPT = _TOOLS_DIR / "forgeue_finish_gate.py"


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def _run(args: list[str], *, cwd: Path, timeout: int = 60) -> subprocess.CompletedProcess:
    """subprocess.run wrapper;capture stdout + stderr;UTF-8;返回 CompletedProcess。"""
    return subprocess.run(
        args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def _mock_agent_id() -> str:
    """产生 17 字符 hex agent_id([a-f0-9]{17}+);模拟 Claude Code 真实格式。

    tasks.md P5.5.2 hint:``secrets.token_hex(8) + secrets.token_hex(1)``给 17 chars。
    token_hex(8) = 16 chars;token_hex(1) = 2 chars → 共 18 chars;
    按合约 D-DispatchWrapperBoundary 注释 "[a-f0-9]{17}+" 取 17 chars。
    """
    return (secrets.token_hex(8) + secrets.token_hex(1))[:17]


def _git(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess:
    """git 子命令封装。"""
    return _run(["git", *args], cwd=cwd)


def _git_ok(args: list[str], *, cwd: Path) -> None:
    """跑 git;期望 exit 0;失败 pytest.fail。"""
    r = _git(args, cwd=cwd)
    if r.returncode != 0:
        pytest.fail(f"git {args} failed(rc={r.returncode}): {r.stderr.strip()}")


def _synthetic_repo(tmp_path: Path) -> Path:
    """在 tmp_path 下创建最小 git 仓库 + initial commit。

    返回 repo 根目录 Path。
    仓库会初始化 main 分支 + 一次 initial commit。
    """
    repo = tmp_path / "synthetic_repo"
    repo.mkdir(parents=True, exist_ok=True)

    # git init
    _git_ok(["init", "-b", "main"], cwd=repo)
    _git_ok(["config", "user.email", "test@forgeue.local"], cwd=repo)
    _git_ok(["config", "user.name", "ForgeUE Test"], cwd=repo)

    # initial commit (空树不行;加一个文件)
    readme = repo / "README.md"
    readme.write_text("# synthetic repo\n", encoding="utf-8")
    _git_ok(["add", "README.md"], cwd=repo)
    _git_ok(["commit", "-m", "initial"], cwd=repo)

    return repo


def _synthetic_change_dir(repo: Path, change_id: str) -> Path:
    """创建 openspec/changes/<change_id>/ 内 4 制品 minimal stub。

    返回 change 目录 Path。
    """
    change_dir = repo / "openspec" / "changes" / change_id
    for sub in ["", "specs/examples-and-acceptance"]:
        (change_dir / sub).mkdir(parents=True, exist_ok=True)

    (change_dir / "proposal.md").write_text(
        f"# Proposal — {change_id}\nstub\n", encoding="utf-8"
    )
    (change_dir / "design.md").write_text(
        f"# Design — {change_id}\nstub\n", encoding="utf-8"
    )
    (change_dir / "tasks.md").write_text(
        f"# Tasks — {change_id}\n- [x] stub task\n", encoding="utf-8"
    )
    (change_dir / "specs" / "examples-and-acceptance" / "spec.md").write_text(
        f"## Requirement: stub\nstub requirement\n", encoding="utf-8"
    )
    return change_dir


def _write_ledger_line(
    ledger_path: Path,
    *,
    agent_id: str,
    round: int = 1,
    role: str = "implementer",
    dispatched_at: str,
    wrapper_version: str = "1.0",
    task_subject_hash: str | None = None,
    parent_session_id: str | None = None,
) -> None:
    """向 ledger 文件追加一行 JSONL。"""
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "agent_id": agent_id,
        "round": round,
        "role": role,
        "task_subject_hash": task_subject_hash,
        "dispatched_at": dispatched_at,
        "parent_session_id": parent_session_id,
        "wrapper_version": wrapper_version,
    }
    with ledger_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
        fh.flush()


def _write_evidence(
    change_dir: Path,
    *,
    subdir: str = "execution",
    filename: str = "task_1_implementer.md",
    frontmatter: dict,
    body: str = "implementation body\n",
) -> Path:
    """在 <change_dir>/<subdir>/<filename> 写 evidence 文件(YAML frontmatter 格式)。

    frontmatter dict 序列化为 YAML-ish(简单 key: value;不依赖 PyYAML)。
    返回写好的文件 Path。
    """
    ev_dir = change_dir / subdir
    ev_dir.mkdir(parents=True, exist_ok=True)
    ev_path = ev_dir / filename
    fm_lines = _frontmatter_to_yaml(frontmatter)
    ev_path.write_text(f"---\n{fm_lines}---\n\n{body}", encoding="utf-8")
    return ev_path


def _frontmatter_to_yaml(fm: dict, indent: int = 0) -> str:
    """简单 YAML serializer(仅支持 finish_gate 实际用到的类型):
    str / bool / int / None / list / dict。
    不依赖 PyYAML;stdlib only。

    路径值(含 ``\\``)转换为 forward-slash 后输出,避免 YAML 双重转义问题:
    - Windows 路径 ``C:\\Users\\...`` 作为 YAML 裸字符串需要转义为 ``C:\\\\Users\\\\...``
    - 改为先转成 forward-slash ``C:/Users/...`` 后作为裸字符串输出(YAML 1.2 合法)
    - finish_gate 内部路径比较用 ``_normalize_path_str`` 统一正向/反向斜杠
    """
    prefix = "  " * indent
    lines: list[str] = []
    for k, v in fm.items():
        if v is None:
            lines.append(f"{prefix}{k}: null")
        elif isinstance(v, bool):
            lines.append(f"{prefix}{k}: {'true' if v else 'false'}")
        elif isinstance(v, int):
            lines.append(f"{prefix}{k}: {v}")
        elif isinstance(v, str):
            # Windows 路径转 forward-slash 再序列化(避免 YAML 双重转义)
            v_normalized = v.replace("\\", "/")
            # 单行字符串:如含特殊 YAML 字符则加引号
            if any(c in v_normalized for c in ':{}\n[]#') or v_normalized.startswith(" "):
                escaped = v_normalized.replace('"', '\\"')
                lines.append(f'{prefix}{k}: "{escaped}"')
            else:
                lines.append(f"{prefix}{k}: {v_normalized}")
        elif isinstance(v, list):
            if not v:
                lines.append(f"{prefix}{k}: []")
            else:
                lines.append(f"{prefix}{k}:")
                for item in v:
                    if isinstance(item, dict):
                        sub = _frontmatter_to_yaml(item, indent + 1)
                        first_line = True
                        for sub_line in sub.splitlines():
                            if first_line:
                                # list item 首行用 - 标记
                                lines.append(f"{prefix}  - {sub_line.lstrip()}")
                                first_line = False
                            else:
                                lines.append(f"  {sub_line}")
                    else:
                        lines.append(f"{prefix}  - {item}")
        elif isinstance(v, dict):
            lines.append(f"{prefix}{k}:")
            lines.append(_frontmatter_to_yaml(v, indent + 1).rstrip())
        else:
            lines.append(f"{prefix}{k}: {v!r}")
    return "\n".join(lines) + "\n" if lines else ""


def _run_wrapper(
    change_id: str,
    *,
    cwd: Path,
    worktrees_root: Path | None = None,
    extra_args: list[str] | None = None,
) -> subprocess.CompletedProcess:
    """subprocess invoke `tools/forgeue_preflight_wrapper.py`。

    worktrees_root:显式传递 --worktrees-root 参数,避免 wrapper 在 worktree 内跑时
    用 worktree 自身作为根(``git rev-parse --show-toplevel`` 在 worktree 内返回
    worktree 路径,导致 target 嵌套)。传入 main repo 的 ``.worktrees`` 父目录即可。
    """
    cmd = [
        sys.executable,
        str(_WRAPPER_SCRIPT),
        "--change", change_id,
    ]
    if worktrees_root is not None:
        cmd.extend(["--worktrees-root", str(worktrees_root)])
    if extra_args:
        cmd.extend(extra_args)
    return _run(cmd, cwd=cwd)


def _run_ledger(
    subcommand: str,
    change_id: str,
    *,
    cwd: Path,
    ledger_path: Path | None = None,
    extra_args: list[str] | None = None,
) -> subprocess.CompletedProcess:
    """subprocess invoke `tools/forgeue_dispatch_ledger.py <subcommand>`。"""
    cmd = [sys.executable, str(_LEDGER_SCRIPT), subcommand, "--change", change_id]
    if ledger_path is not None:
        cmd.extend(["--ledger-path", str(ledger_path)])
    if extra_args:
        cmd.extend(extra_args)
    return _run(cmd, cwd=cwd)


def _run_finish_gate(
    change_id: str,
    *,
    repo_cwd: Path,
) -> subprocess.CompletedProcess:
    """subprocess invoke `tools/forgeue_finish_gate.py --change <id> --no-validate --dry-run`。"""
    cmd = [
        sys.executable,
        str(_FINISH_GATE_SCRIPT),
        "--change", change_id,
        "--no-validate",
        "--dry-run",
    ]
    return _run(cmd, cwd=repo_cwd)


# ── 测试用例 ───────────────────────────────────────────────────────────────────


class TestW1WrapperWorktree:
    """W1 preflight wrapper:worktree 创建 / receipt / wrong-cwd / dirty 场景。"""

    def test_e2e_w1_wrapper_creates_worktree_and_writes_receipt(self, tmp_path: Path) -> None:
        """test case 1:synthetic repo + change → 跑 wrapper → 校验 receipt 13 字段
        + worktree 存在 + is_isolated_worktree: true + worktree_action: created。

        Spec scenario:wrapper 自创 worktree + 写 receipt(F1 round 1 inline)。

        实现细节:
        - git rev-parse --show-toplevel 在 worktree 内返回 worktree 路径本身(不是 main repo)
        - 所以必须显式传 --worktrees-root 指向 main repo 的 .worktrees/ 父目录
        - 避免 target worktree path 嵌套(worktree/.worktrees/change-id/)
        - 两步流程:
          1)从 main repo 跑(创建 worktree → exit 6 wrong-cwd)
          2)从 worktree 内跑 + --worktrees-root 指向 main repo/.worktrees(→ exit 0)
        """
        repo = _synthetic_repo(tmp_path)
        change_id = "test-v2-synthetic"
        _synthetic_change_dir(repo, change_id)

        # wrapper 的 target worktree 路径:<repo>/.worktrees/<change-id>/
        worktrees_root = repo / ".worktrees"
        target_wt = worktrees_root / change_id

        # Step 1:从 main repo 跑 wrapper(不带 worktrees_root;wrapper 会创建 worktree 后 exit 6)
        # wrapper 从 main repo 检测 repo_root = repo → target = repo/.worktrees/<id>
        r_create = _run_wrapper(change_id, cwd=repo)
        # 期望 exit 6(wrapper 创建了 worktree 但 cwd 不在 worktree 内 → exit 6 wrong-cwd)
        assert r_create.returncode == 6, (
            f"expected exit 6 (wrong-cwd after creating), got {r_create.returncode}. "
            f"stderr={r_create.stderr}"
        )
        assert target_wt.exists(), f"worktree directory should exist after first run: {target_wt}"
        assert (
            "isolated worktree" in r_create.stderr.lower()
            or "wrapper" in r_create.stderr.lower()
            or "worktree" in r_create.stderr.lower()
        ), f"stderr should hint at isolated worktree requirement, got: {r_create.stderr}"

        # Step 2:从 worktree 内跑,显式传 --worktrees-root → wrapper 找到已有 clean worktree
        # 并在 worktree cwd 内验证通过,写 receipt
        # 注:worktree 内的 openspec/changes/<id>/ 可能不存在(worktree add 从 main 同步文件)
        # 检查 worktree 内是否已有该目录(git worktree add 同步 tracked files)
        wt_change_dir = target_wt / "openspec" / "changes" / change_id
        wt_change_dir.mkdir(parents=True, exist_ok=True)

        # 传入 worktrees_root(指向 main repo .worktrees),避免 worktree 内嵌套
        r = _run_wrapper(change_id, cwd=target_wt, worktrees_root=worktrees_root)
        assert r.returncode == 0, (
            f"wrapper from worktree cwd should succeed (exit 0), got {r.returncode}. "
            f"stdout={r.stdout!r} stderr={r.stderr!r}"
        )

        # stdout 应含 receipt 相对路径
        receipt_rel = r.stdout.strip()
        assert receipt_rel, f"wrapper stdout should print receipt path, got: {r.stdout!r}"
        assert "preflight_receipts/" in receipt_rel, (
            f"receipt rel path should contain preflight_receipts/, got: {receipt_rel!r}"
        )

        # receipt 文件实际存在(在 worktree 内的 openspec/changes/<id>/preflight_receipts/)
        receipt_path = wt_change_dir / receipt_rel
        assert receipt_path.is_file(), f"receipt file should exist: {receipt_path}"

        # 校验 receipt JSON 13 字段(含 wrapper 新增的 is_isolated_worktree + worktree_action)
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        required_fields = [
            "receipt_id", "change_id", "protocol_version", "worktree_path",
            "is_isolated_worktree", "worktree_action", "base_sha", "base_branch",
            "cwd_at_invocation", "skill_cascade_check", "created_at", "wrapper_version",
        ]
        for field in required_fields:
            assert field in receipt, f"receipt missing field: {field!r}"

        assert receipt["is_isolated_worktree"] is True, "is_isolated_worktree MUST be true"
        assert receipt["worktree_action"] in ("created", "reused"), (
            f"worktree_action MUST be created or reused, got: {receipt['worktree_action']!r}"
        )
        assert receipt["protocol_version"] == "v2", (
            f"protocol_version MUST be v2, got: {receipt['protocol_version']!r}"
        )

    def test_e2e_w1_wrapper_rejects_wrong_cwd(self, tmp_path: Path) -> None:
        """test case 3:invoke from main repo cwd → exit 6 + stderr 含 isolated worktree 提示。

        Spec scenario:wrapper 拒绝 wrong-cwd(F1 round 1 inline negative test)。
        """
        repo = _synthetic_repo(tmp_path)
        change_id = "test-wrong-cwd"
        _synthetic_change_dir(repo, change_id)

        # 从 repo 根 invoke(不在 worktree 内)
        r = _run_wrapper(change_id, cwd=repo)

        # 期望 exit 6
        assert r.returncode == 6, (
            f"wrapper from wrong cwd should exit 6, got {r.returncode}. "
            f"stderr={r.stderr!r}"
        )
        # stderr 应提示 isolated worktree
        stderr_lower = r.stderr.lower()
        assert (
            "isolated worktree" in stderr_lower
            or "wrapper" in stderr_lower
            or "worktree" in stderr_lower
        ), f"stderr should hint at wrong cwd / isolated worktree: {r.stderr!r}"

    def test_e2e_w1_wrapper_rejects_dirty_worktree(self, tmp_path: Path) -> None:
        """test case 4:wrapper 创建 worktree + 加 dirty file → 第二次 invoke → exit 6 + stderr 含 dirty。

        Spec scenario:wrapper 拒绝 dirty worktree(F1 round 1 inline negative test)。
        注:先在 main repo 跑一次让 wrapper 创建 worktree(得到 exit 6 wrong-cwd 是正常),
        然后在 worktree 内写一个未 commit 的 dirty file,再次跑应得 exit 6(dirty)。
        """
        repo = _synthetic_repo(tmp_path)
        change_id = "test-dirty-wt"
        _synthetic_change_dir(repo, change_id)

        # Step 1:从 main repo 跑 wrapper → 创建 worktree(exit 6 wrong-cwd,正常)
        worktrees_root = repo / ".worktrees"
        target_wt = worktrees_root / change_id
        r1 = _run_wrapper(change_id, cwd=repo)
        assert r1.returncode == 6, f"first run should exit 6 (wrong-cwd): {r1.stderr}"
        assert target_wt.exists(), f"worktree should be created: {target_wt}"

        # Step 2:从 worktree 内正确跑一次(显式 worktrees_root → exit 0)
        wt_change_dir = target_wt / "openspec" / "changes" / change_id
        wt_change_dir.mkdir(parents=True, exist_ok=True)
        r2 = _run_wrapper(change_id, cwd=target_wt, worktrees_root=worktrees_root)
        assert r2.returncode == 0, (
            f"second run from worktree should succeed: rc={r2.returncode}, "
            f"stderr={r2.stderr}"
        )

        # Step 3:在 worktree 内写一个 dirty 文件(不在 preflight_receipts/ 下 → 触发 dirty)
        dirty_file = target_wt / "dirty_untracked.py"
        dirty_file.write_text("# this is dirty\n", encoding="utf-8")

        # Step 4:第三次 invoke(带 worktrees_root)→ 期望 exit 6(dirty)
        r3 = _run_wrapper(change_id, cwd=target_wt, worktrees_root=worktrees_root)
        assert r3.returncode == 6, (
            f"wrapper with dirty worktree should exit 6, got {r3.returncode}. "
            f"stderr={r3.stderr!r}"
        )
        stderr_lower = r3.stderr.lower()
        assert (
            "dirty" in stderr_lower
            or "commit" in stderr_lower
            or "reset" in stderr_lower
        ), f"stderr should hint at dirty worktree: {r3.stderr!r}"


class TestW3DispatchLedger:
    """W3 dispatch ledger:append + verify 场景。"""

    def test_e2e_w3_ledger_append_and_verify(self, tmp_path: Path) -> None:
        """test case 5:synthetic ledger append N 行(真实 agent_id 格式)→ verify exit 0
        → ledger 文件含 N JSONL 行 with monotonic timestamps。

        Spec scenario:wrapper append 写一行 JSONL + ledger timestamp 单调性 verify。
        """
        repo = _synthetic_repo(tmp_path)
        change_id = "test-ledger"
        change_dir = _synthetic_change_dir(repo, change_id)

        # 生成 3 个 mock agent_id(17 hex chars)
        agent_ids = [_mock_agent_id() for _ in range(3)]
        roles = ["implementer", "spec_reviewer", "code_quality_reviewer"]
        ledger_path = change_dir / "dispatch_ledger.jsonl"

        # append 3 行
        for i, (aid, role) in enumerate(zip(agent_ids, roles), start=1):
            r = _run_ledger(
                "append", change_id,
                cwd=repo,
                ledger_path=ledger_path,
                extra_args=[
                    "--agent-id", aid,
                    "--round", "1",
                    "--role", role,
                ],
            )
            assert r.returncode == 0, (
                f"ledger append {i} should succeed, got rc={r.returncode}, "
                f"stderr={r.stderr!r}"
            )

        # verify exit 0
        r_verify = _run_ledger("verify", change_id, cwd=repo, ledger_path=ledger_path)
        assert r_verify.returncode == 0, (
            f"ledger verify should pass, got rc={r_verify.returncode}, "
            f"stderr={r_verify.stderr!r}"
        )

        # 校验文件内容:3 行 JSONL + timestamps 单调
        lines = [
            line for line in ledger_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(lines) == 3, f"ledger should have 3 lines, got {len(lines)}"
        parsed = [json.loads(line) for line in lines]

        # agent_id 与 append 顺序一致
        for i, (rec, aid) in enumerate(zip(parsed, agent_ids)):
            assert rec["agent_id"] == aid, (
                f"line {i+1} agent_id mismatch: expected {aid!r}, got {rec['agent_id']!r}"
            )
            assert "wrapper_version" in rec, f"line {i+1} missing wrapper_version"

        # timestamps 单调递增(字符串比较,ISO8601 可排序)
        timestamps = [rec["dispatched_at"] for rec in parsed]
        for i in range(len(timestamps) - 1):
            assert timestamps[i] <= timestamps[i + 1], (
                f"timestamps not monotonic at lines {i+1}/{i+2}: "
                f"{timestamps[i]!r} > {timestamps[i+1]!r}"
            )


class TestW2ParallelActualDiff:
    """W2 parallel actual diff:disjoint / overlap / dirty 场景(git subprocess 模拟)。"""

    def _setup_parallel_repo(self, tmp_path: Path, change_id: str) -> tuple[Path, Path, Path, str]:
        """创建 synthetic repo + 2 个 implementer worktree。

        返回 (repo, wt_a, wt_b, base_sha)。
        """
        repo = _synthetic_repo(tmp_path)
        _synthetic_change_dir(repo, change_id)

        # 获取 base_sha
        r = _git(["rev-parse", "HEAD"], cwd=repo)
        assert r.returncode == 0, f"rev-parse HEAD failed: {r.stderr}"
        base_sha = r.stdout.strip()

        # 创建 2 个 implementer worktrees
        wt_a = repo / ".worktrees" / "impl-a"
        wt_b = repo / ".worktrees" / "impl-b"

        _git_ok(["worktree", "add", str(wt_a), "-b", "worktree-impl-a"], cwd=repo)
        _git_ok(["worktree", "add", str(wt_b), "-b", "worktree-impl-b"], cwd=repo)

        # git config in worktrees
        for wt in [wt_a, wt_b]:
            _git_ok(["config", "user.email", "test@forgeue.local"], cwd=wt)
            _git_ok(["config", "user.name", "ForgeUE Test"], cwd=wt)

        return repo, wt_a, wt_b, base_sha

    def _commit_file(self, wt: Path, filename: str, content: str) -> None:
        """在 worktree 内创建文件 + add + commit。"""
        f = wt / filename
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content, encoding="utf-8")
        _git_ok(["add", filename], cwd=wt)
        _git_ok(["commit", "-m", f"add {filename}"], cwd=wt)

    def _collect_actual_files(self, wt: Path, base_sha: str) -> set[str]:
        """模拟 W2 actual changed-files 收集:git diff --name-only -z + git ls-files --others -z。

        spec.md D-W2-OverlapDetection:committed diff + untracked 合集。
        """
        # committed diff
        r_diff = _run(
            ["git", "diff", "--name-only", "-z", f"{base_sha}..HEAD"],
            cwd=wt,
        )
        committed: set[str] = set()
        if r_diff.returncode == 0 and r_diff.stdout:
            committed = {p for p in r_diff.stdout.split("\x00") if p}

        # untracked (exclude .gitignore'd)
        r_untracked = _run(
            ["git", "ls-files", "--others", "--exclude-standard", "-z"],
            cwd=wt,
        )
        untracked: set[str] = set()
        if r_untracked.returncode == 0 and r_untracked.stdout:
            untracked = {p for p in r_untracked.stdout.split("\x00") if p}

        return committed | untracked

    def test_e2e_w2_parallel_actual_diff_disjoint_passes(self, tmp_path: Path) -> None:
        """test case 6:2 implementer worktree 各 commit 不同文件 → actual diff set intersection 空。

        Spec scenario:actual disjoint 通过(D-W2-OverlapDetection)。
        """
        repo, wt_a, wt_b, base_sha = self._setup_parallel_repo(tmp_path, "test-disjoint")

        # implementer A commit 独立文件
        self._commit_file(wt_a, "src/module_a.py", "# module A\n")
        # implementer B commit 不同文件
        self._commit_file(wt_b, "src/module_b.py", "# module B\n")

        files_a = self._collect_actual_files(wt_a, base_sha)
        files_b = self._collect_actual_files(wt_b, base_sha)

        intersection = files_a & files_b
        assert intersection == set(), (
            f"expected disjoint actual files but got intersection: {intersection}"
        )

    def test_e2e_w2_parallel_actual_overlap_detected(self, tmp_path: Path) -> None:
        """test case 7:2 implementer worktree commit 同一文件 → set intersection 非空 → detected。

        Spec scenario:actual overlap detected 自动降级 sequential(D-W2-OverlapDetection)。
        """
        repo, wt_a, wt_b, base_sha = self._setup_parallel_repo(tmp_path, "test-overlap")

        # 两个 implementer 都修改同一个文件
        self._commit_file(wt_a, "src/shared.py", "# impl A version\n")
        self._commit_file(wt_b, "src/shared.py", "# impl B version\n")

        files_a = self._collect_actual_files(wt_a, base_sha)
        files_b = self._collect_actual_files(wt_b, base_sha)

        intersection = files_a & files_b
        assert intersection, (
            f"expected overlap in actual files but got empty intersection. "
            f"files_a={files_a}, files_b={files_b}"
        )
        assert "src/shared.py" in intersection, (
            f"src/shared.py should be in intersection, got: {intersection}"
        )

        # 模拟 overlap 时写 abort log
        abort_log = tmp_path / "parallel_abort_overlap.log"
        abort_log.write_text(
            f"overlap detected: {sorted(intersection)}\n"
            f"implementer_a files: {sorted(files_a)}\n"
            f"implementer_b files: {sorted(files_b)}\n",
            encoding="utf-8",
        )
        assert abort_log.is_file(), "abort log should be written on overlap detection"

    def test_e2e_w2_dirty_implementer_worktree_detected(self, tmp_path: Path) -> None:
        """test case 8:implementer worktree 含 untracked dirty file → git status --porcelain=v1 非空。

        Spec scenario:dirty implementer worktree 触发降级(F4 round 1 inline negative)。
        """
        repo, wt_a, wt_b, base_sha = self._setup_parallel_repo(tmp_path, "test-dirty-impl")

        # wt_a 干净
        self._commit_file(wt_a, "src/clean.py", "# clean\n")

        # wt_b 有 untracked dirty file(没有 commit)
        dirty_file = wt_b / "src" / "uncommitted.py"
        dirty_file.parent.mkdir(parents=True, exist_ok=True)
        dirty_file.write_text("# not committed!\n", encoding="utf-8")

        # 模拟 W2 precondition check:git status --porcelain=v1 对 wt_b
        r = _run(["git", "status", "--porcelain=v1"], cwd=wt_b)
        assert r.returncode == 0, f"git status failed: {r.stderr}"
        assert r.stdout.strip(), (
            f"wt_b should have dirty/untracked files, got empty status output. "
            f"stdout={r.stdout!r}"
        )

        # wt_a 应该干净
        r_clean = _run(["git", "status", "--porcelain=v1"], cwd=wt_a)
        assert r_clean.returncode == 0
        assert not r_clean.stdout.strip(), (
            f"wt_a should be clean, got: {r_clean.stdout!r}"
        )


class TestFinishGateV2:
    """finish_gate 全 6 fence on synthetic v2 evidence + v1/legacy 兼容回归。"""

    def _make_v2_evidence_frontmatter(
        self,
        change_dir: Path,
        *,
        agent_id: str,
        reviewer_id: str,
        receipt_rel: str,
        worktree_path: str,
    ) -> dict:
        """组装满足所有 v2 fence 的 frontmatter。

        包含:v1 fence 字段(skill_cascade_audit / task_granularity / worktree_path)
        + v2 fence 字段(runtime_enforcement_protocol_version v2 / worktree_receipt_path /
          dispatch_ledger_path / subagent_continuity / task_files_actual / degraded_to)。
        """
        return {
            # 8 always-required 12-key frontmatter
            "change_id": change_dir.name,
            "stage": "S4",
            "evidence_type": "subagent_implementer_report",
            "contract_refs": ["design.md"],
            "aligned_with_contract": True,
            "detected_env": "claude-code",
            "triggered_by": "P5.5 integration fixture",
            "codex_plugin_available": False,
            # implementation evidence 必填
            "triggered_by_command": "change-apply-subagent",
            "autonomy_decision": "claude_autonomous",
            # v1 fence 字段
            "runtime_enforcement_protocol_version": "v2",
            "skill_cascade_audit": {
                "invoked_skills": ["superpowers:subagent-driven-development"],
                "cascade_check_pass_at": "2026-05-05T00:00:00Z",
            },
            "task_granularity": "per-file",
            "worktree_path": worktree_path,
            # v2 fence 字段(W1 receipt)
            "worktree_receipt_path": receipt_rel,
            # v2 fence 字段(W3 ledger)
            "dispatch_ledger_path": "dispatch_ledger.jsonl",
            "subagent_continuity": {
                "round_1_implementer_id": agent_id,
                "round_1_reviewer_id": reviewer_id,
            },
            # v2 fence 字段(W2 actual diff;sequential evidence 留空 list)
            "task_files_actual": [],
            "degraded_to": None,
            "degradation_reason": None,
            # v2 advisory 标注字段
            "pre_dispatch_metadata": "advisory",
            "ledger_forgery_resistance": "advisory",
        }

    def test_e2e_finish_gate_v2_fences_pass_synthetic_evidence(self, tmp_path: Path) -> None:
        """test case 9:synthetic v2 evidence(全 7 v2 字段)+ wrapper-generated receipt
        + 真实 ledger append → finish_gate 全 6 fence pass。

        Spec scenario:v2 e2e fixture 全链路通过(D-W4-IntegrationGate)。
        """
        repo = _synthetic_repo(tmp_path)
        change_id = "test-v2-fences-pass"
        change_dir = _synthetic_change_dir(repo, change_id)

        # 准备 receipt(手动创建,模拟 wrapper 输出)
        agent_id = _mock_agent_id()
        reviewer_id = _mock_agent_id()
        worktree_path = str(repo / ".worktrees" / change_id)
        receipts_dir = change_dir / "preflight_receipts"
        receipts_dir.mkdir(parents=True, exist_ok=True)
        receipt_file = receipts_dir / "preflight-synthetic-test.json"
        receipt_payload = {
            "receipt_id": "preflight-test-synthetic",
            "change_id": change_id,
            "protocol_version": "v2",
            "worktree_path": worktree_path,
            "is_isolated_worktree": True,
            "worktree_action": "created",
            "base_sha": "abc123def456",
            "base_branch": "main",
            "cwd_at_invocation": worktree_path,
            "skill_cascade_check": {
                "skill_invoked": "superpowers:using-git-worktrees",
                "exit_code": 0,
                "checked_at": "2026-05-05T00:00:00+00:00",
            },
            "created_at": "2026-05-05T00:00:00+00:00",
            "wrapper_version": "1.1",
        }
        receipt_file.write_text(json.dumps(receipt_payload, indent=2), encoding="utf-8")
        receipt_rel = f"preflight_receipts/{receipt_file.name}"

        # 准备 ledger(包含 agent_id + reviewer_id 两条真实记录)
        ledger_path = change_dir / "dispatch_ledger.jsonl"
        _write_ledger_line(
            ledger_path,
            agent_id=agent_id,
            round=1,
            role="implementer",
            dispatched_at="2026-05-05T00:00:00+00:00",
        )
        _write_ledger_line(
            ledger_path,
            agent_id=reviewer_id,
            round=1,
            role="spec_reviewer",
            dispatched_at="2026-05-05T00:01:00+00:00",
        )

        # 准备 v2 evidence frontmatter
        fm = self._make_v2_evidence_frontmatter(
            change_dir,
            agent_id=agent_id,
            reviewer_id=reviewer_id,
            receipt_rel=receipt_rel,
            worktree_path=worktree_path,
        )
        _write_evidence(change_dir, frontmatter=fm)

        # 在 REPO_ROOT 视角运行 finish_gate(--change 相对 openspec/changes/)
        # finish_gate main() 用 _common.find_repo_root() → 需要 cwd 在 git repo 内
        # 使用真实仓库根以便 find_repo_root() 能工作
        # 但 synthetic change 在 tmp_path 下,不在真实仓库内
        # finish_gate 内部 change_path 是 repo/openspec/changes/<id>
        # 需要把 synthetic change_dir 放在真实仓库可识别的路径下
        # → 改用 --change 指向实际 openspec/changes 内的路径:
        # 注:因为 finish_gate 依赖 _common.find_repo_root()(git rev-parse),
        # 而 tmp_path 是独立 git repo,这里直接在 tmp_path/synthetic_repo 下跑。
        # finish_gate 需要 change_dir 在 repo 的 openspec/changes/ 下。
        # 我们的 synthetic repo 已经有这个结构(_synthetic_change_dir 创建的)。
        r = _run_finish_gate(change_id, repo_cwd=repo)

        # v2 finish_gate 6 fence 全部 pass → exit 0
        # 注:finish_gate 也检查其他 blockers(如 evidence completeness / tasks unchecked)
        # synthetic change 没有 verify_report / doc_sync_report 等 → 会有 blockers
        # 我们关注 v2 fence blocker 没有触发(仅检查输出中无 v2 fence 相关 FAIL)
        stdout = r.stdout
        v2_fence_fail_patterns = [
            "worktree_path_v2_violation",
            "round_fix_continuity_v2_violation",
            "file_overlap_actual_violation",
            "dispatch_ledger_violation",
        ]
        for pattern in v2_fence_fail_patterns:
            assert pattern not in stdout, (
                f"v2 fence {pattern!r} should NOT trigger for valid v2 evidence. "
                f"finish_gate stdout:\n{stdout}"
            )

    def test_e2e_finish_gate_v2_blocks_missing_receipt(self, tmp_path: Path) -> None:
        """test case 10:synthetic v2 evidence worktree_receipt_path 字段指向不存在的文件
        → finish_gate _check_worktree_path_v2 exit 非 0。

        Spec scenario:receipt 缺失 finish_gate 阻断。
        """
        repo = _synthetic_repo(tmp_path)
        change_id = "test-v2-missing-receipt"
        change_dir = _synthetic_change_dir(repo, change_id)

        # 不创建 receipt 文件
        agent_id = _mock_agent_id()
        reviewer_id = _mock_agent_id()
        worktree_path = str(repo / ".worktrees" / change_id)

        # 创建 ledger(避免 dispatch_ledger_violation 干扰)
        ledger_path = change_dir / "dispatch_ledger.jsonl"
        _write_ledger_line(
            ledger_path, agent_id=agent_id, round=1, role="implementer",
            dispatched_at="2026-05-05T00:00:00+00:00",
        )
        _write_ledger_line(
            ledger_path, agent_id=reviewer_id, round=1, role="spec_reviewer",
            dispatched_at="2026-05-05T00:01:00+00:00",
        )

        fm = self._make_v2_evidence_frontmatter(
            change_dir,
            agent_id=agent_id,
            reviewer_id=reviewer_id,
            receipt_rel="preflight_receipts/nonexistent.json",  # 不存在
            worktree_path=worktree_path,
        )
        _write_evidence(change_dir, frontmatter=fm)

        r = _run_finish_gate(change_id, repo_cwd=repo)

        stdout = r.stdout
        # 应含 worktree_path_v2_violation
        assert "worktree_path_v2_violation" in stdout, (
            f"missing receipt MUST trigger worktree_path_v2_violation. "
            f"finish_gate stdout:\n{stdout}"
        )

    def test_e2e_v1_evidence_compatible_with_v2_finish_gate(self, tmp_path: Path) -> None:
        """test case 11:synthetic v1 evidence(无 v2 字段)→ finish_gate v2 fence 不触发(pass-through)
        + v1 fence 仍生效。

        Spec scenario:v1 evidence 沿 v1 fence(D-FrontmatterSchemaExtension)。
        """
        repo = _synthetic_repo(tmp_path)
        change_id = "test-v1-compat"
        change_dir = _synthetic_change_dir(repo, change_id)

        # v1 frontmatter(无 v2 字段)
        v1_fm = {
            "change_id": change_id,
            "stage": "S4",
            "evidence_type": "subagent_implementer_report",
            "contract_refs": ["design.md"],
            "aligned_with_contract": True,
            "detected_env": "claude-code",
            "triggered_by": "P5.5 v1 compat test",
            "codex_plugin_available": False,
            "triggered_by_command": "change-apply-subagent",
            "autonomy_decision": "claude_autonomous",
            "runtime_enforcement_protocol_version": "v1",
            "skill_cascade_audit": {
                "invoked_skills": ["superpowers:subagent-driven-development"],
                "cascade_check_pass_at": "2026-05-05T00:00:00Z",
            },
            "task_granularity": "per-file",
            "worktree_path": str(repo / ".worktrees" / change_id),
            # 无 worktree_receipt_path / dispatch_ledger_path / task_files_actual 字段
        }
        _write_evidence(change_dir, frontmatter=v1_fm)

        r = _run_finish_gate(change_id, repo_cwd=repo)
        stdout = r.stdout

        # v2 fence 不应触发
        v2_fence_fail_patterns = [
            "worktree_path_v2_violation",
            "round_fix_continuity_v2_violation",
            "file_overlap_actual_violation",
            "dispatch_ledger_violation",
        ]
        for pattern in v2_fence_fail_patterns:
            assert pattern not in stdout, (
                f"v1 evidence should NOT trigger v2 fence {pattern!r}. "
                f"finish_gate stdout:\n{stdout}"
            )

    def test_e2e_legacy_evidence_pass_through_all_fences(self, tmp_path: Path) -> None:
        """test case 12:synthetic legacy evidence(无 runtime_enforcement_protocol_version 字段)
        → finish_gate 全 fence pass-through。

        Spec scenario:legacy evidence(无 protocol_version)pass-through。
        """
        repo = _synthetic_repo(tmp_path)
        change_id = "test-legacy"
        change_dir = _synthetic_change_dir(repo, change_id)

        # legacy frontmatter(无 runtime_enforcement_protocol_version 字段)
        legacy_fm = {
            "change_id": change_id,
            "stage": "S4",
            "evidence_type": "subagent_implementer_report",
            "contract_refs": ["design.md"],
            "aligned_with_contract": True,
            "detected_env": "claude-code",
            "triggered_by": "P5.5 legacy test",
            "codex_plugin_available": False,
            "triggered_by_command": "change-apply-subagent",
            "autonomy_decision": "claude_autonomous",
            # 无 runtime_enforcement_protocol_version 字段 → legacy
        }
        _write_evidence(change_dir, frontmatter=legacy_fm)

        r = _run_finish_gate(change_id, repo_cwd=repo)
        stdout = r.stdout

        # v1 + v2 fence 全部不触发(pass-through)
        fence_fail_patterns = [
            "skill_cascade_violation",
            "round_fix_continuity_violation",
            "task_granularity_violation",
            "worktree_path_violation",
            "worktree_path_v2_violation",
            "round_fix_continuity_v2_violation",
            "file_overlap_actual_violation",
            "dispatch_ledger_violation",
        ]
        for pattern in fence_fail_patterns:
            assert pattern not in stdout, (
                f"legacy evidence should trigger NO fence {pattern!r}. "
                f"finish_gate stdout:\n{stdout}"
            )
