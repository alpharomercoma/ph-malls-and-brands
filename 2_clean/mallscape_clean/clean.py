"""Stage 2 - standardize and normalize the scraped listings.

Strictly non-destructive: `stores.parquet` from stage 1 is never modified.
This stage reads it and writes `stores_clean.parquet` alongside, where every
raw column survives untouched and normalized values are added as new columns.
When a normalization is uncertain the raw value is kept and the row is flagged
rather than silently coerced - a wrong-but-clean value is worse than a
recognisably messy one.

Columns added
-------------
``store_name``      display form: unicode-normalized, whitespace-collapsed,
                    smart quotes folded, ALL-CAPS title-cased
``brand_key``       user-visible tenant key (from :mod:`mallscape_clean.normalize`)
``category_std``    harmonized taxonomy - the twelve chains publish 101
                    different category strings for the same handful of concepts
``floor_std``       canonical floor label ("Level 2", "Lower Ground", ...)
``floor_level``     signed integer level where one can be inferred (basement
                    negative, ground 0); null when the label is not a level
``store_format``    atm, kiosk, cart, express, drive-thru and so on, else
                    "standard". A bank branch and an ATM booth share a brand
                    but are not the same tenant, so the distinction is kept
                    here rather than folded into ``brand_key``
``phone_e164``      first phone in +63 E.164 form, null if unparseable
``dq_flags``        pipe-separated data-quality flags, empty string when clean

Determinism: pure function of the input snapshot. No clock, no randomness,
no dict-order dependence.
"""

from __future__ import annotations

import re
import unicodedata

import pandas as pd

from mallscape_clean.normalize import brand_key

# --- category taxonomy -------------------------------------------------------
# Ordered rules: first match wins, so put specific patterns before general ones.
# Built against the full observed vocabulary (101 distinct raw values).
CATEGORY_RULES: list[tuple[str, str]] = [
    (r"cyberzone|cybermart|gadget|telecom|computer|electronic|mobile.?phone", "electronics"),
    (r"grocer|supermarket|food retail|convenience", "groceries"),
    (r"cinema|amusement|recreation|entertainement|entertainment|experience"
     r"|arcade|recharge", "entertainment"),
    (r"bank|atm|government|courier|school|fellowship|services", "services"),
    (r"optical|health|beauty|wellness|salon|spa|drug|clinic|pharmac", "health_beauty"),
    (r"dining|dine|food|restaurant|bakeshop|bread|pastr|coffee|fast.?food|kiosk"
     r"|ice.?cream|juice|shake|fries|milk|dairy|snack|waffle|shawarma|candies", "dining"),
    (r"apparel|fashion|shoes|bag|luggage|accessor|jewel|watch|fragrance|department", "fashion"),
    (r"home|furnish|appliance|hardware|houseware|real estate", "home"),
    (r"hobb|specialt|bookstore|book|toy|sport|pet|photo|flower|novelt", "specialty"),
    (r"shopping|shops?|retail|essentials", "shopping"),
]
_UNKNOWN = {"", "all", "undefined", "others", "other", "n/a", "none"}

