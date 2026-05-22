## Context

### 当前状态

**F-C(framework write 侧)**:`src/framework/runtime/executors/export.py`

```python
# L91 (current)
run_folder = Path(target.project_root) / "Content" / "Generated" / ctx.run.run_id
run_folder.mkdir(parents=True, exist_ok=True)

# L102-125 drop loop (current)
for art in importable:
    target_fs = run_folder / Path(art.payload_ref.file_path).name
    shutil.copy2(src_fs, target_fs)  # 所有 modality 都落 Generated/
```

`importable` 含 `image / mesh / audio / video / material`(L219 whitelist);video mp4 被一并落到 `Content/Generated/<run_id>/<original_name>.mp4`,违反 D12 协议(`comfy-agent-cli-video-adoption` Phase 3 D12:mp4 落 Movies/、`.uasset` 落 Generated/)。

**F-D(UE read 侧)**:`ue_scripts/run_import.py`

```python
# L67-70 (current)
with open(bundle.evidence_path, "r", encoding="utf-8") as _f:
    for _ev in _json.load(_f) or []:
        if _ev.get("status") == "skipped" and _ev.get("op_id"):
            pre_skipped_op_ids.add(_ev["op_id"])
```

裸 `status="skipped"` 过滤,但 L89-92 自身也写 `status="skipped"`(no UE-side handler);同 evidence.json 第二次读取时 self-collision。

**当前补救 — domain_video 二次 copy**:`ue_scripts/domain_video.import_video_entry`

```python
# L53-64 (current)
movies_dir = Path(project_root) / "Content" / "Movies" / run_id
movies_dir.mkdir(parents=True, exist_ok=True)
target_mp4 = movies_dir / f"{ue_name}.mp4"
shutil.copy2(str(source_fs), str(target_mp4))  # 第二次 copy
```

framework 落 `Content/Generated/<run_id>/<orig>.mp4`,UE 端再 copy 到 `Content/Movies/<run_id>/MS_<base>.mp4`。结果:
1. 双重 IO(video 单文件 ~5-15MB / A14B 模型 100MB+)
2. Generated/ 下 `<orig>.mp4` 是无主孤儿(`.uasset` 通过 Movies/ 下的 path 解析,Generated/ mp4 不被引用)
3. UE packaging 可能把 Generated/<orig>.mp4 误打包(取决于 packaging filter)

**协议层文档**:`openspec/specs/ue-export-bridge/spec.md` L234-242 当前明文写 "domain_video.import_video_entry copies mp4 to Content/Movies/<run_id>/" — 把 D12 责任放在 UE 端;本 change 把责任前移到 framework 端。

### Constraints

- `ue_scripts/` MUST NOT `import framework.*`(NFR-PORT-003);UE 端只 stdlib + `import unreal`。
- Evidence schema 演进必须向后兼容(`skip_reason: ... | None = None` 默认 None;Pydantic field default)。
- video manifest_only 路径已 ship + L2 evidence 落地(`live_smoke_video_*`);D12 路径分流要保 P4 真机 commandlet 不回归。
- `target_object_path`(UE asset path,`/Game/Generated/<run_id>/MS_<base>`)与 framework drop 物理路径(`Content/Movies/<run_id>/MS_<base>.mp4`)是**两条平行轨道** — `.uasset` 仍落 Generated/,asset path 不变;只是 mp4 source 物理位置变了。

### Stakeholders

- **Framework code 用户**:`framework.run` CLI / pytest integration test 调用 ExportExecutor — 行为透明改进(无 API 变化)。
- **UE 端 Python 编辑器用户**:`exec(open('ue_scripts/run_import.py').read())` — 行为透明改进(domain_video 删 copy 后 UE 端逻辑更短)。
- **L2 evidence(live smoke)运维**:video pipeline 单文件 IO 减半 + Generated/ 下不再留 video mp4 垃圾。

## Goals / Non-Goals

### Goals

