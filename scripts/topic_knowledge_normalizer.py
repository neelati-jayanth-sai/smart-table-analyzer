from __future__ import annotations

import hashlib
import re
from pathlib import PurePosixPath

CAMEL_PATTERN = re.compile(r"([a-z0-9])([A-Z])")
LINK_PATTERN = re.compile(r"\[([^\]]+)\]\([^\)]+\)")
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+")
MAX_SLUG_LENGTH = 80
SKIP_LABELS = {"index", "overview", "readme"}
SKIP_PATH_SEGMENTS = {
    "blog",
    "doc",
    "docs",
    "glossary",
    "post",
    "posts",
    "site",
    "static",
    "user-guide",
}
STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "into",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "what",
    "when",
    "why",
    "with",
}


def topic_candidates(raw_path: str, heading_path_text: str) -> list[tuple[str, str, str]]:
    candidates = []
    seen = set()
    for phrase, kind in _path_phrases(raw_path) + _heading_phrases(heading_path_text):
        normalized = _normalize_topic(phrase, kind)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        candidates.append(normalized)
    return candidates


def _path_phrases(raw_path: str) -> list[tuple[str, str]]:
    path = PurePosixPath(raw_path)
    phrases = []
    for part in path.parts[:-1]:
        if part.lower() in SKIP_PATH_SEGMENTS:
            continue
        phrases.append((part, "path"))
    phrases.append((path.stem or path.name, "stem"))
    return phrases


def _heading_phrases(heading_path_text: str) -> list[tuple[str, str]]:
    parts = []
    for part in heading_path_text.split(" > "):
        phrase = part.strip()
        if phrase and phrase.lower() not in SKIP_LABELS:
            parts.append((phrase, "heading"))
    return parts


def _normalize_topic(phrase: str, kind: str) -> tuple[str, str, str] | None:
    display = _clean_phrase(phrase)
    if not display:
        return None
    prepared = CAMEL_PATTERN.sub(r"\1 \2", display)
    prepared = prepared.replace("/", " ").replace("_", " ").replace("-", " ").replace(".", " ")
    tokens = [token.lower() for token in TOKEN_PATTERN.findall(prepared)]
    if not tokens:
        return None
    filtered = [token for token in tokens if token not in STOPWORDS and not _drop_number(token, len(tokens) > 1)]
    if kind == "path" and len(filtered) == 1 and filtered[0] in SKIP_PATH_SEGMENTS:
        return None
    normalized_tokens = filtered or [token for token in tokens if not _drop_number(token, len(tokens) > 1)]
    slug = _stable_slug(normalized_tokens)
    if not slug or slug in SKIP_LABELS:
        return None
    return slug, display, kind


def _clean_phrase(phrase: str) -> str:
    display = LINK_PATTERN.sub(r"\1", phrase.strip())
    display = display.replace("`", "")
    return " ".join(display.split())


def _stable_slug(tokens: list[str]) -> str:
    slug = "-".join(tokens)
    if len(slug) <= MAX_SLUG_LENGTH:
        return slug
    digest = hashlib.sha1(slug.encode("utf-8")).hexdigest()[:12]
    return f"{slug[: MAX_SLUG_LENGTH - 13].rstrip('-')}-{digest}"


def _drop_number(token: str, mixed_phrase: bool) -> bool:
    return mixed_phrase and token.isdigit()
