import math
from collections import Counter
from typing import Iterable, Optional


def shannon_entropy(text: Optional[str]) -> float:
    if not text:
        return 0.0
    counts = Counter(text)
    total = sum(counts.values())
    if total == 0:
        return 0.0
    entropy = 0.0
    for c in counts.values():
        p = c / total
        entropy -= p * math.log2(p)
    return entropy


def avg_token_entropy(tokens: Iterable[str]) -> float:
    tokens = [t for t in tokens if t]
    if not tokens:
        return 0.0
    return sum(shannon_entropy(t) for t in tokens) / len(tokens)