- **G1**:Framework export 端按 D12 路径分流 video mp4 → `Content/Movies/<run_id>/MS_<base>.mp4`,其余 modality 仍 `Content/Generated/<run_id>/`。
- **G2**:Evidence schema 加 `skip_reason: Literal["permission_denied", "no_handler"] | None = None` 字段;F-C 在 PermissionPolicy denied 时填 `permission_denied`;F-D 自身 append no-handler skipped 时填 `no_handler`。
- **G3**:`run_import.py` L69 过滤改为 `if status=="skipped" and skip_reason=="permission_denied"`,UE 端自身写的 no-handler skipped 不被吞。
- **G4**:`domain_video.import_video_entry` 删除"二次 copy mp4"逻辑(framework 已落 Movies/),仅保留 FileMediaSource `.uasset` 创建 + `file_path` 设置。
- **G5**:加新 unit + integration fence 守门 + retire 两条 active follow-on entries(cancelled-completed)。

### Non-Goals

- **NG1**:不改其他 modality(image / mesh / audio / material)的 drop 路径 — 仅 video mp4 受 D12 影响。
- **NG2**:不引入更多 skip_reason 枚举值 —— 只 `permission_denied` + `no_handler` 两值;后续 follow-on 触发实际需求时再扩。
- **NG3**:不改 PermissionPolicy build 流程(manifest 仍含 denied entry,UE 端按 evidence pre-scan 过滤;原契约保持)。
- **NG4**:不引入 evidence schema migration tool(evidence.json 是 per-run artifact,不存在跨 run 兼容需求;旧 run_id 的 evidence 不会被新 run_import 重读)。
- **NG5**:不动 image_sequence cinematic 路径(留 follow-on `comfy-video-image-sequence-adoption`);不动 webm format(`comfy-video-webm-adoption`)。

## Decisions

### D1:Framework 端落地 mp4 时 video 用 `MS_<base>.mp4` 命名,**非 video modality 保持 raw artifact basename**(round 1 codex F2 修订)

**选项**:

| 选项 | 描述 | 双 copy? | filename 一致性 | NG1 兼容? |
|---|---|---|---|---|
| α | framework 落 `Content/Movies/<run_id>/<orig>.mp4`,domain_video 仍 copy 到 `MS_<base>.mp4` | ❌ 不消除 | 不一致(framework `<orig>` ≠ UE `MS_<base>`)| ✅ |
| β(round 1 codex F2 reject)| framework 落 `Content/Movies/<run_id>/MS_<base>.mp4` + **所有 modality** 改用 `<ue_name>.<ext>`(包括 image/audio/mesh/material)| ✅ 单次 IO | 一致 | ❌ 违 NG1 + 同 display_name 双 artifact 时 `shutil.copy2` 静默覆盖 |
| **β'(选;round 1 codex F2 accepted-codex 修订)** | video → `Content/Movies/<run_id>/MS_<base>.mp4`(用 `_derive_ue_name`);**非 video modality(image/audio/mesh/material)继续用 `Path(art.payload_ref.file_path).name` raw artifact basename**;domain_video 删 copy | ✅ video 单次 IO | video 一致;非 video 与今天行为完全相同 | ✅ NG1 保持 |
| γ | framework 不 drop video,domain_video 跨 framework 边界读 `art.payload_ref.file_path` 直接 copy | n/a | 一致(原 framework path)| ✅ 但违 NFR-PORT-003 |

**决定**:**β'**(round 1 codex F2 修订)

**理由**:
- 单次 IO(video 文件 ~5-15MB,A14B 模型 100MB+,双 copy 浪费可观)。
- video 文件名一致性 — manifest entry `source_uri = "Content/Movies/<run_id>/MS_<base>.mp4"` 与物理文件名匹配,UE 端 `FileMediaSource.file_path = "Movies/<run_id>/MS_<base>.mp4"` 完整对齐。
- **非 video 保 raw filename**:今天 `export.py:115` 是 `Path(art.payload_ref.file_path).name`,`manifest_builder.py:114` source_uri 也用 raw artifact path;改为 `<ue_name>.<ext>` 会:
  - 违 NG1(本 change 不改其他 modality drop 路径 / 行为)
  - 引入 silent collision 风险:两个同 `display_name` 的 artifact(典型 candidate_set 模式如 `comfy_local_smoke.json` 多 candidate)→ `_derive_ue_name` 都返同 `T_tavern.png` → `shutil.copy2` 后一个静默覆盖前一个
