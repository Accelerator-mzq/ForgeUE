"""Ad-hoc: 探测 PackyCode 的协议风格 + 支持的模型 id。

跑：python probe_packycode.py

读 .env 里的 PACKYCODE_KEY，逐一尝试常见的 base URL + 端点 + 鉴权头组合：
- Anthropic-兼容：  POST /v1/messages          headers: x-api-key + anthropic-version
- OpenAI-兼容：    POST /v1/chat/completions  headers: Authorization: Bearer

同时轮几个候选 model id。哪条组合回 200 即是 PackyCode 支持的路径。
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

from framework.observability.secrets import hydrate_env


BASES = [
    "https://www.packyapi.com",
    "https://www.packyapi.com/v1",
    "https://api.packycode.com",
    "https://api.packycode.com/v1",
    "https://share.packycode.com",
    "https://share.packycode.com/v1",
]

MODELS = [
    "claude-opus-4-6",
    "claude-opus-4-7",
    "claude-opus-4-7-20251001",
    "claude-sonnet-4-6",
    "claude-haiku-4-5",
    "claude-haiku-4-5-20251001",
    "anthropic/claude-opus-4-6",
    "gpt-4o-mini",
    "gpt-5",
]

USER_MSG = [{"role": "user", "content": "reply with ONLY the word pong"}]


_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")


def probe_anthropic(base: str, key: str, model: str) -> tuple[int, str]:
    url = f"{base.rstrip('/')}/v1/messages"
    body = json.dumps({"model": model, "max_tokens": 16, "messages": USER_MSG}).encode()
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json", "User-Agent": _UA},
    )
    return _do(req)


def probe_openai(base: str, key: str, model: str) -> tuple[int, str]:
    url = f"{base.rstrip('/')}/v1/chat/completions"
    body = json.dumps({"model": model, "max_tokens": 16, "messages": USER_MSG}).encode()
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Authorization": f"Bearer {key}",
                 "content-type": "application/json", "User-Agent": _UA},
    )
    return _do(req)


def probe_list_models_openai(base: str, key: str) -> tuple[int, str]:
    url = f"{base.rstrip('/')}/v1/models"
    req = urllib.request.Request(url, method="GET",
                                  headers={"Authorization": f"Bearer {key}",
                                           "User-Agent": _UA})
    return _do(req)


def _do(req) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except Exception as e:
        return 0, f"<transport: {e}>"


def main() -> int:
    hydrate_env()
    key = os.environ.get("PACKYCODE_KEY")
    if not key:
        print("PACKYCODE_KEY missing in .env"); return 2

    # Step 1 —— 各 base 试 /v1/models（OpenAI 兼容通常暴露）
    print("=== Step 1: OpenAI-style /v1/models probe ===")
    for b in BASES:
        status, body = probe_list_models_openai(b, key)
        head = body[:300].replace("\n", " ")
        print(f"[{status}] GET {b}/v1/models  →  {head}")

    # Step 2 —— 每个 base 试 Anthropic + OpenAI 两种协议 × 两个常见模型
    print("\n=== Step 2: test call with claude-opus-4-6 ===")
    for b in BASES:
        s1, body1 = probe_anthropic(b, key, "claude-opus-4-6")
        head1 = body1[:200].replace("\n", " ")
        print(f"[{s1}] POST {b}/v1/messages      anthropic → {head1}")
        s2, body2 = probe_openai(b, key, "claude-opus-4-6")
        head2 = body2[:200].replace("\n", " ")
        print(f"[{s2}] POST {b}/v1/chat/completions openai → {head2}")

    print("\nNext: pick the (base, protocol, model_id) combo that returned 200.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
