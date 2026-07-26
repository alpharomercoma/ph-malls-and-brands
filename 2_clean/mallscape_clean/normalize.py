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
}

_PARENS = re.compile(r"\([^)]*\)")
_BRANCH_SUFFIX = re.compile(
    r"\s*[-–]\s*(atm|kiosk|cart|stall|booth|express|branch|level \d+|[lb]\d+[a-z]?|2nd branch)$",
    re.IGNORECASE,
)
_NON_ALNUM = re.compile(r"[^a-z0-9& ]+")


def brand_key(raw: str) -> str:
    """Collapse a raw store name to a stable cross-chain brand identifier."""
    s = raw.split("|")[0]                      # drop "Name | phone" leftovers
    s = _PARENS.sub(" ", s)                    # drop "(Pedro Gil Wing)" etc.
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = s.lower()
    s = s.replace("'", "").replace("’", "")
    s = _BRANCH_SUFFIX.sub("", s.strip())
    s = _NON_ALNUM.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"^(the )", "", s)
    return ALIASES.get(s, s)
