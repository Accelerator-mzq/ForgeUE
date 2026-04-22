# probes/ — 手工 smoke / 诊断脚本

本目录存放**手工触发**的冒烟与诊断脚本。它们不是运行时代码(不被 `src/framework/` 导入),也不是测试(不参与 `pytest` 收集),用于:

- 快速验证某个 provider 的 key / endpoint 是否打通
- 复现并定位线上 bug(如 "Hunyuan 3D 返回了什么格式?")
- 探测 provider 行为变化(如 GLM 水印参数是否生效)
- 框架级冒烟(registry 展开 / alias 路由是否对)

运行时代码与测试是对外契约,这里的脚本是内部工具。

---

## 目录结构与分类规则

```
probes/
├── smoke/          框架级通用冒烟(不依赖特定 provider)
│   ├── probe_aliases.py         alias → PreparedRoute 展开
│   ├── probe_chat.py            chat completion 通道
│   ├── probe_framework.py       registry + router + capability 三件套
│   └── probe_models.py          models.yaml 解析
│
└── provider/       provider 专属行为诊断(依赖具体 key / endpoint)
    ├── probe_glm_image_debug.py          GLM-Image 参数探测
    ├── probe_glm_watermark_param.py      GLM 水印开关
    ├── probe_glm_watermark_via_framework.py  GLM 水印(走 framework 路径)
    ├── probe_hunyuan_3d_format.py        Hunyuan 3D 返回格式 + URL 排序
    └── probe_packycode.py                PackyCode(Claude 中转)
```

## 新建 probe 放哪里?

决策树:

```
你的 probe 是否需要某家 provider 的 API key 或具体 endpoint?
├── 不需要(只用 mock / fake / 框架内部对象) → probes/smoke/
└── 需要 → probes/provider/
```

典型 smoke:
- 验证 `ModelRegistry.resolve("text_cheap")` 展开的 `PreparedRoute` 字段齐全
- 验证 `CapabilityRouter` 注册顺序对 `qwen/*` 前缀生效
- 验证 `load_task_bundle` 对某个 bundle 的展开结果

典型 provider:
- 验证 `DASHSCOPE_API_KEY` 可用,qwen-image-2 生成一张图并落盘
- 定位某家 provider 偶发 5xx 的真实响应 body
- 探测新接入 provider 的 submit/poll/download 三段是否如文档描述

---

## 命名约定

| 模式 | 用途 |
| --- | --- |
| `probe_<domain>.py` | smoke 类,domain 是框架概念(如 `aliases` / `models` / `framework`) |
| `probe_<provider>.py` | provider 类,单一 provider 整体冒烟(如 `probe_packycode`) |
| `probe_<provider>_<aspect>.py` | provider 类,针对该 provider 某个具体行为(如 `probe_glm_watermark_param`) |

反例:
- ❌ `test_*.py` — 测试用途,应放 `tests/`
- ❌ `my_debug.py` — 无 `probe_` 前缀,不易识别
- ❌ `probe_stuff.py` — 含糊,不知道在探什么

---

## 工程约定(必须遵守)

### 1. 模块顶层零副作用(lazy-init)

probe 模块被测试 `inspect.getsource(mod)` 静态审阅时需要 import 成功。顶层**不能**做:

```python
# ❌ 禁止
_OUT.mkdir(exist_ok=True)           # 触发文件系统写
hydrate_env()                        # 触发 .env 读
API_KEY = os.environ["ZHIPU_API_KEY"]  # 触发 KeyError
```

```python
# ✅ 正确
_OUT = Path("probes_output")

def _get_key() -> str:
    return os.environ["ZHIPU_API_KEY"]

def main() -> None:
    hydrate_env()
    _OUT.mkdir(exist_ok=True)
    key = _get_key()
    ...
```

这是 **L3 fence**:`tests/unit/test_probe_framework.py::test_glm_probes_have_no_import_side_effects` 守门。写 probe 时顶层做 I/O,测试会 raise。

### 2. ASCII 状态标记(Windows GBK 兼容)

Windows stdout 默认 GBK,emoji 会引发 `UnicodeEncodeError`:

```python
# ❌ 禁止
print("✅ OK")
print("❌ FAIL")

# ✅ 正确
print("[OK]   ...")
print("[FAIL] ...")
print("[SKIP] ...")
```

full probe 脚本可以在顶层 `sys.stdout.reconfigure(encoding="utf-8")` 后用 UTF-8,但 `[OK]` / `[FAIL]` / `[SKIP]` 的 ASCII 风格是我们项目默认,对齐 `CLAUDE.md` / `AGENTS.md` 约定。

### 3. Exit code 语义(三态)

```
exit 0   全部 OK(含 skip)
exit 1   有真实失败(不是 skip)
```

skip 不计入失败。样板见 `probes/smoke/probe_framework.py::_probe_route` 与 `main()`。

### 4. Opt-in 守护付费调用

对 mesh / 大图 / 付费调用,默认 skip,显式 opt-in 才跑:

```python
if os.environ.get("FORGEUE_PROBE_MESH", "").strip().lower() in {"1","true","yes","on"}:
    # 真调
else:
    return ("skip", "opt-in not set (FORGEUE_PROBE_MESH=1)")
```

