## Context

`add-run-comparison-baseline-regression`(2026-04-25 archive)在 Task 5 实装 `framework.comparison.cli` 时,被 Codex review 第二轮捕获 import-fence Blocker:测试 `TestCliImportFence` 必须验证 CLI 进程不污染 `sys.modules` 写侧执行链路。但 `framework.comparison.loader` 顶层 `from framework.artifact_store.hashing import hash_payload` 会触发 `framework/artifact_store/__init__.py` 顶层执行,该 `__init__` 当前 eager-import:

```python
# src/framework/artifact_store/__init__.py(当前 23 行)
from framework.artifact_store.hashing import hash_inputs, hash_payload
from framework.artifact_store.lineage import LineageIndex
from framework.artifact_store.payload_backends import (
    PayloadBackend, PayloadBackendRegistry, PayloadTooLarge, get_backend_registry,
)
from framework.artifact_store.repository import ArtifactRepository
from framework.artifact_store.variant_tracker import VariantTracker
```

后果:loader / cli 进程 `sys.modules` 必含 `framework.artifact_store.repository` + `framework.artifact_store.payload_backends`(connect transitive 进 `framework.core.artifact` + `framework.observability.compactor` 等)。Task 5 裁决是接受现状 + 收窄 fence(只锁 9 个执行链路前缀),并在 `cli.py` docstring + 测试 docstring 显式记录 carve-out。

跨子系统改 `artifact_store/__init__.py` 越过 `add-run-comparison-baseline-regression` 的 "Modules NOT affected" 边界,留作独立 change(本 change)处理。

`framework/comparison/__init__.py:1-122` 是同 repo 现成 PEP 562 lazy export 参考实现,本设计直接复用其模式。

**Callsite 调研结果**(grep 全 repo,**排除** `src/framework/artifact_store/**` 包内部 — 内部 intra-package import 合法、无须改动):

| 类别 | 文件数(包外) | 典型形式 | lazy 兼容 |
| --- | --- | --- | --- |
| 顶层符号 import | 30+ | `from framework.artifact_store import ArtifactRepository, get_backend_registry` | ✅ PEP 562 透明转发 |
| 子模块路径 import(包外,公开 API)| 0 | `import framework.artifact_store.repository` / `framework.artifact_store.repository.X` | N/A — 无包外 callsite 走该路径 |
| 子模块限定访问(包外,公开 helper)| 1 | `from framework.artifact_store.hashing import hash_payload`(`comparison/loader.py`) | ✅ `hashing` 不延迟 |
| **子模块限定访问(包外,sub-package 内部 backend 类)** | **1 file / 2 imports** | `tests/unit/test_payload_backends.py:9` 顶层 import + `:84` function-local import,均访问 `framework.artifact_store.payload_backends` 子包(`BlobBackend` / `FileBackend` / `InlineBackend` / `file_backend.FILE_MAX_BYTES`) | ✅ payload_backends sub-package 整体保持 eager 内部结构;lazy `__getattr__` 只决定**顶层**包是否预加载 |

**包内部**(`src/framework/artifact_store/**`)有合法 intra-package 子模块 import,如 `repository.py:24-29` 引 `lineage` / `payload_backends.base` / `variant_tracker`,`payload_backends/__init__.py` 引自身 submodule —— 这些是包结构内的 import,只在 lazy `__getattr__` 触发对应符号加载时才执行,**不**对 read-only consumer 产生 transitive 污染。fence test 必须排除包内部 + `test_payload_backends.py` 这个 sub-package 专属测试,否则会假阳性。

**`tests/unit/test_payload_backends.py` 的特殊性**:它测的是 payload_backend 子包内部行为(`BlobBackend` / `FileBackend` / `InlineBackend` / 私有常量 `FILE_MAX_BYTES` 通过 monkeypatch 修改)—— `BlobBackend` / `FileBackend` / `InlineBackend` 三个类**未**列入 `framework/artifact_store/__init__.py::__all__`(`__all__` 只暴露 `PayloadBackend` / `PayloadBackendRegistry` / `PayloadTooLarge` / `get_backend_registry` 抽象层 + 工厂),它们是子包内部实现细节。该测试通过子模块路径访问是合法 sub-package consumer 关系,与"read-only 外部 consumer 不污染 sys.modules"的契约目标无关。fence test 3.1.3 需显式排除此文件并记录原因。

