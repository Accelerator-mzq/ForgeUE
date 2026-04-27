## Why

`framework.comparison.loader` 必须在模块顶层 `from framework.artifact_store.hashing import hash_payload`(loader 的 hash 重算职责依赖该 helper)。Python 子模块 import 必先执行父包 `__init__.py`,而当前 `src/framework/artifact_store/__init__.py` 在顶层 eager-import `repository` / `payload_backends` / `lineage` / `variant_tracker` 全部公共符号。

后果:任何 import `framework.comparison.loader` / `cli` 的进程,`sys.modules` 都会带上 `framework.artifact_store.repository` 与 `framework.artifact_store.payload_backends` —— 即便 loader / CLI 源码从未直接调用写侧 API。`add-run-comparison-baseline-regression` Task 5 在 CLI 实装时被迫接受此事实:`tests/unit/test_run_comparison_loader.py::TestImportFence` 与 `tests/unit/test_run_comparison_cli.py::TestCliImportFence` 只把 9 个执行链路前缀(`runtime` / `providers` / `review_engine` / `ue_bridge` / `workflows` / `observability` / `server` / `schemas` / `pricing_probe`)列入禁止清单,**未**加入 `artifact_store.repository` / `payload_backends`,fence 的覆盖面被人为收窄。

`framework/comparison/__init__.py` 已用 PEP 562 `__getattr__` lazy export 处理同类问题(loader / diff_engine / reporter 三类符号按需 lazy import,write back 进 `globals()` 做 PEP 562 cache)—— 同 repo 现成参考实现可直接套用。

## What Changes

- `src/framework/artifact_store/__init__.py` 改为 PEP 562 `__getattr__` lazy export:
  - `hashing` 子模块的 `hash_inputs` / `hash_payload` 保留 eager(零依赖、~50 行,任何 caller 都用得到,延迟无意义)
  - `ArtifactRepository`(来自 `repository`)、`PayloadBackend` / `PayloadBackendRegistry` / `PayloadTooLarge` / `get_backend_registry`(来自 `payload_backends`)、`LineageIndex`(来自 `lineage`)、`VariantTracker`(来自 `variant_tracker`)改为 lazy attribute access
  - `__all__` 保持不变(对外 API 表面不动)
  - `TYPE_CHECKING` 块导入 lazy 符号供静态类型检查
  - **实现 `__dir__` 函数返回 `sorted(set(__all__) | set(globals()))`**(F3 codex finding 后补齐),保 `dir()` / `inspect.getmembers()` 见全 public API 表面,使"公共 API 表面零变化"承诺真正可达;比 `framework/comparison/__init__.py` reference 实现更严格
- `tests/unit/test_run_comparison_loader.py::TestImportFence` 与 `tests/unit/test_run_comparison_cli.py::TestCliImportFence` 禁止清单回收:把 `framework.artifact_store.repository` / `framework.artifact_store.payload_backends` / `framework.artifact_store.lineage` / `framework.artifact_store.variant_tracker` 加回禁止项;`hashing` 仍允许出现(loader 显式依赖)
- `src/framework/comparison/cli.py` 顶部 docstring 与 `tests/unit/test_run_comparison_cli.py::TestCliImportFence` docstring 移除 "transitive load 不可避免" 的 carve-out 说明
- 30+ 现有 callsite(`from framework.artifact_store import ArtifactRepository, get_backend_registry` 等)保持不变 —— PEP 562 让它们透明享受懒加载,首次属性访问触发实际 import

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `artifact-contract`:新增 Requirement「Package import surface is lazy-load by default」+ 1 个 Scenario,把 "read-only consumer 不得 transitive 加载写侧模块" 从测试 fence 提升为 spec 级行为约束。这避免未来再有 `comparison`-类只读 consumer 出现时 fence 又被人工放宽。

## Impact

**代码影响**(改动范围严格圈定):

- `src/framework/artifact_store/__init__.py`:从 23 行 eager re-export 改为 ~70 行 PEP 562 lazy 模板(参考 `src/framework/comparison/__init__.py:50-95`)
- `tests/unit/test_run_comparison_loader.py`:`TestImportFence` 禁止清单 + 4
- `tests/unit/test_run_comparison_cli.py`:`TestCliImportFence` 禁止清单 + 4
- `src/framework/comparison/cli.py`:docstring 删去 carve-out 段落
- 新增 fence:`tests/unit/test_artifact_store_lazy_imports.py` —— 守门 `import framework.artifact_store` 之后 `sys.modules` **不**含 `repository` / `payload_backends` / `lineage` / `variant_tracker`,直到首次访问对应符号

**不动的模块**:`runtime/` / `providers/` / `review_engine/` / `ue_bridge/` / `workflows/` / `observability/` / `server/` / `schemas/` / `pricing_probe/` 全部不动。30+ 个现有 callsite 因 `__all__` 不变 + PEP 562 透明转发,代码层无须修改。

**风险与缓解**:

- 风险 A:某 callsite 依赖 `artifact_store.repository` 作为可访问属性(如 `framework.artifact_store.repository.ArtifactRepository`)—— Grep 实测 0 个 callsite 走子模块路径,全部走顶层 `from framework.artifact_store import X`;PEP 562 可覆盖
- 风险 B:`mypy` / `pyright` 静态类型检查在 lazy 模式下丢失类型信息 —— 用 `if TYPE_CHECKING:` 块引导静态分析(`framework/comparison/__init__.py:30-48` 已验证此 pattern 在本 repo `mypy` 配置下可工作)
- 风险 C:lazy import 在循环依赖场景下产生 `AttributeError` —— `artifact_store` 子模块互不依赖(`hashing` / `lineage` / `variant_tracker` 零依赖,`repository` 依赖 `hashing` + `payload_backends`,`payload_backends` 依赖 `hashing`),首次访问任一符号都不会触发循环;无 cycle
- 风险 D:全套测试矩阵回归 —— Level 0 `pytest -q` 实测、Level 1 CLI 离线冒烟(`mock_linear.json` + `image_pipeline.json`)纳入 verify 阶段必跑

**契约文件影响**:仅 `openspec/specs/artifact-contract/spec.md` 加 1 个 Requirement + 1 个 Scenario。`docs/` 五件套不实质变更(fence 测试归 NFR-MAINT-001 守门清单更新,属测试 spec 文本同步,留 doc-sync gate 阶段处理)。
