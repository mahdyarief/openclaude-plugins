from __future__ import annotations

import inspect
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from engine.run_lock import run_lock


@dataclass
class ToolSpec:
    name: str
    description: str
    # Extra keys a ``**payload`` tool accepts, so the harness can see them in
    # the input schema instead of guessing.
    payload_keys: tuple[str, ...] = ()


@dataclass
class ResourceSpec:
    uri: str
    description: str


# Annotation fragments (``from __future__ import annotations`` keeps them as
# strings) mapped to JSON Schema types, most specific container first.
_TYPE_HINTS: tuple[tuple[str, str], ...] = (
    ("list[", "array"),
    ("tuple[", "array"),
    ("dict[", "object"),
    ("Mapping[", "object"),
    ("bool", "boolean"),
    ("int", "integer"),
    ("float", "number"),
    ("str", "string"),
    ("Path", "string"),
)


def _json_type(annotation: Any) -> dict[str, Any]:
    text = annotation if isinstance(annotation, str) else getattr(annotation, "__name__", "")
    for fragment, json_type in _TYPE_HINTS:
        if fragment in text:
            return {"type": json_type}
    return {}


def input_schema(method: Any, payload_keys: Iterable[str] = ()) -> dict[str, Any]:
    """Build a JSON Schema for a tool method from its Python signature."""

    properties: dict[str, Any] = {}
    required: list[str] = []
    takes_payload = False
    for name, param in inspect.signature(method).parameters.items():
        if param.kind is inspect.Parameter.VAR_KEYWORD:
            takes_payload = True
            continue
        if param.kind is inspect.Parameter.VAR_POSITIONAL:
            continue
        prop = _json_type(param.annotation)
        if param.default is inspect.Parameter.empty:
            required.append(name)
        elif param.default is not None:
            prop["default"] = param.default
        properties[name] = prop
    if takes_payload:
        for key in payload_keys:
            properties.setdefault(key, {})
    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        schema["required"] = required
    return schema


def reject_unknown_keys(payload: dict[str, Any], allowed: Iterable[str], *, tool: str) -> None:
    """Fail loudly on misspelt arguments instead of silently dropping them."""

    unknown = sorted(set(payload) - set(allowed))
    if unknown:
        raise ValueError(
            f"{tool}: unknown argument(s) {', '.join(unknown)}; "
            f"accepted: {', '.join(sorted(allowed))}"
        )


class BasePaperAssistMcpServer:
    server_name = "base"

    def tools(self) -> list[ToolSpec]:
        return []

    def resources(self) -> list[ResourceSpec]:
        return []

    def tool_schema(self, spec: ToolSpec) -> dict[str, Any]:
        return input_schema(getattr(self, spec.name), spec.payload_keys)

    def capabilities(self) -> dict[str, Any]:
        return {
            "server": self.server_name,
            "tools": [
                {**asdict(spec), "inputSchema": self.tool_schema(spec)} for spec in self.tools()
            ],
            "resources": [asdict(spec) for spec in self.resources()],
        }

    def call_tool(self, tool_name: str, **payload: Any) -> dict[str, Any]:
        if not any(spec.name == tool_name for spec in self.tools()):
            raise ValueError(f"Unsupported tool `{tool_name}` for server `{self.server_name}`")
        tool = getattr(self, tool_name)
        result = tool(**payload)
        if isinstance(result, dict):
            return {
                "server": self.server_name,
                "tool": tool_name,
                **result,
            }
        return {
            "server": self.server_name,
            "tool": tool_name,
            "result": result,
        }

    def read_resource(self, resource_uri: str, **payload: Any) -> dict[str, Any]:
        raise ValueError(f"Unsupported resource `{resource_uri}` for server `{self.server_name}`")

    @contextmanager
    def workspace_lock(self, workspace: str | Path) -> Iterator[None]:
        workspace_path = Path(workspace).expanduser().resolve()
        with run_lock(workspace_path, timeout=30, poll_interval=0.2, verbose=True):
            yield
