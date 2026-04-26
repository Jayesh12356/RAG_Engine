"""Generate typed Python + TypeScript SDKs from the FastAPI OpenAPI schema.

Why this exists:
    The roadmap calls for shipping consumer-friendly SDKs alongside the
    API so internal services and the marketing site can call us without
    re-implementing request shapes. We deliberately avoid pulling in a
    heavyweight tool like ``openapi-generator`` because:

    * we want the build to stay pure-Python with **no** Java dependency,
    * the surface is small (a few dozen routes, plain JSON in/out),
    * we keep full control over naming so the generated TS code lines up
      with the existing ``helpdesk-ui/src/lib/api.ts`` style.

Usage::

    # Default — write SDKs to app/sdk/python and helpdesk-ui/src/lib/sdk.
    python -m scripts.gen_sdk

    # Pull from a running server instead of the in-process app.
    python -m scripts.gen_sdk --url http://localhost:8000/openapi.json

The output is small, readable code that uses ``httpx`` (Python) and the
browser ``fetch`` API (TS). Both clients respect the cookie auth stub the
backend already enforces.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PY_OUT = ROOT / "app" / "sdk" / "python"
DEFAULT_TS_OUT = ROOT / "helpdesk-ui" / "src" / "lib" / "sdk"


# ── Helpers ─────────────────────────────────────────────────────────────────


def _camel_to_snake(name: str) -> str:
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def _safe_python_name(operation_id: str | None, method: str, path: str) -> str:
    if operation_id:
        cleaned = re.sub(r"[^A-Za-z0-9_]", "_", operation_id)
        cleaned = re.sub(r"__+", "_", cleaned).strip("_")
        if cleaned:
            return _camel_to_snake(cleaned)
    cleaned_path = re.sub(r"[^A-Za-z0-9]+", "_", path).strip("_") or "root"
    return f"{method.lower()}_{cleaned_path}".lower()


def _safe_ts_name(operation_id: str | None, method: str, path: str) -> str:
    base = _safe_python_name(operation_id, method, path)
    parts = base.split("_")
    return parts[0] + "".join(p.title() for p in parts[1:])


def _resolve_ref(spec: dict[str, Any], ref: str) -> dict[str, Any]:
    parts = ref.lstrip("#/").split("/")
    cur: Any = spec
    for p in parts:
        cur = cur[p]
    return cur


def _ts_type(schema: dict[str, Any] | None, spec: dict[str, Any], *, in_models: bool = False) -> str:
    if not schema:
        return "unknown"
    if "$ref" in schema:
        ref = schema["$ref"].split("/")[-1]
        return ref if in_models else f"Models.{ref}"
    if "anyOf" in schema or "oneOf" in schema:
        union = schema.get("anyOf") or schema.get("oneOf") or []
        return " | ".join(_ts_type(s, spec, in_models=in_models) for s in union) or "unknown"
    type_ = schema.get("type")
    if type_ == "array":
        return f"{_ts_type(schema.get('items') or {}, spec, in_models=in_models)}[]"
    if type_ == "object" or "properties" in schema:
        return "Record<string, unknown>"
    if type_ == "integer" or type_ == "number":
        return "number"
    if type_ == "boolean":
        return "boolean"
    if type_ == "string":
        return "string"
    if type_ == "null":
        return "null"
    return "unknown"


def _py_type(schema: dict[str, Any] | None, spec: dict[str, Any]) -> str:
    if not schema:
        return "Any"
    if "$ref" in schema:
        return "dict[str, Any]"  # keep python clients simple — no model imports
    if "anyOf" in schema or "oneOf" in schema:
        union = schema.get("anyOf") or schema.get("oneOf") or []
        py_union = " | ".join(_py_type(s, spec) for s in union)
        return py_union or "Any"
    type_ = schema.get("type")
    if type_ == "array":
        return f"list[{_py_type(schema.get('items') or {}, spec)}]"
    if type_ == "object" or "properties" in schema:
        return "dict[str, Any]"
    if type_ == "integer":
        return "int"
    if type_ == "number":
        return "float"
    if type_ == "boolean":
        return "bool"
    if type_ == "string":
        return "str"
    if type_ == "null":
        return "None"
    return "Any"


def _iter_operations(spec: dict[str, Any]) -> Iterable[tuple[str, str, dict[str, Any]]]:
    for path, methods in (spec.get("paths") or {}).items():
        if not isinstance(methods, dict):
            continue
        for method, op in methods.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            yield method.lower(), path, op or {}


def _format_path_to_python(path: str) -> tuple[str, list[str]]:
    """Convert ``/foo/{id}`` → ``f"/foo/{id}"`` plus ordered param list."""
    params = re.findall(r"{([^}]+)}", path)
    return path, params


# ── Schema model emission (TS only — Python keeps things dict-shaped) ──────


def _emit_ts_models(spec: dict[str, Any]) -> str:
    schemas = (spec.get("components") or {}).get("schemas") or {}
    out: list[str] = []
    for name, schema in schemas.items():
        if not isinstance(schema, dict):
            continue
        if schema.get("enum"):
            literals = " | ".join(json.dumps(v) for v in schema["enum"])
            out.append(f"export type {name} = {literals};\n")
            continue
        properties = schema.get("properties") or {}
        required = set(schema.get("required") or [])
        if not properties:
            out.append(f"export type {name} = Record<string, unknown>;\n")
            continue
        lines = [f"export interface {name} {{"]
        for prop, prop_schema in properties.items():
            optional = "" if prop in required else "?"
            ts = _ts_type(
                prop_schema if isinstance(prop_schema, dict) else {},
                spec,
                in_models=True,
            )
            description = (prop_schema or {}).get("description") if isinstance(prop_schema, dict) else None
            if description:
                lines.append(f"  /** {description.strip()} */")
            lines.append(f"  {prop}{optional}: {ts};")
        lines.append("}\n")
        out.append("\n".join(lines))
    return "\n".join(out)


# ── Python client emission ──────────────────────────────────────────────────


PY_CLIENT_HEADER = '''"""Auto-generated synchronous + async client for the helpdesk RAG API.

