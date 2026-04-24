# ForgeUE Validation Matrix

验证分三级:Level 0 离线必跑,Level 1 需要 LLM key,Level 2 需要 ComfyUI / UE / 真实外部服务。任何文档中的测试数量不一致,一律以 `python -m pytest -q` **本地实际运行结果**为准。

---

## 0. 通用原则

- **不硬编码测试总数**。README / CHANGELOG / docs / specs 中出现不一致时,先标记为 doc drift,再以实测为准。
- **不 mock 关键边界**:download / EventBus / DAG / BudgetTracker / bundle Artifact 流走真实对象(NFR-MAINT-004 / 005)。
- **付费调用默认 opt-in**:framework 单元 / 集成测试走 `FakeAdapter` + `FakeComfyWorker`;真实 provider 走 `probes/provider/*` 且需显式 `FORGEUE_PROBE_*=1`。
- **产物落项目树**:`./artifacts/<YYYY-MM-DD>/<run_id>/` 或 `./demo_artifacts/<YYYY-MM-DD>/...`;禁用 `/tmp/...`。

### 0.1 Shell 选择说明(Git Bash vs PowerShell)

本文档的代码块默认以 **Git Bash** 为主(与 `CLAUDE.md` / `AGENTS.md` 的 Windows Shell 约定一致)。PowerShell 用户按以下三条规则翻译即可,本文只对 **env 注入 / `tail` 管道 / `<UE>` 调用** 等关键段落给出并列 PowerShell 等价块。

| Bash 语法 | PowerShell 等价 | 说明 |
|---|---|---|
| `ENV=value <cmd>` | `$env:ENV="value"; <cmd>` | 内联环境变量不能直接用;必须先 `$env:` 赋值再调用 |
| `<cmd> \| tail -N` | `<cmd> \| Select-Object -Last N` | PowerShell 无 `tail`;`Select-Object -Last` 是 pipeline 原生 |
| 行尾 `\`(反斜线续行) | 行尾 `` ` ``(反引号)或改为单行 | PowerShell 不认 `\` 续行;反引号要在行末,反引号后不能有空格 |
| `python -m pytest -q` | `python -m pytest -q` | 纯 Python 入口在两边一致,不需要翻译 |
| `./artifacts/<YYYY-MM-DD>/...` 路径 | 同左 | PowerShell 接受正斜线 `/`,无需改写 |

PowerShell 调用外部 `.exe` 带空格路径时用调用操作符:`& "<path/with space/tool.exe>" arg1 arg2`。

---

## 1. Level 0 — 无 API key 必跑

目标:纯离线,15~20 秒内跑完全量自动化验收。任何 commit 前必须绿。

### 1.1 全量自动化

```bash
# 全量测试(数量以实测为准,不硬编码)
python -m pytest -q

# 收集但不执行(想看真实用例数)
python -m pytest --collect-only -q | tail -5

# 分阶段闭环(P0-P4)
python -m pytest tests/integration/test_p{0,1,2,3,4}_*.py -v

# L4 image → 3D 契约(offline,不含 live)
python -m pytest tests/integration/test_l4_image_to_3d.py -v

# 单模块单测
python -m pytest tests/unit/test_event_bus.py -v
```

```powershell
# PowerShell 等价(只有 `tail -5` 需要翻译,其余 pytest 调用一致)
python -m pytest -q
python -m pytest --collect-only -q | Select-Object -Last 5
python -m pytest tests/integration/test_p{0,1,2,3,4}_*.py -v
python -m pytest tests/integration/test_l4_image_to_3d.py -v
python -m pytest tests/unit/test_event_bus.py -v
```

### 1.2 CLI 离线冒烟

```bash
# 纯 mock 三步线性 pipeline(无 API key)
python -m framework.run \
    --task examples/mock_linear.json \
    --run-id demo \
    --artifact-root ./artifacts

# 期望:terminal 打印 status: succeeded,./artifacts/<today>/demo/run_summary.json 落盘
```

```powershell
# PowerShell 等价(反斜线续行改写为反引号)
python -m framework.run `
    --task examples/mock_linear.json `
    --run-id demo `
    --artifact-root ./artifacts
```

### 1.3 框架级 smoke probe(无 key)

```bash
python -m probes.smoke.probe_framework
python -m probes.smoke.probe_aliases
python -m probes.smoke.probe_models
```

### 1.4 手工看产物(pytest 默认 tmp_path 会被回收)

```bash
python -m pytest tests/integration/test_p4_ue_manifest_only.py --basetemp=./demo_artifacts/runs/p4_inspect
```

### Level 0 通过条件

- `python -m pytest -q` 全绿
- CLI 离线 demo 不抛异常,`run_summary.json` 落盘
- smoke probe 全部 `[OK]` / `[SKIP]`

---