- γ 违 NFR-PORT-003(`ue_scripts/` 不 import framework);也违 ForgeUE 单一职责(framework = path infra,UE = asset creation)。
- 实施成本:`_derive_ue_name` 已在 `manifest_builder.py:177` 实装,`export.py` drop loop 调 helper 拿到 video 的 `MS_<base>.mp4`;非 video 直接拿 raw basename(零新逻辑)。

**Trade-off**:filename 协议在 video / 非 video 之间不对称(video 用 ue_name,非 video 用 raw)。这是有意为之的 minimum-change 修复,不引入跨 modality 的 silent breaking change。后续若有需求统一所有 modality 的 UE 命名,走独立 follow-on 走整改(需先解决同 display_name collision)。

### D2:Drop target 计算逻辑放在 `manifest_builder` 模块还是 `export.py` 内 helper?

**选项**:

| 选项 | 位置 | 理由 |
|---|---|---|
| α | `manifest_builder.py` 加 public `derive_drop_target(art, project_root, run_id) -> tuple[Path, str]` | manifest_builder 已 own `_KIND_MAP` + `_PREFIX_BY_KIND` + `_derive_ue_name`,逻辑集中 |
| **β(选)** | 新增 `framework/ue_bridge/path_policy.py` module,提供 `derive_drop_target(...)` + 引用 manifest_builder helper | 与 `permission_policy.py` 同款单一职责模块,后续扩 image_sequence / webm 路径分流时易扩展 |
| γ | `export.py` 内私有 helper `_drop_target_dir(art, project_root, run_id)` | 简洁,但 manifest_builder 与 export.py 共享 derive_ue_name 时仍需跨模块 import |

**决定**:**α**(放 manifest_builder.py;不新增模块,YAGNI)

**理由**:
- `manifest_builder` 已 own naming/path policy 数据(`_KIND_MAP` / `_PREFIX_BY_KIND` / `_derive_ue_name`);加 `derive_drop_target` 顺势扩展。
- β 拆模块过早 — 当前只 video 一种分流,YAGNI 拒绝预设 image_sequence / webm 的不存在需求。当 follow-on 实际触发时再拆模块。
- γ 在 export.py 内私有 helper 会重复 _PREFIX_BY_KIND 逻辑(coupling);拒绝。

**API**(round 1 codex F4 + F1 修订;签名加 `target: UEOutputTarget` + 非 video 保 raw filename + _KIND_MAP miss 不 raise):
```python
# manifest_builder.py (new public helper)
def derive_drop_target(
    art: Artifact, *, target: UEOutputTarget, run_id: str,
) -> tuple[Path, str]:
    """返回 (drop_dir, target_filename) — D12 路径分流 + UE naming(video only).

    Precondition:caller MUST 先用 `is_manifest_importable(art)` filter(沿 D10);
    若调用者未 precondition filter,_KIND_MAP miss 时 fall through 到非 video 分支
    返回 `(Generated/<run_id>, raw_basename)` — 不 raise。

    - video mp4 → (project_root/Content/Movies/<run_id>, MS_<base>.mp4)
        其中 MS_<base> = `_derive_ue_name(art, kind="file_media_source", policy=target.asset_naming_policy)`
    - 其他 importable modality(image/audio/mesh/material)→ (project_root/Content/Generated/<run_id>, raw_basename)
        其中 raw_basename = `Path(art.payload_ref.file_path).name`(沿 NG1 保 raw filename)
    """
```

