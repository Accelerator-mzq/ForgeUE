# FOR-24 Linux Runner CI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 GitHub Actions 上补一条 Ubuntu Linux CI，自动跑通项目的离线全量测试。

**Architecture:** 采用单个 `ubuntu-latest` job，先安装项目运行与测试依赖，再执行 `python -m pytest -q` 作为唯一主门禁。文档同步只改最少三处：acceptance 状态、测试矩阵和 backlog 归档，保持 NFR-PORT-002 的状态一致。

**Tech Stack:** GitHub Actions、Python 3.12、`pip install -e .[dev,llm,server]`、pytest、Markdown 文档。

---

### Task 1: 写 workflow 守门测试

**Files:**
- Create: `tests/unit/test_linux_ci_workflow.py`

- [ ] **Step 1: 写失败测试**

```python
from pathlib import Path


def test_linux_ci_workflow_declares_ubuntu_and_pytest():
    path = Path(".github/workflows/linux-ci.yml")
    text = path.read_text(encoding="utf-8")
    assert "ubuntu-latest" in text
    assert "python -m pytest -q" in text
    assert "actions/checkout" in text
    assert "actions/setup-python" in text
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest -q tests/unit/test_linux_ci_workflow.py -v`
Expected: `FileNotFoundError` 或断言失败，因为 workflow  هنوز不存在。

### Task 2: 新增 Linux workflow

**Files:**
- Create: `.github/workflows/linux-ci.yml`

- [ ] **Step 1: 写最小 workflow**

```yaml
name: linux-ci

on:
  push:
  pull_request:

jobs:
  pytest:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev,llm,server]"

      - name: Run pytest
        run: python -m pytest -q
```

- [ ] **Step 2: 运行守门测试确认通过**

Run: `python -m pytest -q tests/unit/test_linux_ci_workflow.py -v`
Expected: `PASS`

### Task 3: 同步文档与 backlog

**Files:**
- Modify: `docs/acceptance/acceptance_report.md:310,705`
- Modify: `docs/testing/test_spec.md:561`
- Modify: `docs/backlog/active.md`
- Modify: `docs/backlog/archived.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: 更新验收状态与测试矩阵**

```markdown
| NFR-PORT-002 Linux CI | GitHub Actions ubuntu-latest | ✅ |
| TBD-T-001 | GitHub Actions Linux CI runner | NFR-PORT-002 | ✅ | 已建立 |
```

```markdown
| TBD-T-001 | 接入 Linux CI(当前仅本地 Windows 验证) |
```

改为 Linux workflow 已落地后的描述。

- [ ] **Step 2: 迁移 backlog 条目到 archived**

把 `LR-0123` 从 `docs/backlog/active.md` 删除，并在 `docs/backlog/archived.md` 新增 tombstone，写清 workflow 路径、验证命令和结果。

- [ ] **Step 3: 在 CHANGELOG 记录变更**

新增一条 Unreleased bullet，说明 Linux runner workflow 已加入，且离线 pytest 作为主门禁。

### Task 4: 终验

**Files:**
- None

- [ ] **Step 1: 跑相关单测**

Run:
`python -m pytest -q tests/unit/test_linux_ci_workflow.py tests/unit/test_video_metadata.py tests/unit/test_video_worker.py tests/unit/test_comfy_subprocess_video.py tests/unit/test_generate_video_comfy.py`

- [ ] **Step 2: 跑全量测试**

Run:
`python -m pytest -q`

Expected: 全绿，Linux workflow 内容与本地验证一致。
