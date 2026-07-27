"""Resolve brand keys to a canonical brand.

`brand_key` normalizes a store name; it does not decide that two names are the
same business. Without that second step `starbucks` and `starbucks coffee` are
two brands with 57 and 79 malls, and neither number is Starbucks' reach.

Merging is deliberately **explicit**. The alias table is an allow-list read
from `registry/brand_aliases.json`; nothing merges unless it is written there.
Similarity is used only to *propose* candidates into the review file, never to
act, because similarity cannot tell these apart:

    mi store (14 malls)   vs  sm store (69 malls)     Xiaomi vs The SM Store
    bpi (61)              vs  bpi atm (21)            a branch is not an ATM

The first is a false positive an automatic merger would have taken; the second
is a distinction an earlier version of this project destroyed and had to undo.
An allow-list cannot make either mistake.
"""

from __future__ import annotations

import difflib
import json
from importlib import resources

import pandas as pd

# Only compare keys that are plausibly the same length, and only among brands
# with enough reach to matter. Both bounds exist to keep the proposal list
# short enough that a human will actually read it.
_MIN_REACH_TO_PROPOSE = 5
_SIMILARITY = 0.86


def load_aliases() -> dict[str, str]:
    """`{variant: canonical}`, read from the committed registry."""
    try:
        raw = resources.files("mallscape_scrape.registry").joinpath("brand_aliases.json").read_text()
    except FileNotFoundError:
        return {}
    doc = json.loads(raw)
    aliases: dict[str, str] = {}
    for canonical, variants in doc.get("aliases", {}).items():
        for variant in variants:
            if variant == canonical:
                continue
            aliases[variant] = canonical
    return aliases


def resolve(brand_keys: pd.Series) -> pd.Series:
    """Map each key to its canonical form, leaving unlisted keys untouched."""
    aliases = load_aliases()
    if not aliases:
        return brand_keys.copy()
    # One hop only. A chain of aliases would make the result depend on
    # iteration order, so the registry is required to point straight at the
    # canonical name.
    return brand_keys.map(lambda k: aliases.get(k, k))


def propose_merges(stores: pd.DataFrame) -> pd.DataFrame:
    """Near-identical brand keys that a human should rule on.

    Output only. Nothing here changes the data; it exists so the alias registry
    can grow from evidence rather than from memory.
    """
    named = stores[stores["brand_key"] != ""]
    reach = named.groupby("brand_key")["mall_id"].nunique()
    aliases = load_aliases()
    keys = sorted(k for k, n in reach.items() if n >= _MIN_REACH_TO_PROPOSE)

    rows = []
    for i, left in enumerate(keys):
        for right in keys[i + 1 :]:
            if aliases.get(left) == right or aliases.get(right) == left:
                continue                       # already decided
            if abs(len(left) - len(right)) > 8:
                continue
            score = difflib.SequenceMatcher(None, left, right).ratio()
            if score < _SIMILARITY:
                continue
            rows.append({
                "brand_key": left,
                "candidate": right,
                "malls": int(reach[left]),
                "candidate_malls": int(reach[right]),
                "similarity": round(score, 3),
            })
    frame = pd.DataFrame(rows, columns=["brand_key", "candidate", "malls", "candidate_malls", "similarity"])
    return frame.sort_values(["similarity", "brand_key"], ascending=[False, True]).reset_index(drop=True)
