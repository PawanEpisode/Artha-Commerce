#!/usr/bin/env python3
"""Quality gate for Recall seed JSON files (schema 1).

Fails (exit 1) on:
  * duplicate item refs (within a file or across the files checked)
  * section / case_law items with no reference_keys
  * malformed reference_keys (not lower-case, > 80 chars, > 20 per item)
  * over-length fields (line fields > 200 chars, markdown fields > 4,000 chars)
  * items with no importance, or importance outside mandatory/important/bullet
  * near-duplicate prompts inside one deck
  * (optional) long verbatim runs copied from source text: pass --source-text-dir
    pointing at a folder of *.txt extractions. The source text is read only for
    comparison and is never written anywhere.

Usage:
  python scripts/recall-seed-check.py [files...]            # default: all *.json in seed/cma-final-paper13/
  python scripts/recall-seed-check.py --source-text-dir DIR [--run-words 12] [files...]
"""
import argparse
import difflib
import glob
import json
import os
import re
import sys

SEED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "apps", "api", "modules", "recall", "seed")
IMPORTANCE = {"mandatory", "important", "bullet"}
LINE_MAX, MD_MAX = 200, 4000
KEY_MAX, KEYS_PER_ITEM = 80, 20
KEY_RE = re.compile(r"^[a-z0-9][a-z0-9:._()/\-]*$")
NEAR_DUP = 0.90


def is_md(name):
    return name.endswith("_md")


def prompt_of(item):
    f = item.get("fields", {})
    for k in ("prompt_md", "text_md", "term", "case_name", "mnemonic", "title"):
        if f.get(k):
            return k, f[k]
    return None, ""


def norm_words(text):
    return re.findall(r"[a-z0-9₹%]+", text.lower())


def load_source_shingles(dirpath, n):
    shingles = set()
    for p in sorted(glob.glob(os.path.join(dirpath, "*.txt"))):
        with open(p, encoding="utf-8", errors="ignore") as fh:
            w = norm_words(fh.read())
        for i in range(len(w) - n + 1):
            shingles.add(" ".join(w[i:i + n]))
    return shingles


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--source-text-dir")
    ap.add_argument("--run-words", type=int, default=12)
    a = ap.parse_args()
    files = a.files or sorted(glob.glob(os.path.join(SEED_DIR, "cma-final-paper13", "*.json")))
    if not files:
        print("no files to check")
        return 1
    shingles = load_source_shingles(a.source_text_dir, a.run_words) if a.source_text_dir else None
    errors, seen_refs, total = [], {}, 0

    for path in files:
        base = os.path.basename(path)
        data = json.load(open(path, encoding="utf-8"))
        for deck in data.get("decks", []):
            slug = deck.get("slug")
            prompts = []
            for it in deck.get("items", []):
                total += 1
                ref = it.get("ref")
                where = f"{base}:{ref}"
                if ref in seen_refs:
                    errors.append(f"{where}: duplicate ref (also in {seen_refs[ref]})")
                seen_refs[ref] = base
                if it.get("importance") not in IMPORTANCE:
                    errors.append(f"{where}: missing or invalid importance {it.get('importance')!r}")
                keys = it.get("reference_keys") or []
                if it.get("kind") in ("section", "case_law") and not keys:
                    errors.append(f"{where}: {it.get('kind')} item has no reference_keys")
                if len(keys) > KEYS_PER_ITEM:
                    errors.append(f"{where}: {len(keys)} reference_keys (max {KEYS_PER_ITEM})")
                for k in keys:
                    if len(k) > KEY_MAX or not KEY_RE.match(k):
                        errors.append(f"{where}: bad reference key {k!r}")
                for fname, val in (it.get("fields") or {}).items():
                    if not isinstance(val, str):
                        continue
                    lim = MD_MAX if is_md(fname) else LINE_MAX
                    if len(val) > lim:
                        errors.append(f"{where}: field {fname} is {len(val)} chars (max {lim})")
                    if shingles is not None:
                        w = norm_words(val)
                        for i in range(len(w) - a.run_words + 1):
                            if " ".join(w[i:i + a.run_words]) in shingles:
                                errors.append(f"{where}: field {fname} has a {a.run_words}+ word run copied from source text near: {' '.join(w[i:i + a.run_words])!r}")
                                break
                k, p = prompt_of(it)
                prompts.append((ref, " ".join(norm_words(p))))
            for i in range(len(prompts)):
                for j in range(i + 1, len(prompts)):
                    ri, pi = prompts[i]
                    rj, pj = prompts[j]
                    if pi and pj and difflib.SequenceMatcher(None, pi, pj).ratio() >= NEAR_DUP:
                        errors.append(f"{base} [{slug}]: near-duplicate prompts {ri} / {rj}")

    print(f"checked {len(files)} file(s), {total} item(s)")
    for e in errors:
        print("FAIL", e)
    print("OK" if not errors else f"{len(errors)} problem(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
