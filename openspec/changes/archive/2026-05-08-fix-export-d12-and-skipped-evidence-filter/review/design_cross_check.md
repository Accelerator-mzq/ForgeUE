---
change_id: fix-export-d12-and-skipped-evidence-filter
stage: S2
evidence_type: design_cross_check
contract_refs:
  - design.md
  - proposal.md
  - specs/ue-export-bridge/spec.md
aligned_with_contract: true
detected_env: claude-code
triggered_by: forgeue:change-plan
codex_plugin_available: true
autonomy_decision: claude_codex_concurred
codex_review_ref: review/codex_design_review.md
created_at: 2026-05-07T18:30:00Z
resolved_at: 2026-05-07T19:15:00Z
resolution_summary: round 1 4 finding(F1+F2+F3 high + F4 medium)全 accepted-codex;全部 inline writeback 修 design.md + specs/ue-export-bridge/spec.md(F1 _KIND_MAP-based importable / F2 非 video 保 raw filename / F3 domain_video file_path 从 source_uri 派生 / F4 derive_drop_target 签名加 target:UEOutputTarget);disputed_open=0
disputed_open: 0
runtime_enforcement_protocol_version: v1
skill_cascade_audit:
  invoked_skills:
    - superpowers:writing-plans
  cascade_check_pass_at: 2026-05-07T18:25:00Z
review_type: design_cross_check
review_round: 1
---

# Design Cross-Check — fix-export-d12-and-skipped-evidence-filter

## A. Decision Summary(Claude 立场冻结;在 codex 调用之前写好)

本 change scope:cluster 2 follow-on 单 change 修两个 pre-existing branch-work bug —— F-C(`src/framework/runtime/executors/export.py`)违 D12 video mp4 路径分流 + F-D(`ue_scripts/run_import.py`)skipped 过滤过宽。两 bug 通过 `evidence.json` + `manifest.json` 接口耦合 → 单 change 同 schema 演进(`Evidence.skip_reason` 字段)处理。

### A.1 9 个 D-decision 清单(design.md §Decisions)

| ID | Decision | Claude 立场 |
|---|---|---|
| **D1 / Filename** | framework 落 `Content/Movies/<run_id>/MS_<base>.mp4` 直接命名(选项 β);domain_video 删 copy | 单次 IO + filename 与 manifest entry 一致;选项 α 双 copy 不消除 / 选项 γ 违 NFR-PORT-003(`ue_scripts` 不 import framework)被拒;实施需 `_derive_ue_name` 提为 public helper |
| **D2 / Helper 位置** | `derive_drop_target` 加在 `manifest_builder.py`(选项 α);不新拆 `path_policy.py` | YAGNI:当前只 video 一种分流;`manifest_builder` 已 own `_KIND_MAP` + `_PREFIX_BY_KIND` + `_derive_ue_name`,顺势扩展;follow-on 触发 image_sequence / webm 时再拆模块 |
| **D3 / Schema** | `Evidence.skip_reason: Literal["permission_denied", "no_handler"] \| None = None`(选项 α) | Pydantic Literal 强制枚举值;default None 后向兼容;选项 β string / γ id-prefix / δ error-string-prefix 全被拒(均 brittle 或语义错位)|
| **D4 / 后向兼容** | F-D 仅识别 `skip_reason=="permission_denied"`,旧 evidence 字段缺失走 None 路径(选项 α)| Evidence per-run 一对一;不存在跨 run 重读场景;选项 β string fallback 是死代码 / 选项 γ migration tool 重得没必要 |
| **D5 / UE 端 no-handler** | UE 端写 no-handler skipped 也填 `skip_reason="no_handler"`(选项 α)| 协议完整性 + 双侧统一;`evidence_writer.make_record` 加 optional kwarg 成本极低 |
| **D6 / domain_video 简化幅度** | 删 `shutil.copy2` 同时删 `movies_dir.mkdir`(选项 α)| 单一职责:framework=path infra,UE=asset creation;选项 β"防御性"在 framework 端永远先跑场景下没价值 |
| **D7 / run_folder 概念** | 不拆 asset_folder/media_folder 双概念(选项 α);保单 `run_folder` 用于 manifest+plan+evidence | evidence/manifest/plan 仍单一位置 Generated/(`discover_bundle` 复用);"run_folder" 多处使用,改名风险高于收益 |
| **D8 / PermissionPolicy denied entry** | 不改 manifest 是否含 denied entry(选项 α);仍含 + UE 端 evidence pre-scan 跳过 | 不动既有契约;manifest=完整声明性 desired state,evidence=实际执行结果;denied entry 在 manifest 是有意义的 declarative record |
| **D9 / spec 修订范围** | 触发 `openspec/specs/ue-export-bridge/spec.md` L234-242 + L93 修订(已写入本 change `specs/ue-export-bridge/spec.md` delta)| MODIFIED 把 D12 责任从 UE 端 domain_video 前移到 framework export;ADDED 加 derive_drop_target / Evidence skip_reason / run_import filter 三 requirement |