`export.py` drop loop 调用(round 1 codex F1 修订;`is_manifest_importable` 兜底防 _KIND_MAP miss):
```python
importable = [a for a in upstream_artifacts if self._is_importable(a)]
# 注:`_is_importable` 沿 D10 收敛 _KIND_MAP 单一真源:
#   payload.kind==file AND modality∈{...} AND is_manifest_importable(art)
# unsupported shape(如 video.webm)被 silent skip — 与 manifest_builder
# silent skip 行为对齐,不在 drop loop 阶段 crash(round 1 codex F1)
for art in importable:
    drop_dir, target_filename = derive_drop_target(
        art, target=ctx.task.ue_target, run_id=ctx.run.run_id,
    )
    drop_dir.mkdir(parents=True, exist_ok=True)
    target_fs = drop_dir / target_filename
    shutil.copy2(src_fs, target_fs)
```

### D3:Evidence schema `skip_reason` 字段形态

**选项**:

| 选项 | 形态 | types-aware | 后向兼容 |
|---|---|---|---|
| **α(选)** | `skip_reason: Literal["permission_denied", "no_handler"] \| None = None` | ✅ Pydantic Literal | ✅ default None |
| β | `skip_reason: str \| None = None`(自由 string)| ❌ 任意 string | ✅ default None |
| γ | `error.startswith("PermissionPolicy:")` string prefix(无 schema 改)| ❌ 字符串约定 | ✅ 但 brittle |
| δ | `evidence_item_id` 前缀 `ev_perm_<...>` | ❌ ID 不应携带语义 | ✅ |

**决定**:**α**(已在 brainstorming Q1 确认)

**理由**:
- Pydantic `Literal` 强制枚举值,IDE / mypy 可静态检查。
- 后向兼容 — 旧 evidence.json 字段缺失,Pydantic load 时取 None;F-D filter 仅在 `skip_reason == "permission_denied"` 时过滤,旧 evidence(无字段)不被 F-D 过滤(等同 N/A)。
- 扩 enum 易 — 后续 follow-on 加新 skip 子类只改 Literal type,F-D filter 显式判断不会"误吞"未知值。

### D4:F-D 旧 evidence.json(无 skip_reason 字段)如何处理?

**选项**:

| 选项 | F-D 行为 | 影响 |
|---|---|---|
| **α(选)** | 仅识别 `skip_reason == "permission_denied"`,旧 evidence(字段 None)不过滤 | 新 run 完全干净;旧 run 不存在 cross-run 重读场景(evidence 与 run_id 一对一) |
| β | 同时支持 `skip_reason==permission_denied` 和 `error.startswith("PermissionPolicy:")` 字符串 fallback | 守旧 — 但本 change 同时改 F-C,新 evidence 一定有 skip_reason,fallback 永不触发,YAGNI |
| γ | schema migration tool 一次性升级旧 evidence | 重 — 旧 evidence 不会被新 run_import 重读,无升级必要 |

**决定**:**α**

**理由**:
- Evidence 是 per-run artifact,与 `run_id` 一对一;run_import 永远在同 run 的 evidence.json 上工作,不存在跨 run 重读场景。
- 旧 evidence(本 change 之前生成的)永远不会被新 run_import 读取(已 archive 的 run 不会重跑)。
- β 的 `error.startswith("PermissionPolicy:")` 是死代码(本 change 同时改写 F-C,新 evidence 一定带 skip_reason)。
- γ 重得没必要。

### D5:UE 端 no-handler skipped 是否也用 `skip_reason` 字段?

**选项**:

| 选项 | UE 端 `make_record(status="skipped", error="no UE-side handler...")` 是否填 skip_reason? |
|---|---|
| **α(选)** | 是 — `skip_reason="no_handler"`,`evidence_writer.make_record` 加可选 `skip_reason` 参数 |
| β | 否 — 仅 framework 端 PermissionPolicy denied 填;UE 端 skipped 字段为 None |

**决定**:**α**

**理由**:
- 协议完整性 — 双侧统一,F-C 写 `permission_denied`,F-D 写 `no_handler`,任意一方读时都能区分。
- 实施成本极低(`evidence_writer.make_record` 加一个 optional kwarg)。
- 未来若再加 skipped 子类(missing_entry 等),协议位置已就位。

### D6:domain_video.import_video_entry 简化幅度 + file_path 派生协议(round 1 codex F3 修订)

**选项**(简化幅度):

