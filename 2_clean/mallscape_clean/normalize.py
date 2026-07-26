"""Brand-name normalization: raw store names -> cross-chain ``brand_key``.

SM lists "Uniqlo", Robinsons lists "UNIQLO"; kiosks repeat per floor; names
carry branch/floor suffixes. The brand_key strips all of that so presence
analysis can match brands across chains and malls.
"""

from __future__ import annotations

import re
import unicodedata

# canonical merges for spellings the mechanical rules can't unify
ALIASES = {
    "mcdo": "mcdonalds",
    "mc donalds": "mcdonalds",
    "bdo unibank": "bdo",
    "banco de oro": "bdo",
    "bpi family savings bank": "bpi",
    "bank of the philippine islands": "bpi",
    "jollibee foods": "jollibee",
    "the generics pharmacy": "tgp",
    "generics pharmacy": "tgp",
    "watsons personal care": "watsons",
    "sm appliance center": "sm appliance",
    "ace hardware philippines": "ace hardware",
    "mercury drug store": "mercury drug",
    "7 eleven": "7eleven",
    "seven eleven": "7eleven",
    "zus coffee ph": "zus coffee",
    "bank of the philippine islands (bpi)": "bpi",
    "bank of the philippine islands atm": "bpi atm",
    "banco de oro atm": "bdo atm",
}

_PARENS = re.compile(r"\(([^)]*)\)")
_ATM = re.compile(r"\b(?:atm|automated teller)\b", re.IGNORECASE)
_PAREN_MATCH_NOISE = re.compile(
    r"\b(?:kiosk|cart|stall|booth|express|branch|"
    r"level|floor|wing|atrium|food hall|food court|alabang[- ]zapote|"
    r"center atrium|timezone|pixie forest|x[- ]site|new|open|opening soon|"
    r"closed|temporarily closed|renovation)\b",
    re.IGNORECASE,
)
_BRANCH_SUFFIX = re.compile(
    r"\s*[--]\s*(kiosk|cart|stall|booth|express|branch|level \d+|[lb]\d+[a-z]?|2nd branch)$",
    re.IGNORECASE,
)
_NON_ALNUM = re.compile(r"[^a-z0-9&() ]+")


def brand_key(raw: str) -> str:
    """Collapse a raw store name to a stable, user-visible tenant identifier."""
    s = raw.split("|")[0]                      # drop "Name | phone" leftovers
    # An ATM is a materially different mall tenant from a bank branch, so it
    # remains part of the identifier ("bpi atm"), while location/status noise
    # is removed and meaningful sub-brands remain intact.
    def parenthetical(match: re.Match[str]) -> str:
        content = match.group(1)
        if _ATM.search(content):
            return " atm "
        if _PAREN_MATCH_NOISE.search(content):
            return " "
        return f" ({content}) "

    s = _PARENS.sub(parenthetical, s)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = s.lower()
    s = s.replace("'", "").replace("'", "")
    s = _BRANCH_SUFFIX.sub("", s.strip())
    s = _NON_ALNUM.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"^(the )", "", s)
    return ALIASES.get(s, s)
