"""Hybrid retrieval: BM25 (keywords) + cosine similarity (embeddings), fused with reciprocal rank fusion."""
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Document, DocumentChunk

TOKEN = re.compile(r"[\w\u0300-\u036F\u0600-\u06FF\u0900-\u0DFF]+")


def tokenize(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


@dataclass
class Hit:
    chunk_id: int
    document_id: str
    filename: str
    page: int | None
    text: str
    score: float


def bm25_scores(query: list[str], docs: list[list[str]], k1: float = 1.5, b: float = 0.75) -> list[float]:
    n = len(docs)
    if not query or n == 0:
        return [0.0] * n
    qset = set(query)
    avgdl = (sum(len(d) for d in docs) / n) or 1.0
    df: Counter[str] = Counter()
    per_doc: list[tuple[Counter[str], int]] = []
    for d in docs:
        counts = Counter(t for t in d if t in qset)
        per_doc.append((counts, len(d)))
        df.update(counts.keys())
    scores = []
    for counts, length in per_doc:
        s = 0.0
        for term, freq in counts.items():
            idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
            s += idf * freq * (k1 + 1) / (freq + k1 * (1 - b + b * length / avgdl))
        scores.append(s)
    return scores


def retrieve(
    db: Session,
    user_id: str,
    doc_ids: list[str],
    query: str,
    query_vec: np.ndarray | None,
    k: int,
    small_doc_chars: int,
) -> list[Hit]:
    if not doc_ids:
        return []
    rows = db.execute(
        select(
            DocumentChunk.id, DocumentChunk.document_id, DocumentChunk.ordinal,
            DocumentChunk.page, DocumentChunk.text, DocumentChunk.embedding,
        ).where(DocumentChunk.user_id == user_id, DocumentChunk.document_id.in_(doc_ids))
    ).all()
    if not rows:
        return []
    names = dict(db.execute(select(Document.id, Document.filename).where(Document.id.in_(doc_ids))).all())

    def hit(i: int, score: float) -> Hit:
        r = rows[i]
        return Hit(r.id, r.document_id, names.get(r.document_id, "document"), r.page, r.text, score)

    # Small corpus: the whole thing fits in the prompt, so send it in reading order (best for "summarise this").
    if sum(len(r.text) for r in rows) <= small_doc_chars:
        order = sorted(range(len(rows)), key=lambda i: (rows[i].document_id, rows[i].ordinal))
        return [hit(i, 0.0) for i in order]

    lex = bm25_scores(tokenize(query), [tokenize(r.text) for r in rows])
    lex_rank = [i for i in sorted(range(len(rows)), key=lambda i: -lex[i]) if lex[i] > 0][: k * 4]

    vec_rank: list[int] = []
    if query_vec is not None:
        usable = [i for i, r in enumerate(rows) if r.embedding and len(r.embedding) == query_vec.nbytes]
        if usable:
            matrix = np.vstack([np.frombuffer(rows[i].embedding, dtype=np.float32) for i in usable])
            sims = matrix @ query_vec
            vec_rank = [usable[j] for j in np.argsort(-sims)[: k * 4]]

    fused: dict[int, float] = defaultdict(float)
    for rank, i in enumerate(lex_rank):
        fused[i] += 1 / (60 + rank)
    for rank, i in enumerate(vec_rank):
        fused[i] += 1 / (60 + rank)
    best = sorted(fused, key=lambda i: -fused[i])[:k]
    return [hit(i, fused[i]) for i in best]
