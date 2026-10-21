"""
Domain logic for label normalisation and provider name deduplication (F-12 ERD 2.1, 2.6).
"""

from __future__ import annotations

import re
import unicodedata


def normalise_label(label: str) -> str:
    """
    Normalises a printed label to a canonical slug:
    e.g. "Illustration 12", "Ill. 12", "Illustration-12" -> "ill-12"
         "Q.7(a)", "Question 7a" -> "q-7a"
         "Example 3", "Ex. 3" -> "ex-3"
         "Exercise 4" -> "exer-4"
         "TYK 5", "Test Your Knowledge 5" -> "tyk-5"
         "Practical 2", "Problem 2" -> "practical-2"
    """
    if not label:
        return ""

    s = label.strip().lower()
    # Normalize unicode
    s = unicodedata.normalize("NFKD", s)

    # Prefix mappings
    prefix_patterns = [
        (r"^(?:illustration|illustrations|ill\.?|il\.)\s*[-_.:]?\s*", "ill-"),
        (r"^(?:exercise|exercises|exer\.?)\s*[-_.:]?\s*", "exer-"),
        (r"^(?:example|examples|ex\.?)\s*[-_.:]?\s*", "ex-"),
        (r"^(?:question|questions|q\.?)\s*[-_.:]?\s*", "q-"),
        (r"^(?:test\s+your\s+knowledge|tyk)\s*[-_.:]?\s*", "tyk-"),
        (r"^(?:practical\s+(?:problem|question)?|problem)\s*[-_.:]?\s*", "practical-"),
        (r"^(?:case\s+study|case)\s*[-_.:]?\s*", "case-"),
        (r"^(?:true[\s/_-]+false|t/f)\s*[-_.:]?\s*", "tf-"),
    ]

    matched_prefix = None
    rest = s
    for pattern, canon_prefix in prefix_patterns:
        m = re.match(pattern, s)
        if m:
            matched_prefix = canon_prefix
            rest = s[m.end():]
            break

    # Clean up rest: keep alphanumeric and lowercase
    rest_clean = re.sub(r"[^a-z0-9]+", "", rest)

    if matched_prefix:
        return f"{matched_prefix}{rest_clean}"

    # Generic slug fallback
    slug = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return slug


def extract_ordinal(label: str) -> int | None:
    """
    Extracts the primary integer ordinal from a label if present:
    e.g. "Illustration 12" -> 12, "Q.7(a)" -> 7, "Example 3" -> 3.
    """
    if not label:
        return None
    m = re.search(r"\b(\d+)\b", label)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None


def normalise_provider_name(name: str) -> str:
    """
    Normalises a provider name for deduplication:
    Lower case, ASCII, punctuation and common words removed:
    ('classes', 'academy', 'institute', 'tutorials', 'commerce', 'ca', 'cs', 'cma').
    """
    if not name:
        return ""

    s = name.strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = re.sub(r"[^\w\s]", " ", s)

    words = s.split()
    stop_words = {
        "classes", "academy", "institute", "tutorials", "tutorial",
        "commerce", "ca", "cs", "cma", "coaching", "learning", "education",
        "pvt", "ltd", "private", "limited", "the", "and", "&",
    }
    filtered = [w for w in words if w not in stop_words]
    if not filtered:
        filtered = words

    return "".join(filtered)
