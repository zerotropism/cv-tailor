"""BM25: a lexical score with no model. Ranking uses it to preselect the CVs the model scores."""

import math
import re
import unicodedata
from collections import Counter
from collections.abc import Mapping

K1 = 1.5
B = 0.75


def tokens(text: str) -> list[str]:
    """Lowercase words without accents: 'Ingénieur' and 'ingenieur' are the same token."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.findall(r"[a-z0-9]+", plain)


def bm25_scores(query: str, documents: Mapping[str, str]) -> dict[str, float]:
    """Okapi BM25 score of each document for the query, the job description."""
    bags = {name: Counter(tokens(text)) for name, text in documents.items()}
    lengths = {name: sum(bag.values()) for name, bag in bags.items()}
    average_length = sum(lengths.values()) / len(lengths)
    count = len(bags)
    document_frequency = Counter(term for bag in bags.values() for term in bag)

    def idf(term: str) -> float:
        n = document_frequency[term]
        return math.log(1 + (count - n + 0.5) / (n + 0.5))

    query_terms = set(tokens(query))
    scores = {}
    for name, bag in bags.items():
        norm = K1 * (1 - B + B * lengths[name] / average_length)
        scores[name] = sum(
            idf(term) * bag[term] * (K1 + 1) / (bag[term] + norm)
            for term in query_terms
            if term in bag
        )
    return scores


def lexical_ranking(query: str, documents: Mapping[str, str]) -> list[str]:
    """Document names by decreasing BM25 score; ties keep the input order."""
    scores = bm25_scores(query, documents)
    return sorted(documents, key=lambda name: scores[name], reverse=True)
