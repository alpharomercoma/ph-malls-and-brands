"""Geographic region for a property, inferred from its text.

Only three of the twelve operators publish a region. The rest give an address,
a name, or coordinates, so region is inferred here rather than left null, and
the inference lives in one place so every scraper resolves it the same way.

Order matters: Metro Manila is tested first because provincial place names also
appear as street names inside Metro Manila addresses ("Legazpi Street, Makati").
"""

from __future__ import annotations

import re
import unicodedata

# Order matters: Metro Manila is checked first because provincial place names
# also appear as street names inside MM addresses ("Legazpi Street, Makati").
METRO_MANILA = (
    "makati", "taguig", "pasig", "marikina", "paranaque", "caloocan",
    "mandaluyong", "pasay", "las pinas", "muntinlupa", "malabon", "navotas",
    "valenzuela", "san juan", "pateros", "quezon city", "manila city",
    "metro manila", "bonifacio global city", "bgc", "city of manila",
    "antipolo", "montalban", "rodriguez rizal", "san mateo rizal",
    "angono", "cainta", "taytay rizal", "binangonan", "manila",
)
NORTH_LUZON = (
    "pampanga", "angeles city", "tarlac", "bulacan", "nueva ecija",
    "pangasinan", "la union", "ilocos", "cagayan valley", "isabela",
    "benguet", "baguio", "zambales", "subic", "bataan", "aurora", "abra",
    "balagtas", "cabagan", "tumauini", "santiago city", "ilagan", "gapan",
    "cauayan", "guimba", "plaridel", "meycauayan", "pulilan", "tarlac city",
)
SOUTH_LUZON = (
    "cavite", "laguna", "batangas", "quezon province", "albay", "legazpi city",
    "camarines", "sorsogon", "masbate", "marinduque", "mindoro", "palawan",
    "naga city", "binan", "santa rosa", "sta rosa", "nuvali", "tagaytay",
    "dasmarinas", "imus", "vermosa", "lemery", "tanay", "morong", "polangui",
    "calapan", "san andres", "sta cruz", "santa cruz", "tayabas", "lipa",
    "bauan", "rosario", "noveleta", "silang", "sorsogon", "los banos",
)
VISAYAS = (
    "cebu", "bacolod", "iloilo", "negros", "panay", "leyte", "samar", "bohol",
    "tacloban", "dumaguete", "ormoc", "capiz", "roxas city", "antique",
    "aklan", "boracay", "siquijor", "biliran", "guimaras", "talisay", "pavia",
)
MINDANAO = (
    "davao", "cagayan de oro", "zamboanga", "general santos", "gensan",
    "butuan", "iligan", "cotabato", "surigao", "agusan", "misamis",
    "bukidnon", "pagadian", "tagum", "koronadal", "dipolog", "ozamiz",
    "marawi", "lanao", "sultan kudarat", "basilan", "tawi",
)
REGION_KEYWORDS = (
    ("metro-manila", METRO_MANILA),
    ("north-luzon", NORTH_LUZON),
    ("south-luzon", SOUTH_LUZON),
    ("visayas", VISAYAS),
    ("mindanao", MINDANAO),
)
_QC_ABBREV = re.compile(r"\bq\.?\s?c\.?\b")

# Generous at every edge: Batanes in the north, Tawi-Tawi in the south. A
# coordinate outside this is a bad value, not a Philippine property, so it is
# the one test every coordinate has to pass before anything else uses it.
PH_BOUNDS = (4.5, 21.5, 116.0, 127.0)   # lat_min, lat_max, lon_min, lon_max


def in_bounds(lat: float | None, lon: float | None) -> bool:
    if lat is None or lon is None:
        return False
    lat_min, lat_max, lon_min, lon_max = PH_BOUNDS
    return lat_min <= lat <= lat_max and lon_min <= lon <= lon_max


def parse_coords(lat: object, lon: object) -> tuple[float, float] | None:
    """Coordinates from a source field, or None if absent or implausible.

    Sources publish these as strings, as numbers, as empty strings and
    occasionally as zeros. Every one of those has to become None rather than a
    pin in the Gulf of Guinea.
    """
    try:
        pair = (float(lat), float(lon))
    except (TypeError, ValueError):
        return None
    return pair if in_bounds(*pair) else None


def derive_region(text: str, lat: float | None, lon: float | None) -> str | None:
    """Best-effort region bucket from address text, falling back to coordinates."""
    # fold accents so "Las Pinas" matches "Las Pinas"
    haystack = (
        unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    )
    if _QC_ABBREV.search(haystack):
        return "metro-manila"
    for region, keywords in REGION_KEYWORDS:
        if any(k in haystack for k in keywords):
            return region
    # coordinate fallback, only for plausible Philippine coordinates
    if lat and lon and in_bounds(lat, lon):
        if lat > 14.8:
            return "north-luzon"
        if lat >= 14.35 and 120.85 <= lon <= 121.15:
            return "metro-manila"
        if lat >= 12.5:
            return "south-luzon"
        if lat >= 9.0:
            return "visayas"
        return "mindanao"
    return None


def region_for(*parts: object, lat: float | None = None, lon: float | None = None) -> str | None:
    """Best-effort region from any combination of name, address and coordinates."""
    text = " ".join(str(p) for p in parts if p)
    return derive_region(text, lat, lon) if text or (lat and lon) else None