避免 `.env` 里 `FORGEUE_PROBE_MESH=false` 被误判为开启。参考 `tests/unit/test_probe_framework.py::test_probe_route_mesh_skip_rejects_falsy_env_values`。

### 5. 输出路径(统一约定)

**所有 probe 产物**都必须走 `probes._output.probe_output_dir(tier, name)` helper,目录格式:

```
./demo_artifacts/<YYYY-MM-DD>/probes/<tier>/<name>/<HHMMSS>/<file>
```

- `<YYYY-MM-DD>`:运行当天的 ISO 日期,按字符串排序 = 时间排序
- `<tier>`:`smoke` 或 `provider`,对应本目录下的子目录
- `<name>`:probe 基名(去掉 `probe_` 前缀),如 `framework` / `glm_image_debug` / `hunyuan_3d_format`
- `<HHMMSS>`:本次 run 启动时间戳;同次 run 内所有产物聚在同一目录,不同 run 不覆盖

**正确用法**(lazy 单例缓存):

```python
_OUT_DIR_CACHE: Path | None = None

def _get_out_dir() -> Path:
    global _OUT_DIR_CACHE
    if _OUT_DIR_CACHE is None:
        from probes._output import probe_output_dir
        _OUT_DIR_CACHE = probe_output_dir("provider", "glm_image_debug")
    return _OUT_DIR_CACHE

def _trial(label: str, ...) -> None:
    out_dir = _get_out_dir()          # 首次调用才 mkdir
    out = out_dir / f"{label}.png"     # helper 已 mkdir,直接写
    out.write_bytes(data)
```

helper 已处理 `mkdir(parents=True, exist_ok=True)`,调用方**不要**再写 mkdir。

**禁用**:
- ❌ `/tmp/...`:Git-Bash 在 Windows 下翻译到 `C:\Users\...\AppData\Local\Temp`,脱离项目树
- ❌ 硬编码路径(如 `Path("./demo_artifacts/probe_debug")`):绕过命名约定,不同 probe 互相覆盖
- ❌ 在模块顶层调 `probe_output_dir(...)`:触发 mkdir I/O,违反 lazy-init fence

`./artifacts/` 和 `./demo_artifacts/` 都已在 `.gitignore`,产物不入仓。

---

## 运行方式

从项目根执行,用 dotted path:

```bash
# smoke
python -m probes.smoke.probe_framework
python -m probes.smoke.probe_aliases
python -m probes.smoke.probe_chat
python -m probes.smoke.probe_models

# provider(需要对应 key)
python -m probes.provider.probe_packycode
python -m probes.provider.probe_glm_image_debug
python -m probes.provider.probe_hunyuan_3d_format

# provider opt-in(额外 env guard)
FORGEUE_PROBE_HUNYUAN_3D=1 python -m probes.provider.probe_hunyuan_3d_submit   # 付费 submit+poll
FORGEUE_PROBE_HUNYUAN_3D=1 python -m probes.provider.probe_hunyuan_3d_query \
    --job-id <id>                                                              # 免费 /query(TBD-007)
FORGEUE_PROBE_VISUAL_REVIEW=1 python -m probes.provider.probe_visual_review    # 付费 review x2(TBD-008)
```

`probes/`、`probes/smoke/`、`probes/provider/` 都是 Python package(带 `__init__.py`),可以从 `tests/` 和 `src/framework/` 里通过标准 import 访问。

---

## 测试守门

| 测试 | 守护的契约 |
| --- | --- |
| `tests/unit/test_probe_framework.py::probe_mod` fixture | `probes.smoke.probe_framework` 可 import + lazy hydrate |
| `test_probe_route_skip_*` | `_probe_route` 三态返回契约 |
| `test_probe_hunyuan_3d_format_*` | 复用 runtime 的格式检测与 URL 排序 |
| `test_probe_magic_rejects_unknown_payload_as_unknown_not_glb` | magic bytes gate(probe 不得把 HTML 错误页误报为 GLB) |
| `test_glm_probes_have_no_import_side_effects` | 3 个 GLM probe 的 lazy-init fence |
| `test_probe_hunyuan_3d_format_no_import_side_effects` | Hunyuan 3D probe 的 lazy-init fence |
| `test_probe_aliases_skip_returns_none_status` | probe_aliases skip 语义 |
| `test_probe_route_mesh_skip_rejects_falsy_env_values` | opt-in 守护不接受 `false`/`0` |

新建 probe 若涉及类似的行为(lazy-init / 格式检测 / opt-in / 三态状态),应在 `test_probe_framework.py` 加对应守门测试。

---

## 不做的事

- ❌ 从 `src/framework/` 内 import probe(probe 是外部工具,不是 runtime 依赖)
- ❌ 在 probe 里写"业务逻辑"(该放到 `src/framework/`)
- ❌ 把 probe 伪装成 `test_*.py`(语义不同:probe 是诊断,test 是断言)
- ❌ pyproject.toml 的 `packages.find` 不包含 `probes*`(不随 wheel 发布)
