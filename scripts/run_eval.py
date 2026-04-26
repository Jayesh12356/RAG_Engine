"""RAG evaluation harness — gated by ``RUN_EVAL=1``.

Runs ``QueryPipeline`` against the golden set in
``tests/eval/golden.yaml`` and prints aggregate scores per category and
overall. Metrics:

* **faithfulness** — ratio of expected keywords that occur in the
  generated answer (whitespace-collapsed, case-insensitive).
* **citation_precision** — for each case, fraction of cited sources
  whose ``pdf_name`` contains any of the expected source substrings.
* **recall@k** — 1.0 when at least one expected source appears in the
  top-k citations, else 0.0; aggregated as a mean per category.
* **refusal** — for cases marked ``expected_refusal: true``, hits when
  the response is ``refused=True``; else hits when it is not.

Usage:

    RUN_EVAL=1 python scripts/run_eval.py --golden tests/eval/golden.yaml

A non-zero exit code is returned when any category's faithfulness drops
below ``--min-faithfulness`` (default 0.6) — useful for nightly CI.

The script is intentionally dependency-light: it only relies on PyYAML
which the project already pulls in. No live LLM calls are mocked, so
the harness exercises the *real* providers configured via env. That
makes it explicitly opt-in (``RUN_EVAL=1``).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore[import-untyped]
except Exception:  # pragma: no cover — surfaced when PyYAML is missing
    print("PyYAML not installed; run `pip install pyyaml`.", file=sys.stderr)
    raise


# Importing the live pipeline lazily keeps `--help` instantaneous.


@dataclass
class CaseResult:
    case_id: str
    category: str
    refused: bool
    answer: str
    citations: list[dict[str, Any]]
    faithfulness: float = 0.0
    citation_precision: float = 0.0
    recall_at_k: float = 0.0
    refusal_hit: float = 0.0
    expected_refusal: bool = False
    elapsed_sec: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _faithfulness(answer: str, keywords: list[str]) -> float:
    if not keywords:
        return 1.0
    a = _norm(answer)
    if not a:
        return 0.0
    hits = sum(1 for k in keywords if _norm(k) in a)
    return hits / len(keywords)


def _citation_precision(
    citations: list[dict[str, Any]], expected_sources: list[str]
) -> float:
    if not citations:
        return 0.0
    if not expected_sources:
        return 1.0
    expected_lc = [s.lower() for s in expected_sources]

    def _match(c: dict[str, Any]) -> bool:
        haystack = " ".join(
            str(c.get(k, "")) for k in ("pdf_name", "document_id", "chunk_id")
        ).lower()
        return any(e in haystack for e in expected_lc)

    hits = sum(1 for c in citations if _match(c))
    return hits / len(citations)


def _recall_at_k(citations: list[dict[str, Any]], expected_sources: list[str]) -> float:
    if not expected_sources:
        return 1.0
    if not citations:
        return 0.0
    expected_lc = [s.lower() for s in expected_sources]
    for c in citations:
        haystack = " ".join(
            str(c.get(k, "")) for k in ("pdf_name", "document_id", "chunk_id")
        ).lower()
        if any(e in haystack for e in expected_lc):
            return 1.0
    return 0.0


async def _run_case(case: dict[str, Any]) -> CaseResult:
    from app.models.query import QueryRequest
    from app.query.pipeline import QueryPipeline

    pipeline = QueryPipeline(demo_mode=False)
    req = QueryRequest(
        question=case["question"],
        service_category=case.get("category"),
        include_citations=True,
    )

    import time

    t0 = time.time()
    response = await pipeline.run(req)
    elapsed = time.time() - t0

    expected_kw = list(case.get("expected_keywords") or [])
    expected_src = list(case.get("expected_sources") or [])
    expected_refusal = bool(case.get("expected_refusal") or False)

    citations = [c.model_dump() for c in (response.citations or [])]
    if not citations:
        citations = [s.model_dump() for s in (response.sources or [])]

    if expected_refusal:
        refusal_hit = 1.0 if response.refused else 0.0
        faith = 1.0 if response.refused else 0.0
        cp = 1.0 if response.refused else 0.0
        recall = 1.0 if response.refused else 0.0
    else:
        refusal_hit = 0.0 if response.refused else 1.0
        faith = _faithfulness(response.answer, expected_kw)
        cp = _citation_precision(citations, expected_src)
        recall = _recall_at_k(citations, expected_src)

    return CaseResult(
        case_id=case["id"],
        category=(case.get("category") or "GENERAL"),
        refused=bool(response.refused),
        answer=response.answer,
        citations=citations,
        faithfulness=faith,
        citation_precision=cp,
        recall_at_k=recall,
        refusal_hit=refusal_hit,
        expected_refusal=expected_refusal,
        elapsed_sec=round(elapsed, 3),
        raw=response.model_dump(),
    )


def _aggregate(results: list[CaseResult]) -> dict[str, Any]:
    by_cat: dict[str, list[CaseResult]] = {}
    for r in results:
        by_cat.setdefault(r.category, []).append(r)

    def _avg(rows: list[CaseResult], attr: str) -> float:
        return round(sum(getattr(r, attr) for r in rows) / max(1, len(rows)), 3)

    summary: dict[str, Any] = {"by_category": {}, "overall": {}}
    for cat, rows in by_cat.items():
        summary["by_category"][cat] = {
            "n": len(rows),
            "faithfulness": _avg(rows, "faithfulness"),
            "citation_precision": _avg(rows, "citation_precision"),
            "recall_at_k": _avg(rows, "recall_at_k"),
            "refusal_accuracy": _avg(rows, "refusal_hit"),
        }
    summary["overall"] = {
        "n": len(results),
        "faithfulness": _avg(results, "faithfulness"),
        "citation_precision": _avg(results, "citation_precision"),
        "recall_at_k": _avg(results, "recall_at_k"),
        "refusal_accuracy": _avg(results, "refusal_hit"),
    }
    return summary


def _print_table(summary: dict[str, Any]) -> None:
    print("\n=== RAG eval summary ===")
    by_cat = summary.get("by_category", {})
    print(
        f"{'category':18s} {'n':>3s} {'faith':>7s} {'cite':>7s} {'rec@k':>7s} {'ref':>7s}"
    )
    for cat, stats in sorted(by_cat.items()):
        print(
            f"{cat:18s} {stats['n']:>3d} "
            f"{stats['faithfulness']:>7.2f} "
            f"{stats['citation_precision']:>7.2f} "
            f"{stats['recall_at_k']:>7.2f} "
            f"{stats['refusal_accuracy']:>7.2f}"
        )
    overall = summary.get("overall", {})
    print(
        f"{'OVERALL':18s} {overall.get('n', 0):>3d} "
        f"{overall.get('faithfulness', 0.0):>7.2f} "
        f"{overall.get('citation_precision', 0.0):>7.2f} "
        f"{overall.get('recall_at_k', 0.0):>7.2f} "
        f"{overall.get('refusal_accuracy', 0.0):>7.2f}"
    )


def _load_cases(path: Path) -> list[dict[str, Any]]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    cases = list((raw or {}).get("cases") or [])
    for c in cases:
        if "id" not in c or "question" not in c:
            raise ValueError(f"Case missing id or question: {c}")
    return cases


async def _main_async(args: argparse.Namespace) -> int:
    cases = _load_cases(Path(args.golden))
    results: list[CaseResult] = []
    for c in cases:
        try:
            res = await _run_case(c)
        except Exception as exc:
            print(f"[error] {c.get('id')}: {exc}", file=sys.stderr)
            res = CaseResult(
                case_id=c.get("id", "?"),
                category=c.get("category", "GENERAL"),
                refused=False,
                answer="",
                citations=[],
                expected_refusal=bool(c.get("expected_refusal") or False),
            )
        results.append(res)
        if args.verbose:
            print(
                f"[case] {res.case_id:30s} faith={res.faithfulness:.2f} "
                f"cite={res.citation_precision:.2f} rec={res.recall_at_k:.2f} "
                f"ref={res.refusal_hit:.2f} t={res.elapsed_sec}s"
            )

    summary = _aggregate(results)
    _print_table(summary)

    if args.json_out:
        out = {
            "summary": summary,
            "cases": [
                {
                    "id": r.case_id,
                    "category": r.category,
                    "refused": r.refused,
                    "expected_refusal": r.expected_refusal,
                    "faithfulness": r.faithfulness,
                    "citation_precision": r.citation_precision,
                    "recall_at_k": r.recall_at_k,
                    "refusal_hit": r.refusal_hit,
                    "elapsed_sec": r.elapsed_sec,
                    "answer": r.answer,
                }
                for r in results
            ],
        }
        Path(args.json_out).write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(f"\nWrote JSON report to {args.json_out}")

    overall_faith = float(summary["overall"].get("faithfulness", 0.0))
    if overall_faith < args.min_faithfulness:
        print(
            f"\n[fail] overall faithfulness {overall_faith:.2f} "
            f"< threshold {args.min_faithfulness:.2f}",
            file=sys.stderr,
        )
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the RAG evaluation harness against golden.yaml.",
    )
    parser.add_argument(
        "--golden",
        default="tests/eval/golden.yaml",
        help="Path to the golden YAML.",
    )
    parser.add_argument(
        "--json-out",
        default="",
        help="Optional path to write a JSON report.",
    )
    parser.add_argument(
        "--min-faithfulness",
        type=float,
        default=0.6,
        help="Fail the run if overall faithfulness drops below this.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print per-case scores as they finish.",
    )
    args = parser.parse_args(argv)

    if not os.environ.get("RUN_EVAL"):
        print(
            "RUN_EVAL not set; skipping. Set RUN_EVAL=1 to execute the eval suite.",
            file=sys.stderr,
        )
        return 0

    return asyncio.run(_main_async(args))


if __name__ == "__main__":
    sys.exit(main())
