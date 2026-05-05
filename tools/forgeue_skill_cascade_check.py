"""ForgeUE skill cascade dependency checker (D-SkillCascadeCheck + D-SkillRootMultiSource).

设计文档:openspec/changes/enhance-workflow-automation-runtime-enforcement/design.md
        ``D-SkillCascadeCheck`` + ``D-SkillRootMultiSource``。

功能(stdlib only):
    - 输入:目标 SKILL 名(如 ``superpowers:subagent-driven-development``)+
      controller 已 invoke 的 skill 列表(逗号分隔)。
    - 静态读 ``SKILL.md`` → 解析 ``## Integration`` 段下
      ``**Required workflow skills:**`` 子段的 bullet。
    - bullet 含 ``REQUIRED`` 标记 → 视为 prereq dependency。
    - 输出:未 invoke 的 dep 列表 + exit code(0 = OK / 5 = missing dep 或 unknown skill)。

SKILL.md 路径推断(D-SkillRootMultiSource 优先级链,首个命中即返回):

    1. CLI flag ``--skill-root <path>``(显式 override)
    2. env var ``FORGEUE_SKILL_ROOT``(env override)
    3. ``./.claude/skills``(repo-local;沿 cwd)
    4. ``~/.claude/plugins/cache/claude-plugins-official/<plugin>/<version>/skills/``
       (Anthropic Claude Code default;version 取 lex-largest 即 latest semver)
    5. ``~/.claude/plugins/cache/<plugin>/<version>/skills/``(其他 Claude plugin)
    6. ``~/.codex/skills``(Codex CLI)
    7. ``${CODEX_HOME}/skills``(Codex 自定义)
    8. ``./.agents/skills``(Anthropic agents 自定义)

Skill 名规范化:
    - ``namespace:name`` → 去掉 namespace 前缀做 root probe(``name`` 是文件夹名)。
    - 各 root 都按同 bare name 探测;namespace 信息只用于诊断输出。

Exit codes:
    - ``0`` — 所有 REQUIRED dep 都已 invoke,或者 SKILL 没有 ``## Integration`` 段。
    - ``5`` — 缺 REQUIRED dep,或者 SKILL.md 在所有 root 都找不到。
    - ``2`` — argparse 拒绝(默认)。

Stdlib only:不依赖 PyYAML / requests / 任何 third-party。SKILL.md frontmatter
不解析(与本工具无关);只看 ``## Integration`` 段下的 markdown bullet。
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# allow ``python tools/forgeue_skill_cascade_check.py`` 直接跑(沿 forgeue_env_detect 风格)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common  # noqa: E402


ENV_VAR_NAME = "FORGEUE_SKILL_ROOT"
CODEX_HOME_ENV = "CODEX_HOME"


# ---------------------------------------------------------------------------
# regex
# ---------------------------------------------------------------------------


# ``## Integration`` 段标题(允许大小写 / trailing 空格 / 多空格)
_INTEGRATION_HEADER_RE = re.compile(
    r"^##\s+Integration\s*$",
    re.MULTILINE | re.IGNORECASE,
)

# 任何下一个 ``## XXX`` 段标题(用于切段)
_NEXT_H2_RE = re.compile(r"^##\s+", re.MULTILINE)

# ``**Required workflow skills:**`` 子段标题(允许大小写 / 多空格)
_REQUIRED_SUBSECTION_RE = re.compile(
    r"^\*\*Required\s+workflow\s+skills:\*\*\s*$",
    re.MULTILINE | re.IGNORECASE,
)

# 任何下一个 ``**XXX:**`` 子段标题(切子段)
_NEXT_SUBSECTION_RE = re.compile(
    r"^\*\*[\w][\w\s]*:\*\*\s*$",
    re.MULTILINE,
)

# bullet 格式:``- **<skill-name>** - <text including REQUIRED>``
# group 1 = skill name(允许 ``namespace:name``)
_BULLET_REQUIRED_RE = re.compile(
    r"^\s*-\s+\*\*([^\*\n]+?)\*\*\s+.*?\bREQUIRED\b",
    re.MULTILINE,
)


# ---------------------------------------------------------------------------
# skill root resolution (D-SkillRootMultiSource)
# ---------------------------------------------------------------------------


@dataclass
class _ProbeAttempt:
    root: Path
    matched: bool


def _bare_name(skill_name: str) -> str:
    """``superpowers:foo`` → ``foo`` (去 namespace 前缀,文件夹名)。"""
    return skill_name.split(":")[-1].strip()


def _direct_roots(override_root: str | None) -> list[Path]:
    """直接 root(无需 version glob)— 按 D-SkillRootMultiSource 优先级链。"""
    roots: list[Path] = []
    if override_root:
        roots.append(Path(override_root))
    env_val = os.environ.get(ENV_VAR_NAME)
    if env_val:
        roots.append(Path(env_val))
    roots.append(Path.cwd() / ".claude" / "skills")  # repo-local
    roots.append(Path.home() / ".codex" / "skills")
    codex_home = os.environ.get(CODEX_HOME_ENV)
    if codex_home:
        roots.append(Path(codex_home) / "skills")
    roots.append(Path.cwd() / ".agents" / "skills")
    return roots


def _probe_plugin_cache(bare_name: str) -> Path | None:
    """探 ``~/.claude/plugins/cache/<plugin>/<version>/skills/<bare_name>/SKILL.md``。

    Anthropic-official plugin(``claude-plugins-official``)优先;然后其他 plugin。
    多 version 时取 lex-largest(对 semver lex sort 即 latest)。
    """
    plugin_cache = Path.home() / ".claude" / "plugins" / "cache"
    if not plugin_cache.is_dir():
        return None

    # 子树 ``claude-plugins-official`` 优先
    anthropic_root = plugin_cache / "claude-plugins-official"
    if anthropic_root.is_dir():
        match = _latest_version_match(anthropic_root, bare_name)
        if match is not None:
            return match

    # 其他 plugin 子树(同样按 latest version 排序)
    return _latest_version_match(plugin_cache, bare_name)


def _latest_version_match(root: Path, bare_name: str) -> Path | None:
    """在 ``root`` 下 rglob ``skills/<bare_name>/SKILL.md``,取 lex-largest 路径。"""
    candidates = sorted(
        root.rglob(f"skills/{bare_name}/SKILL.md"),
        key=lambda p: str(p),
        reverse=True,  # 高版本在前
    )
    return candidates[0] if candidates else None


def resolve_skill_md(
    skill_name: str,
    override_root: str | None = None,
) -> Path | None:
    """按 D-SkillRootMultiSource 优先级链探 SKILL.md;首个命中即返回。

    返回 ``None`` 当所有 root 都没找到 — 调用方决定是否当 unknown skill 处理。
    """
    bare = _bare_name(skill_name)
    if not bare:
        return None

    # 优先级 1-3、6-8:直接 root(<root>/<bare>/SKILL.md)
    for root in _direct_roots(override_root):
        if not _is_above_priority_for_plugin_cache(root):
            continue  # placeholder — 始终 True;留给 future override 重排
        md = root / bare / "SKILL.md"
        if md.is_file():
            return md

    # 优先级 4-5:plugin cache(version glob 后取 latest)
    plugin_match = _probe_plugin_cache(bare)
    if plugin_match is not None:
        return plugin_match

    # 全 miss
    return None


def _is_above_priority_for_plugin_cache(_root: Path) -> bool:
    # 当前所有 direct root 都比 plugin cache 优先级高/低关系按 _direct_roots 顺序处理;
    # 这个 hook 留给 future scenario(如 plugin cache 之后再加 fallback)。
    return True


# ---------------------------------------------------------------------------
# Integration section parser
# ---------------------------------------------------------------------------


def parse_required_deps_from_path(skill_md_path: Path | None) -> list[str]:
    """读 SKILL.md → 返回 REQUIRED dep skill name 列表。

    返回空列表当:
        - ``skill_md_path is None``(unknown skill)
        - SKILL.md 没有 ``## Integration`` 段
        - 段内没有 ``**Required workflow skills:**`` 子段
        - 子段内没有 bullet 含 ``REQUIRED`` 标记

    skill name 保留原 namespace 前缀(``superpowers:foo``),与 ``--invoked`` 对齐。
    """
    if skill_md_path is None or not skill_md_path.is_file():
        return []
    try:
        text = skill_md_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    return _parse_required_deps(text)


def _parse_required_deps(text: str) -> list[str]:
    """纯 string 操作:SKILL.md 全文 → REQUIRED dep 列表。"""
    section = _slice_integration_section(text)
    if section is None:
        return []
    subsection = _slice_required_subsection(section)
    if subsection is None:
        return []

    deps: list[str] = []
    for m in _BULLET_REQUIRED_RE.finditer(subsection):
        name = m.group(1).strip()
        # 防 ``**Foo (Phase 4)**`` 类带括号 — 取第一个 token 前的部分
        name = name.split("(")[0].strip()
        if name and name not in deps:
            deps.append(name)
    return deps


def _slice_integration_section(text: str) -> str | None:
    m = _INTEGRATION_HEADER_RE.search(text)
    if not m:
        return None
    start = m.end()
    nxt = _NEXT_H2_RE.search(text, start)
    end = nxt.start() if nxt else len(text)
    return text[start:end]


def _slice_required_subsection(section: str) -> str | None:
    m = _REQUIRED_SUBSECTION_RE.search(section)
    if not m:
        return None
    start = m.end()
    # 下一个 ``**XXX:**`` 子段标题做切段终点
    rest = section[start:]
    nxt = _NEXT_SUBSECTION_RE.search(rest)
    end = start + nxt.start() if nxt else len(section)
    return section[start:end]


# ---------------------------------------------------------------------------
# cascade check API
# ---------------------------------------------------------------------------


def _normalize_invoked(invoked: list[str]) -> set[str]:
    """``["superpowers:foo", " superpowers:bar "]`` → ``{"superpowers:foo", "superpowers:bar"}``。

    空字符串 / 空白条目过滤;namespace 前缀大小写敏感(沿 SKILL.md 原样)。
    """
    return {item.strip() for item in invoked if item and item.strip()}


def _matches_dep(dep: str, invoked_set: set[str]) -> bool:
    """dep 与 invoked 比较 — 完整匹配 OR bare-name 匹配(允许 invoke 不带 namespace)。"""
    if dep in invoked_set:
        return True
    bare = _bare_name(dep)
    return any(_bare_name(i) == bare for i in invoked_set)


def check_cascade(
    skill_name: str,
    invoked: list[str],
    skill_root_override: str | None = None,
) -> tuple[int, list[str]]:
    """主入口 — 返回 ``(exit_code, missing_deps)``。

    - exit_code == 0 → cascade OK(全部 dep 已 invoke,或 SKILL 无 dep)
    - exit_code == 5 → unknown skill 或 missing dep
    - missing_deps:
        - SKILL 找不到时 = 含一个 sentinel ``f"<unknown:{skill_name}>"`` 的列表
        - dep 缺时 = 缺失 dep 名(原 namespace 前缀)的有序列表
    """
    md = resolve_skill_md(skill_name, override_root=skill_root_override)
    if md is None:
        return 5, [f"<unknown-skill:{skill_name}>"]

    deps = parse_required_deps_from_path(md)
    if not deps:
        return 0, []

    invoked_set = _normalize_invoked(invoked)
    missing = [d for d in deps if not _matches_dep(d, invoked_set)]
    if missing:
        return 5, missing
    return 0, []


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="forgeue_skill_cascade_check",
        description=(
            "Verify that controller has invoked all REQUIRED dependency skills "
            "declared in <skill>'s SKILL.md `## Integration` section."
        ),
    )
    p.add_argument(
        "--skill",
        required=True,
        help="Target skill name (e.g. superpowers:subagent-driven-development).",
    )
    p.add_argument(
        "--invoked",
        default="",
        help=(
            "Comma-separated list of skills already invoked by controller "
            "(e.g. 'superpowers:using-git-worktrees,superpowers:writing-plans')."
        ),
    )
    p.add_argument(
        "--skill-root",
        default=None,
        help=(
            "Override skill root directory (highest priority in D-SkillRootMultiSource "
            "probe chain). Useful for testing or non-default plugin layouts."
        ),
    )
    return p


def _parse_invoked_arg(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item and item.strip()]


def main(argv: list[str] | None = None) -> int:
    _common.setup_utf8_stdout()
    parser = _build_parser()
    args = parser.parse_args(argv)
    invoked = _parse_invoked_arg(args.invoked)

    exit_code, missing = check_cascade(
        skill_name=args.skill,
        invoked=invoked,
        skill_root_override=args.skill_root,
    )

    if exit_code == 0:
        print(_common.console_safe(f"[OK] cascade check passed for {args.skill}"))
        return 0

    if missing and missing[0].startswith("<unknown-skill:"):
        print(
            _common.console_safe(
                f"[FAIL] unknown skill: {args.skill} "
                f"(probed CLI override / FORGEUE_SKILL_ROOT / repo-local / "
                f"plugin cache / codex / .agents)"
            ),
            file=sys.stderr,
        )
        return 5

    print(
        _common.console_safe(
            f"[FAIL] cascade check missing {len(missing)} REQUIRED dep(s) for {args.skill}:"
        ),
        file=sys.stderr,
    )
    for dep in missing:
        print(_common.console_safe(f"  - {dep}"), file=sys.stderr)
    return 5


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
