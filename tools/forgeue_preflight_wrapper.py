#!/usr/bin/env python3
"""W1 preflight wrapper [DEPRECATED in default flow per ADR-013] — D-W1-ReceiptSchema(F1 round 1 inline:wrapper 自管 worktree)+ D-DispatchWrapperBoundary。

设计文档:
    openspec/changes/enhance-workflow-automation-executable-enforcement/design.md
        ``D-W1-ReceiptSchema`` + ``D-DispatchWrapperBoundary``

合约源(spec):
    openspec/changes/enhance-workflow-automation-executable-enforcement/specs/
        examples-and-acceptance/spec.md  Requirement: Preflight wrapper receipt JSON contract

功能(stdlib only):
    - 命令模板在 dispatch 前调用本 wrapper;wrapper 自己用 ``git worktree`` subprocess
      创建 / 验证 isolated worktree(**不**依赖 ``superpowers:using-git-worktrees`` SKILL),
      并强制校验 cwd 实际位于 wrapper-managed worktree 内(否则 fail-closed exit 6)。
    - 跑 ``forgeue_skill_cascade_check.py`` 内嵌 cascade 校验(skill dependency 完整)。
    - 写 machine-generated receipt JSON 到 ``<change>/preflight_receipts/<receipt_id>.json``
      (13 字段含 ``is_isolated_worktree`` + ``worktree_action``)。
    - LLM 只复制 ``worktree_path`` + ``receipt_id`` 两字段到 evidence frontmatter。

Wrapper 自管 worktree 算法(沿 design.md D-W1-ReceiptSchema):
    1. 计算 target worktree path = ``<worktrees-root>/<change-id>/``
    2. ``git worktree list --porcelain`` 解析:
       - target in list + clean → reuse(``worktree_action: reused``)
       - target in list + dirty → exit 6(``worktree_action: rejected_dirty``)
       - target NOT in list → ``git worktree add <target> -b worktree-<change-id>``
         (``worktree_action: created``)
    3. 强制 cwd 校验:``os.path.realpath(cwd) == os.path.realpath(target)``,
       不一致 → exit 6 stderr 提示 "isolated worktree"
    4. resolve git state:base_sha / base_branch
    5. 跑 cascade check subprocess
    6. 生成 receipt JSON + 写 ``<receipts-dir>/<receipt_id>.json``
    7. stdout 输出 receipt 相对路径(供命令模板 capture)

Exit codes:
    - 0  — 全 OK,receipt 已写
    - 5  — cascade check fail(unknown skill / 缺 REQUIRED dep)
    - 6  — git 状态异常 / wrong-cwd / dirty worktree / git 仓库不存在
    - 7  — receipt 写失败(目录不可写 / IO 异常)
    - 2  — argparse 拒绝(默认)

stdlib only:不依赖 PyYAML / requests / 任何 third-party。
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# allow ``python tools/forgeue_preflight_wrapper.py`` 直接跑(沿 forgeue_env_detect 风格)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common  # noqa: E402


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# wrapper 协议版本(receipt 字段 ``wrapper_version``);protocol_version 与 evidence
# frontmatter ``runtime_enforcement_protocol_version`` 对齐(v2)
WRAPPER_VERSION = "1.1"
PROTOCOL_VERSION = "v2"

# ADR-013 D-WrapperDeprecate(2026-05-06):wrapper 标 deprecated 但 functional —
# 命令模板 default decline 路径不再调用 wrapper(仅 user 显式 opt-in
# `worktree_mode: wrapper_worktree` 时调用)。LLM / docs 引用 wrapper 时应附此 notice。
__deprecated_note__ = (
    "[DEPRECATED in default flow per ADR-013] forgeue_preflight_wrapper.py "
    "remains functional for opt-in bug-fix iteration use case "
    "(worktree_mode: wrapper_worktree path). Default flow走 ADR-013 D-RestoreConsentGate "
    "consent gate (decline → in_place mode;skill_worktree mode 不调本 wrapper)."
)

# Exit codes — 与 spec.md scenarios + design.md D-W1-ReceiptSchema 对齐
EXIT_OK = 0
EXIT_CASCADE_FAIL = 5
EXIT_GIT_FAIL = 6
EXIT_RECEIPT_FAIL = 7

# 默认 cascade check 校验的主 skill(命令模板 dispatch 前必先 invoke 这个 skill)
DEFAULT_SKILL = "superpowers:using-git-worktrees"

# 工具脚本路径(相对 wrapper 自身)
_THIS_DIR = Path(__file__).resolve().parent
SKILL_CASCADE_TOOL = _THIS_DIR / "forgeue_skill_cascade_check.py"


# ---------------------------------------------------------------------------
# Git subprocess helpers(stdlib only — 沿 _common.git_rev_parse 风格)
# ---------------------------------------------------------------------------


def _run_git(args: list[str], *, cwd: Path) -> tuple[int, str, str]:
    """跑 git 子命令;返回 (returncode, stdout, stderr)。

    Wrapper 重度依赖 git CLI(``worktree list`` / ``worktree add`` / ``rev-parse`` /
    ``status``);相比 ``_common.git_rev_parse`` 单 sha 校验,本 helper 通用。
    """
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(cwd),
            timeout=30,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as exc:
        return -1, "", f"git invocation failed: {exc}"
    return result.returncode, result.stdout, result.stderr


def _git_repo_root(cwd: Path) -> Path | None:
    """resolve main repo root, even when called from inside a worktree.

    ADR-013 codex round 2 plan review F3 writeback(W7-a wrapper bug fix):
    原 ``git rev-parse --show-toplevel`` 在 worktree 内返 worktree 自身路径,
    `_resolve_target_worktree` 算出 nested target → ``git worktree add`` 在
    nested 路径试图创建第二 worktree → "Filename too long" 链锁失败。

    Fix:用 ``git rev-parse --git-common-dir`` 取共享 ``.git`` directory
    (worktree 内返 main repo 的 ``.git`` 绝对路径;main repo 内返相对 ``.git``
    或 absolute 视 git 版本/config),parent 即 main repo root。统一两种调用
    上下文(main repo / worktree)→ 不再 nested。
    """
    rc, out, _ = _run_git(["rev-parse", "--git-common-dir"], cwd=cwd)
    if rc != 0:
        return None
    out = out.strip()
    if not out:
        return None
    common_dir = Path(out)
    if not common_dir.is_absolute():
        # main repo 内 git-common-dir 返相对 ``.git`` → 拼到 cwd 算 main repo root
        common_dir = (cwd / common_dir).resolve()
    else:
        common_dir = common_dir.resolve()
    return common_dir.parent


def _git_status_clean(cwd: Path, *, ignore_paths: tuple[str, ...] = ()) -> bool:
    """``git status --porcelain`` 返回空 → tree clean;非空 → dirty。

    ``ignore_paths``:wrapper 自己写出的 runtime artifact 路径(如
    ``openspec/changes/<change>/preflight_receipts/``)— 这些 path 下的
    untracked file 不应判定 worktree dirty(否则 wrapper 第二次调用永远失败)。
    匹配走 startswith(porcelain 输出形如 ``?? path/to/file``)。
    """
    # ``--untracked-files=all`` 是关键 — 默认 ``--untracked-files=normal`` 会把
    # 全 untracked 子树折叠成一个 ``?? path/to/dir/`` 条目,导致深层 ignore_paths
    # 前缀匹配失败(porcelain 给的是 ``?? openspec/`` 而非
    # ``?? openspec/changes/<id>/preflight_receipts/<file>``)。
    rc, out, _ = _run_git(
        ["status", "--porcelain", "--untracked-files=all"],
        cwd=cwd,
    )
    if rc != 0:
        # git status 跑不通本身视为 dirty(保守 — 后续 path 走 exit 6)
        return False
    if not out.strip():
        return True
    if not ignore_paths:
        return False
    # 逐行解析:porcelain v1 每行 ``XY <path>``;X/Y 是 status code,2-char 后空格
    # 然后 path。我们关心 path 是否落在 ignore_paths 之内 → 视为 clean。
    for line in out.splitlines():
        if not line.strip():
            continue
        # 取 path 段(第 4 个字符开始;`?? foo/bar` 或 ` M foo/bar`)
        if len(line) < 4:
            return False
        path_part = line[3:].strip()
        # rename / copy 行格式 ``R  old -> new``;取 -> 后的新 path 用于比较
        if " -> " in path_part:
            path_part = path_part.split(" -> ", 1)[1].strip()
        # quoted path(含特殊字符时 git 加引号)— 简单去引号
        if path_part.startswith('"') and path_part.endswith('"'):
            path_part = path_part[1:-1]
        # 归一为 forward slash 比较(porcelain 总是 forward slash;ignore_paths 同款)
        path_part = path_part.replace("\\", "/").lstrip("./")
        matched = False
        for prefix in ignore_paths:
            normalized = prefix.replace("\\", "/").lstrip("./").rstrip("/") + "/"
            if path_part.startswith(normalized):
                matched = True
                break
        if not matched:
            return False
    return True


def _git_worktree_list(repo_root: Path) -> list[dict[str, str]]:
    """解析 ``git worktree list --porcelain`` → 列表 of {worktree, HEAD, branch, ...}。

    porcelain 输出格式(每个 worktree 用空行分隔,key value 一行一个):
        worktree /path/to/wt
        HEAD <sha>
        branch refs/heads/<name>

        worktree /path/to/another
        HEAD <sha>
        bare
    """
    rc, out, _ = _run_git(["worktree", "list", "--porcelain"], cwd=repo_root)
    if rc != 0:
        return []
    entries: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in out.splitlines():
        line = line.rstrip()
        if not line:
            if current:
                entries.append(current)
                current = {}
            continue
        if " " in line:
            key, _, val = line.partition(" ")
            current[key] = val
        else:
            # 单 token 如 ``bare`` / ``detached`` / ``locked``(无 value)
            current[line] = ""
    if current:
        entries.append(current)
    return entries


def _git_resolve_state(cwd: Path) -> tuple[str | None, str | None]:
    """resolve worktree 当前 base_sha + base_branch。返回 (sha, branch) 任一可 None。"""
    rc1, out1, _ = _run_git(["rev-parse", "HEAD"], cwd=cwd)
    sha = out1.strip() if rc1 == 0 else None

    rc2, out2, _ = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
    branch = out2.strip() if rc2 == 0 else None
    # detached HEAD 时 ``--abbrev-ref`` 返回 ``HEAD``;保留原值,evidence audit 可见
    return sha, branch


# ---------------------------------------------------------------------------
# Worktree management(D-W1-ReceiptSchema 自管 worktree 算法)
# ---------------------------------------------------------------------------


def _resolve_target_worktree(
    repo_root: Path,
    change_id: str,
    worktrees_root: Path | None,
) -> Path:
    """计算 target worktree path = ``<worktrees-root>/<change-id>/``;default
    ``<repo>/.worktrees/<change-id>/``。返回 absolute resolved path。
    """
    base = worktrees_root if worktrees_root is not None else (repo_root / ".worktrees")
    return (base / change_id).resolve()


def _ensure_worktree(
    repo_root: Path,
    target: Path,
    change_id: str,
    *,
    runtime_artifact_paths: tuple[str, ...] = (),
) -> tuple[str, str | None]:
    """确保 target worktree 存在 + clean。返回 (worktree_action, error_message)。

    worktree_action 取值:
        - ``"created"`` — wrapper 新创建
        - ``"reused"``  — 已存在 + clean,重用
        - ``"rejected_dirty"`` — 已存在但 dirty,error_message 含细节
        - ``"rejected_create_failed"`` — git worktree add 失败,error_message 含细节

    ``runtime_artifact_paths``:wrapper 自己写出的 runtime artifact 相对路径
    (如 ``openspec/changes/<change>/preflight_receipts/``)— 这些路径下的
    untracked file 不计入 dirty 判断(沿 D-W1-ReceiptSchema:wrapper 写 receipt
    本身不应让 worktree 立即 dirty,否则下一次 reuse 路径永远走不到)。
    """
    target_real = os.path.realpath(target)
    entries = _git_worktree_list(repo_root)
    found = False
    for entry in entries:
        wt_path = entry.get("worktree", "")
        if not wt_path:
            continue
        if os.path.realpath(wt_path) == target_real:
            found = True
            break

    if found:
        # 校验 dirty 状态(忽略 wrapper 自己写的 runtime artifact)
        if not _git_status_clean(target, ignore_paths=runtime_artifact_paths):
            return "rejected_dirty", (
                f"wrapper-managed worktree dirty (please commit or reset first): {target}"
            )
        return "reused", None

    # 不在 list 中 → 创建
    target.parent.mkdir(parents=True, exist_ok=True)
    branch_name = f"worktree-{change_id}"
    rc, _out, err = _run_git(
        ["worktree", "add", str(target), "-b", branch_name],
        cwd=repo_root,
    )
    if rc != 0:
        # branch 已存在 → 重试不带 -b(D-OQ-1 边界:branch orphaned 时复用)
        rc2, _out2, err2 = _run_git(
            ["worktree", "add", str(target)],
            cwd=repo_root,
        )
        if rc2 != 0:
            return "rejected_create_failed", (
                f"git worktree add failed: first attempt err={err.strip()}; "
                f"retry err={err2.strip()}"
            )
    return "created", None


# ---------------------------------------------------------------------------
# Cascade check(内嵌 forgeue_skill_cascade_check.py)
# ---------------------------------------------------------------------------


def _run_cascade_check(skill_name: str, *, cwd: Path) -> tuple[int, str]:
    """跑 ``python forgeue_skill_cascade_check.py --skill <name> --invoked <name>``。

    invoked 默认就是 skill 本身(校验主 skill 自己的 dependency 解析无错;不要求
    LLM 真 invoke 全 cascade — 那是命令模板层的事)。返回 (exit_code, stderr)。
    """
    if not SKILL_CASCADE_TOOL.is_file():
        # 本仓库内必有此文件,缺失视为环境异常 — 走 exit 5(cascade fail)
        return 5, f"cascade check tool not found: {SKILL_CASCADE_TOOL}"
    try:
        proc = subprocess.run(
            [
                sys.executable,
                str(SKILL_CASCADE_TOOL),
                "--skill",
                skill_name,
                "--invoked",
                skill_name,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(cwd),
            timeout=30,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as exc:
        return 5, f"cascade check subprocess failed: {exc}"
    return proc.returncode, proc.stderr or proc.stdout


# ---------------------------------------------------------------------------
# Receipt assembly(D-W1-ReceiptSchema 13 字段)
# ---------------------------------------------------------------------------


def _now_iso8601() -> str:
    """ISO 8601 UTC 时间戳(沿 _common 风格;Python 3.11+ ``isoformat`` 直接产 ``+00:00``)。"""
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


def _gen_receipt_id(change_id: str) -> str:
    """``preflight-<change>-<iso8601>-<short_hex8>``。"""
    # iso8601 中 ``:`` 在 Windows 文件名非法 → 替换为 ``-``(沿 forgeue_finish_gate 同款)
    ts = _now_iso8601().replace(":", "-").replace("+", "p")
    short = secrets.token_hex(4)  # 8 hex chars
    return f"preflight-{change_id}-{ts}-{short}"


def _build_receipt(
    *,
    change_id: str,
    receipt_id: str,
    worktree_path: Path,
    worktree_action: str,
    base_sha: str | None,
    base_branch: str | None,
    cwd_at_invocation: Path,
    skill_name: str,
    cascade_exit_code: int,
    cascade_checked_at: str,
    created_at: str,
) -> dict[str, object]:
    """组装 13 字段 receipt JSON dict(顺序固定;沿 design.md D-W1-ReceiptSchema)。"""
    return {
        "receipt_id": receipt_id,
        "change_id": change_id,
        "protocol_version": PROTOCOL_VERSION,
        "worktree_path": str(worktree_path),
        "is_isolated_worktree": True,
        "worktree_action": worktree_action,
        "base_sha": base_sha,
        "base_branch": base_branch,
        "cwd_at_invocation": str(cwd_at_invocation),
        "skill_cascade_check": {
            "skill_invoked": skill_name,
            "exit_code": cascade_exit_code,
            "checked_at": cascade_checked_at,
        },
        "created_at": created_at,
        "wrapper_version": WRAPPER_VERSION,
    }


def _write_receipt(
    receipts_dir: Path,
    receipt_id: str,
    payload: dict[str, object],
) -> tuple[Path | None, str | None]:
    """写 receipt JSON;返回 (file_path, error_message)。

    OSError(目录不可写 / 路径不存在 / 权限拒绝)→ (None, err)。
    """
    try:
        receipts_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return None, f"failed to create receipts dir {receipts_dir}: {exc}"
    file_path = receipts_dir / f"{receipt_id}.json"
    try:
        file_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        return None, f"failed to write receipt {file_path}: {exc}"
    return file_path, None


# ---------------------------------------------------------------------------
# CLI orchestration
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="forgeue_preflight_wrapper",
        description=(
            "[DEPRECATED in default flow per ADR-013] "
            "W1 preflight wrapper: self-managed isolated worktree (git worktree "
            "subprocess) + skill cascade check + 13-field receipt JSON. "
            "LLM only copies worktree_path + receipt_id to evidence frontmatter. "
            "Remains functional for opt-in `worktree_mode: wrapper_worktree` "
            "(bug-fix iteration / explicit isolation); default flow passes to consent gate "
            "decline -> in_place mode (no wrapper invocation)."
        ),
    )
    p.add_argument(
        "--change",
        required=True,
        help="Change id (matches openspec/changes/<id>/ directory name).",
    )
    p.add_argument(
        "--skill",
        default=DEFAULT_SKILL,
        help=(
            "Skill name to embed in skill_cascade_check (default: "
            f"{DEFAULT_SKILL}). Wrapper does NOT invoke the SKILL tool; just "
            "runs forgeue_skill_cascade_check.py to verify SKILL.md exists."
        ),
    )
    p.add_argument(
        "--cwd",
        default=None,
        help="Override current working directory used for cwd realpath check.",
    )
    p.add_argument(
        "--worktrees-root",
        default=None,
        help="Override worktrees parent directory (default: <repo>/.worktrees/).",
    )
    p.add_argument(
        "--receipts-dir",
        default=None,
        help=(
            "Override receipts directory (default: "
            "<worktree>/openspec/changes/<change>/preflight_receipts/)."
        ),
    )
    p.add_argument(
        "--reuse-if-clean",
        action="store_true",
        help=(
            "Advisory flag (D-OQ-1): wrapper always reuses an existing clean "
            "worktree per spec; this flag is accepted for future opt-in semantics."
        ),
    )
    return p


def _emit_stderr(msg: str) -> None:
    print(_common.console_safe(msg), file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    """主入口 — 沿 D-W1-ReceiptSchema 算法 + spec.md scenarios。"""
    _common.setup_utf8_stdout()
    parser = _build_parser()
    args = parser.parse_args(argv)

    change_id: str = args.change
    skill_name: str = args.skill
    invoke_cwd = Path(args.cwd).resolve() if args.cwd else Path.cwd().resolve()

    # Step 1:resolve repo root via cwd(允许 wrapper 在 main repo 或 worktree 内调用)
    repo_root = _git_repo_root(invoke_cwd)
    if repo_root is None:
        _emit_stderr(
            f"[FAIL] not inside a git repository: cwd={invoke_cwd}"
        )
        return EXIT_GIT_FAIL

    # Step 2:计算 target worktree path
    worktrees_root = (
        Path(args.worktrees_root).resolve() if args.worktrees_root else None
    )
    target_worktree = _resolve_target_worktree(repo_root, change_id, worktrees_root)

    # 计算 wrapper 自己写出的 runtime artifact 相对路径(供 dirty check 忽略;
    # 沿 D-W1-ReceiptSchema:wrapper 写 receipt 不应让 worktree 立即 dirty,
    # 否则第二次调用永远 fail)
    runtime_artifact_rel = (
        f"openspec/changes/{change_id}/preflight_receipts"
    )

    # Step 3:确保 worktree 存在 + clean(自管 worktree 算法)
    action, err = _ensure_worktree(
        repo_root,
        target_worktree,
        change_id,
        runtime_artifact_paths=(runtime_artifact_rel,),
    )
    if action == "rejected_dirty":
        _emit_stderr(f"[FAIL] {err}")
        return EXIT_GIT_FAIL
    if action == "rejected_create_failed":
        _emit_stderr(f"[FAIL] {err}")
        return EXIT_GIT_FAIL

    # Step 4:强制 cwd 校验 — wrapper 必须在 wrapper-managed worktree 内调用
    cwd_real = os.path.realpath(invoke_cwd)
    target_real = os.path.realpath(target_worktree)
    if cwd_real != target_real:
        # 友好提示:wrapper 已经创建了 worktree,但用户 / controller 此次跑在 main repo
        # → 提示 cd 到 worktree 重新跑(沿 design.md D-W1-ReceiptSchema tradeoff)
        _emit_stderr(
            f"[FAIL] wrapper must be invoked from inside the isolated worktree.\n"
            f"  expected cwd: {target_worktree}\n"
            f"  actual cwd:   {invoke_cwd}\n"
            f"  worktree action this run: {action}\n"
            f"  please: cd \"{target_worktree}\" && re-run the wrapper command."
        )
        return EXIT_GIT_FAIL

    # Step 5:resolve git state(在 worktree 内取 HEAD / branch)
    base_sha, base_branch = _git_resolve_state(target_worktree)

    # Step 6:跑 cascade check 内嵌校验
    cascade_checked_at = _now_iso8601()
    cascade_rc, cascade_err = _run_cascade_check(skill_name, cwd=target_worktree)
    if cascade_rc != 0:
        _emit_stderr(
            f"[FAIL] skill cascade check failed (exit {cascade_rc}) for skill={skill_name}.\n"
            f"  detail: {cascade_err.strip() if cascade_err else '(no stderr)'}"
        )
        return EXIT_CASCADE_FAIL

    # Step 7:组装 + 写 receipt JSON
    created_at = _now_iso8601()
    receipt_id = _gen_receipt_id(change_id)
    payload = _build_receipt(
        change_id=change_id,
        receipt_id=receipt_id,
        worktree_path=target_worktree,
        worktree_action=action,
        base_sha=base_sha,
        base_branch=base_branch,
        cwd_at_invocation=invoke_cwd,
        skill_name=skill_name,
        cascade_exit_code=cascade_rc,
        cascade_checked_at=cascade_checked_at,
        created_at=created_at,
    )

    # 决定 receipts_dir(default: 在 worktree 内 ``openspec/changes/<change>/preflight_receipts/``)
    if args.receipts_dir is not None:
        receipts_dir = Path(args.receipts_dir).resolve()
    else:
        receipts_dir = (
            target_worktree / "openspec" / "changes" / change_id / "preflight_receipts"
        )

    receipt_path, write_err = _write_receipt(receipts_dir, receipt_id, payload)
    if receipt_path is None:
        _emit_stderr(f"[FAIL] {write_err}")
        return EXIT_RECEIPT_FAIL

    # Step 8:stdout 输出 receipt 相对路径(供命令模板 capture)
    # 命令模板写到 evidence frontmatter ``worktree_receipt_path``;路径相对
    # ``<change>/`` 目录(沿 design.md D-W1-ReceiptSchema "LLM-readable 字段约定")
    if args.receipts_dir is not None:
        # 自定义 receipts_dir 时按文件名相对输出(测试 fixture 用)
        rel = receipt_path.name
    else:
        rel = f"preflight_receipts/{receipt_path.name}"
    print(rel)
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
