## Context

Phase 1 mesh(`comfy-agent-cli-mesh-audio-video-adoption`,2026-05-03 归档)在 `ComfyAgentWorker` 内部建立了 capability dispatch 协议(`_CAPABILITY_BY_MODEL_ID` / `_REQUIRED_OUTPUT_KEY` / `_AUXILIARY_OUTPUT_KEYS_BY_CAP` / `_REJECTED_OUTPUT_KEYS_BY_CAP` 4-dict + 三段表 `_validate_outputs`),并显式预留了 audio / video 两路 follow-on hook(Phase 1 spec.md 三段表里 audio 行已写「TBD by `comfy-agent-cli-audio-adoption`」)。

Phase 2 audio capability 接入的核心阻塞**不是** ComfyUI 协议层(已就绪),而是 ForgeUE **缺 audio worker baseline**:

- 没有 `AudioCandidate` dataclass(`MeshCandidate` 在 [mesh_worker.py:65](src/framework/providers/workers/mesh_worker.py#L65) 已建)
- 没有 `AudioWorker` ABC(`MeshWorker` 在 [mesh_worker.py:77](src/framework/providers/workers/mesh_worker.py#L77) 已建)
- 没有 `GenerateAudioExecutor`(`GenerateMeshExecutor` 在 [generate_mesh.py](src/framework/runtime/executors/generate_mesh.py) 已建)
- 没有 `audio.t2a` step type 注册到 workflow loader
- 没有 `audio_local` alias(将作为 SRS FR-MODEL-007 第 11 alias)

SRS §7.3 TBD-002「Audio worker(AudioCraft 接入),待音频资产需求明确」—— ComfyUI 本地 audio capability 是 Phase 2 的真实驱动力,本 change 用「第一真实客户」立 audio worker 通用契约,避免先空建 ABC 再反复改(YAGNI)。Phase 1 mesh 复用既有 mesh ABC 是因为 Hunyuan3D / Tripo3D 时代已建好,audio 没有这个 free baseline,所以本 change 比 Phase 1 略大。

UE 侧 audio 链路已就绪:[manifest_builder.py:45](src/framework/ue_bridge/manifest_builder.py#L45) 已有 `("audio", "waveform"): "sound_wave"` 映射,`domain_audio.import_audio_entry` 入口在 [import_plan_builder.py](src/framework/ue_bridge/import_plan_builder.py) 已注册,SRS FR-UE-003 `import_audio` 在基线版本已通过 P4 真机验证(2026-04-23)。

ComfyUI 共享目录暴露 2 个 audio manifest:

| manifest | 模型 | path 入参 | 输出节点 | output primary |
|---|---|---|---|---|
| `Audio_Workflows/audio_ace_step_1_t2a_instrumentals` | ACE-Step v1 3.5B | `tags` (TextEncodeAceStepAudio) + `lyrics` | `SaveAudioMP3` | `audio/flac`(声明) |
| `Audio_Workflows/audio_stable_audio_example` | Stable Audio Open 1.0 | `text` (CLIPTextEncode node id "6") + `negative_prompt` (id "7") | `SaveAudioMP3` | `audio/flac`(声明) |

注意:两个 manifest 的 `outputs.primary` 都标注 `audio/flac`,但输出节点都是 `SaveAudioMP3`(节点名暗示 mp3)。这是 ComfyUI 节点命名历史遗留 — `SaveAudioMP3` 节点实际可输出 flac/mp3 取决于节点参数。本 change 的 `AudioCandidate.format` 由 ComfyUI agent CLI stdout JSON `outputs.audio` 列表里的实际**文件扩展名**检测决定,不依赖 manifest 声明(详见 D10)。

模型权重(ACE-Step 3.5B / Stable Audio Open ~1B)体积比 Phase 1 mini-Hunyuan3D(2GB)小,首次运行 ComfyUI 会自动从 HuggingFace 拉,**不需要**像 Phase 1 round 5 D10 那样手工建 LoadImage 变体 manifest 解决 6GB 主模型问题。

## Goals / Non-Goals

**Goals:**

- 建立 `AudioWorker` ABC 通用契约(类比 `MeshWorker`),`AudioCandidate` dataclass(类比 `MeshCandidate`),异常树 `AudioWorkerError` / `AudioWorkerTimeout` / `AudioWorkerUnsupportedResponse`(类比 mesh 三层)
- 建立 `GenerateAudioExecutor` 执行器(类比 `GenerateMeshExecutor` 但走 text-to-audio 路径,**不接** source bytes),`audio.t2a` step type 注册
- 在 `ComfyAgentWorker` 4-dict 扩 audio capability 落子,加新方法 `generate_audio(spec, num_candidates, seed, timeout_s) -> list[AudioCandidate]`
- 注册 `comfy/local-audio` virtual model + `audio_local` alias 到 `ModelRegistry`(SRS FR-MODEL-007 第 11 alias)
- 提供 `examples/comfy_local_smoke_audio.json` 端到端 bundle + L2 evidence 真实 FLAC 落 `artifacts/`(双终端模式,沿 Phase 1)
- Documentation Sync Gate 10 文档同步;TBD-002 lift + TBD-009 Phase 2 完成
- 沿 Phase 1 失败模式映射模式给 audio worker 加 mode 路由(`audio_worker_timeout` / `audio_worker_unsupported` → `Decision.abort_or_fallback`)
- 沿 Phase 1 ADR-007 边界(`pricing.per_task_usd > 0`):本地 ComfyUI audio `pricing: null` → 非 premium → 内部 retry loop;远端 audio worker(future)`per_task_usd > 0` → premium → strict no-silent-retry

**Non-Goals:**

- 远端 AudioCraft worker 协议接入(TBD-002 字面意思的 audio worker AudioCraft 接入)留独立 follow-on change(`audio-worker-audiocraft-adoption` 或类似命名 — 本 change scope=ABC + ComfyUI 第一客户;远端协议在 ABC 落地后 follow-on 实施,沿 Phase 1 D3 split 模式)
- ComfyUI video capability(Phase 3)留 `comfy-agent-cli-video-adoption` follow-on
- ComfyUI audio lifecycle 仍 `none` only(沿用 Phase 1 D6 + SRS TBD-010)
- audio-to-audio 路径(类比 image-to-mesh 那种 source bytes 输入模式)— 本 change scope=text-to-audio only;未来若 ComfyUI 暴露 audio-to-audio manifest(如 audio remix / 风格迁移)再走 follow-on,沿 mesh `comfy_image_param_key` + `_resolve_source_*` 模式
- AudioMetadata 的 advanced 字段(channels / bit_depth / encoder version 等):本 change 只接 SRS FR-STORE-004 列出的 `format` / `duration_seconds` / `sample_rate` 三个 metadata 字段,其它 advanced 字段在用户实际使用驱动下增加
- review_engine 的 audio quality rubric(类比 `ue_asset_quality.yaml` 但针对 audio):本 change scope=不接 audio review;Phase 1 mesh 也没接 mesh review(沿用 image review 模板),audio 同样;follow-on `audio-review-rubric-adoption` 单独建 rubric
- `framework.review_engine` audio-aware 审查:本 change scope=不接;沿用现有 review 流程(audio artifact 走通用文本 + metadata review)
- examples-and-acceptance 里 a2_audio fence 类比 a2_mesh:本 change scope=examples-and-acceptance 只加 Level 0/1/2 acceptance entry,不要求 a2_audio 集成测试 fence(audio 远端真实使用场景未到,P5+ 多模态端到端 smoke 待后续)

## Decisions

### D1 — Capability 由 model id 推断,沿用 Phase 1 dispatch 协议

**决策**:`ComfyAgentWorker._CAPABILITY_BY_MODEL_ID` 表扩第三 entry — `"comfy/local-audio": "audio"`。bundle 不引入 `outputs_kind` / `capability` 字段;capability 仅由 resolved model id 推断;unknown id `__init__` raise `WorkerUnsupportedResponse`(沿 Phase 1 D1)。

**理由**:Phase 1 D1 已锁定此协议,扩字典是 forward-compatible 增量,不需要新设计。bundle 协议保持稳定(Phase 1 锁定的 `comfy_workflow` + `comfy_params` + `comfy_lifecycle` 三字段不动),用户切换 capability 只通过 alias / model id 切换。

**Alternative 考虑**:bundle 加 `step.config.spec.outputs_kind: "audio"` 显式字段。**Rejected**:Phase 1 已 deferred 此选项;两个表达 audio capability 的字段(model id + outputs_kind)冗余且可能不一致。

### D2 — 4-dict 三段表 audio capability 落子

**决策**:`ComfyAgentWorker` 4-dict 扩 audio:

| dict | audio entry |
|---|---|
| `_CAPABILITY_BY_MODEL_ID` | `"comfy/local-audio": "audio"` |
| `_REQUIRED_OUTPUT_KEY` | `"audio": "audio"` |
| `_AUXILIARY_OUTPUT_KEYS_BY_CAP` | `"audio": set()` |
| `_REJECTED_OUTPUT_KEYS_BY_CAP` | `"audio": {"images", "glb", "video"}` |

**REQUIRED**:`outputs.audio` non-empty(string list,文件路径)。
**AUXILIARY**:无(audio capability 不容忍其它 outputs key non-empty;mesh-mode 容忍 `outputs.images` 是因为 mesh manifest 常顺手生成 PNG preview;audio manifest 不会顺手出 image / glb / video)。
**REJECTED**:`outputs.images` / `outputs.glb` / `outputs.video` non-empty 即 raise `WorkerUnsupportedResponse`。

**理由**:Phase 1 D2 已锁定三段表协议;扩 audio 落子是字典扩展,无需新代码逻辑(`_validate_outputs` 实装已 capability-agnostic 通过 4-dict 查表)。`outputs.audio` 作为 REQUIRED key 与 ComfyUI agent CLI 的输出协议一致(SaveAudioMP3 / SaveAudio 节点都把 audio 文件路径放 `outputs.audio` list)。

**Alternative 考虑**:把 `outputs.images` 作为 AUXILIARY 容忍(类比 mesh)。**Rejected**:audio manifest 输出 PNG preview 不是常见模式(ACE-Step / Stable Audio 都没有);若未来某 audio manifest 有 spectrogram preview,届时 follow-on change 再扩 AUXILIARY,YAGNI。

### D3 — Scope split:本 change 仅接 ComfyUI audio + audio worker baseline

**决策**:本 change scope = audio-only ComfyUI capability + AudioWorker ABC + AudioCandidate + GenerateAudioExecutor + audio.t2a step type;远端 AudioCraft 协议接入 + ComfyUI video capability 各自开独立 follow-on change。

**理由**:沿 Phase 1 D3 split 模式 — 单 change 跨多 provider / 多 capability 风险大,review 难拉齐。Phase 1 mesh 拆分得到的好处:design / spec / tasks 焦点收敛,5 轮 codex review 都对单 capability 充分覆盖。Phase 2 audio 同模式。

**TBD-002 lift 论据**:SRS §7.3 TBD-002 原义是「Audio worker(AudioCraft 接入)」 — 把 ABC 与远端实装绑在一起延后。本 change 用「ComfyUI 本地 audio 是真实驱动力」分两步走:**先建 ABC + ComfyUI 第一客户(本 change)**,**远端 AudioCraft 协议落地(follow-on)**。这与 mesh 路径一致(Phase 1 不接远端 AudioCraft / 新远端 mesh,只用 ComfyUI 当 ABC 第一客户;若 mesh 不存在 Hunyuan3D,Phase 1 也会同模式同步建 mesh ABC)。

**Alternative 考虑**:继续 block 等到 AudioCraft 接入需求出现再统一接 ABC + AudioCraft + ComfyUI 三件套。**Rejected**:用户当前没 AudioCraft 需求,等待会让 ComfyUI audio 一起延后;AudioCraft 协议(REST 或其它)与 ComfyUI agent CLI subprocess 协议正交,ABC 不应被远端协议细节绑架。

### D4 — ADR-007 边界沿用 `pricing.per_task_usd > 0` 判定

**决策**:本地 ComfyUI audio `comfy_local_audio` model 的 `pricing: null`(本地 GPU,无 per-task 费用),`pricing.per_task_usd` is None / 0 → 非 premium → `GenerateAudioExecutor._generate_via_comfy_worker` 内部 retry loop 用 `policy.max_attempts`(默认 2);wrapped `AudioWorkerTimeout` 经 FailureModeMap 走 `audio_worker_timeout` mode → `Decision.abort_or_fallback`(与远端 audio worker 终态一致,不是 retry_same_step)。

未来远端 audio worker(AudioCraft 等)`pricing.per_task_usd > 0` → premium → 主流程 `attempts=1` 强制 + ADR-007 strict no-silent-retry。

**理由**:沿 Phase 1 D4 round 2 修订,用现有 `BudgetTracker.estimate_*_call_cost_usd` 字段判断 premium,不引入新 `is_premium` API。

**Alternative 考虑**:把所有 audio worker 默认 premium。**Rejected**:本地 ComfyUI 跑 audio 是 free GPU 时间,失败重试无外部成本;若一刀切 attempts=1,本地常见 OOM 一次性失败需要用户手动 resume,UX 差。

### D5 — AudioCandidate provenance + 顶层 audio metadata 字段(F3 round-2 修订:顶层字段统一,**不**双源)

**决策**(F3 round-2 修订:顶层字段 ACCEPTED,与 SRS FR-STORE-004 audio metadata 字段对齐;`AudioCandidate.metadata` 仅承载 provenance,**不**复制 `duration_seconds` / `sample_rate`):

`AudioCandidate` 顶层字段(SRS FR-STORE-004 audio metadata 三件套):

```python
@dataclass
class AudioCandidate:
    data: bytes
    format: Literal["flac", "mp3", "wav"]                 # REQUIRED;D10 magic-bytes 校验后的格式
    metadata: dict[str, Any] = field(default_factory=dict) # 仅 provenance(下方 5 keys)
    duration_seconds: float | None = None                  # SRS FR-STORE-004;F4 round-2:本 change scope=None(ComfyUI 不暴露)
    sample_rate: int | None = None                         # SRS FR-STORE-004;同上
```

`AudioCandidate.metadata` 严格只放 provenance(与 Phase 1 mesh `MeshCandidate.metadata["worker_metadata"]` 同结构):

```python
{
    "comfy_manifest": str,                # e.g. "Audio_Workflows/audio_stable_audio_example"
    "comfy_params_snapshot": dict[str, Any],  # bundle 给的 comfy_params 副本(prompt / seed / duration_seconds 都在内)
    "comfy_capability": "audio",          # 显式 capability tag
    "comfy_original_filename": str,       # ComfyUI 输出原文件名(e.g. "ComfyUI_00001_.flac")
    "comfy_subprocess_run_metadata": dict, # subprocess 退出码 / 总耗时 / cli args(沿 Phase 1)
}
```

**`GenerateAudioExecutor.execute` 持久化合同**:

```python
ctx.repository.put(
    value=cand.data,
    payload_kind=PayloadKind.file,
    file_suffix=f".{cand.format}",
    metadata={
        # SRS FR-STORE-004 audio metadata 三件套(顶层 Artifact.metadata key,从 candidate 顶层字段读)
        "format": cand.format,
        "duration_seconds": cand.duration_seconds,    # None when ComfyUI doesn't expose
        "sample_rate": cand.sample_rate,              # None
        # provenance 子树(从 candidate.metadata 读)
        "worker_metadata": dict(cand.metadata),
        # ... 其它 lineage / variant_kind 字段
    },
)
```

**理由**(F3 codex finding round-2 修订):
- Round-1 `Rejected 顶层字段` 是矛盾自洽:同一 design doc D10 段构造 `AudioCandidate(..., duration_seconds=..., sample_rate=...)` 用顶层字段,各 spec 也用顶层访问 — Rejected 论据不成立
- Round-2 ACCEPTED 顶层字段是因为:(a) SRS FR-STORE-004 直接命名 `duration_seconds` / `sample_rate` 作为 audio metadata 字段;(b) executor 持久化只从顶层读(单一 source of truth),`AudioCandidate.metadata` 只承载 provenance(provenance 与 metadata 不重复 → 不双源)
- `format_detected` debug 字段去掉(redundant — `format` 顶层已是 magic-bytes 校验后的 ground truth per F5)

**Alternative 考虑(round-2)**:retain dual storage(顶层 + metadata 子键 都有 duration_seconds / sample_rate)。**Rejected**:executor 在 `repo.put` 时不知道读哪个 → spec / 实施 / fence 三方分裂 → F3 codex finding 原始问题。

### D6 — comfy_lifecycle: "none" only,沿用 Phase 1

**决策**:audio capability 路径下 `comfy_lifecycle: "none"` 唯一支持;`ensure_running` / `ensure_release` / `self_managed_session` 留 SRS TBD-010 `executor-async-rewrite` 后续 change 解锁(沿 Phase 1 D6)。

`ComfyAgentWorker.__init__` 守门已存在(`default_lifecycle != "none"` raise `WorkerUnsupportedResponse`),audio capability 加 dispatch 不影响此守门(__init__ 守门在 capability 推断之后,但 lifecycle 守门在 __init__ 第一段,顺序保持)。

**理由**:executor async rewrite 是跨 capability 的运行时改造,不应在 audio change scope 内做。本地 ComfyUI 用户用「双终端」模式(用户自管 server 进程),与 Phase 1 一致。

### D7 — text-to-audio 路径,无 source bytes(audio 与 mesh 的核心差异)

**决策**:`GenerateAudioExecutor` 走 text-to-audio 流程,**不**调 `_resolve_source_image(ctx)`,**不**写 source bytes 到 ComfyUI input/ 目录,**不**注入 `comfy_params["input_image"]`。bundle prompt 直接走 `step.config.spec.comfy_params.{tags|text|...}`,executor 只负责把 prompt 透传给 `ComfyAgentWorker.generate_audio(spec, ...)`。

`ComfyAgentWorker.generate_audio` 签名:

```python
def generate_audio(
    self,
    *,
    spec: dict,                    # bundle step.config.spec(含 comfy_workflow / comfy_params / comfy_lifecycle)
    num_candidates: int,
    seed: int | None,
    timeout_s: float,
) -> list[AudioCandidate]:
```

注意:**没有** `prompt: str` 参数 — prompt 已经在 `spec["comfy_params"]` 里(bundle 直接给),executor 不解构(沿 Phase 1 mesh 风格,只是 mesh 多了 `source_image_filename` 因为 image-to-mesh 是 mesh-specific 的两步 DAG 必须)。

**理由**:audio 是单步 text-to-audio(无上游 step),与 mesh 的 image-to-mesh 两步 DAG(上游 image step + 下游 mesh step,depends_on)结构不同。bundle 直接把 prompt 写进 `comfy_params` 是最简单且与 mesh `comfy_params.tags`(若 user 写 mesh manifest 含 prompt 字段)一致的协议。

**Alternative 考虑 1**:`step.config.spec.prompt: str` 单独字段,executor 注入 `comfy_params["text"]`(类比 mesh 的 `comfy_image_param_key` 默认 `"input_image"` 模式)。**Rejected**:audio manifest 的 prompt 字段名因 manifest 不同(ACE-Step 用 `tags` + `lyrics`;Stable Audio 用 `text` + `negative_prompt`),executor 不应把多字段语义压到单字段;`step.config.spec.comfy_params` 已是 manifest-aware 自由字典,bundle 作者直接给 manifest 期待的 key 是最直接的。

**Alternative 考虑 2**:加 `step.config.spec.comfy_prompt_param_key: str` 让 bundle 显式声明 prompt key,executor 从 `step.config.spec.prompt: str` 注入。**Rejected**:audio manifest 常需多个 prompt 字段(positive + negative + style tags),单 key 模型不够;让 bundle 直接给 comfy_params 字典更灵活。

**Implication**:`examples/comfy_local_smoke_audio.json` 直接在 `comfy_params` 里写 `text` / `tags` / `lyrics` / `negative_prompt` 等,具体 key 由选用的 manifest 决定;executor 不验证 key 命名,manifest 不接受时 ComfyUI agent CLI 报错(via `ComfyWorkerError` → wrapped `AudioWorkerError`)。

### D8 — Audio prompt 注入约定:bundle 直接给 comfy_params

**决策**:bundle 作者直接在 `step.config.spec.comfy_params` 里写 manifest 期待的所有参数(prompt / negative_prompt / tags / lyrics / duration_seconds / seed / steps / filename_prefix);executor 不解构 / 不注入 / 不验证。

**理由**:见 D7 reasoning。

**示例 bundle**(摘自 `examples/comfy_local_smoke_audio.json`):

```json
{
  "id": "audio_t2a",
  "kind": "audio.t2a",
  "config": {
    "spec": {
      "comfy_workflow": "Audio_Workflows/audio_stable_audio_example",
      "comfy_params": {
        "text": "heavenly choral electronic dance, uplifting, ethereal pads, 130bpm",
        "negative_prompt": "",
        "duration_seconds": 10.0,
        "seed": 42,
        "steps": 50
      },
      "comfy_lifecycle": "none"
    },
    "provider_policy": {
      "capability_required": "audio.t2a",
      "models_ref": "audio_local"
    },
    "policy": {
      "max_attempts": 2,
      "timeout_seconds": 300
    },
    "depends_on": []
  }
}
```

**Implication**:用户切换 manifest(ACE-Step ↔ Stable Audio)时手工调整 `comfy_params` keys;executor 不感知 manifest schema。Phase 1 mesh 的 `comfy_image_param_key` 模式不引入到 audio。

### D9 — AudioWorker ABC 设计 + 内部 retry loop

**决策**:`AudioWorker(ABC)` ABC 在 `src/framework/providers/workers/audio_worker.py` 新建,签名:

```python
class AudioWorker(ABC):
    name: str
    
    @abstractmethod
    def generate_audio(
        self,
        *,
        spec: dict,                    # bundle step.config.spec
        num_candidates: int,
        seed: int | None,
        timeout_s: float,
    ) -> list[AudioCandidate]: ...
```

**注意**:ABC `generate_audio` 签名与 `ComfyAgentWorker.generate_audio` 一致(no `prompt: str` 参数,prompt 在 spec 里);未来远端 AudioWorker(AudioCraft 等)同 ABC,实现自己的 spec 解析约定(可能直接读 `spec["prompt"]` 或 `spec["audiocraft_*"]`)。这是 ABC 通用契约的最大公约数。

**异常树**(类比 mesh_worker.py):

```python
class AudioWorkerError(RuntimeError): ...
class AudioWorkerTimeout(AudioWorkerError): ...
class AudioWorkerUnsupportedResponse(AudioWorkerError): ...
```

**`GenerateAudioExecutor._generate_via_comfy_worker` 内部 retry loop**(F2 round-2 修订:三 except 块拆分,timeout 才 retry,deterministic 不 retry,wrap 必须用 `from exc`,**不**裸 `raise`;对照 `generate_mesh.py:160-172` Phase 1 实装):

```python
def _generate_via_comfy_worker(
    self,
    ctx: StepContext,
    spec: dict,
    num: int,
    seed: int | None,
    timeout_s: float,
) -> list[AudioCandidate]:
    policy = ctx.step.retry_policy  # 顶层字段 per task.py:37(NOT ctx.step.config.policy)
    attempts = policy.max_attempts if policy else 2  # 本地非 premium per ADR-007 边界
    last_exc: AudioWorkerError | None = None
    worker = ComfyAgentWorker(model_id="comfy/local-audio", ...)
    for attempt in range(attempts):
        try:
            return worker.generate_audio(spec=spec, num_candidates=num, seed=seed, timeout_s=timeout_s)
        except ComfyWorkerTimeout as exc:
            # timeout: wrap + 条件 retry(本地非 premium)
            wrapped: AudioWorkerError = AudioWorkerTimeout(str(exc))
            last_exc = wrapped
            if attempt + 1 >= attempts:
                raise wrapped from exc  # 用尽 attempts:抛 wrapped(NOT 裸 raise — bare raise 会重抛原始 ComfyWorkerTimeout,FailureModeMap 看不到 audio mode)
            # else continue(若 retry policy 有 backoff,_backoff(policy, attempt))
        except ComfyWorkerUnsupportedResponse as exc:
            # deterministic error: 不 retry(参数错 / outputs 校验错 重试也错;违 R2-F2 retry budget critical fence)
            raise AudioWorkerUnsupportedResponse(str(exc)) from exc
        except ComfyWorkerError as exc:
            # generic worker error: 不 retry
            raise AudioWorkerError(str(exc)) from exc
    assert last_exc is not None
    raise last_exc  # safety net(应 unreachable;timeout 路径已 raise)
```

**关键 round-2 修订点**(F2 codex finding):
- ⚠️ Round-1 把三种 ComfyWorker 异常用单 except 块统一 retry → 错。Deterministic unsupported / generic 不应 retry(违 mesh round-2 R2-F2 教训 + tasks fence `test_local_comfy_audio_executor_does_not_retry_on_worker_unsupported_response`)
- ⚠️ Round-1 最后一次失败用裸 `raise` → 错。Bare `raise` 在 except 块内重抛**原始** `ComfyWorkerTimeout`,而非 `wrapped: AudioWorkerTimeout` → FailureModeMap.from_exception 匹配不到 `AudioWorkerTimeout` 分支 → `audio_worker_timeout` mode + `abort_or_fallback` decision 全部失效 → orchestrator 走 generic worker_timeout 路径 → 错误的 retry / fallback 行为
- ✅ Round-2 三 except 块对齐 mesh 实装(`generate_mesh.py:160-172`):timeout `raise wrapped from exc` 用尽 attempts 时;unsupported / generic 立即 `raise XxxResponse(...) from exc` 不 retry

**异常 wrap 与 FailureModeMap 协作**:

| inner exc | wrapped exc | retry? | FailureModeMap mode | Decision |
|---|---|---|---|---|
| `ComfyWorkerTimeout` | `AudioWorkerTimeout` | yes(直到 attempts 用尽) | `audio_worker_timeout` | `abort_or_fallback` |
| `ComfyWorkerUnsupportedResponse` | `AudioWorkerUnsupportedResponse` | **no**(deterministic) | `audio_worker_unsupported` | `abort_or_fallback` |
| `ComfyWorkerError` (其它) | `AudioWorkerError` | **no**(generic) | `audio_worker_unsupported`(归类) | `abort_or_fallback` |

**理由**:沿 Phase 1 D9 mesh 模式精确镜像;`abort_or_fallback` 是终态(不 retry_same_step,因为内部 retry 已尝试),orchestrator 走 `on_fallback` 配置(若 bundle 配 fallback model),否则终止 step 不静默重试。

### D10 — AudioCandidate.format 检测(扩展名 + 强制 magic bytes)+ outputs.audio 路径解析(F4 + F5 round-2 修订)

**决策**(F5 round-2 修订:magic bytes 二次校验从「不强制」反转为「强制」,沿 Phase 1 mesh FR-WORKER-006 GLB magic 二次校验模式;F4 round-2 修订:`outputs.metadata.audio` 路径不存在,duration / sample_rate 顶层字段固定 None):

`ComfyAgentWorker.generate_audio` 实装步骤:

1. 调 `_run_subprocess_and_validate(spec, timeout_s) -> dict`(Phase 1 已存在的 private helper),subprocess 跑 `python -m comfyui_api run <manifest>` 拿 stdout JSON envelope
2. `_validate_outputs(outputs)`(Phase 1 三段表)校验 `outputs.audio` non-empty + 无 rejected key(`outputs.images / glb / video` 非空 raise)
3. 遍历 `outputs.audio`(string list of absolute paths,per F4 probe `runner.py::extract_outputs` 真源 — 不是相对路径,**不**需要 `_resolve_output_path` 拼接)
4. 检测扩展名:`Path(abs_path).suffix.lower()[1:]` ∈ `{"flac", "mp3", "wav"}`;不在 raise `WorkerUnsupportedResponse`;为 `AudioCandidate.format` 字段
5. 读 bytes:`data = Path(abs_path).read_bytes()`
6. **Magic bytes 二次校验**(F5 round-2 修订:**强制**,与扩展名一致才接受,否则 raise):
   - `flac` → `data[:4] == b"fLaC"`(FLAC magic per RFC 9639)
   - `mp3` → `data[:3] == b"ID3"` OR `data[:2] in (b"\xff\xfb", b"\xff\xfa", b"\xff\xf3", b"\xff\xf2")`(ID3v2 tag 或 MPEG frame sync)
   - `wav` → `data[:4] == b"RIFF"` AND `data[8:12] == b"WAVE"`(RIFF chunk + WAVE format)
   - 不匹配:raise `WorkerUnsupportedResponse(f"audio format mismatch: extension={ext} but magic bytes={data[:12].hex()}")`
7. 构造 `AudioCandidate(data=data, format=ext, metadata={"comfy_manifest": ..., "comfy_params_snapshot": dict(spec.get("comfy_params") or {}), "comfy_capability": "audio", "comfy_original_filename": Path(abs_path).name, "comfy_subprocess_run_metadata": {...}}, duration_seconds=None, sample_rate=None)` ×N(per F4:duration / sample_rate 在本 change scope 始终 None,因 ComfyUI agent CLI `extract_outputs` 不暴露 — 见 `notes/audio_subprocess_probe_20260503.md` OQ-3)

**理由**:
- **扩展名**优先于 manifest 声明(`outputs.primary: audio/flac` 是 hint,SaveAudioMP3 节点实际写出格式 hash 节点参数;真相在文件本身)
- **Magic bytes**强制:扩展名能撒谎(`.flac` 文件可能内容是 mp3 / HTML 错误页 / 截断)— 文件 header 字节是真实 ground truth;ForgeUE 不能让错配文件落进 Artifact tree 等 UE `import_audio` 时再 raise(too late)。Phase 1 mesh FR-WORKER-006 强制 GLB `b"glTF"` magic 是同模式;audio 跟进。
- **WAV 检测取 12 字节**:RIFF 4 + size 4 + WAVE 4 = 12 字节;前 4 字节 `b"RIFF"` 不够(也是 AVI / ANI 容器 magic)
- **MP3 检测两路**:历史 ID3 tag 在文件头(`b"ID3"`),无 ID3 tag 时第一帧是 MPEG sync(`0xFF 0xFB` / `0xFA` 等)— 两路 OR
- **三种格式 whitelist** 防止 ComfyUI 输出 weird 格式(如 ogg)被静默接受 — UE `import_audio` 支持的格式有限,whitelist 强制契约

**Alternative 考虑 1**:不检测扩展名,信任 manifest `outputs.primary` 声明。**Rejected**:同上,manifest 声明是 hint。

**Alternative 考虑 2**:扩展名 whitelist 加 ogg / opus / m4a。**Rejected**:UE `import_audio` 通过 `unreal.SoundFactory` 支持的格式标准是 wav / flac / mp3(参考 [permission_policy.py](src/framework/ue_bridge/permission_policy.py));超出此 whitelist 的格式让 follow-on change 加(YAGNI)。

**Alternative 考虑 3(round-2 新加)**:Magic bytes 校验留 follow-on change(YAGNI)。**Rejected**:F5 codex finding 准确指出「扩展名等同 payload」推论不成立(`.flac` 内容可能是 MP3 / HTML / 截断);Phase 1 mesh GLB magic 强制是规范模式,audio 不应特殊化偏离。Magic bytes gate 不增加实施复杂度(每格式 4-12 字节 prefix check),不应推迟。

**Alternative 考虑 4(round-2 新加)**:duration / sample_rate 用 `wave` / `aifc` / `mutagen` 解析。**Rejected**:`wave` 仅支持 WAV;`aifc` 仅支持 AIFF;FLAC / MP3 需要第三方 codec lib(mutagen 推荐但本 change scope 不引入);ForgeUE `repo.put` 接受 `duration_seconds=None`(per artifact-contract spec acceptance Scenario);UE `unreal.SoundFactory` import 时自己解析 audio header — ForgeUE metadata best-effort None 不破坏 UE pipeline。Follow-on change `audio-metadata-parser` 单独引入 mutagen 或 stdlib `wave` 解析。

### D11 — Live smoke manifest 选择(对照 Phase 1 D6)

**决策**:本 change L2 evidence 走 `Audio_Workflows/audio_stable_audio_example`(Stable Audio Open 1.0)作为主推 manifest,理由:

- Stable Audio Open 1.0 模型权重小(~1B,~2GB);ACE-Step 3.5B 大(~7GB)
- Stable Audio 用 `CLIPTextEncode` + 标准 `KSampler`,与 ComfyUI image 路径节点同源,ComfyUI agent CLI 解析最稳
- ACE-Step 用 `TextEncodeAceStepAudio`(ACE-Step custom node)+ `EmptyAceStepLatentAudio`,需要 ACE-Step custom node 安装好,首次跑容易踩 custom node missing 坑

**Implementation**:`examples/comfy_local_smoke_audio.json` 用 Stable Audio manifest;debug log 留 ACE-Step 路径作为 fallback 验证条件(若用户报告 Stable Audio 跑不通,debug 时切 ACE-Step 验证 ComfyAgentWorker audio dispatch 协议本身)。

**Alternative 考虑**:同时跑两个 manifest 作为 L2 evidence。**Rejected**:Phase 1 mesh L2 evidence 也只跑了一个 manifest(round 5 mini-LoadImage 变体);单 manifest 足以验证 capability dispatch + AudioCandidate 落盘;两个 manifest 的 GPU 时间双倍。

### D12 — examples-and-acceptance 加 audio bundle + Documentation Sync Gate

**决策**:`examples/comfy_local_smoke_audio.json` 单 step bundle(`audio.t2a` step,直接 text-to-audio,无上游 image step);test_spec.md 加 audio fence 索引(预计 ~30-35 fence 量级);acceptance_report 加 audio capability 验收行(P5+ 多模态端到端 smoke 仍 follow-on,本 change 仅落 Level 0/1/2)。

具体 fence 表见 tasks.md。

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| ACE-Step custom node 在用户机器未装,Stable Audio manifest 不出问题但 ACE-Step 跑出 cryptic error | D11 选 Stable Audio 作为主 L2 manifest;debug log 显式记录两个 manifest 状态;本 change 不强求 ACE-Step 跑通(ACE-Step 在 ComfyUI 共享目录有 manifest 但 ForgeUE 不依赖) |
| ComfyUI agent CLI 的 `outputs.audio` 字段实际名可能与预期不一致(manifest declares `outputs.primary = "audio/flac"` 是 declaration,agent CLI 实际暴露的 outputs key 可能是 `audio` 也可能是别的) | tasks.md G2 早期实施 `probes/provider/probe_comfy_audio.py` opt-in probe,跑一次真实 ComfyUI 看 stdout JSON 结构;若 outputs key 非 `audio`,在 design doc 加 round-2 修订更新 4-dict |
| AudioCandidate metadata 的 duration_seconds / sample_rate ComfyUI 不暴露,落 None;UE 侧 `import_audio` 是否能容忍 metadata 缺失 | UE 侧不强制读 ForgeUE metadata(unreal.SoundFactory 自己解析 audio 文件 header);ForgeUE metadata 是 best-effort,P4 验证不依赖 metadata 完整性。SRS FR-STORE-004 要求字段存在但不要求 non-null(参考现有 image metadata 实装:width/height 有时也是 None) |
| audio_worker_timeout / audio_worker_unsupported FailureModeMap mode 漏掉某个 inner exception 类型(类比 Phase 1 R4-F1 R3-F1 的 wrapped exception 路由问题) | tasks.md 显式加 fence `test_failure_mode_map_audio_*` 覆盖所有 inner exc → wrapped → mode → Decision 映射,沿 Phase 1 round 4 R4-F1 sweep 模式 |
| L2 evidence 跑双终端时 ComfyUI 服务冷启 30-90s,首次模型权重下载额外加 ~5-10 分钟(Stable Audio Open 模型 HuggingFace 拉);用户体验差 | tasks.md L2 evidence 任务前置「冷启 + 首次模型下载」步骤,建议用户在 implementation 期间先手动跑一次 ComfyUI Stable Audio 让模型缓存好,再跑 ForgeUE smoke;evidence 文件记录两种状态(冷启 vs 复跑) |
| TBD-002 lift 论据是否被 codex review 接受(Phase 1 D3 用相同模式 split 出 audio + video follow-on,但本 change scope 同步 lift TBD-002 是新动作 — codex 可能要求 TBD-002 lift 单独走 ADR / proposal) | proposal.md 已显式说明 TBD-002 lift 论据(ComfyUI audio 是真实驱动力,ABC 不应被远端协议绑架);若 plan-stage codex review 要求拆分,可把「ABC + AudioCandidate + GenerateAudioExecutor」单独拆成 `audio-worker-baseline` change,本 change 等其归档后只接 ComfyUI capability。tasks.md 不预 commit split — 等 codex 实际 raise concern 再决策 |
| audio.t2a step type 注册可能与现有 step type 命名空间冲突(`image.generation` / `image.edit` / `mesh.generation` / `text.structured` / `text.review` / `select` / `validate` / `export`) | grep `step_type` 在 [workflows/loader.py](src/framework/workflows/loader.py) 检查命名空间,确认 `audio.t2a` 唯一;follow-on `audio.audio2audio`(remix)不在本 change scope |
| 失败模式 mode 名 `audio_worker_timeout` / `audio_worker_unsupported` 与 mesh 镜像但 audio 应该有自己的语义边界(audio 内容质量校验 vs mesh 几何校验 vs image 视觉校验) | 本 change 仅接 wrapper 层 mode(timeout / unsupported);content quality / format integrity 留 follow-on `audio-quality-validation` change 接(类比 Phase 1 mesh 的 magic bytes 校验是 follow-on 才加的) |
| examples/comfy_local_smoke_audio.json 落盘 FLAC 真实音频内容不可控(随机 prompt + seed 出来不一定好听) — L2 evidence 主观判断难 | L2 evidence 客观判定:(1) FLAC 文件存在 (2) 文件大小 > 100KB(避免 0-byte 假成功)(3) 文件 header 是 `fLaC` magic(4) duration 接近 bundle 声明的 `duration_seconds`(±10%)。**不**主观判断音频质量(留人工 spot-check) |
| **Stable Audio Open 1.0 license 商业边界**(F6 round-2 修订)— D11 默认选择的 manifest 用 Stable Audio Open 1.0 模型,license 是 [Stability AI Community License](https://stability.ai/license);[官方 research paper](https://stability.ai/news-updates/stable-audio-open-research-paper) 明确 commercial use up to $1M annual revenue;超过此门槛的企业需要 Stability Enterprise License。UE 生产链项目可预见交付 / 企业使用风险 | (1) `examples/comfy_local_smoke_audio.json` 文档段(README / sibling note)显式标注 license 限制 + 链接 Stability 官方 license 页;(2) `CLAUDE.md` ComfyUI section 加 license note,提示企业用户切 ACE-Step v1(更宽松 license)或自审 Stability 当前 license 边界;(3) 用户**可替换** manifest(bundle `comfy_workflow` 字段是 string,运行时切 `Audio_Workflows/audio_ace_step_1_t2a_instrumentals` 或自家 manifest 都可) — 不锁死 Stable Audio Open;(4) ForgeUE 框架本身不分发模型权重,license 边界由用户与上游模型作者直接对齐 |

## Migration Plan

**Backward compatibility**:本 change 是纯 additive — 不删除 / 不修改现有 image / mesh capability 行为,所有 audio 相关 entry 都是新建。Phase 1 锁定的 bundle 协议 `comfy_workflow` + `comfy_params` + `comfy_lifecycle` 三字段不动。

**Apply 顺序(对照 Phase 1 8-commit chain,见 tasks.md)**:

1. AudioWorker baseline(ABC + Candidate + 异常树 + FakeAudioWorker fixture)
2. ComfyAgentWorker 4-dict 扩 audio + `generate_audio` 方法
3. config/models.yaml + tests/fixtures/test_models.yaml + ModelRegistry test fence
4. GenerateAudioExecutor + workflow loader 注册 + `_should_use_comfy_worker_path` + `_generate_via_comfy_worker`
5. FailureModeMap audio_worker_* mode + from_exception
6. DryRunPass `_check_comfy_reachability` 扩 audio + `examples/comfy_local_smoke_audio.json` 新建
7. test_comfy_subprocess.py 扩 audio fence + test_generate_audio_comfy.py 新建 + test_audio_worker.py 新建 + test_workflow_loader.py 加 audio.t2a fence
8. Documentation Sync Gate(10 文档同步)+ probes/provider/probe_comfy_audio.py + L2 live smoke evidence

**Rollback 策略**:本 change 是 additive,rollback = git revert change branch;现有 image / mesh capability 不受影响,用户 bundle 不需要修改即可继续跑 image / mesh 路径。

**Forward compat hooks**:Phase 3 video capability follow-on change(`comfy-agent-cli-video-adoption`)沿用本 change 建立的 4-dict 扩展模式 + 新建 VideoWorker ABC(类比 AudioWorker ABC 但视频 specifics 不同 — 帧率 / codec / 容器格式);本 change 不预 commit video API。

## Open Questions

**OQ-1**(F4 round-2 RESOLVED):ComfyUI agent CLI 的 `outputs.audio` 实际字段名是 `outputs.audio`(string list)还是 `outputs.audio.[*]`(嵌套结构)?
- **决策影响**:`_validate_outputs` 三段表的 `_REQUIRED_OUTPUT_KEY["audio"] = "audio"` 是否正确
- **Resolution**(2026-05-03 cross-check round 1 probe):静态阅读 `D:/AI/ComfyUI/scripts/comfyui_api/runner.py::extract_outputs`(line 186-249)证实 — `outputs = {"images": [...], "audio": [...], "glb": [...], "raw": <full per-node-id dict>}`;`outputs.audio` 是 string list of **absolute paths**;`_REQUIRED_OUTPUT_KEY["audio"] = "audio"` 正确。详见 `notes/audio_subprocess_probe_20260503.md`。

**OQ-2**(F4 round-2 RESOLVED):`outputs.audio` list 长度通常 == 1(单 SaveAudioMP3 节点)还是 N(num_candidates 由 KSampler batch 控制)?
- **决策影响**:`generate_audio` 的 `num_candidates` 参数与 ComfyUI 实际产出 candidate 数的关系
- **Resolution**(2026-05-03 cross-check round 1 probe):两个 audio manifest(ACE-Step + Stable Audio)均为单 SaveAudioMP3 节点;单 subprocess run 通常产 1 file;`num_candidates > 1` 由 caller(`GenerateAudioExecutor._generate_via_comfy_worker`)多次 subprocess 实现,沿 Phase 1 mesh `_run_mesh_subprocess` per-candidate loop 模式。详见 `notes/audio_subprocess_probe_20260503.md`。

**OQ-3**(F4 round-2 RESOLVED with constraint):AudioCandidate.duration_seconds / sample_rate 的 source 是 ComfyUI agent CLI stdout JSON metadata 字段,还是需要 ForgeUE 自己解析 FLAC header?
- **决策影响**:tasks.md 是否新增 `audio_metadata_parser` helper
- **Resolution**(2026-05-03 cross-check round 1 probe):ComfyUI agent CLI `extract_outputs` **不暴露** audio metadata(仅 collect path strings,丢失 per-node metadata);`outputs.metadata.audio` JSON 路径**不存在**(round-1 design 写错)。本 change scope=`AudioCandidate.duration_seconds = None` + `sample_rate = None` 固定值;`Artifact.metadata.duration_seconds = None` 经 `repo.put` 落盘(per artifact-contract spec acceptance Scenario,UE `import_audio` 通过 `unreal.SoundFactory` 自己解析 audio header,不依赖 ForgeUE metadata 完整性)。Follow-on change `audio-metadata-parser` 引入 mutagen / stdlib `wave` 解析,本 change YAGNI。详见 `notes/audio_subprocess_probe_20260503.md`。

**OQ-4**:`audio_local` alias 和 `comfy/local-audio` virtual model id,是否要在 SRS FR-MODEL-007 alias 列表显式加(把 alias count 从 10 → 11)?
- **决策影响**:Documentation Sync Gate SRS 章节范围
- **resolve**:确定 yes,沿 Phase 1 mesh `mesh_local` alias 加到第 10 项的模式;tasks.md G7 显式更新 SRS FR-MODEL-007 alias count

**OQ-5**:`probes/provider/probe_comfy_audio.py` opt-in env var 命名(`FORGEUE_PROBE_COMFY_AUDIO=1`?)
- **决策影响**:probe 命名规范一致性(Phase 1 mesh probe 用 `FORGEUE_PROBE_MESH=1`)
- **resolve**:tasks.md G8 明确用 `FORGEUE_PROBE_COMFY_AUDIO=1`(更具体,与 mesh probe 区分);若用户偏好 `FORGEUE_PROBE_AUDIO=1`,debug 阶段调整

**OQ-6**:Phase 1 round 5 实测 ComfyUI subprocess CLI 走 `python -m comfyui_api run <manifest>` 命令,manifest 路径是相对 `FORGEUE_COMFY_SCRIPTS_DIR/scripts/comfyui_api/manifests/` 的 dotted path 还是绝对 / 相对路径?
- **决策影响**:bundle `comfy_workflow` 字段值的写法(`"Audio_Workflows/audio_stable_audio_example"` 还是 `"audio_workflows.audio_stable_audio_example"` 还是 `"D:/AI/ComfyUI/scripts/comfyui_api/manifests/Audio_Workflows/audio_stable_audio_example.json"`)
- **resolve**:对照 Phase 1 mesh bundle [examples/comfy_local_smoke_mesh.json](examples/comfy_local_smoke_mesh.json) 实测格式;Phase 1 用 `"GameAssets/03_mini_image_to_3d_hunyuan_loadimage"`(无 `.json` 后缀,POSIX path with `/`)— audio 沿用同格式
