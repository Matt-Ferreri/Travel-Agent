"""
Minimal stdio MCP server exposing travel weather.

Protocol: JSON-RPC 2.0 over newline-delimited stdin/stdout (MCP-compatible).
Run: python -m mcp_integration.weather_server
"""
from __future__ import annotations

import json
import sys
from typing import Any

# Ensure project root imports work when launched as a subprocess.
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.registry import get_weather  # noqa: E402

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "travel-weather-mcp", "version": "0.1.0"}

WEATHER_TOOL = {
    "name": "get_weather",
    "description": (
        "Get a short weather forecast for a city via the Travel Agent MCP weather server "
        "(Open-Meteo live or local fixture)."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "City name, e.g. Boston"},
            "forecast_days": {
                "type": "integer",
                "description": "Number of forecast days (1-7)",
                "minimum": 1,
                "maximum": 7,
            },
        },
        "required": ["city"],
        "additionalProperties": False,
    },
}


def _write(message: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(message) + "\n")
    sys.stdout.flush()


def _ok(req_id: Any, result: dict[str, Any]) -> None:
    _write({"jsonrpc": "2.0", "id": req_id, "result": result})


def _err(req_id: Any, code: int, message: str) -> None:
    _write({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})


def _handle(msg: dict[str, Any]) -> None:
    method = msg.get("method")
    req_id = msg.get("id")
    params = msg.get("params") or {}

    # Notifications have no id and expect no response.
    if req_id is None and method:
        return

    if method == "initialize":
        _ok(
            req_id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": SERVER_INFO,
            },
        )
        return

    if method == "tools/list":
        _ok(req_id, {"tools": [WEATHER_TOOL]})
        return

    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if name != "get_weather":
            _err(req_id, -32602, f"Unknown tool: {name}")
            return
        try:
            result = get_weather(
                city=str(arguments.get("city", "")),
                forecast_days=int(arguments.get("forecast_days") or 3),
            )
            _ok(
                req_id,
                {
                    "content": [{"type": "text", "text": json.dumps(result)}],
                    "structuredContent": result,
                    "isError": False,
                },
            )
        except Exception as exc:  # noqa: BLE001 — surface tool errors over MCP
            _ok(
                req_id,
                {
                    "content": [{"type": "text", "text": json.dumps({"error": str(exc)})}],
                    "isError": True,
                },
            )
        return

    if method == "ping":
        _ok(req_id, {})
        return

    _err(req_id, -32601, f"Method not found: {method}")


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(msg, dict):
            _handle(msg)


if __name__ == "__main__":
    main()