## 2. Level 1 — 需要 LLM key

前提:`.env` 里至少配置一个 provider key(参照 `.env.example`)。

### 2.1 真实 LLM 结构化抽取(P1)

```bash
python -m framework.run \
    --task examples/character_extract.json \
    --run-id r1 \
    --live-llm
```

```powershell
# PowerShell 等价(反斜线续行改写为反引号)
python -m framework.run `
    --task examples/character_extract.json `
    --run-id r1 `
    --live-llm
```

### 2.2 生产 pipeline + 内嵌 review(P3,LLM 侧,图像走 FakeComfy)

```bash
python -m framework.run \
    --task examples/image_pipeline.json \
    --run-id r3 \
    --live-llm
```

```powershell
# PowerShell 等价
python -m framework.run `
    --task examples/image_pipeline.json `
    --run-id r3 `
    --live-llm
```

### 2.3 图像编辑(L5-A)

```bash
python -m framework.run \
    --task examples/image_edit_pipeline.json \
    --run-id r_edit \
    --live-llm
```

```powershell
# PowerShell 等价
python -m framework.run `
    --task examples/image_edit_pipeline.json `
    --run-id r_edit `
    --live-llm
```

### 2.4 UE5 API 查询

```bash
python -m framework.run \
    --task examples/ue5_api_query.json \
    --run-id r_ue5_api \
    --live-llm
```

```powershell
# PowerShell 等价
python -m framework.run `
    --task examples/ue5_api_query.json `
    --run-id r_ue5_api `
    --live-llm
```

### 2.5 Provider 诊断(opt-in 轻量)

```bash
python -m probes.provider.probe_packycode
python -m probes.provider.probe_glm_image_debug
python -m probes.provider.probe_glm_watermark_param
python -m probes.provider.probe_glm_watermark_via_framework
```

### 2.6 视觉 review 质量分层(opt-in)

```bash
FORGEUE_PROBE_VISUAL_REVIEW=1 python -m probes.provider.probe_visual_review
```

```powershell
# PowerShell 等价(内联 env 拆为 $env: 赋值 + 调用)
$env:FORGEUE_PROBE_VISUAL_REVIEW="1"; python -m probes.provider.probe_visual_review
```

产物:`./demo_artifacts/<YYYY-MM-DD>/probes/provider/probe_visual_review/<HHMMSS>/comparison_table.md`

### 2.7 Pricing probe(dry-run 默认 / --apply 才改 YAML)

```bash
# 看所有 provider 的抓取结果(不改文件)
python -m framework.pricing_probe

# 确认无误后再落 config/models.yaml
python -m framework.pricing_probe --apply
```

### Level 1 通过条件

- 每条 CLI live 命令 `status: succeeded`
- BudgetTracker 汇总的 `total_cost_usd` 合理(与预期阶数一致)
- probe 全部 `[OK]`,无 `[FAIL]`
- pricing probe `manual` 条目未被覆盖

---

## 3. Level 2 — ComfyUI / UE / 真实外部运行时

前提:
- 本地 ComfyUI 或 Tencent Hunyuan 3D key;
- 装有 UE 5.x 的机器 + 空白或已有 UE 工程 + `.uproject` 启用 `PythonScriptPlugin`。

### 3.1 ComfyUI HTTP pipeline(P3,真实出图)

```bash
# 先起 ComfyUI:http://127.0.0.1:8188
python -m framework.run \
    --task examples/image_pipeline.json \
    --run-id r_comfy \
    --live-llm \
    --comfy-url http://127.0.0.1:8188
```

```powershell
# PowerShell 等价(反斜线续行改写为反引号)
python -m framework.run `
    --task examples/image_pipeline.json `
    --run-id r_comfy `
    --live-llm `
    --comfy-url http://127.0.0.1:8188
```

注意:bundle 的 `workflow_graph` 需要手工补,参见 `examples/image_pipeline.json`。

### 3.2 Hunyuan 3D mesh 生成(贵族 API,opt-in)

```bash
# 先用 submit / format probe 验证 key 与接口
FORGEUE_PROBE_HUNYUAN_3D=1 python -m probes.provider.probe_hunyuan_3d_submit
FORGEUE_PROBE_HUNYUAN_3D=1 python -m probes.provider.probe_hunyuan_3d_format

# 查历史 job_id 真实状态(避免 blind retry 双扣,ADR-007)
FORGEUE_PROBE_HUNYUAN_3D=1 python -m probes.provider.probe_hunyuan_3d_query --job-id <JOB_ID>

# 真实 L4 image → 3D(会真实扣费)
python -m framework.run \
    --task examples/image_to_3d_pipeline_live.json \
    --run-id r_mesh \
    --live-llm
```

