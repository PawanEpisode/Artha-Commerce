"""
Question deduplication fingerprints, SimHash, and banding (F-06 ERD 2.10).
"""

from __future__ import annotations

import hashlib
import re


def normalise_for_fingerprint(text: str) -> str:
    """
    Normalises text for exact and template fingerprinting:
    - Lower case
    - Remove LaTeX math delimiters ($ and $$)
    - Remove LaTeX spacing commands
    - Collapse whitespace
    - Numbers kept
    """
    if not text:
        return ""

    s = text.lower()
    # Remove math delimiters
    s = s.replace("$$", " ").replace("$", " ")
    # Strip LaTeX commands like \text{itc} -> itc or \mathbf{x} -> x
    s = re.sub(r"\\[a-zA-Z]+(?:\{([^}]*)\})?", r" \1 ", s)
    # Remove common latex spacing commands
    s = re.sub(r"\\[,;!]|\\quad|\\qquad", " ", s)
    # Replace markdown punctuation/formatting chars with space
    s = re.sub(r"[\*\_#`~\[\]\(\)\{\}\?\:\;\,\.\+\=\-\/\\]", " ", s)
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s


def compute_fp_exact(stem_md: str, option_bodies: list[str] | None = None, key_str: str = "") -> str:
    """
    SHA-256 of normalised stem plus sorted normalised options plus key.
    """
    norm_stem = normalise_for_fingerprint(stem_md)
    norm_opts = sorted(normalise_for_fingerprint(opt) for opt in (option_bodies or []) if opt)
    combined = f"{norm_stem}::options:{'|'.join(norm_opts)}::key:{key_str.strip().lower()}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def compute_fp_template(stem_md: str, option_bodies: list[str] | None = None, key_str: str = "") -> str:
    """
    Same as fp_exact with every number replaced by '#': same question with different figures ("variant").
    """
    norm_stem = normalise_for_fingerprint(stem_md)
    norm_opts = sorted(normalise_for_fingerprint(opt) for opt in (option_bodies or []) if opt)
    combined = f"{norm_stem}::options:{'|'.join(norm_opts)}::key:{key_str.strip().lower()}"
    # Replace numbers with #
    templated = re.sub(r"\b\d+(?:\.\d+)?\b|\d+", "#", combined)
    return hashlib.sha256(templated.encode("utf-8")).hexdigest()


def _to_signed_16(val: int) -> int:
    """Convert unsigned 16-bit integer (0..0xFFFF) to signed 16-bit (-32768..32767)."""
    return val if val < 0x8000 else val - 0x10000


def _to_signed_64(val: int) -> int:
    """Convert unsigned 64-bit integer to signed 64-bit for Django BigIntegerField."""
    return val if val < (1 << 63) else val - (1 << 64)


def simhash_64(text: str) -> int:
    """
    Computes a 64-bit SimHash of word 3-grams in the text.
    Returns an unsigned 64-bit integer.
    """
    norm = normalise_for_fingerprint(text)
    words = re.findall(r"\w+", norm)

    # Generate 3-grams
    if len(words) >= 3:
        grams = [" ".join(words[i : i + 3]) for i in range(len(words) - 2)]
    elif words:
        # Fallback to word unigrams or character 3-grams if fewer than 3 words
        grams = words if len(norm) < 6 else [norm[i : i + 3] for i in range(len(norm) - 2)]
    else:
        return 0

    v = [0] * 64
    for gram in grams:
        digest = hashlib.sha256(gram.encode("utf-8")).digest()[:8]
        gram_hash = int.from_bytes(digest, byteorder="big")
        for i in range(64):
            bit = (gram_hash >> (63 - i)) & 1
            if bit == 1:
                v[i] += 1
            else:
                v[i] -= 1

    simhash = 0
    for i in range(64):
        if v[i] > 0:
            simhash |= 1 << (63 - i)

    return simhash


def compute_simhash_and_bands(text: str) -> tuple[int, int, int, int, int]:
    """
    Computes 64-bit SimHash and the four 16-bit bands (b0..b3).
    Returns (signed_simhash, b0, b1, b2, b3) formatted for Django integer fields.
    """
    u_simhash = simhash_64(text)
    b0_u = (u_simhash >> 48) & 0xFFFF
    b1_u = (u_simhash >> 32) & 0xFFFF
    b2_u = (u_simhash >> 16) & 0xFFFF
    b3_u = u_simhash & 0xFFFF

    return (
        _to_signed_64(u_simhash),
        _to_signed_16(b0_u),
        _to_signed_16(b1_u),
        _to_signed_16(b2_u),
        _to_signed_16(b3_u),
    )


def hamming_distance(h1: int, h2: int) -> int:
    """Calculates Hamming distance between two 64-bit integer hashes."""
    # Convert signed 64 to unsigned 64 if needed
    u1 = h1 & 0xFFFFFFFFFFFFFFFF
    u2 = h2 & 0xFFFFFFFFFFFFFFFF
    return bin(u1 ^ u2).count("1")
