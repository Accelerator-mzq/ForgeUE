"""A1 一键启动 — UE Python 内执行入口。

用法(任选其一):
  1. UE 编辑器 Tools / File 菜单 → Execute Python Script... → 选本文件
  2. UE Python Console / Output Log Python 模式:
       exec(open(r'D:\\ClaudeProject\\ForgeUE_claude\\ue_scripts\\a1_run.py').read())

会做:
  - 设 FORGEUE_RUN_FOLDER 指向 D:\\UnrealProjects\\ForgeUEDemo\\Content\\Generated\\a1_demo
  - 调用 run_import.py 完成 import_plan 的真实 UE asset import
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

RUN_FOLDER = os.environ.get(
    "FORGEUE_RUN_FOLDER",
    r"D:\UnrealProjects\ForgeUEDemo\Content\Generated\a1_demo",
)
SCRIPTS_DIR = str(Path(__file__).resolve().parent)

os.environ["FORGEUE_RUN_FOLDER"] = RUN_FOLDER
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

print(f"[A1] FORGEUE_RUN_FOLDER = {RUN_FOLDER}")
print(f"[A1] run folder exists  = {Path(RUN_FOLDER).is_dir()}")

import run_import  # noqa: E402

run_import.run()
print("[A1] run_import finished — check Content Browser + evidence.json")
