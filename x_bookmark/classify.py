"""Offline topic classifier (heuristics). Optional LLM hook via env.

Default path is keyword scoring so Vault Scout can run with no network.
Low-confidence and ambiguous posts go to the `needs-review` Doc.

To plug a better classifier later:
  export X_BOOKMARK_CLASSIFIER=my_pkg.mod:classify
where `classify(post: dict) -> x_bookmark.classify.Classification`.
"""

from __future__ import annotations

import importlib
import os
import re
from dataclasses import dataclass
from typing import Callable, Iterable, Optional

from x_bookmark.constants import FILE_CONFIDENCE_THRESHOLD, NEEDS_REVIEW, TOPIC_DOCS

# Longer phrases first. Values are weights.
TOPIC_KEYWORDS: dict[str, tuple[tuple[str, int], ...]] = {
    "AI": (
        ("large language model", 3),
        ("machine learning", 3),
        ("deep learning", 3),
        ("neural net", 2),
        ("chatgpt", 3),
        ("openai", 2),
        ("anthropic", 2),
        ("huggingface", 2),
        ("hugging face", 2),
        ("transformer", 2),
        ("inference", 1),
        ("embedding", 2),
        ("fine-tun", 2),
        ("fine tun", 2),
        ("copilot", 2),
        ("llm", 3),
        ("gpt", 3),
        ("claude", 2),
        ("gemini", 1),
        ("prompt", 1),
        ("agentic", 2),
        ("diffusion", 1),
        ("rag", 2),
        ("ai", 2),
    ),
    "Career": (
        ("job search", 3),
        ("job offer", 3),
        ("staff engineer", 2),
        ("performance review", 2),
        ("linkedin", 1),
        ("recruiter", 3),
        ("interview", 3),
        ("hiring", 3),
        ("layoff", 2),
        ("resume", 3),
        ("career", 3),
        ("promotion", 2),
        ("salary", 2),
        ("workplace", 1),
        ("headcount", 2),
        ("manager", 1),
        ("hiring loop", 3),
        ("job", 1),
        ("cv", 2),
    ),
    "Fashion": (
        ("fashion week", 3),
        ("streetwear", 3),
        ("ready-to-wear", 3),
        ("couture", 3),
        ("runway", 3),
        ("wardrobe", 2),
        ("designer", 1),
        ("apparel", 2),
        ("garment", 2),
        ("outfit", 3),
        ("sneaker", 2),
        ("fashion", 3),
        ("vogue", 2),
        ("tailor", 1),
        ("clothing", 2),
        ("dress", 1),
    ),
    "Markets": (
        ("interest rate", 2),
        ("federal reserve", 3),
        ("stock market", 3),
        ("bitcoin", 3),
        ("ethereum", 2),
        ("nasdaq", 3),
        ("futures", 2),
        ("inflation", 2),
        ("earnings", 2),
        ("trading", 2),
        ("trader", 2),
        ("crypto", 2),
        ("equity", 2),
        ("recession", 2),
        ("portfolio", 2),
        ("market", 2),
        ("s&p", 3),
        ("spx", 2),
        ("bond", 1),
        ("yield", 1),
        ("etf", 2),
        ("fed", 2),
        ("gdp", 2),
        ("btc", 2),
        ("eth", 1),
        ("stock", 2),
    ),
    "Media": (
        ("journalism", 3),
        ("journalist", 3),
        ("newsletter", 2),
        ("newsroom", 3),
        ("hollywood", 2),
        ("podcast", 3),
        ("youtube", 2),
        ("streaming", 2),
        ("publisher", 2),
        ("editorial", 2),
        ("reporter", 3),
        ("press", 1),
        ("media", 2),
        ("film", 1),
        ("news", 1),
        ("tv", 1),
    ),
    "Misc": (
        ("recipe", 3),
        ("cooking", 3),
        ("travel", 2),
        ("vacation", 2),
        ("concert", 2),
        ("garden", 2),
        ("football", 2),
        ("soccer", 2),
        ("music", 1),
        ("sport", 2),
        ("nba", 2),
        ("nfl", 2),
        ("pet", 1),
        ("cat", 1),
        ("dog", 1),
    ),
}

@dataclass(frozen=True)
class Classification:
    """Where a bookmark should land, plus topic tags for the Doc section."""

    doc: str
    topics: tuple[str, ...]
    confidence: int
    reason: str


def classify(post: dict) -> Classification:
    """Classify one export post. Uses X_BOOKMARK_CLASSIFIER if set."""
    override = _load_override()
    if override is not None:
        return override(post)
    return classify_heuristic(post)


def classify_heuristic(post: dict) -> Classification:
    text = _text_for_scoring(post)
    scores = {topic: _score(text, kws) for topic, kws in TOPIC_KEYWORDS.items()}
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    best_topic, best_score = ranked[0]
    second_topic, second_score = ranked[1]

    guessed = tuple(topic for topic, score in ranked if score > 0)
    confidence = _confidence_from_score(best_score)
    reason_hits = f"scores={ {k: v for k, v in ranked if v} }"

    if best_score <= 0:
        return Classification(
            doc=NEEDS_REVIEW,
            topics=(),
            confidence=25,
            reason="no keyword hits",
        )

    ambiguous = second_score > 0 and (best_score - second_score) < 2
    if ambiguous:
        return Classification(
            doc=NEEDS_REVIEW,
            topics=guessed[:2],
            confidence=min(confidence, 50),
            reason=f"ambiguous {best_topic} vs {second_topic}; {reason_hits}",
        )

    if confidence < FILE_CONFIDENCE_THRESHOLD:
        return Classification(
            doc=NEEDS_REVIEW,
            topics=(best_topic,),
            confidence=confidence,
            reason=f"low confidence for {best_topic}; {reason_hits}",
        )

    return Classification(
        doc=best_topic,
        topics=(best_topic,),
        confidence=confidence,
        reason=f"{best_topic} {reason_hits}",
    )


def _text_for_scoring(post: dict) -> str:
    parts = [
        str(post.get("text") or ""),
        str(post.get("author") or ""),
        str(post.get("author_name") or ""),
    ]
    return " ".join(parts).lower()


def _score(text: str, keywords: Iterable[tuple[str, int]]) -> int:
    score = 0
    for phrase, weight in keywords:
        if _contains(text, phrase):
            score += weight
    return score


def _contains(text: str, phrase: str) -> bool:
    if " " in phrase or "-" in phrase or "&" in phrase:
        return phrase in text
    if phrase == "ai":
        return bool(re.search(r"(?<![a-z])ai(?![a-z])", text))
    if len(phrase) <= 3:
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", text))
    return phrase in text


def _confidence_from_score(score: int) -> int:
    if score >= 6:
        return 95
    if score >= 4:
        return 90
    if score >= 3:
        return 85
    if score >= 2:
        return 75
    if score >= 1:
        return 70
    return 25


def _load_override() -> Optional[Callable[[dict], Classification]]:
    spec = os.environ.get("X_BOOKMARK_CLASSIFIER", "").strip()
    if not spec:
        return None
    module_name, _, func_name = spec.partition(":")
    if not module_name or not func_name:
        raise ValueError(
            "X_BOOKMARK_CLASSIFIER must be module:function, "
            f"got {spec!r}"
        )
    module = importlib.import_module(module_name)
    func = getattr(module, func_name)
    return func


def known_docs() -> tuple[str, ...]:
    return TOPIC_DOCS + (NEEDS_REVIEW,)