# --- floor normalization -----------------------------------------------------
_ORDINAL_WORDS = {
    "ground": 0, "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
}
_NON_LEVEL = re.compile(
    r"kiosk|cart|al fresco|food ?hall|food ?court|parkway|park|annex|bldg|building"
    r"|carpark|car ?park|roof|concourse|mezzanine|wing|atrium|activity|garden",
    re.I,
)
_SMART = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-"})  # noqa: RUF001 - the table maps these on purpose
# leading/trailing separators left over from the source markup
_EDGE_JUNK = re.compile(r"^[\s\-,|]+|[\s\-,|]+$")
_VOWEL = re.compile(r"[AEIOU]")
_PUNCT = ".,:;!?()[]{}\"'"
# Vowel-less tokens that are ordinary words, not acronyms.
_NOT_ACRONYMS = frozenset({
    "BY", "MY", "GYM", "SKY", "DRY", "FLY", "TRY", "WHY", "SHY", "SPY",
    "MR", "MRS", "DR", "JR", "SR", "ST", "TV",
})
# Acronyms that do carry a vowel, so the vowel test alone would miss them.
_ACRONYMS = frozenset({
    "ADC", "ATM", "BDO", "BPI", "CBTL", "GNC", "KFC", "OPPO", "SM", "UAE",
    "USA", "UNO", "AXA", "AIA", "ABC", "ACE", "AMA", "IBM", "SSI", "UCPB",
})
# Trailing noise some operators append to the tenant name itself. Only these
# three shapes are stripped, because they are never part of a business name:
# a parenthesised phone number, an operational status marker, and a bare phone
# number tacked onto the end. Other parentheticals are kept, since they often
# distinguish a real sub-brand ("Executive Optical (Fun Optics)").
_NAME_NOISE = re.compile(
    r"\s*\(\s*[\d\-\s/.+]{6,}\)\s*$"
    r"|\s*\(\s*(?:new|open|opening soon|soon|closed|temporarily closed"
    r"|temp\.? closed|renovation)\s*\)\s*$"
    r"|\s+[\d][\d\-\s/]{6,}$",
    re.I,
)
# Tenant format complements the tenant key. A bank branch and an ATM booth are
# separate tenant identifiers, and this column supports format-level analysis.
_FORMATS = (
    ("atm", r"\batm\b|\bautomated teller\b"),
    ("kiosk", r"\bkiosk\b"),
    ("cart", r"\bcart\b"),
    ("booth", r"\bbooth\b"),
    ("express", r"\bexpress\b"),
    ("drive-thru", r"\bdrive[\s-]?thru\b|\bdrive[\s-]?through\b"),
    ("satellite", r"\bsatellite\b"),
    ("extension", r"\bextension\b|\bannex\b"),
    ("stall", r"\bstall\b"),
    ("counter", r"\bcounter\b"),
    ("takeout", r"\bto[\s-]?go\b|\btake[\s-]?out\b"),
)
_FORMAT_RES = tuple((name, re.compile(pat, re.I)) for name, pat in _FORMATS)
_PHONE_SPLIT = re.compile(r"\s*(?:/|;|,| or )\s*", re.I)


def clean_name(raw: str) -> str:
    """Display-ready store name.

    Case is changed only for ALL-CAPS input, where the capitalization carries
    no information. Mixed-case names are left alone because their casing is
    usually deliberate (``iStore``, ``BENCH/``).

    Title-casing an all-caps string damages acronyms: ``CLN`` becomes ``Cln``
    and ``PLDT`` becomes ``Pldt``. Tokens are therefore kept as-is when they
    look like an acronym rather than a word. The test is having no vowel,
    which separates ``PNB``, ``LBC`` and ``BBQ`` from ``BENCH`` and ``HERBS``,
    plus a short list for the vowel-carrying acronyms that actually occur.
    """
    s = unicodedata.normalize("NFKC", str(raw)).translate(_SMART)
    s = re.sub(r"\s+", " ", s)
    # strip repeatedly: a name can carry both a status marker and a phone
    for _ in range(3):
        stripped = _NAME_NOISE.sub("", s)
        if stripped == s:
            break
        s = stripped
    s = _EDGE_JUNK.sub("", s)
    if not s or s != s.upper():
        return s

    out = []
    for token in s.split(" "):
        core = token.strip(_PUNCT)
        if _is_acronym(core):
            out.append(token)
            continue
        titled = token.title()
        # .title() breaks possessives ("BAKER'S" -> "Baker'S") and any letter
        # following a digit or apostrophe
        titled = re.sub(r"(?<=[\'\d])([A-Z])", lambda m: m.group(1).lower(), titled)
        # Mc/Mac names keep an internal capital: Mcdonald's -> McDonald's
        titled = re.sub(r"\b(Ma?c)([a-z])", lambda m: m.group(1) + m.group(2).upper(), titled)
        out.append(titled)
    return " ".join(out)


