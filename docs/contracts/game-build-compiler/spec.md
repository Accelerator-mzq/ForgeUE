# Game Build Compiler Contract

## 目的

Game Build Compiler 是 ForgeUE 的 engine-neutral GDD-to-game-build planning 契约。它迁移 AGENT_UE5 Design Compiler 中可泛化的设计编译语义,但不迁移 UE-only plugin code、Monopoly-specific extraction rules、Bridge Passthrough MCP tools 或具体 Unreal/Godot project paths。

Phase A 是 contract-only 阶段。它只定义和校验结构化 planning artifacts,为后续 Workflow smoke 与 EngineAdapter lowering 留接口;它不创建可玩 demo,不落地引擎工程文件,也不绕过 ForgeUE runtime 直接交付 Unreal 或 Godot 项目。

## 来源

- 迁移设计:`docs/superpowers/specs/2026-05-24-agent-ue5-to-forgeue-migration-design.md`
- Schema 实现:`src/framework/schemas/game_build_compiler.py`
- Schema 测试:`tests/unit/test_game_build_compiler_schemas.py`
- Fixture 测试:`tests/unit/test_game_build_compiler_fixtures.py`
- Fixture 目录:`tests/fixtures/game_build_compiler/`

## 当前行为

系统提供五个 structured schema refs,并把它们注册到 structured generation 使用的 `SchemaRegistry`:

- `game_build.contract` -> `GameBuildContract`
- `game_build.clarification_report` -> `GameBuildClarificationReport`
- `game_build.graph` -> `GameBuildGraph`
- `game_build.build_ir` -> `GameBuildIR`
- `game_build.handoff` -> `GameBuildHandoff`

`framework.schemas.game_build_compiler.register_builtin_schemas()` 负责注册以上 refs。CLI orchestrator 构建时会调用该注册函数,因此 `generate_structured` 和 schema validation 路径读取的是同一个 registry 命名空间。

## Engine-Neutral 边界

Game Build Compiler Phase A MUST NOT write Unreal or Godot project files。`GameBuildIR` 和 `GameBuildAction` 只能表达跨引擎意图,例如 `blueprint_or_cpp`、`scene_plus_gdscript` 这类 preference;具体文件、package、scene、script、map、asset 路径必须留给后续 adapter-specific lowering。

当前实现会递归扫描 `GameBuildAction` 的任意字段、list/dict value,以及 nested dict key。以下 concrete path signal 在 Phase A 中全部禁止:

- `Source/`
- `/Game/`
- `Content/`
- `res://`
- `.uasset`
- `.umap`
- `.h`
- `.cpp`
- `.gd`
- `.tscn`

## Requirements

### Requirement: schema registry

系统 SHALL 将 `game_build.contract`、`game_build.clarification_report`、`game_build.graph`、`game_build.build_ir` 和 `game_build.handoff` 注册到 structured generation 使用的 registry。

#### Scenario: CLI orchestrator exposes Game Build Compiler schemas

- GIVEN `_build_orchestrator(tmp_path)` 创建 runtime orchestrator
- WHEN builtin schemas registration 完成
- THEN `get_schema_registry().names()` 包含五个 `game_build.*` schema refs
- AND `tests/unit/test_game_build_compiler_schemas.py::test_cli_orchestrator_registers_game_build_compiler_schemas` 守住该行为

### Requirement: graph edge closure

系统 SHALL 拒绝 `GameBuildGraph.edges[*].from_node` 或 `GameBuildGraph.edges[*].to_node` 指向未声明 node id 的 graph。

#### Scenario: unknown graph endpoint is rejected

- GIVEN graph 只声明 `gameplay-core-loop`
- WHEN edge 引用未声明的 `ui-hud`
- THEN validation 失败,错误包含 `unknown edge endpoint`
- AND `tests/unit/test_game_build_compiler_schemas.py::test_game_build_graph_rejects_edges_to_missing_nodes` 守住该行为

### Requirement: GameBuildIR concrete path rejection

系统 SHALL 拒绝 `GameBuildIR.actions` 中任意字段、nested dict value 或 nested dict key 携带具体 Unreal/Godot 路径。系统 MAY 接受 engine preference 字符串,例如 `blueprint_or_cpp` 或 `scene_plus_gdscript`,只要它们不包含 concrete path signal。

#### Scenario: concrete path in action value is rejected

- GIVEN `engine_requirements.unreal.asset_path` 为 `/Game/Demo/UI/WBP_HUD`
- WHEN `GameBuildIR.model_validate(payload)` 运行
- THEN validation 失败,错误包含 `engine-specific concrete path`
- AND `tests/unit/test_game_build_compiler_schemas.py::test_game_build_ir_rejects_unreal_concrete_paths` 守住该行为

#### Scenario: concrete path in action inputs is rejected

- GIVEN `GameBuildAction.inputs` 包含 `/Game/Demo/UI/WBP_HUD`
- WHEN `GameBuildIR.model_validate(payload)` 运行
- THEN validation 失败,错误包含 `engine-specific concrete path`
- AND `tests/unit/test_game_build_compiler_schemas.py::test_game_build_ir_rejects_concrete_paths_in_action_inputs` 守住该行为

#### Scenario: concrete path in nested dict key is rejected

- GIVEN `engine_requirements.unreal` 使用 `/Game/Demo/UI/WBP_HUD` 作为 nested dict key
- WHEN `GameBuildIR.model_validate(payload)` 运行
- THEN validation 失败,错误包含 `engine-specific concrete path`
- AND `tests/unit/test_game_build_compiler_schemas.py::test_game_build_ir_rejects_concrete_paths_in_action_requirement_keys` 守住该行为

### Requirement: fixture validation

系统 SHALL 在 `tests/fixtures/game_build_compiler/` 提供可离线校验的 GDD 与 JSON fixtures。JSON fixtures SHALL 通过对应 Pydantic model 校验,并保持 engine-neutral。

#### Scenario: fixture pack validates without external services

- GIVEN `tests/fixtures/game_build_compiler/` 下的 fixture files
- WHEN `tests/unit/test_game_build_compiler_fixtures.py` 用 UTF-8 加载它们
- THEN `GameBuildContract`、`GameBuildGraph`、`GameBuildIR` 和 `GameBuildHandoff` 均通过校验
- AND 校验不需要 API keys、network、Unreal、Godot、ComfyUI 或 provider APIs

#### Scenario: fixtures stay engine-neutral

- GIVEN fixture JSON 合并为一个文本流
- WHEN 测试扫描 `Source/`、`/Game/`、`Content/`、`res://`、`.uasset`、`.umap`、`.h`、`.cpp`、`.gd`、`.tscn`
- THEN 这些 concrete path signal 都不得出现
- AND `tests/unit/test_game_build_compiler_fixtures.py::test_game_build_compiler_fixtures_stay_engine_neutral` 守住该行为

## 非目标

- Phase A 不创建 workflow bundle。
- Phase A 不生成 C++、Blueprint、GDScript、scenes、maps 或 assets。
- Phase A 不调用 Unreal、Godot、ComfyUI 或 provider APIs。
- Phase A 不新增 MCP tools。
- Phase A 不承诺 playable demo 或 engine project writes。

## 验证命令

```text
python -m pytest tests/unit/test_game_build_compiler_schemas.py tests/unit/test_game_build_compiler_fixtures.py tests/unit/test_game_build_compiler_contract_doc.py -q
python -m pytest -q
```