```powershell
# PowerShell 等价(内联 env 拆为 $env: 赋值 + 调用;续行改为反引号)
# 对同一 Shell 会话,$env: 赋值一次即对后续所有 python 调用生效,无需每行重复
$env:FORGEUE_PROBE_HUNYUAN_3D="1"
python -m probes.provider.probe_hunyuan_3d_submit
python -m probes.provider.probe_hunyuan_3d_format
python -m probes.provider.probe_hunyuan_3d_query --job-id <JOB_ID>

python -m framework.run `
    --task examples/image_to_3d_pipeline_live.json `
    --run-id r_mesh `
    --live-llm
```

**重要**:mesh.generation 失败时 stderr 会打印 job_id,**不要**直接 `--resume`。先用 `probe_hunyuan_3d_query --job-id <...>` 确认服务端 job 状态,再决定是否 resume。

### 3.3 UE 真机冒烟(A1 commandlet 路径,0 GUI)

```bash
# Step 1:framework 侧跑 live bundle(~60 秒,约 $0.12 USD)
PYTHONPATH=src python -m framework.run \
    --task examples/ue_export_pipeline_live.json \
    --live-llm \
    --run-id a1_demo

# Step 2:UE 5.x commandlet 真机 import(~20 秒,无 GUI)
#   要求:<UE>/Engine/Binaries/Win64/UnrealEditor-Cmd.exe 可用
#         <project>.uproject 已启用 PythonScriptPlugin
FORGEUE_RUN_FOLDER="<artifact_root>/<today>/a1_demo/Content/Generated/a1_demo" \
"<UE>/Engine/Binaries/Win64/UnrealEditor-Cmd.exe" \
    "<project>.uproject" \
    -ExecutePythonScript="<repo>/ue_scripts/a1_run.py"
```

```powershell
# PowerShell 等价
# Step 1:framework 侧跑 live bundle
$env:PYTHONPATH="src"
python -m framework.run `
    --task examples/ue_export_pipeline_live.json `
    --live-llm `
    --run-id a1_demo

# Step 2:UE 5.x commandlet 真机 import
#   $env: 注入 FORGEUE_RUN_FOLDER;UnrealEditor-Cmd.exe 路径含空格,必须用调用操作符 &
$env:FORGEUE_RUN_FOLDER="<artifact_root>/<today>/a1_demo/Content/Generated/a1_demo"
& "<UE>/Engine/Binaries/Win64/UnrealEditor-Cmd.exe" `
    "<project>.uproject" `
    -ExecutePythonScript="<repo>/ue_scripts/a1_run.py"
```

期望:
- `Content Browser` 出现导入的贴图 / 静态网格 / 音频
- `<project>/Content/Generated/a1_demo/evidence.json` 追加了每个导入操作的记录

### 3.4 UE GUI Python Console(可选)

```python
# UE GUI 里打开 Python Console
exec(open('<repo>/ue_scripts/run_import.py').read())
```

### Level 2 通过条件

- ComfyUI 路径产出真实贴图 Artifact(`file` 载体)
- Hunyuan 3D 路径产出 `.glb` Artifact(magic bytes `glTF` 校验通过)
- UE commandlet 或 Console 导入成功,`evidence.json` 记录齐全
- 任何失败都走 FailureModeMap 分类,不静默重试、不双扣

---

## 4. 验证事实来源清单(按需查)

| 问题 | 去哪里看 |
|---|---|
| 真正的测试数量 | Git Bash: `python -m pytest --collect-only -q \| tail -5` · PowerShell: `python -m pytest --collect-only -q \| Select-Object -Last 5` |
| 某 FR 对应测试 | `docs/acceptance/acceptance_report.md` §4 |
| 某 bundle 的用途 | `docs/acceptance/acceptance_report.md` §3 + `openspec/specs/examples-and-acceptance/spec.md` |
| probe 约定 | `probes/README.md` §5 + `openspec/specs/probe-and-validation/spec.md` |
| failure mode 映射 | `src/framework/runtime/failure_mode_map.py` + `docs/design/LLD.md` §5.7 |
| 定价事实 | `config/models.yaml`(`pricing_autogen.sourced_on` + `source_url`) |
| 贵族 API 策略 | `docs/requirements/SRS.md` ADR-007 + `CHANGELOG.md` TBD-007 |

---

## 5. 当 validation 失败时

- **L0 失败**:先跑单个失败用例 `-v` 看详细输出,不要打包汇报。
- **L1 失败**:检查 `.env`、BudgetTracker 是否上限命中、provider 返回体是否包了 HTML(FR-WORKER-010)。
- **L2 失败**:先走 probe 验证 provider key 是否有效,再看 ComfyUI / UE 进程日志。mesh 失败**必须**先 query,不要 resume。

任何失败都应该对应 FailureMode 分类(NFR-REL-001);未分类的异常本身就是 bug。