## Goals / Non-Goals

**Goals**:

1. `framework/artifact_store/__init__.py` 改为 PEP 562 lazy export,`import framework.artifact_store` 后 `sys.modules` **不**含 `repository` / `payload_backends` / `lineage` / `variant_tracker`,直到首次访问对应符号
2. `tests/unit/test_run_comparison_loader.py` 与 `tests/unit/test_run_comparison_cli.py` 的 fence 禁止清单加回 `repository` / `payload_backends` / `lineage` / `variant_tracker`,关闭 carve-out
3. 公共 API 表面零变化(`__all__` 不动、30+ callsite 零修改)
4. 全套 ForgeUE 测试矩阵(848 baseline)无回归
5. `openspec/specs/artifact-contract/spec.md` 新增 1 个 Requirement「import surface lazy-load」+ 1 个 Scenario,把约束从测试层提升到 spec 层

**Non-Goals**:

- ❌ 不改任何 `artifact_store` 子模块文件(`hashing.py` / `repository.py` / `payload_backends/*` / `lineage.py` / `variant_tracker.py` 全部不动)
- ❌ 不改 `runtime/` / `providers/` / `review_engine/` / `ue_bridge/` / `workflows/` / `observability/` 的任何 callsite
- ❌ 不改 `Artifact` / `PayloadRef` / `Lineage` / `Checkpoint` schema
- ❌ 不引入新依赖(PEP 562 是 Python 3.7+ 标准库特性,本项目要求 Python 3.12+)
- ❌ 不实现 `framework.observability.run_comparison` 等其他 deferred 项;本 change scope 严格限于 artifact_store 包导入表面

## Decisions

### Decision 1:沿用 `framework/comparison/__init__.py` 的 PEP 562 模板

**Why X over Y**:

- 选项 A(采纳)— PEP 562 `__getattr__` + write-back 进 `globals()` 做模块级 cache + `if TYPE_CHECKING:` 块辅助静态类型分析。同 repo `framework/comparison/__init__.py:50-95` 已验证可工作(848 用例全绿,mypy 无 noise)。
- 选项 B(拒绝)— 在每个 caller 处改成 `from framework.artifact_store.repository import ArtifactRepository`。要改 30+ 文件,违反"不改 callsite"目标,且把内部包结构泄漏到 caller 边界。
- 选项 C(拒绝)— 把 `__init__.py` 清空,要求所有 caller 显式 import 子模块。同 B 的代价 + 破坏 `__all__` 公共 API 契约。

**模板细节**:

```python
# src/framework/artifact_store/__init__.py(目标形态,~70 行)
from __future__ import annotations
from typing import TYPE_CHECKING, Any

# eager:零依赖、~50 行,任何 caller 都用得到
from framework.artifact_store.hashing import hash_inputs, hash_payload

if TYPE_CHECKING:
    from framework.artifact_store.lineage import LineageIndex
    from framework.artifact_store.payload_backends import (
        PayloadBackend, PayloadBackendRegistry, PayloadTooLarge, get_backend_registry,
    )
    from framework.artifact_store.repository import ArtifactRepository
    from framework.artifact_store.variant_tracker import VariantTracker

_LAZY_REPOSITORY_NAMES = frozenset({"ArtifactRepository"})
_LAZY_PAYLOAD_BACKEND_NAMES = frozenset({
    "PayloadBackend", "PayloadBackendRegistry", "PayloadTooLarge", "get_backend_registry",
})
_LAZY_LINEAGE_NAMES = frozenset({"LineageIndex"})
_LAZY_VARIANT_NAMES = frozenset({"VariantTracker"})

def __getattr__(name: str) -> Any:
    if name in _LAZY_REPOSITORY_NAMES:
        from framework.artifact_store import repository
        value = getattr(repository, name)
        globals()[name] = value
        return value
    if name in _LAZY_PAYLOAD_BACKEND_NAMES:
        from framework.artifact_store import payload_backends
        value = getattr(payload_backends, name)
        globals()[name] = value
        return value
    if name in _LAZY_LINEAGE_NAMES:
        from framework.artifact_store import lineage
        value = getattr(lineage, name)
        globals()[name] = value
        return value
    if name in _LAZY_VARIANT_NAMES:
        from framework.artifact_store import variant_tracker
        value = getattr(variant_tracker, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module 'framework.artifact_store' has no attribute {name!r}")


def __dir__() -> list[str]:
    """PEP 562 dir() override.

    Eager export historically populated module globals so dir() and
    inspect.getmembers() returned the full public surface. Under PEP 562
    __getattr__ alone, lazy symbols are absent from dir() until first access.
    Returning sorted(__all__ ∪ globals()) preserves the eager-export
    introspection contract: dir() always shows the documented public API +
    any already-cached lazy symbols + private helpers populated at module
    load time. inspect.getmembers() iterates dir() then getattr-each, so
    calling it triggers full lazy materialization (one-time O(N) cost).
    """
    return sorted(set(__all__) | set(globals()))


__all__ = [
    "ArtifactRepository", "LineageIndex", "PayloadBackend", "PayloadBackendRegistry",
    "PayloadTooLarge", "VariantTracker", "get_backend_registry", "hash_inputs", "hash_payload",
]
```