def _is_acronym(token: str) -> bool:
    """True when an all-caps token should keep its capitalization."""
    if len(token) < 2 or not token.isalpha():
        return False
    if token in _NOT_ACRONYMS:
        return False
    return token in _ACRONYMS or not _VOWEL.search(token)


def standardize_category(raw, chain: str) -> str:
    """Map a chain's own category string onto the shared taxonomy."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return "unknown"
    value = str(raw).strip().lower()
    # Ortigas exposes a numeric type id, which carries no meaning here
    if not value or value in _UNKNOWN or value.isdigit():
        return "unknown"
    for pattern, canonical in CATEGORY_RULES:
        if re.search(pattern, value):
            return canonical
    return "unknown"


def standardize_floor(raw) -> tuple[str | None, int | None]:
    """Return (canonical label, numeric level). Level is null when the label
    denotes a place rather than a storey (Kiosk, Food Hall, Roof Deck...)."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None, None
    text = re.sub(r"\s+", " ", str(raw)).strip()
    if not text:
        return None, None
    low = text.lower()

    # basements first - "B2"/"Basement 2" are negative levels
    m = re.search(r"\b(?:basement|b)\s*(\d+)\b", low)
    if m:
        n = int(m.group(1))
        return f"Basement {n}", -n
    if "basement" in low:
        return "Basement", -1
    if re.search(r"\blower ground\b|\blgf\b|\blg\b", low):
        return "Lower Ground", -1
    if re.search(r"\bupper ground\b|\bugf\b", low):
        return "Upper Ground", 1
    if re.search(r"\bground\b|\bgf\b|\bg/f\b|\bgfl\b", low) and not _NON_LEVEL.search(low):
        return "Ground", 0

    # numeric storeys. Two shapes, because "2F" has no word boundary between
    # the digit and the F (Megaworld and Ortigas both use it):
    #   compact - "2F", "2/F", "2L"
    #   spelled - "Level 2", "2nd Floor", "Floor 2"
    level = None
    compact = re.match(r"^(\d{1,2})\s*/?\s*(?:f|l)\b", low)
    spelled = re.search(r"(?:level|floor)\s*(\d{1,2})|\b(\d{1,2})\s*(?:st|nd|rd|th)?\s*(?:floor|level)", low)
    word = next((w for w in _ORDINAL_WORDS if w in low), None)
    if compact:
        level = int(compact.group(1))
    elif spelled:
        level = int(spelled.group(1) or spelled.group(2))
    elif word:
        level = _ORDINAL_WORDS[word]
    if level is not None and not _NON_LEVEL.search(low):
        return f"Level {level}", level

    # a real place, not a storey - keep the label, no numeric level
    return text.title() if text == text.upper() else text, None


def store_format(raw) -> str:
    """Classify the tenant format named in the listing, else "standard"."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return "standard"
    text = str(raw)
    for name, pattern in _FORMAT_RES:
        if pattern.search(text):
            return name
    return "standard"


def to_e164(raw) -> str | None:
    """First Philippine number in +63 E.164 form, or null if unparseable."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    first = _PHONE_SPLIT.split(str(raw).strip())[0]
    digits = re.sub(r"\D", "", first)
    if not digits:
        return None
    if digits.startswith("63") and len(digits) == 12:
        return "+" + digits
    if digits.startswith("0") and len(digits) == 11:      # 09xx mobile
        return "+63" + digits[1:]
    if len(digits) == 10 and digits.startswith("9"):      # 9xx mobile, no trunk
        return "+639" + digits[1:]
    if len(digits) in (7, 8):                             # local landline, no area code
        return None
    if digits.startswith("02") and len(digits) in (9, 10):
        return "+63" + digits[1:]
    return None


