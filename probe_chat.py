"""Ad-hoc: try calling the proxy's /v1/messages with several candidate model ids.

用法：
    python probe_chat.py                   # 用内置的候选列表
    python probe_chat.py MiniMax-M2 abab6.5s-chat  # 加额外候选

成功的候选打印 '>>> OK <id>: ...'；失败的打印代理返回的错误 JSON。
LiteLLM 真正调用时用的 model 参数就是成功的那个 id（前面加 "anthropic/" 前缀
让 LiteLLM 走 Anthropic adapter）。
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

from framework.observability.secrets import hydrate_env


DEFAULT_CANDIDATES = [
    "MiniMax-M2",
    "MiniMax-M2.7",
    "minimax-m2",
    "abab6.5s-chat",
    "abab6.5-chat",
    "abab6.5g-chat",
    "claude-haiku-4-5-20251001",   # 标准 Anthropic id；若代理透传官方则这个会过
]


def try_model(url: str, headers: dict, model: str) -> tuple[int, str]:
    body = json.dumps({
        "model": model,
        "max_tokens": 16,
        "messages": [{"role": "user", "content": "reply with ONLY the word pong"}],
    }).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except Exception as e:
        return 0, f"<transport error: {e}>"


def main(argv: list[str]) -> int:
    hydrate_env()
    key = os.environ.get("ANTHROPIC_API_KEY")
    base = os.environ.get("ANTHROPIC_API_BASE")
    if not key or not base:
        print("ANTHROPIC_API_KEY or ANTHROPIC_API_BASE missing in .env")
        return 2
    url = f"{base.rstrip('/')}/v1/messages"

    candidates = DEFAULT_CANDIDATES + [a for a in argv[1:] if a]
    headers = {
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    for model in candidates:
        status, body = try_model(url, headers, model)
        if status == 200:
            print(f">>> OK {model}: {body[:500]}")
            print(f"\n→ YAML 里填: \"anthropic/{model}\"")
            return 0
        print(f"--- {status} {model}: {body[:200]}")
    print("\nAll candidates failed. Paste any non-transport error to me.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
