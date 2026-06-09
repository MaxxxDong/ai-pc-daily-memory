from __future__ import annotations

import math
import re
from collections import Counter
from typing import Iterable

from source_loader import SourceItem


WORD_RE = re.compile(r"[A-Za-z0-9_+#.-]+|[\u4e00-\u9fff]")


def tokenize(text: str) -> list[str]:
    return [match.group(0).lower() for match in WORD_RE.finditer(text or "")]


def retrieve_context(query: str, sources: Iterable[SourceItem], limit: int = 8) -> list[SourceItem]:
    source_list = list(sources)
    if not source_list:
        return []
    query_tokens = tokenize(query)
    if not query_tokens:
        return sorted(source_list, key=lambda source: len(source.text), reverse=True)[:limit]

    docs = [tokenize(source.text) for source in source_list]
    avg_len = sum(len(doc) for doc in docs) / max(1, len(docs))
    dfs = Counter(token for doc in docs for token in set(doc))
    query_counts = Counter(query_tokens)

    scored: list[tuple[float, SourceItem]] = []
    for source, tokens in zip(source_list, docs):
        counts = Counter(tokens)
        score = 0.0
        doc_len = max(1, len(tokens))
        for token, query_weight in query_counts.items():
            tf = counts[token]
            if tf <= 0:
                continue
            idf = math.log((len(docs) - dfs[token] + 0.5) / (dfs[token] + 0.5) + 1.0)
            bm25 = (tf * 2.2) / (tf + 1.2 * (0.25 + 0.75 * doc_len / max(1.0, avg_len)))
            score += idf * bm25 * query_weight
        title_tokens = set(tokenize(source.title))
        title_bonus = 0.25 * len(title_tokens.intersection(query_counts))
        if score or title_bonus:
            scored.append((score + title_bonus, source))

    if not scored:
        return sorted(source_list, key=lambda source: len(source.text), reverse=True)[:limit]
    return [source for _, source in sorted(scored, key=lambda item: item[0], reverse=True)[:limit]]

