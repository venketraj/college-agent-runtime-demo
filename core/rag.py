"""Tiny RAG: chunk the handbook, embed with Ollama (nomic-embed-text), cosine search in numpy.

Falls back to TF-IDF keyword vectors if the embedding model isn't available, so the demo still runs.
"""
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import ollama

from .models import EMBED_MODEL, OLLAMA_HOST

HANDBOOK = Path(__file__).resolve().parent.parent / "data" / "handbook"


@dataclass
class Chunk:
    source: str
    section: str
    text: str


def load_chunks(max_chars: int = 700) -> list[Chunk]:
    chunks = []
    for f in sorted(HANDBOOK.glob("*.md")):
        for sec in re.split(r"\n(?=## )", f.read_text(encoding="utf-8")):
            if not sec.startswith("## "):
                continue
            title, _, body = sec.partition("\n")
            buf = ""
            for para in body.strip().split("\n"):
                if len(buf) + len(para) > max_chars and buf:
                    chunks.append(Chunk(f.name, title[3:].strip(), buf.strip()))
                    buf = ""
                buf += para + "\n"
            if buf.strip():
                chunks.append(Chunk(f.name, title[3:].strip(), buf.strip()))
    return chunks


class Index:
    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        docs = [f"{c.section}\n{c.text}" for c in chunks]
        try:
            self.client = ollama.Client(host=OLLAMA_HOST)
            self.vecs = self._embed([f"search_document: {d}" for d in docs])
            self.method = f"embeddings · {EMBED_MODEL} · {self.vecs.shape[1]} dims"
        except Exception:
            self.client = None
            self._fit_tfidf(docs)
            self.method = "keyword TF-IDF (embedding model not available)"

    def _embed(self, texts):
        v = np.array(self.client.embed(model=EMBED_MODEL, input=texts).embeddings, dtype=np.float32)
        return v / np.linalg.norm(v, axis=1, keepdims=True)

    # --- TF-IDF fallback
    @staticmethod
    def _tok(t):
        return re.findall(r"[a-z0-9]+", t.lower())

    def _fit_tfidf(self, docs):
        toks = [self._tok(d) for d in docs]
        df = Counter(w for t in toks for w in set(t))
        self.vocab = {w: i for i, w in enumerate(df)}
        self.idf = np.array([math.log((1 + len(docs)) / (1 + df[w])) + 1 for w in self.vocab], dtype=np.float32)
        self.vecs = np.stack([self._tfidf(t) for t in toks])

    def _tfidf(self, toks):
        v = np.zeros(len(self.vocab), dtype=np.float32)
        for w, c in Counter(toks).items():
            if w in self.vocab:
                v[self.vocab[w]] = c
        v *= self.idf
        n = np.linalg.norm(v)
        return v / n if n else v

    def search(self, query: str, k: int = 4) -> list[tuple[float, Chunk]]:
        q = self._embed([f"search_query: {query}"])[0] if self.client else self._tfidf(self._tok(query))
        scores = self.vecs @ q
        top = np.argsort(-scores)[:k]
        return [(float(scores[i]), self.chunks[i]) for i in top]


def format_context(hits) -> str:
    return "\n\n".join(f"[{i + 1}] ({c.source} › {c.section})\n{c.text}" for i, (_, c) in enumerate(hits))
