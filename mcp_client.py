from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

PROJECT_ROOT = Path(__file__).resolve().parent
SERVER_PATH = PROJECT_ROOT / "mcp_server.py"


def normalize_mcp_result(result: Any) -> str:
    if result is None:
        return ""

    if isinstance(result, dict) and isinstance(result.get("text"), str):
        return result["text"]

    if isinstance(getattr(result, "text", None), str):
        return result.text

    if hasattr(result, "content"):
        parts: list[str] = []
        for item in result.content:
            if isinstance(item, dict):
                if "text" in item:
                    parts.append(str(item["text"]))
                elif "content" in item:
                    parts.append(str(item["content"]))
                else:
                    parts.append(json.dumps(item, ensure_ascii=False))
            elif hasattr(item, "text"):
                parts.append(str(item.text))
            elif hasattr(item, "model_dump"):
                item_data = item.model_dump()
                if isinstance(item_data.get("text"), str):
                    parts.append(item_data["text"])
                else:
                    parts.append(json.dumps(item_data, ensure_ascii=False))
            else:
                parts.append(str(item))
        text = "\n".join(parts).strip()
        if text:
            return text

    if hasattr(result, "model_dump"):
        try:
            return json.dumps(result.model_dump(), ensure_ascii=False)
        except Exception:
            pass

    if isinstance(result, (list, tuple)):
        return "\n".join(normalize_mcp_result(item) for item in result).strip()

    if isinstance(result, dict):
        return json.dumps(result, ensure_ascii=False, default=str)

    return str(result)


async def _call_mcp_tool_async(
    name: str, arguments: dict[str, Any] | None = None
) -> str:
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_PATH)],
        cwd=str(PROJECT_ROOT),
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(name, arguments or {})
            return normalize_mcp_result(result)


def call_mcp_tool(name: str, arguments: dict[str, Any] | None = None):
    return asyncio.run(_call_mcp_tool_async(name, arguments))