### A.2 3 ADDED + 2 MODIFIED Requirements(specs/ue-export-bridge/spec.md delta)

**ADDED**:
1. **ExportExecutor drop loop applies D12 path split via `manifest_builder.derive_drop_target`**:framework 端落 video mp4 → `Content/Movies/<run_id>/MS_<base>.mp4`;build_manifest 同 helper 计算 source_uri;cross-module consistency fence
2. **Evidence schema includes `skip_reason` enum field**:`Literal["permission_denied", "no_handler"] | None = None`;framework PermissionPolicy denied 填 `permission_denied`;UE 端 no-handler 填 `no_handler`
3. **run_import.py filters only PermissionPolicy-denied skipped evidence**:`if status=="skipped" and skip_reason=="permission_denied"` 三 AND 过滤

**MODIFIED**:
4. **domain_video.import_video_entry assumes mp4 already at source_uri**(原 spec L234-242 改写):删 copy + 删 mkdir;若 mp4 missing 防御性返回 failed
5. **Permission tiers govern domain operations**(原 spec L91-107 增量):skipped Evidence 加 `skip_reason="permission_denied"` 字段(纯字段补强,不动 enum 边界)

### A.3 Risk + Mitigation(design.md §Risks 6 行)

| Risk | Claude Mitigation |
|---|---|
| `derive_drop_target` 双源不一致(framework drop 路径 ≠ manifest source_uri) | manifest_builder + export.py 共调同函数(单源);加 `test_manifest_entry_source_uri_matches_framework_drop_path` fence |
| Evidence schema 字段破坏旧 fixture Pydantic load | `skip_reason: ... \| None = None` default;Pydantic 兼容;旧 fixture 静默 load None |
| domain_video 删 copy 导致 P4 stub-unreal 测试覆盖度下降 | integration test 加 fence:framework drop 后 mp4 已在 Movies/(stub 测协议,真机走 commandlet);domain_video 仅校验 FileMediaSource asset API call |
| video L2 live smoke 回归(模型 ~3GB / 单次 7 分钟)| L2 在 P5 verify 阶段一次跑;若回归 fail-fast 到 design 重审 |
| image_sequence cinematic follow-on 触发时 D2 单文件方案需重构为 path_policy.py 模块 | follow-on 启动时再拆模块(YAGNI);本 change 不预设 |
| F-C / F-D 字段拼写不一致(skip_reason vs skipReason) | schema fence:Pydantic dump 字段名等于 `"skip_reason"`;run_import.py 字段名等同 |

### A.4 0 个 Open Question

design.md `## Open Questions` 段写"无"。所有 D-decision 均已选 + 评估;实施期出现任何契约层暴露走标准 writeback 协议(`drift_decision: written-back-to-design`)回写。

### A.5 期望 codex 重点审视的 Risk surface