| 选项 | 改动 |
|---|---|
| **α(选)** | 删 `shutil.copy2` + 删 `movies_dir.mkdir`(framework 已建);仅保留 FileMediaSource asset 创建 + `file_path` 设置 |
| β | 删 `shutil.copy2`,保留 `mkdir(exist_ok=True)` 防御性 |

**决定**:**α**

**理由**:
- framework 端已 `drop_dir.mkdir(parents=True, exist_ok=True)`,UE 端 mkdir 是冗余防御。
- α 保持单一职责清晰:framework = path/IO infra,UE = asset creation;两侧契约对齐。
- β 的"防御性"在 framework 永远先跑的情况下没有实际价值(若 framework drop 都失败,evidence 已 status=failed,domain_video 不会被调用)。

**round 1 codex F3 揭示的 latent 设计 smell + 修订**:

旧 `domain_video.import_video_entry` 用两条独立路径:
- `source_fs` 验证(L44):用 `entry["source_uri"]` 解析
- `target_mp4` copy 目标(L49-51, L56)+ `relative_file_path` for FileMediaSource(L94):**用 `entry["target_object_path"]` 反推 run_id / ue_name**

旧 `shutil.copy2(source_fs, target_mp4)` 把 source 文件搬到 target-derived 路径,**隐式同步**两条路径(若 source_uri 与 target 不一致,copy 会 fail 或产物错位但写出真实文件)。

D6 删 copy 后:**source_uri 与 target_object_path 反推路径若 mismatch,`source_fs.is_file()` 验证 source 通过,但 FileMediaSource.file_path 设 target-derived 路径(无对应物理文件)→ `import_video_entry` 返 success 但 .uasset 引用缺失 movie**。

