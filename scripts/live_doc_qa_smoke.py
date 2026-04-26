"""Live document-Q&A smoke runner against a running backend.

Hammers ``/query`` with a matrix of positive, adversarial, and edge-case
questions, then prints a pass/fail report. Designed for quick post-deploy
sanity checks; **calls real LLM + embedding APIs**, so each invocation costs
real tokens (about a dozen completions per pass).

Usage::

    # backend already running on 8000 with the seeded image_pdfs/ corpus
    python scripts/live_doc_qa_smoke.py

    # different host / port / case selection
    python scripts/live_doc_qa_smoke.py --base-url http://localhost:8000 \
        --only positive_who_is

Exit code 0 = every case passed, 1 = at least one case failed.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx

# Windows consoles default to cp1252; LLM answers and decorations may include
# characters outside that map (curly quotes, em-dashes, bullets). Force UTF-8
# so the runner never crashes mid-report.
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )
    sys.stderr = io.TextIOWrapper(
        sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )

# Wired to the persona/refusal change in app/query/rag_generator.py.
REFUSAL_PHRASE = "I don't have information about this in the provided documents."


# ──────────────────────────────────────────────────────────────────────────
# Test-case schema
# ──────────────────────────────────────────────────────────────────────────
@dataclass
class Case:
    """A single live Q&A assertion.

    ``checks`` is a list of callables that each take the parsed
    ``/query`` response (``dict``) and return ``(ok, detail)``. All checks
    must pass for the case to pass.
    """

    id: str
    question: str
    kind: str  # positive | adversarial | edge
    checks: list[Callable[[dict], tuple[bool, str]]] = field(default_factory=list)
    request_overrides: dict = field(default_factory=dict)
    expect_status: int = 200


# ──────────────────────────────────────────────────────────────────────────
# Reusable check helpers (closures so they capture expected values cleanly)
# ──────────────────────────────────────────────────────────────────────────
def _answer(resp: dict) -> str:
    return (resp.get("answer") or "").strip()


def _confidence(resp: dict) -> float:
    try:
        return float(resp.get("confidence") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def expect_not_refused() -> Callable[[dict], tuple[bool, str]]:
    def _c(resp: dict) -> tuple[bool, str]:
        ans = _answer(resp).lower()
        refused = bool(resp.get("refused")) or REFUSAL_PHRASE.lower() in ans
        if refused:
            return False, "model refused but a grounded answer was expected"
        if not ans:
            return False, "answer was empty"
        return True, "answered"

    return _c


def expect_refused() -> Callable[[dict], tuple[bool, str]]:
    def _c(resp: dict) -> tuple[bool, str]:
        ans = _answer(resp).lower()
        refused = bool(resp.get("refused")) or REFUSAL_PHRASE.lower() in ans
        if not refused:
            return False, f"expected refusal, got: {_answer(resp)[:120]!r}"
        return True, "refused as expected"

    return _c


def expect_min_confidence(min_conf: float) -> Callable[[dict], tuple[bool, str]]:
    def _c(resp: dict) -> tuple[bool, str]:
        c = _confidence(resp)
        if c < min_conf:
            return False, f"confidence={c:.2f} < {min_conf:.2f}"
        return True, f"confidence={c:.2f} ≥ {min_conf:.2f}"

    return _c


def expect_max_confidence(max_conf: float) -> Callable[[dict], tuple[bool, str]]:
    def _c(resp: dict) -> tuple[bool, str]:
        c = _confidence(resp)
        if c > max_conf:
            return False, f"confidence={c:.2f} > {max_conf:.2f}"
        return True, f"confidence={c:.2f} ≤ {max_conf:.2f}"

    return _c


def expect_citation_to(pdf_name_substr: str) -> Callable[[dict], tuple[bool, str]]:
    def _c(resp: dict) -> tuple[bool, str]:
        cites = resp.get("citations") or []
        if not cites:
            return False, "no citations returned"
        for cite in cites:
            name = (cite.get("pdf_name") or "").lower()
            if pdf_name_substr.lower() in name:
                return True, f"citation -> {cite.get('pdf_name')}"
        return (
            False,
            "no citation pointed to "
            f"'{pdf_name_substr}'; got "
            f"{[c.get('pdf_name') for c in cites]}",
        )

    return _c


def expect_keyword_any(*keywords: str) -> Callable[[dict], tuple[bool, str]]:
    def _c(resp: dict) -> tuple[bool, str]:
        ans = _answer(resp).lower()
        hit = [kw for kw in keywords if kw.lower() in ans]
        if not hit:
            return False, f"none of {list(keywords)} in answer"
        return True, f"hit: {hit}"

    return _c


def expect_keyword_all(*keywords: str) -> Callable[[dict], tuple[bool, str]]:
    def _c(resp: dict) -> tuple[bool, str]:
        ans = _answer(resp).lower()
        miss = [kw for kw in keywords if kw.lower() not in ans]
        if miss:
            return False, f"missing keywords: {miss}"
        return True, "all keywords present"

    return _c


# ──────────────────────────────────────────────────────────────────────────
# Test matrix (CV-grounded)
# ──────────────────────────────────────────────────────────────────────────
CV_PDF_HINT = "cv-jayesh-koli"


def build_cases(min_positive_conf: float) -> list[Case]:
    return [
        # ── POSITIVE: must answer, hit confidence floor, cite the CV ──
        Case(
            id="positive_who_is",
            question="Who is Jayesh?",
            kind="positive",
            checks=[
                expect_not_refused(),
                expect_min_confidence(min_positive_conf),
                expect_citation_to(CV_PDF_HINT),
                expect_keyword_any("jayesh", "engineer", "genai", "backend"),
            ],
        ),
        Case(
            id="positive_skills",
            question="What programming languages and frameworks does Jayesh know?",
            kind="positive",
            checks=[
                expect_not_refused(),
                expect_min_confidence(min_positive_conf),
                expect_citation_to(CV_PDF_HINT),
                expect_keyword_any("python", "javascript", "react", "fastapi", "node"),
            ],
        ),
        Case(
            id="positive_companies",
            question="What companies has Jayesh worked at?",
            kind="positive",
            checks=[
                expect_not_refused(),
                expect_min_confidence(min_positive_conf),
                expect_citation_to(CV_PDF_HINT),
                expect_keyword_any("jio", "reliance"),
            ],
        ),
        Case(
            id="positive_education",
            question="What is Jayesh's educational background?",
            kind="positive",
            checks=[
                expect_not_refused(),
                expect_min_confidence(min_positive_conf),
                expect_citation_to(CV_PDF_HINT),
                expect_keyword_any("bits pilani", "pillai", "computer science", "m.tech"),
            ],
        ),
        Case(
            id="positive_recent_project",
            question="Summarize Jayesh's most recent project from his CV.",
            kind="positive",
            checks=[
                expect_not_refused(),
                expect_min_confidence(min_positive_conf),
                expect_citation_to(CV_PDF_HINT),
                expect_keyword_any("rag", "llm", "policy", "genai", "evaluation"),
            ],
        ),
        Case(
            id="positive_synthesis_role",
            question=(
                "Based on his CV, what technical skills make Jayesh suitable for "
                "an AI/RAG engineer role?"
            ),
            kind="positive",
            checks=[
                expect_not_refused(),
                expect_min_confidence(min_positive_conf),
                expect_citation_to(CV_PDF_HINT),
                expect_keyword_any("rag", "llm", "embedding", "retrieval", "genai"),
            ],
        ),
        Case(
            id="positive_summary_format",
            question="Give a 3-bullet career summary for Jayesh.",
            kind="positive",
            checks=[
                expect_not_refused(),
                expect_min_confidence(min_positive_conf),
                expect_citation_to(CV_PDF_HINT),
                expect_keyword_any("-", "*", "•"),  # bulleted list
            ],
        ),
        # ── ADVERSARIAL: must refuse, low confidence ──
        Case(
            id="adv_einstein",
            question="Who is Albert Einstein?",
            kind="adversarial",
            checks=[
                expect_refused(),
                expect_max_confidence(0.40),
            ],
        ),
        Case(
            id="adv_capital_france",
            question="What is the capital of France?",
            kind="adversarial",
            checks=[
                expect_refused(),
                expect_max_confidence(0.40),
            ],
        ),
        Case(
            id="adv_jayesh_address",
            question="What is Jayesh's home address?",
            kind="adversarial",
            checks=[
                expect_refused(),
                expect_max_confidence(0.40),
            ],
        ),
        Case(
            id="adv_jayesh_salary",
            question="What is Jayesh's exact salary in INR?",
            kind="adversarial",
            checks=[
                expect_refused(),
                expect_max_confidence(0.40),
            ],
        ),
        # ── EDGE ──
        Case(
            id="edge_empty",
            question="",
            kind="edge",
            checks=[
                # Either FastAPI 422 or backend refusal — both are acceptable.
            ],
            expect_status=-1,  # accept any
        ),
        Case(
            id="edge_multipart",
            question="What languages does Jayesh know AND list his projects?",
            kind="edge",
            checks=[
                expect_not_refused(),
                expect_min_confidence(min_positive_conf),
                expect_citation_to(CV_PDF_HINT),
                expect_keyword_any("python", "javascript", "node", "react"),
                expect_keyword_any("rag", "llm", "policy", "genai", "evaluation"),
            ],
        ),
    ]


# ──────────────────────────────────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────────────────────────────────
def run_case(client: httpx.Client, base_url: str, case: Case) -> tuple[bool, dict, list[str]]:
    """Run one case, return (passed, raw_response_or_meta, [check_details])."""
    payload = {"question": case.question, "include_citations": True}
    payload.update(case.request_overrides)
    t0 = time.monotonic()
    try:
        r = client.post(f"{base_url}/query", json=payload, timeout=120.0)
    except Exception as exc:
        return False, {"error": str(exc)}, [f"transport error: {exc}"]
    latency_ms = int((time.monotonic() - t0) * 1000)

    if case.expect_status not in (-1, r.status_code):
        try:
            body = r.json()
        except Exception:
            body = {"raw": r.text[:200]}
        return (
            False,
            body,
            [f"HTTP {r.status_code} != expected {case.expect_status} ({latency_ms} ms)"],
        )

    if case.id == "edge_empty":
        # Accept anything reasonable: 4xx/422 OR a refusal.
        try:
            body = r.json()
        except Exception:
            body = {"raw": r.text[:200]}
        if 400 <= r.status_code < 500:
            return True, body, [f"HTTP {r.status_code} on empty query (acceptable)"]
        ans = (body.get("answer") or "").lower()
        if REFUSAL_PHRASE.lower() in ans:
            return True, body, ["refused empty query (acceptable)"]
        return (
            False,
            body,
            [
                f"empty-query case neither refused nor 4xx; status={r.status_code}, "
                f"answer={body.get('answer', '')[:80]!r}"
            ],
        )

    try:
        body = r.json()
    except Exception:
        return False, {"raw": r.text[:300]}, [f"non-json response (status {r.status_code})"]

    details: list[str] = [f"HTTP {r.status_code}, {latency_ms} ms"]
    all_ok = True
    for check in case.checks:
        ok, msg = check(body)
        details.append(("[ok]  " if ok else "[fail] ") + msg)
        if not ok:
            all_ok = False
    return all_ok, body, details


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-url", default="http://localhost:8000")
    p.add_argument("--only", help="Run only the case with this id")
    p.add_argument(
        "--min-positive-conf",
        type=float,
        default=0.40,
        help="Confidence floor for positive cases (defaults to settings.CONFIDENCE_THRESHOLD)",
    )
    p.add_argument("--json", action="store_true", help="Emit a JSON report on stdout")
    args = p.parse_args(argv)

    cases = build_cases(min_positive_conf=args.min_positive_conf)
    if args.only:
        cases = [c for c in cases if c.id == args.only]
        if not cases:
            print(f"no case matched --only={args.only!r}", file=sys.stderr)
            return 2

    # Health check first; surface a clear error before burning tokens.
    with httpx.Client(timeout=15.0) as client:
        try:
            h = client.get(f"{args.base_url}/health")
            h.raise_for_status()
        except Exception as exc:
            print(f"backend healthcheck failed at {args.base_url}: {exc}", file=sys.stderr)
            return 3

    total = len(cases)
    passed = 0
    report: list[dict] = []
    with httpx.Client() as client:
        for case in cases:
            ok, body, details = run_case(client, args.base_url, case)
            status = "PASS" if ok else "FAIL"
            print(f"[{status}] {case.kind:>11s}  {case.id}  :: {case.question!r}")
            for d in details:
                print(f"        {d}")
            ans = (body.get("answer") or "")[:200].replace("\n", " | ")
            if ans:
                print(f"        answer> {ans}")
            print()
            if ok:
                passed += 1
            report.append(
                {
                    "id": case.id,
                    "kind": case.kind,
                    "question": case.question,
                    "passed": ok,
                    "details": details,
                    "answer": body.get("answer"),
                    "confidence": body.get("confidence"),
                    "refused": body.get("refused"),
                    "citations": [
                        {
                            "pdf_name": c.get("pdf_name"),
                            "page_number": c.get("page_number"),
                            "score": c.get("score"),
                        }
                        for c in (body.get("citations") or [])[:3]
                    ],
                }
            )

    print(f"=== {passed}/{total} passed ===")
    if args.json:
        print(json.dumps({"passed": passed, "total": total, "cases": report}, indent=2))

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