- **D1 选项 β(framework 直接命名 MS_<base>.mp4)是否引入 ue_name 计算时机污染**:当前 `_derive_ue_name` 在 manifest_builder.py:177 私有调用,本 change 提为 public 跨模块用。若 codex 指出"ue_name 计算依赖 `target.asset_naming_policy` 而 export.py drop loop 不应该感知 naming policy"——Claude 立场:naming policy 已是 `target` 字段,export.py 已有 `target` 引用,跨模块共享 helper 不污染 — 倾向 accepted-claude 拒绝。但若 codex 揭示更深架构层 concern(如 path_policy 应该和 naming_policy 解耦),Claude 倾向 accepted-codex(转 disputed-pending 等用户裁决)。
- **D3 / D5 enum 设计**:当前仅 `permission_denied` + `no_handler` 两值。codex 可能建议加 `missing_entry`(L96-100 entries_by_id miss 当前用 `status="failed"`,但语义上算"skip but recoverable")或 `dependency_failed`。Claude 立场:本 change scope 严控只 cover 既有两条 follow-on 触及的 skip 类型;新枚举值留 future change(YAGNI)— 倾向 accepted-claude 拒绝(若 codex 仅是建议性)或 accepted-codex 调整(若 codex 揭示当前两值不能 cover 当前已存在的 skip 路径)。
- **D6 删 mkdir 是否有 race condition risk**:framework 端 drop loop `mkdir(parents=True, exist_ok=True)` + 后续 UE 端 import_video_entry 中间窗口期(几秒到几分钟,取决于 import_plan 大小)若 user 手工删 Movies/ 目录,domain_video 会 FileMediaSource create 报 error。Claude 立场:user 手删 framework 落地目录是异常路径,framework 端 fail-fast(`status="failed"`)即合规;不引入 UE 端冗余 mkdir 防御 — 倾向 accepted-claude 拒绝(若 codex 提议加回 mkdir defensive)。
- **D8 manifest 含 denied entry 的下游消费者影响**:codex 可能指出"manifest 含 denied entry 让下游 P4 commandlet 看到 entry 但 evidence 已 skipped,UI 展示矛盾"。Claude 立场:manifest 是 declarative desired state,evidence 是 actual execution state;UI / 审计层应同时读两份才能 reconcile;不动 manifest 语义 — 倾向 accepted-claude 拒绝。
- **derive_drop_target 对非 video importable modality 的 filename 计算可能与既有行为发生 silent change**:当前 `export.py:115` 用 `Path(art.payload_ref.file_path).name`(原 artifact filename);改为 `derive_drop_target` 后用 `<ue_name>.<ext>`(UE-naming filename)。这是非 video modality 的 filename change。Claude 立场:本意是单源契约 — manifest entry source_uri 与物理文件名一致是契约稳定要求;若 codex 揭示"既有 P4 真机 evidence 依赖原 filename 而非 ue_name"——Claude 倾向 accepted-codex 改为"非 video 仍用原 filename,仅 video 用 MS_<base>"(D1 缩 scope 到只 video filename rename)。这是本 change 风险最高的潜在 silent regression,优先 codex 审视。

### A.6 Cross-check Process(沿 design.md §3 Cross-check Protocol)