### Decision 2:`hashing` 保持 eager,其余四个模块 lazy

**Why X over Y**:

- `hashing.py` 仅 ~50 行、零 framework 依赖、`hash_payload` / `hash_inputs` 是 helper 性质 —— 任何调用方(包括 read-only `comparison.loader`)都可能用到,延迟收益接近 0,延迟代价是首次 hash 计算时多一次 import 开销
- 反过来 `repository` / `payload_backends` 是写侧入口,read-only consumer 永不调用 —— 是延迟的主要受益对象
- `lineage` / `variant_tracker` 体量小但同样属于写侧索引,顺手归 lazy 保持一致性

### Decision 3:Spec 层加 1 个 Requirement,把 fence 从测试提升到契约

`artifact-contract` 现有 Requirement 已规定 "comparison 模块 reads via plain file reads + hash_payload, NOT through repository / payload_backends"(line 173-180),但这是 caller 行为约束。本 change 加一条对**包侧**的对偶约束:

> Requirement:Package import surface is lazy-load by default
>
> The system SHALL NOT load `framework.artifact_store.repository` / `payload_backends` / `lineage` / `variant_tracker` into `sys.modules` at the time `framework.artifact_store` itself is first imported. These submodules SHALL be loaded only when a caller actually accesses one of their exported symbols.
>
> Scenario:Read-only consumer does not transitively load write-side modules
>
> - GIVEN a fresh Python process that imports `framework.artifact_store`(or `framework.artifact_store.hashing`)but never accesses `ArtifactRepository` / `PayloadBackendRegistry` / `LineageIndex` / `VariantTracker`
> - WHEN we inspect `sys.modules`
> - THEN none of `framework.artifact_store.repository` / `framework.artifact_store.payload_backends` / `framework.artifact_store.lineage` / `framework.artifact_store.variant_tracker` are present
>
> Scenario:First attribute access loads the corresponding submodule
>
> - GIVEN a process that imported `framework.artifact_store`
> - WHEN code first dereferences `framework.artifact_store.ArtifactRepository`(through `from framework.artifact_store import ArtifactRepository` or attribute access)
> - THEN `framework.artifact_store.repository` is loaded into `sys.modules` AND the same `ArtifactRepository` object is cached on `framework.artifact_store` module globals so subsequent access bypasses `__getattr__`

这把 `comparison.loader` / `comparison.cli` 的 fence 测试从"防自己跑偏"提升为"包合约保证只读 consumer 不会被强行污染"。

## Risks / Trade-offs

