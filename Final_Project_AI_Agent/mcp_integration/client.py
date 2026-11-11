"""
Sync MCP client for the local weather MCP server (stdio JSON-RPC).

This is a real MCP boundary: the agent talks to a separate server process,
not a plain in-process Python function call alone.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TIMEOUT_S = float(os.getenv("MCP_TIMEOUT_S", "20"))


class McpError(RuntimeError):
    pass


class McpWeatherClient:
    """One-shot stdio session: initialize → tools/list or tools/call → exit."""

    def __init__(self, timeout_s: float | None = None) -> None:
        self.timeout_s = DEFAULT_TIMEOUT_S if timeout_s is None else timeout_s
        self._proc: subprocess.Popen[str] | None = None
        self._next_id = 1

    def __enter__(self) -> "McpWeatherClient":
        env = os.environ.copy()
        # Prefer project venv interpreter when available; else current python.
        python = sys.executable
        self._proc = subprocess.Popen(
            [python, "-m", "mcp_integration.weather_server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(ROOT),
            env=env,
            bufsize=1,
        )
        self._request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "travel-agent", "version": "0.1.0"},
            },
        )
        self._notify("notifications/initialized")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        if self._proc is None:
            return
        proc = self._proc
        self._proc = None
        try:
            if proc.stdin:
                proc.stdin.close()
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        finally:
            for stream in (proc.stdout, proc.stderr):
                try:
                    if stream:
                        stream.close()
                except Exception:
                    pass

    def _request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if self._proc is None or self._proc.stdin is None or self._proc.stdout is None:
            raise McpError("MCP server is not running")
        req_id = self._next_id
        self._next_id += 1
        payload = {"jsonrpc": "2.0", "id": req_id, "method": method}
        if params is not None:
            payload["params"] = params
        self._proc.stdin.write(json.dumps(payload) + "\n")
        self._proc.stdin.flush()

        # Read until matching response id (ignore stray lines).
        deadline_chunks = 0
        max_chunks = 50
        while deadline_chunks < max_chunks:
            line = self._proc.stdout.readline()
            deadline_chunks += 1
            if not line:
                err = ""
                if self._proc.stderr:
                    err = self._proc.stderr.read()
                raise McpError(f"MCP server closed unexpectedly. stderr={err[:500]}")
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("id") != req_id:
                continue
            if "error" in msg:
                raise McpError(str(msg["error"]))
            return msg.get("result") or {}
        raise McpError(f"Timed out waiting for MCP response to {method}")

    def _notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        if self._proc is None or self._proc.stdin is None:
            raise McpError("MCP server is not running")
        payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        self._proc.stdin.write(json.dumps(payload) + "\n")
        self._proc.stdin.flush()

    def list_tools(self) -> list[dict[str, Any]]:
        result = self._request("tools/list")
        tools = result.get("tools") or []
        if not isinstance(tools, list):
            raise McpError("Invalid tools/list response")
        return tools

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        result = self._request("tools/call", {"name": name, "arguments": arguments})
        if result.get("isError"):
            text = ""
            for block in result.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "text":
                    text = block.get("text") or ""
                    break
            try:
                return json.loads(text) if text else {"error": "MCP tool error"}
            except json.JSONDecodeError:
                return {"error": text or "MCP tool error"}
        if isinstance(result.get("structuredContent"), dict):
            return result["structuredContent"]
        for block in result.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "text":
                try:
                    parsed = json.loads(block.get("text") or "{}")
                    if isinstance(parsed, dict):
                        return parsed
                except json.JSONDecodeError:
                    return {"raw": block.get("text")}
        return {"error": "Empty MCP tool result"}


def list_mcp_tools() -> list[dict[str, Any]]:
    with McpWeatherClient() as client:
        return client.list_tools()


def call_mcp_weather(city: str, forecast_days: int = 3) -> dict[str, Any]:
    with McpWeatherClient() as client:
        payload = client.call_tool(
            "get_weather",
            {"city": city, "forecast_days": forecast_days},
        )
    payload = dict(payload)
    payload["mcp"] = {
        "transport": "stdio",
        "server": "mcp_integration.weather_server",
        "tool": "get_weather",
    }
    return payload
