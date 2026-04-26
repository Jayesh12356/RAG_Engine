"""Admin CLI (Wave 3.5).

Run with ``python -m app.cli <subcommand> ...``. Sub-commands:

* ``ingest <path>``        — push a single document through the ingest pipeline.
* ``query <question>``     — run a one-shot query and print the answer.
* ``eval``                 — delegate to :mod:`scripts.run_eval` for the golden set.
* ``export-corpus <out>``  — dump every chunk + metadata to a JSON Lines file.
* ``clear-cache``          — invalidate the answer cache (in-memory + Redis if configured).

The CLI imports lazily so each sub-command only pays for what it touches —
e.g. ``clear-cache`` doesn't spin up the LLM providers, ``query`` doesn't
hit the relational DB if the answer cache misses.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any


def _safe_print(payload: Any) -> None:
    """Best-effort pretty-print — falls back to ``str`` for unserialisable values."""
    try:
        print(json.dumps(payload, indent=2, default=str))
    except Exception:
        print(payload)


# ── ingest ──────────────────────────────────────────────────────────────────
async def _cmd_ingest(args: argparse.Namespace) -> int:
    from app.ingestion.pipeline import IngestPipeline

    path = Path(args.path)
    if not path.is_file():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 2

    try:
        with path.open("rb") as fh:
            content = fh.read()
    except OSError as exc:
        print(f"error: could not read {path}: {exc}", file=sys.stderr)
        return 2

    pipeline = IngestPipeline(demo_mode=args.demo)
    result = await pipeline.run(
        str(path),
        args.service_name,
        pdf_bytes=content,
        content_type="application/octet-stream",
    )
    _safe_print(result.model_dump())
    return 0 if result.status == "success" else 1


# ── query ───────────────────────────────────────────────────────────────────
async def _cmd_query(args: argparse.Namespace) -> int:
    from app.models.query import QueryRequest
    from app.query.pipeline import QueryPipeline

    pipeline = QueryPipeline(demo_mode=args.demo)
    request = QueryRequest(
        question=args.question,
        service_category=args.service_category,
        top_k=args.top_k,
        rerank_top_n=args.rerank_top_n,
        include_citations=args.include_citations,
        tags=list(args.tags or []),
    )
    response = await pipeline.run(request)
    _safe_print(response.model_dump())
    return 0


# ── eval ────────────────────────────────────────────────────────────────────
def _cmd_eval(args: argparse.Namespace) -> int:
    """Run the golden eval harness — delegates to :mod:`scripts.run_eval`."""
    extra: list[str] = []
    if args.golden:
        extra.extend(["--golden", args.golden])
    if args.min_faithfulness is not None:
        extra.extend(["--min-faithfulness", str(args.min_faithfulness)])

    os.environ.setdefault("RUN_EVAL", "1")
    sys.argv = ["run_eval.py", *extra]
    try:
        from scripts.run_eval import main as run_eval_main  # type: ignore
    except Exception as exc:
        print(f"error: could not import scripts.run_eval: {exc}", file=sys.stderr)
        return 2
    try:
        return int(run_eval_main() or 0)
    except SystemExit as exc:
        return int(exc.code or 0)


# ── export-corpus ───────────────────────────────────────────────────────────
async def _cmd_export(args: argparse.Namespace) -> int:
    """Dump every chunk + parent document metadata to a JSON Lines file."""
    from sqlalchemy import select

    from app.db.relational import ChunkModel, DocumentModel, get_session_maker

    session_maker = get_session_maker()
    out_path = Path(args.out)
    count = 0
    async with session_maker() as session:
        docs = (await session.execute(select(DocumentModel))).scalars().all()
        documents_by_id = {d.id: d for d in docs}
        chunks = (await session.execute(select(ChunkModel))).scalars().all()
        with out_path.open("w", encoding="utf-8") as fh:
            for chunk in chunks:
                doc = documents_by_id.get(chunk.document_id)
                fh.write(
                    json.dumps(
                        {
                            "chunk_id": chunk.id,
                            "document_id": chunk.document_id,
                            "text": chunk.text,
                            "metadata": chunk.metadata_ or {},
                            "document": {
                                "filename": doc.filename if doc else None,
                                "summary": doc.summary if doc else None,
                                "tags": list(doc.tags or []) if doc else [],
                            },
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                count += 1
    print(f"wrote {count} chunks to {out_path}")
    return 0


# ── clear-cache ─────────────────────────────────────────────────────────────
async def _cmd_clear_cache(_: argparse.Namespace) -> int:
    """Reset the answer cache (process LRU + optional Redis backend)."""
    from app.query.cache import bump_corpus_version, get_answer_cache

    cache = get_answer_cache()
    if cache is None:
        bump_corpus_version(reason="cli_clear_cache")
        print("answer cache disabled — bumped corpus_version")
        return 0
    try:
        await cache.clear()
    except Exception as exc:
        print(f"warning: cache.clear() failed: {exc}", file=sys.stderr)
    bump_corpus_version(reason="cli_clear_cache")
    print("answer cache cleared")
    return 0


# ── argparse glue ───────────────────────────────────────────────────────────
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="app.cli", description="Admin CLI for the helpdesk RAG engine"
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run with DEMO_MODE forced on (in-memory stores only).",
    )

    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ingest = sub.add_parser("ingest", help="Ingest a single document")
    p_ingest.add_argument("path")
    p_ingest.add_argument("--service-name", default=None)

    p_query = sub.add_parser("query", help="Run a one-shot query")
    p_query.add_argument("question")
    p_query.add_argument("--service-category", default=None)
    p_query.add_argument("--top-k", type=int, default=20)
    p_query.add_argument("--rerank-top-n", type=int, default=None)
    p_query.add_argument(
        "--include-citations", dest="include_citations", action="store_true"
    )
    p_query.add_argument("--tags", nargs="*", default=[])

    p_eval = sub.add_parser("eval", help="Run the RAG eval harness")
    p_eval.add_argument("--golden", default=None)
    p_eval.add_argument("--min-faithfulness", type=float, default=None)

    p_export = sub.add_parser("export-corpus", help="Dump every chunk to a JSONL file")
    p_export.add_argument("out")

    sub.add_parser("clear-cache", help="Reset the answer cache")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.demo:
        os.environ["DEMO_MODE"] = "true"

    coros = {
        "ingest": _cmd_ingest,
        "query": _cmd_query,
        "export-corpus": _cmd_export,
        "clear-cache": _cmd_clear_cache,
    }

    handler = coros.get(args.cmd)
    if handler is not None:
        try:
            return asyncio.run(handler(args))
        except KeyboardInterrupt:
            return 130

    if args.cmd == "eval":
        return _cmd_eval(args)

    raise SystemExit(f"unknown command: {args.cmd}")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
