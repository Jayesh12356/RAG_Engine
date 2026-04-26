"""BM25 sparse encoder used by the hybrid retrieval path.

Persisting the encoder's *corpus statistics* (IDF + average doc length) to
disk is critical: at query time we need the exact same scoring as ingest
to produce vectors that align with what was upserted into Qdrant. A new
``BM25SparseEncoder.load_or_default`` helper does that lookup on every
search call; ingestion writes a fresh snapshot via ``save``.

The encoded vectors are dictionaries of ``{token_id: float}`` where
``token_id`` is a stable, dimension-bounded hash of the token. The bound
(``DIM``) is generous (50 000) which is well within Qdrant's sparse
vector limits and avoids realistic collisions for an English IT corpus.
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

import structlog
from rank_bm25 import BM25Okapi

logger = structlog.get_logger(__name__)


DIM = 50_000


def _token_id(token: str) -> int:
    return abs(hash(token)) % DIM


def _tokenize(text: str) -> list[str]:
    return [t for t in (text or "").lower().split() if t]


class BM25SparseEncoder:
    """BM25 encoder with optional on-disk persistence."""

    def __init__(self) -> None:
        self.bm25: BM25Okapi | None = None

    # ------------------------------------------------------------------ fit
    def fit(self, corpus: Iterable[str]) -> None:
        tokenized_corpus = [_tokenize(doc) for doc in corpus]
        if not tokenized_corpus:
            tokenized_corpus = [["placeholder"]]
        self.bm25 = BM25Okapi(tokenized_corpus)

    # ------------------------------------------------------------------ encode
    def encode(self, text: str) -> dict[int, float]:
        if self.bm25 is None:
            return {}
        tokens = _tokenize(text)
        if not tokens:
            return {}
        sparse_vec: dict[int, float] = {}
        doc_len = len(tokens)
        avgdl = self.bm25.avgdl or 1.0
        k1 = self.bm25.k1
        b = self.bm25.b
        idf_table = self.bm25.idf
        for token in set(tokens):
            idf = idf_table.get(token)
            if not idf:
                continue
            tf = tokens.count(token)
            num = tf * (k1 + 1)
            den = tf + k1 * (1 - b + b * doc_len / avgdl)
            score = idf * (num / max(den, 1e-9))
            if score > 0:
                tid = _token_id(token)
                # Keep the strongest contribution if two tokens collide.
                prev = sparse_vec.get(tid)
                if prev is None or score > prev:
                    sparse_vec[tid] = float(score)
        return sparse_vec

    def encode_batch(self, texts: list[str]) -> list[dict[int, float]]:
        return [self.encode(t) for t in texts]

    # ------------------------------------------------------------------ persistence
    def save(self, directory: str) -> None:
        """Persist IDF table and ``avgdl`` so query-time scoring matches ingest."""
        if self.bm25 is None:
            return
        dir_path = Path(directory)
        dir_path.mkdir(parents=True, exist_ok=True)
        payload = {
            "idf": dict(self.bm25.idf),
            "avgdl": float(self.bm25.avgdl or 1.0),
            "k1": float(self.bm25.k1),
            "b": float(self.bm25.b),
            "dim": DIM,
        }
        snapshot = dir_path / "bm25.json"
        snapshot.write_text(json.dumps(payload), encoding="utf-8")
        logger.info("bm25.save", path=str(snapshot), tokens=len(payload["idf"]))  # type: ignore[arg-type]

    @classmethod
    def load(cls, directory: str) -> BM25SparseEncoder | None:
        snapshot = Path(directory) / "bm25.json"
        if not snapshot.exists():
            return None
        try:
            data = json.loads(snapshot.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("bm25.load.failed", error=str(exc))
            return None
        encoder = cls()
        encoder.bm25 = _RestoredBM25(
            idf=data.get("idf") or {},
            avgdl=float(data.get("avgdl") or 1.0),
            k1=float(data.get("k1") or 1.5),
            b=float(data.get("b") or 0.75),
        )
        return encoder

    @classmethod
    def load_or_default(cls, directory: str) -> BM25SparseEncoder:
        """Return a loaded encoder if a snapshot exists, otherwise an empty one.

        An empty encoder returns ``{}`` from ``encode`` so the caller can
        gracefully fall back to dense-only retrieval until the first ingest
        writes a real snapshot.
        """
        loaded = cls.load(directory)
        if loaded is not None:
            return loaded
        encoder = cls()
        return encoder


class _RestoredBM25:
    """Lightweight stand-in for ``BM25Okapi`` rebuilt from a snapshot.

    Only the attributes ``encode`` reads (``idf``, ``avgdl``, ``k1``, ``b``)
    are required; the corpus matrix is irrelevant at query time.
    """

    __slots__ = ("idf", "avgdl", "k1", "b")

    def __init__(self, idf: dict, avgdl: float, k1: float, b: float) -> None:
        self.idf = idf
        self.avgdl = avgdl
        self.k1 = k1
        self.b = b