- **[Risk A] 某包外 callsite 通过 `framework.artifact_store.repository.X` 子模块路径访问** → Mitigation:已 grep 全 repo,排除 `src/framework/artifact_store/**` 包内部 + `tests/unit/test_payload_backends.py`(payload_backends sub-package 专属测试,合法 sub-package consumer)后 0 个匹配。新增 fence `tests/unit/test_artifact_store_lazy_imports.py::test_no_callsite_uses_submodule_path` 守门,扫 `from framework.artifact_store.repository import` / `from framework.artifact_store.payload_backends import` / `lineage import` / `variant_tracker import`(`hashing` 允许;**fence 主动排除三类**:(a) `src/framework/artifact_store/**` 包内部 intra-package import;(b) `tests/unit/test_payload_backends.py` sub-package 专属测试;(c) 本 change 目录自身)
- **[Risk B] `mypy` / `pyright` 静态类型推断在 lazy 模式下失败** → Mitigation:`if TYPE_CHECKING:` 块导入 lazy 符号供静态分析;`framework/comparison/__init__.py:30-48` 已验证此 pattern 在本 repo `mypy` 配置下不产生类型 noise
- **[Risk C] 循环依赖产生 `AttributeError`** → Mitigation:实测依赖图 `hashing`(零依赖)→ `payload_backends`(依赖 `hashing`)→ `repository`(依赖 `hashing` + `payload_backends`)→ `lineage`(零内部依赖)→ `variant_tracker`(零内部依赖),无 cycle;首次访问任一 lazy 符号都不触发循环
- **[Risk D] PEP 562 的 `__getattr__` 在 IDE 跳转/补全/`dir()`/`inspect.getmembers()` 中不可见** → Mitigation:`__all__` 显式列出全部公共符号,IDE 补全走 `__all__`;`if TYPE_CHECKING:` 让静态跳转可工作;**实现 `__dir__` 函数返回 `sorted(set(__all__) | set(globals()))`**,使 `dir(framework.artifact_store)` 与 `inspect.getmembers()` 在 lazy 符号未访问前**仍**返回完整公共 API 表面(eager 时代的 introspection 契约保留)。`inspect.getmembers()` 遍历 `dir()` + `getattr-each` 会触发全部 lazy 符号一次性加载,这是它的语义本就如此(O(N) 一次性成本),不是回归。该 mitigation 比 `comparison/__init__.py` reference 实现更严格 —— 后者未实装 `__dir__`,本 change 借机补齐
- **[Risk E] 全套测试矩阵某处隐式依赖 transitive load** → Mitigation:Level 0 `pytest -q` 实测必须 848+ 全绿;Level 1 `framework.run --task examples/mock_linear.json` + `examples/image_pipeline.json` 离线冒烟;Level 2 `--live-llm` 不在本 change scope(无 provider key 改动)

## Migration Plan

### Step 1 — 改 `__init__.py`

按 Decision 1 模板替换 `src/framework/artifact_store/__init__.py`。

### Step 2 — 加新 fence 测试

`tests/unit/test_artifact_store_lazy_imports.py` 含三类 fence:

1. `test_import_artifact_store_does_not_pull_repository_or_payload_backends` —— 子进程跑 `import framework.artifact_store` + `import framework.artifact_store.hashing`,断言 `sys.modules` 不含 4 个 lazy 模块
2. `test_first_access_of_lazy_symbol_loads_submodule_and_caches` —— `getattr(framework.artifact_store, "ArtifactRepository")` 首次访问后,`sys.modules` 出现 `repository`,且 `framework.artifact_store.ArtifactRepository` 是同一对象(cache 工作)
3. `test_no_callsite_uses_submodule_path` —— grep 全 repo,断言 `from framework.artifact_store.repository import` / `payload_backends import` / `lineage import` / `variant_tracker import` 零匹配(`hashing` 允许)

### Step 3 — 收紧既有 fence

- `tests/unit/test_run_comparison_loader.py::TestImportFence`:禁止清单加 `framework.artifact_store.repository` / `payload_backends` / `lineage` / `variant_tracker`
- `tests/unit/test_run_comparison_cli.py::TestCliImportFence`:同上
- 删 `cli.py` docstring 与测试 docstring 中 "transitive load 不可避免" 段落

### Step 4 — 跑全套测试矩阵

- `python -m pytest -q` —— 848+ 必须全绿
- `python -m framework.run --task examples/mock_linear.json --run-id _smoke_lazy` —— 离线 P0 冒烟,产物落 `./demo_artifacts/runs/_smoke_lazy/`
- `python -m framework.run --task examples/image_pipeline.json --run-id _smoke_lazy_p3` —— FakeAdapter 离线 P3 冒烟

### Step 5 — Spec delta

加 `openspec/changes/lazy-artifact-store-package-exports/specs/artifact-contract/spec.md` delta,含 1 个 ADDED Requirement + 2 个 Scenario(见 Decision 3)。

### Rollback

风险极低(零 schema 改动 + 零 callsite 改动 + 公共 API 表面不变)。如真出现回归:

- `git revert <commit>` 一步回滚 `__init__.py`
- 测试侧把禁止清单里新加的 4 项移除即可恢复 carve-out

## Open Questions

无。所有设计选择有先例(`framework/comparison/__init__.py`)+ 实测调研(callsite grep)支撑,无须 Pre-implementation 决策。
