"""Ad-hoc: ask the configured Anthropic-compatible proxy what models it serves.

用法：
    python probe_models.py

读取 .env 里的 ANTHROPIC_API_KEY + ANTHROPIC_API_BASE，尝试几种常见的
"列出模型"端点，打印代理返回的内容。能成功的第一个端点即是该代理支持的
模型发现接口。

此文件为一次性排查工具，可按需保留或删除。
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

from framework.observability.secrets import hydrate_env


def probe(url: str, headers: dict) -> tuple[int, str]:
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except Exception as e:
        return 0, f"<transport error: {e}>"


def main() -> int:
    hydrate_env()
    key = os.environ.get("ANTHROPIC_API_KEY")
    base = os.environ.get("ANTHROPIC_API_BASE")
    if not key or not base:
        print("ANTHROPIC_API_KEY or ANTHROPIC_API_BASE missing in .env")
        return 2
    base = base.rstrip("/")

    candidate_urls = [
        f"{base}/v1/models",
        f"{base}/models",
        f"{base}/v1/model/list",
        f"{base}/list_models",
    ]

    common_headers = [
        {"x-api-key": key, "anthropic-version": "2023-06-01"},
        {"Authorization": f"Bearer {key}"},
    ]

    for url in candidate_urls:
        for headers in common_headers:
            status, body = probe(url, headers)
            print(f"--- GET {url}  (auth={list(headers)[0]})  status={status}")
            if status == 200:
                print(body[:2000])
                return 0
            else:
                print(body[:400])
    print("\nNone of the candidate endpoints returned 200. Check MiniMax docs directly:")
    print("  https://platform.minimaxi.com/document/")
    return 1


if __name__ == "__main__":
    sys.exit(main())