Do not edit by hand — regenerate with ``python -m scripts.gen_sdk``.
"""
from __future__ import annotations

from typing import Any

import httpx


class HelpdeskClient:
    """Thin httpx-based wrapper around the helpdesk RAG API.

    The client mirrors the cookie-based auth stub used by the FastAPI
    backend: pass ``cookie="rag_engine_uid=…"`` (or attach an existing
    ``httpx.Cookies`` jar) to keep per-user preferences in scope.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        *,
        cookie: str | None = None,
        timeout: float = 30.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        headers = {"User-Agent": "helpdesk-sdk/1.0"}
        if cookie:
            headers["Cookie"] = cookie
        self._client = client or httpx.Client(
            base_url=self.base_url, timeout=timeout, headers=headers
        )

    def __enter__(self) -> "HelpdeskClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any | None = None,
    ) -> Any:
        response = self._client.request(method, path, params=params, json=json_body)
        response.raise_for_status()
        if response.status_code == 204 or not response.content:
            return None
        ctype = response.headers.get("content-type", "")
        if "application/json" in ctype:
            return response.json()
        return response.content
'''


def _emit_py_method(method: str, path: str, op: dict[str, Any], spec: dict[str, Any]) -> str:
    name = _safe_python_name(op.get("operationId"), method, path)
    summary = (op.get("summary") or op.get("description") or "").strip().splitlines()
    doc = summary[0] if summary else f"{method.upper()} {path}"

    parameters = op.get("parameters") or []
    path_params = [p for p in parameters if p.get("in") == "path"]
    query_params = [p for p in parameters if p.get("in") == "query"]

    sig_args: list[str] = ["self"]
    for p in path_params:
        py_type = _py_type(p.get("schema"), spec)
        sig_args.append(f"{p['name']}: {py_type}")
    for p in query_params:
        py_type = _py_type(p.get("schema"), spec)
        default = " = None"
        py_type = py_type if p.get("required") else f"{py_type} | None"
        if p.get("required"):
            default = ""
        sig_args.append(f"{p['name']}: {py_type}{default}")

    has_body = "requestBody" in op and method != "get"
    if has_body:
        sig_args.append("body: dict[str, Any] | None = None")

    return_schema = (
        op.get("responses", {})
        .get("200", op.get("responses", {}).get("201", {}))
        .get("content", {})
        .get("application/json", {})
        .get("schema")
    )
    return_type = _py_type(return_schema, spec) if return_schema else "Any"

    formatted_path = re.sub(r"{([^}]+)}", r"{\1}", path)

    body_lines: list[str] = []
    body_lines.append(f"        path = f\"{formatted_path}\"")
    if query_params:
        body_lines.append("        params: dict[str, Any] = {}")
        for p in query_params:
            body_lines.append(
                f"        if {p['name']} is not None: params[{p['name']!r}] = {p['name']}"
            )
    else:
        body_lines.append("        params = None")
    if has_body:
        body_lines.append("        json_body = body")
    else:
        body_lines.append("        json_body = None")
    body_lines.append(
        f"        return self._request({method.upper()!r}, path, params=params, json_body=json_body)"
    )

    return (
        f"    def {name}({', '.join(sig_args)}) -> {return_type}:\n"
        f"        \"\"\"{doc}\"\"\"\n"
        + "\n".join(body_lines)
        + "\n"
    )


def _emit_python_client(spec: dict[str, Any]) -> str:
    methods = [
        _emit_py_method(method, path, op, spec)
        for method, path, op in _iter_operations(spec)
    ]
    return PY_CLIENT_HEADER + "\n" + "\n".join(methods)


# ── TypeScript client emission ──────────────────────────────────────────────


TS_HEADER = """// Auto-generated client for the helpdesk RAG API.
// Do not edit by hand — regenerate with `python -m scripts.gen_sdk`.

import type * as Models from "./models"

export interface HelpdeskClientOptions {
  baseUrl?: string
  fetchImpl?: typeof fetch
  cookie?: string
}

export class HelpdeskAPIError extends Error {
  status: number
  body: unknown

  constructor(status: number, body: unknown, message: string) {
    super(message)
    this.status = status
    this.body = body
  }
}

async function request(
  baseUrl: string,
  fetchImpl: typeof fetch,
  cookie: string | undefined,
  method: string,
  path: string,
  params?: Record<string, unknown>,
  body?: unknown,
): Promise<unknown> {
  const url = new URL(baseUrl.replace(/\\/$/, "") + path, baseUrl.includes("://") ? undefined : "http://localhost")
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v === undefined || v === null) continue
      url.searchParams.set(k, String(v))
    }
  }
  const headers: Record<string, string> = { "Content-Type": "application/json" }
  if (cookie) headers["Cookie"] = cookie
  const response = await fetchImpl(url.toString(), {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    credentials: "include",
  })
  if (!response.ok) {
    let parsed: unknown = null
    try {
      parsed = await response.json()
    } catch {
      /* ignore */
    }
    throw new HelpdeskAPIError(response.status, parsed, `${method} ${path} failed: ${response.status}`)
  }
  if (response.status === 204) return null
  const contentType = response.headers.get("content-type") || ""
  if (contentType.includes("application/json")) return response.json()
  return response.text()
}

export function createHelpdeskClient(opts: HelpdeskClientOptions = {}) {
  const baseUrl = (opts.baseUrl || "").replace(/\\/$/, "")
  const fetchImpl = opts.fetchImpl || fetch
  const cookie = opts.cookie
"""


def _emit_ts_method(method: str, path: str, op: dict[str, Any], spec: dict[str, Any]) -> str:
    name = _safe_ts_name(op.get("operationId"), method, path)
    summary = (op.get("summary") or op.get("description") or "").strip().splitlines()
    doc = summary[0] if summary else f"{method.upper()} {path}"

    parameters = op.get("parameters") or []
    path_params = [p for p in parameters if p.get("in") == "path"]
    query_params = [p for p in parameters if p.get("in") == "query"]

    args: list[str] = []
    for p in path_params:
        ts = _ts_type(p.get("schema") or {}, spec)
        args.append(f"{p['name']}: {ts}")
    for p in query_params:
        ts = _ts_type(p.get("schema") or {}, spec)
        marker = "" if p.get("required") else "?"
        args.append(f"{p['name']}{marker}: {ts}")

    has_body = "requestBody" in op and method != "get"
    if has_body:
        args.append("body?: unknown")

    return_schema = (
        op.get("responses", {})
        .get("200", op.get("responses", {}).get("201", {}))
        .get("content", {})
        .get("application/json", {})
        .get("schema")
    )
    return_ts = _ts_type(return_schema or {}, spec) if return_schema else "unknown"

    formatted_path = path
    for p in path_params:
        formatted_path = formatted_path.replace(f"{{{p['name']}}}", f"${{{p['name']}}}")

    params_block = "undefined"
    if query_params:
        params_block = (
            "{ "
            + ", ".join(f"{p['name']}: {p['name']}" for p in query_params)
            + " }"
        )

    body_arg = "body" if has_body else "undefined"

    body = (
        f"    /** {doc} */\n"
        f"    async {name}({', '.join(args)}): Promise<{return_ts}> {{\n"
        f"      return (await request(baseUrl, fetchImpl, cookie, {method.upper()!r}, `{formatted_path}`, {params_block}, {body_arg})) as {return_ts}\n"
        f"    }},"
    )
    return body


def _emit_ts_client(spec: dict[str, Any]) -> str:
    body = TS_HEADER + "\n  return {\n"
    methods = [
        _emit_ts_method(method, path, op, spec)
        for method, path, op in _iter_operations(spec)
    ]
    body += "\n".join(methods) + "\n  }\n}\n"
    return body


# ── OpenAPI loading ─────────────────────────────────────────────────────────


def _load_openapi(url: str | None) -> dict[str, Any]:
    if url:
        import urllib.request

        with urllib.request.urlopen(url) as fh:
            return json.loads(fh.read().decode("utf-8"))
    # In-process: build the FastAPI app and ask it for the schema.
    sys.path.insert(0, str(ROOT))
    from app.main import app  # type: ignore  # noqa: E402

    return app.openapi()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=None, help="Fetch /openapi.json from a running server instead of importing app.main")
    parser.add_argument("--py-out", default=str(DEFAULT_PY_OUT), help="Output dir for the Python SDK")
    parser.add_argument("--ts-out", default=str(DEFAULT_TS_OUT), help="Output dir for the TypeScript SDK")
    args = parser.parse_args(argv)

    spec = _load_openapi(args.url)

    py_dir = Path(args.py_out)
    ts_dir = Path(args.ts_out)
    py_dir.mkdir(parents=True, exist_ok=True)
    ts_dir.mkdir(parents=True, exist_ok=True)

    (py_dir / "__init__.py").write_text(
        "from .client import HelpdeskClient\n\n__all__ = ['HelpdeskClient']\n",
        encoding="utf-8",
    )
    (py_dir / "client.py").write_text(_emit_python_client(spec), encoding="utf-8")

    models_ts = _emit_ts_models(spec)
    (ts_dir / "models.ts").write_text(
        "// Auto-generated from /openapi.json — do not edit.\n\n" + models_ts,
        encoding="utf-8",
    )
    (ts_dir / "client.ts").write_text(_emit_ts_client(spec), encoding="utf-8")
    (ts_dir / "index.ts").write_text(
        "export * from './client'\nexport * from './models'\n",
        encoding="utf-8",
    )

    print(f"Wrote Python SDK → {py_dir}")
    print(f"Wrote TS SDK     → {ts_dir}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