- **Round 1**:codex `/codex:adversarial-review --background` against design.md + spec delta(本段冻结后调用);findings 落 `review/codex_design_review.md`
- **Round 2**(若 round 1 disputed_open > 0):再迭代;但目标是单 round 收敛
- 评估:`disputed_open == 0` → S3 推进;> 0 → 升级 user 裁决(沿 Fence #3 review 冲突)

## B. Codex Findings 对照(round 1 已收 codex output 后填)

### B.1 Finding 总表(round 1)

| F# | Severity | Claim 摘要 | Spec / Design ref | Resolution |
|----|----------|------------|---|------------|
| F1 | high | `_KIND_MAP` miss 在新 design 下从 silent skip 变为 export crash(`_is_importable` 不看 shape,video.webm 通过)| spec L7-10 | **accepted-codex** → 加 `is_manifest_importable(art)` helper 收敛 _KIND_MAP 单一真源;`_is_importable` AND 该 helper;补 video.webm 不 crash 的 fence |
| F2 | high | 非 video modality filename 改用 ue_name 是超 NG1 范围 silent change + 双 artifact 同 display_name 时 shutil.copy2 静默覆盖 | spec L9-14 | **accepted-codex** → derive_drop_target 收窄:video 用 MS_<base>.mp4,**非 video 继续用 raw artifact basename**(`Path(payload_ref.file_path).name`)|
| F3 | high | 删 copy 后 domain_video 验证 source_uri 但 file_path 用 target_object_path 反推,二者偏离时 success 但 .uasset 引用错 mp4 | spec L103-108(MODIFIED)| **accepted-codex** → domain_video.file_path **从 source_uri 派生**(去 Content/ 前缀)+ 校验位于 Content/Movies/<run_id>/ 下;补 source_uri vs target_object_path mismatch fence(不一致 return failed)|
| F4 | medium | derive_drop_target API 签名缺 naming_policy 输入,_derive_ue_name 需要 policy,export 侧传不下来 | design L119-138 | **accepted-codex** → 签名加 `target: UEOutputTarget`;返回 `(drop_dir, target_filename)` 由内部用 `target.asset_naming_policy` 算 ue_name |

### B.2 Resolution 推理

**F1 + F2 是同一个根因**:`_is_importable` modality-only filter 与 `_KIND_MAP` shape-aware filter 不一致 — 当前(D12 修复前)依赖 manifest_builder silent skip 兜底,改为 derive_drop_target raise 后兜底崩塌。Fix 是把 _KIND_MAP 提升为 importable 真源(F1)+ filename 路径限定到 _KIND_MAP 命中的 video 子集(F2)。

**F3 是 latent 设计 smell 被 D6 删 copy 暴露**:旧 domain_video 逻辑 source 验证 / target 引用分两条路径,旧 copy 步骤(把 source 文件搬到 target 路径)隐式同步两者。删 copy 后必须用单一 path source-of-truth — codex 推荐 file_path 从 source_uri 派生比 target_object_path 反推更安全(source_uri 是已验证存在的真实物理路径;target_object_path 仅是 manifest 声明,可能 drift)。

**F4 是 D2 helper 签名设计 oversight**:design.md L119-138 写"复用 `_derive_ue_name(art, kind, policy)`"但签名只列 `(art, project_root, run_id)`。修复 trivial。

### B.3 Writeback Plan

修 design.md + specs/ue-export-bridge/spec.md(本 cross-check 之后立刻执行,非滞后):

- **D2**(design.md):helper 签名加 `target: UEOutputTarget`;返回 tuple `(drop_dir, target_filename)` 不变;内部用 `target.asset_naming_policy`
- **D1**(design.md):filename 协议改为"video → MS_<base>.mp4;**非 video → `Path(art.payload_ref.file_path).name` raw artifact basename**"
- **D6**(design.md):domain_video file_path 派生协议改为"从 entry["source_uri"] 派生(去 Content/ 前缀)+ 校验位于 Content/Movies/<run_id>/"
- **新 D-decision**(design.md):D10 — `is_manifest_importable(art) = _KIND_MAP.get((modality, shape)) is not None` 提为 manifest_builder public helper;`_is_importable` 收敛为 `payload.kind==file AND modality∈{...} AND is_manifest_importable(art)`;drop loop 自然只 process _KIND_MAP 命中 artifact
- **specs/ue-export-bridge/spec.md** 3 ADDED Requirements 改写:
  - "ExportExecutor drop loop applies D12 path split"段:helper 签名 + 非 video 用 raw basename + `is_manifest_importable` precondition
  - "Evidence schema includes skip_reason"段:不变(F1-F4 不影响)
  - "run_import.py filters only PermissionPolicy-denied skipped"段:不变
  - MODIFIED "domain_video.import_video_entry assumes mp4 already at source_uri":file_path 从 source_uri 派生(不再 target 反推)+ 加 source_uri vs target_object_path mismatch fence Scenario
- **新 fence test**(tasks.md 增条目):
  - `test_export_unsupported_shape_does_not_crash_drop_loop`(F1 video.webm 路径)
  - `test_derive_drop_target_preserves_raw_filename_for_non_video`(F2 image/audio/mesh raw basename 保持)
  - `test_domain_video_file_path_derived_from_source_uri`(F3 file_path 派生协议)
  - `test_domain_video_returns_failed_on_source_target_mismatch`(F3 mismatch fence)

## C. Resolution Status

- **disputed_open**: 0
- **All findings accepted-codex** + inline writeback 修 design.md + spec.md(本 cross-check 落地后立刻执行,作为 plan stage 一部分)
- **autonomy_decision**: `claude_codex_concurred`(沿 memory `feedback_autonomy_boundary_simplified` — codex review 拍板与 Claude 立场一致 + 无 framework 修改 / 不可逆 / 钱 / 安全 / 用户约束 fence;writeback design.md 是 plan stage 内正常协议,非"实施 vs design drift")
- **next**:进入 writeback execution(修 design.md + specs)→ 然后 Step 7 writing-plans 生成 execution_plan / micro_tasks → Step 8 writeback-check → Step 9 S3 推进

## D. Independent Verification(沿 ForgeUE memory `feedback_verify_external_reviews`)

| F# | 独立验证步骤 | 验证结论 |
|----|-------------|---|
| F1 | Read `src/framework/runtime/executors/export.py:212-220` `_is_importable` 实装;Read `src/framework/ue_bridge/manifest_builder.py:101-104` _KIND_MAP miss 静默 skip | ✅ 验证成立:`_is_importable` 仅 modality + payload.kind,不查 shape;manifest_builder L101-104 silent skip;新 design `derive_drop_target` raise ValueError 在 _KIND_MAP miss 时会 crash export drop loop。example trigger:`Artifact(modality="video", shape="webm", payload.kind=file)` 通过 `_is_importable` (T) → drop loop 调 derive_drop_target → ValueError → export 整步失败。 |
| F2 | Read `src/framework/runtime/executors/export.py:115` `target_fs = run_folder / Path(art.payload_ref.file_path).name`(raw basename);Read `src/framework/ue_bridge/manifest_builder.py:114` `source_uri = str(PurePosixPath(art.payload_ref.file_path))`(raw artifact path)| ✅ 验证成立:当前 export.py + manifest_builder 都用 raw artifact filename / path;改为 `<ue_name>.<ext>` 是 silent breaking change。collision 例:两个 image candidate metadata `display_name="tavern"` → `_derive_ue_name` 都返 `T_tavern.png` → shutil.copy2 后一个静默覆盖前一个。这是真实存在的 video bundle 路径(`comfy_local_smoke.json` 等 candidate_set 模式典型场景)。 |
| F3 | Read `ue_scripts/domain_video.py:42-95` 完整 import_video_entry;source_fs(L44 用 source_uri)vs target/run_id/ue_name(L49-51 从 target_object_path 反推)vs target_mp4(L56 target-derived 命名)vs file_path(L94 target-derived) | ✅ 验证成立:source 验证用 source_uri,引用路径全用 target_object_path 反推 — 旧 shutil.copy2 把 source 搬到 target-derived 路径,隐式同步;删 copy 暴露此 latent design smell。codex fix(file_path 从已验证 source_uri 派生)正确。 |
| F4 | Read `src/framework/ue_bridge/manifest_builder.py:177-179`(`_derive_ue_name(art, *, kind: str, policy: str)`)+ L111(`_derive_ue_name(art, kind=kind, policy=target.asset_naming_policy)`)| ✅ 验证成立:`_derive_ue_name` 必需 policy 参数;design.md D2 helper 签名 `(art, project_root, run_id)` 缺 policy;export.py drop loop 没法传出 policy。修复 trivial(签名加 `target: UEOutputTarget`)。 |

**4 finding 全部 codex 立场成立,与 Claude A.5 期望审视点高度命中(F1≈期望点 derive_drop_target 对非 video 可能 silent change;F2≈D1 选项 β 是否引入 ue_name 计算时机污染;F3 = 全新发现的 latent design smell — Claude A 阶段未识别)**。F3 是本轮 review 最大价值:Claude `## A.5` 仅在 D6 mkdir race 防御性问题上轻量提及"framework 端永远先跑场景下没价值",未深入"删 copy 后 source vs target 反推路径的解耦风险"。Codex catch 这点是 review 的非冗余增量。