def build(stores: pd.DataFrame, malls: pd.DataFrame | None = None) -> pd.DataFrame:
    """Return a cleaned copy. The input frame is never mutated."""
    df = stores.copy()

    df["store_name"] = df["store_name_raw"].map(clean_name)
    df["brand_key"] = df["store_name"].map(brand_key)
    df["category_std"] = [
        standardize_category(c, ch) for c, ch in zip(df["category"], df["chain"], strict=False)
    ]
    floors = [standardize_floor(f) for f in df["floor"]]
    df["floor_std"] = [f[0] for f in floors]
    df["floor_level"] = pd.array([f[1] for f in floors], dtype="Int64")
    df["store_format"] = df["store_name_raw"].map(store_format)
    df["phone_e164"] = df["phone"].map(to_e164)

    # --- data quality flags: describe, never drop ---
    flags: list[list[str]] = [[] for _ in range(len(df))]
    def flag(mask, label):
        for i in df.index[mask]:
            flags[df.index.get_loc(i)].append(label)

    flag(df["brand_key"].eq(""), "empty_brand_key")
    flag(df["category_std"].eq("unknown"), "category_unmapped")
    # standardize_floor always falls back to the raw label, so "unparsed"
    # could never fire. The useful signal is a floor we could not place
    # on a numeric level (kiosks, food halls, roof decks, wings).
    flag(df["floor"].notna() & df["floor_level"].isna(), "floor_level_unresolved")
    flag(df["phone"].notna() & df["phone_e164"].isna(), "phone_unparsed")
    flag(df["store_name"].str.len() > 60, "name_suspiciously_long")
    # a decimal tail is usually a unit number or price that leaked into the name
    flag(df["store_name"].str.contains(r"\d+\.\d+$", na=False), "numeric_tail")
    dupe = df.duplicated(subset=["chain", "mall_id", "brand_key", "floor_std"], keep=False)
    flag(dupe, "duplicate_in_mall")
    df["dq_flags"] = ["|".join(f) for f in flags]

    ordered = [
        "chain", "mall_id", "store_name_raw", "store_name", "brand_key",
        "category", "category_std", "store_format", "floor", "floor_std", "floor_level",
        "building", "phone", "phone_e164", "source", "scraped_at", "dq_flags",
    ]
    df = df[[c for c in ordered if c in df.columns]]
    return df.sort_values(
        ["chain", "mall_id", "brand_key", "store_name_raw"], kind="mergesort"
    ).reset_index(drop=True)


def category_mapping(stores: pd.DataFrame) -> pd.DataFrame:
    """Audit table: every raw category, its canonical target, and its volume."""
    rows = (
        stores.assign(
            category_std=[
                standardize_category(c, ch) for c, ch in zip(stores["category"], stores["chain"], strict=False)
            ]
        )
        .groupby(["chain", "category", "category_std"], dropna=False)
        .size()
        .rename("listings")
        .reset_index()
    )
    return rows.sort_values(
        ["category_std", "listings", "chain"], ascending=[True, False, True]
    ).reset_index(drop=True)


def normalization_review(stores: pd.DataFrame) -> pd.DataFrame:
    """Return potentially risky raw-name merges for human review."""
    df = stores.copy()
    df["store_name"] = df["store_name_raw"].map(clean_name)
    df["brand_key"] = df["store_name"].map(brand_key)
    out = (
        df[df["brand_key"] != ""]
        .groupby("brand_key")
        .agg(
            raw_variants=("store_name_raw", "nunique"),
            clean_variants=("store_name", "nunique"),
            listings=("brand_key", "size"),
            chains=("chain", "nunique"),
            examples=("store_name_raw", lambda s: " | ".join(sorted(s.unique())[:8])),
        )
        .reset_index()
    )
    return out[(out.raw_variants > 1) & ((out.clean_variants > 1) | (out.raw_variants >= 5))].sort_values(
        ["raw_variants", "listings", "brand_key"], ascending=[False, False, True]
    ).reset_index(drop=True)