**file_path 派生协议修订**(选项 α'):

| 协议 | 描述 |
|---|---|
| 旧(隐式) | source 验证用 source_uri;file_path 用 target_object_path 反推;copy 同步 |
| 新(显式;选)| **file_path 从 source_uri 派生**(去 Content/ 前缀);+ 校验 derived path 位于 `Content/Movies/<run_id>/` 下;+ source_uri 反推 run_id/ue_name 与 target_object_path 反推一致(mismatch return failed)|

新协议下 `import_video_entry`:
1. `source_fs = Path(project_root) / entry["source_uri"]`
2. 若 `not source_fs.is_file()` → return failed("source mp4 not found...")
3. **从 source_uri 派生 file_path**:
   - `relative_to_content = entry["source_uri"]` 去 `Content/` 前缀(若 source_uri 不以 `Content/` 起首 → return failed)
   - 校验 `relative_to_content.startswith("Movies/")` + path part count == 3(`Movies/<run_id>/<ue_name>.mp4`)→ 否则 return failed
   - `relative_file_path = relative_to_content`(直接用,如 `"Movies/<run_id>/MS_<base>.mp4"`)
4. **mismatch fence**:从 source_uri 派生的 `(run_id, ue_name)` 与 target_object_path 反推的 `(run_id, ue_name)` 必须相等;不等 return failed("source_uri / target_object_path mismatch...")
5. `unreal.AssetToolsHelpers...create_asset(...)` + `set_editor_property("file_path", relative_file_path)` 沿用

新协议保 D6 删 copy 单一职责优势 + 消除 latent design smell + 加一道 mismatch fence 守门。

### D7:`run_folder` 概念是否拆分

**选项**:

| 选项 | 描述 |
|---|---|
| **α(选)** | 保持单 `run_folder` 概念(沿用 `Content/Generated/<run_id>/`)用于 manifest.json + import_plan.json + evidence.json;drop 时按 modality 分流到 asset_folder(=run_folder)或 media_folder |
| β | 拆 `asset_folder`(Generated/)+ `media_folder`(Movies/)双概念,manifest.json 等仍在 asset_folder |

**决定**:**α**

**理由**:
- evidence.json + manifest.json + import_plan.json 是 control-plane,单一位置(Generated/)便于 UE 端 `discover_bundle` 定位。
- "run_folder" 概念在 metrics 字段(L202)+ evidence_writer path(L93)+ rebase logic(L134)多处使用;改名重命名风险高于收益。
- β 显式拆双 folder 概念过于抽象 —— 当前只 video 一种分流,YAGNI。

### D8:PermissionPolicy denied entry 是否从 manifest 排除

**选项**:

| 选项 | 描述 |
|---|---|
| **α(选)** | 保持现状 — manifest 仍含 denied entry,evidence 写 skipped,UE 端 pre-scan evidence 跳过 |
| β | 从 manifest 排除 denied entry,UE 端不需 evidence pre-scan |

**决定**:**α**

**理由**:
- 不改既有契约 — manifest = 完整声明性 desired state,evidence = 实际执行结果;denied entry 在 manifest 里是有意义的 declarative record(UE 可视化 / 审计需求时仍能看到 denied entry)。
- β 改 manifest 内容会影响下游消费者(P4 真机 commandlet / docs / acceptance test),scope 蔓延风险高。
- 本 change 只补 schema 缺失,不改 manifest 语义。

### D10:`_is_importable` 收敛到 `_KIND_MAP` 单一真源(round 1 codex F1 新增 decision)

**问题**:当前 `ExportExecutor._is_importable`(`src/framework/runtime/executors/export.py:212-220`)仅看 `payload_ref.kind == file` + `modality ∈ {image, mesh, audio, video, material}`,**不看 shape**。`manifest_builder.build_manifest`(`src/framework/ue_bridge/manifest_builder.py:101-104`)对 `_KIND_MAP.get((modality, shape))` miss 是静默 skip(no manifest entry)。

**当前行为**(本 change pre-fix):video.webm 通过 `_is_importable`(modality=video, payload=file)→ `ExportExecutor` drop loop copy webm 到 `Generated/<run_id>/<orig>.webm`(orphan 文件)→ `manifest_builder.build_manifest` silent skip(no manifest entry)→ UE 端不 import,evidence 无记录。**不 crash 但留 orphan**。

**本 change pre-codex β 设计行为**:`derive_drop_target` 在 `_KIND_MAP` miss 时 raise ValueError → `ExportExecutor.execute` 整个 step 失败 → `Run` halts。这是 silent change(unsupported shape 从 silent skip 变 hard fail)。

**选项**:

| 选项 | 描述 | 行为 |
|---|---|---|
| α(本 change pre-codex) | derive_drop_target raise ValueError;依赖 `_is_importable` filter precondition | unsupported shape → ValueError → export crash |
| **β(选;round 1 codex F1 修订)** | `is_manifest_importable(art) = _KIND_MAP.get((modality, shape)) is not None` 提为 manifest_builder public helper;`_is_importable` 收敛 AND 该 helper;derive_drop_target 在 _KIND_MAP miss 时 fall through 到非 video 分支返 raw basename(不 raise)| unsupported shape(如 video.webm)→ `_is_importable` 返 False(因 _KIND_MAP miss)→ silent skip(对齐 manifest_builder 行为)→ 不 crash |
| γ | derive_drop_target raise ValueError + 加 try/except in drop loop catch + log warning | 复杂;skip 的 artifact 在哪 log / 是否记录 evidence 都需要扩 design |

**决定**:**β**

**理由**:
- 与 manifest_builder 现有 silent skip 行为对齐 — `_KIND_MAP` 是 import 能力的单一真源,_is_importable 收敛到它消除"modality whitelist + shape map miss"双源。
- 不引入 export crash 行为变更(unsupported shape 在今天不 crash;新 design 不应该改这个)。
- `is_manifest_importable` 提为 public helper(不只私有给 build_manifest)— manifest_builder + export.py 共用;`_is_importable` 直接 import 该 helper,避免双源。
- video.webm 触发场景:`comfy-video-webm-adoption` follow-on 触发后会扩 `_KIND_MAP[("video","webm")] = "file_media_source"`,届时通过 `is_manifest_importable` → 自动进 import 路径;在 follow-on 启动前,video.webm artifact 静默 skip 是合理 baseline 行为(沿 image/audio/mesh 同模式)。

**API**:
```python
# manifest_builder.py (new public helper)
def is_manifest_importable(art: Artifact) -> bool:
    """art 是否在 _KIND_MAP 命中 — manifest 能力的单一真源.

    Used by `ExportExecutor._is_importable` AND `manifest_builder.build_manifest`
    to keep import filtering consistent across modules.
    """
    if art.payload_ref.kind != PayloadKind.file:
        return False
    return _KIND_MAP.get((art.artifact_type.modality, art.artifact_type.shape)) is not None
```

`export.py::_is_importable`:
```python
@staticmethod
def _is_importable(art: Artifact) -> bool:
    # round 1 codex F1 修订:收敛到 _KIND_MAP 单一真源(沿 D10);
    # 旧的 modality-only whitelist 与 manifest_builder shape-aware filter 不一致,
    # 导致 unsupported shape(如 video.webm)在新 derive_drop_target 路径下 crash export
    return is_manifest_importable(art)
```

**Trade-off**:`_is_importable` 与 `is_manifest_importable` 看起来重复(只是不同位置),但保留 `_is_importable` 作为 ExportExecutor 局部 hook 是为后续可能的 export-only filter 留扩展点(目前实装只是 thin wrapper)。

### D9:本 change 是否触发 ue-export-bridge spec L234-242 修订

**当前 spec(`openspec/specs/ue-export-bridge/spec.md` L234-242)**:
> domain_video.import_video_entry copies mp4 to `<project_root>/Content/Movies/<run_id>/<MS_<base>>.mp4`

**修订为**:
> ExportExecutor drop loop drops video mp4 to `<project_root>/Content/Movies/<run_id>/MS_<base>.mp4`(via `derive_drop_target` D12 路径分流);domain_video.import_video_entry assumes mp4 already exists at `entry["source_uri"]` location and only creates FileMediaSource `.uasset` + sets `file_path` editor property.

**Spec delta location**:本 change 走 OpenSpec `specs/ue-export-bridge/spec.md` delta;archive 后 sync 进 main spec。

## Risks / Trade-offs

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `derive_drop_target` 提前计算 ue_name 与 manifest_builder 不一致(双源) | Low | High(manifest entry source_uri 与物理文件不匹配 → UE 端 file_path 解析失败) | manifest_builder 内部也调 `derive_drop_target` 同函数(单一 source of truth);加 fence test 校验"manifest entry source_uri 等于 framework 实际 drop 路径(相对 project_root)" |
| Evidence schema field 改动破坏 Pydantic strict load(旧 fixture / 旧 frozen evidence)| Low | Medium | `skip_reason: ... \| None = None` default,Pydantic 兼容;旧 fixture 静默 load 为 None;新 fence 仅校验 *新* fixture 含字段 |
| domain_video 删 copy 后 UE-side test stub 不再触发 mp4 IO,P4 stub-unreal 测试覆盖度下降 | Low | Low | `tests/integration/test_p4_ue_manifest_only.py` 加 fence:framework drop 后 mp4 已存在 `Content/Movies/<run_id>/`(stub-unreal 测试只测协议,实际 UE 真机走 P4 commandlet);domain_video 仅校验 FileMediaSource creation API call |
| video L2 live smoke 回归(模型 ~3GB,单次 7 分钟)| Medium | Medium | L2 evidence 在 P5 verification 阶段一次跑(`examples/comfy_local_smoke_video.json`);若回归,fail-fast 到 design 重审 |
| `image_sequence cinematic` follow-on 触发时,本 change 的 D2 选 manifest_builder.py 单文件方案需要重构为 path_policy.py 模块 | Low | Low | 当 `comfy-video-image-sequence-adoption` follow-on 启动时再拆模块,本 change 不预设 |
| F-C / F-D 接口字段拼写不一致(`skip_reason` vs `skipReason` vs `skipped_reason`)| Very low | High(F-D filter 永远 false) | 加 schema fence test:Evidence pydantic dump 字段名等于 `"skip_reason"`;run_import.py 取字段 string 等于同 |
| **(round 1 codex F1)** unsupported shape(如 video.webm)在新 derive_drop_target 路径 crash export | High(本 change pre-codex 设计下必触)| High(整个 step 失败,无 graceful skip)| **D10 收敛 _is_importable 到 _KIND_MAP**;加 fence `test_export_unsupported_shape_does_not_crash_drop_loop` |
| **(round 1 codex F2)** 非 video modality filename 改为 ue_name 引入 NG1 超范围 silent change + 同 display_name collision | High(candidate_set 模式典型)| High(silent overwrite 后一个 artifact)| **D1 修订非 video 保 raw basename**;加 fence `test_derive_drop_target_preserves_raw_filename_for_non_video` |
| **(round 1 codex F3)** 删 copy 后 source_uri / target_object_path 反推 path mismatch 时 .uasset 引用错 mp4 | Low(framework 内部一致是 build_manifest 强制;手工编辑 evidence / manifest 才触发)| Medium(success but 引用错文件)| **D6 修订:file_path 从 source_uri 派生 + mismatch fence return failed**;加 fence `test_domain_video_returns_failed_on_source_target_mismatch` + `test_domain_video_file_path_derived_from_source_uri` |

## Migration Plan

本 change 内部实施(non-breaking;不需要外部 migration step):

1. **Phase A(F-C 框架侧 schema + drop)**:
   - 加 `Evidence.skip_reason` field
   - 加 `manifest_builder.derive_drop_target` public helper
   - 改 `ExportExecutor.execute` drop loop + `denied_evidence` Evidence emit 带 `skip_reason="permission_denied"`
   - fence:`tests/unit/test_export_video_path_split.py` + `tests/unit/test_evidence_skip_reason.py`

2. **Phase B(F-D UE 侧 filter + simplify)**:
   - `evidence_writer.make_record` 加 `skip_reason` 可选 kwarg
   - `run_import.py` L69 改 filter + L89-92 写 no-handler skipped 时带 `skip_reason="no_handler"`
   - `domain_video.import_video_entry` 删 copy + 删 mkdir
   - fence:`tests/unit/test_run_import_skipped_filter.py`(stub-unreal)+ `tests/unit/test_domain_video_no_copy.py`

3. **Phase C(integration + L2)**:
   - `tests/integration/test_p4_ue_manifest_only.py` 加 D12 路径分流校验(framework drop 后 mp4 in Movies/)
   - L2 evidence 跑一次 `examples/comfy_local_smoke_video.json` 实证(P5 verification)
   - P4 真机 commandlet 实证(由用户在装 UE 5.x 机器手跑)

4. **Phase D(spec + doc sync)**:
   - `openspec/changes/<id>/specs/ue-export-bridge/spec.md` delta(L234-242 修订 + Evidence requirement 加 skip_reason + run_import filter requirement)
   - `docs/design/LLD.md` Evidence schema 段
   - `CHANGELOG.md`
   - active.md 两条 follow-on 迁 archived.md(`cancelled-completed: <commit-ref>`)

**Rollback**:
- Pure code 改动,git revert 即可。
- 旧 evidence.json 不受影响(F-D 字段缺失走 None 路径,等同未改之前行为)。
- Spec delta 一并 revert(归档前的 sync 才会污染 main spec)。

## Reasoning Notes

### Round Summary

| Round | Trigger | Findings | Disposition |
|---|---|---|---|
| 1 | `/forgeue:change-plan` codex `/codex:adversarial-review` design hook | 4(F1+F2+F3 high + F4 medium)| 全 accepted-codex inline writeback;详 `review/design_cross_check.md ## B/C/D`(disputed_open=0);本文件 D1 / D2 / D6 修订 + 新增 D10;Risks 段加 3 行 codex-derived risk;Migration Plan 加 unsupported shape / non-video filename / source-target mismatch 3 类 fence 到 Phase A/B |

## Open Questions

无。所有 D-decision 均已选 + 评估(D1-D10,共 10 项;round 1 codex review 后新增 D10);实施期出现任何契约层暴露(drift)走标准 writeback 协议(`drift_decision: written-back-to-design`)回写本文件。
