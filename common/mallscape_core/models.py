"""Normalized data model shared by all chain scrapers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Mall:
    chain: str          # "sm" | "robinsons" | future chains
    mall_id: str        # stable slug, unique within chain
    mall_name: str
    region: str | None = None
    address: str | None = None
    mall_code: str | None = None   # chain-internal code (SM API mallCode)
    source_url: str | None = None
    # "mall" vs non-mall retail (amusement park, condo podium, office annex);
    # filter on this before comparing chains - see classify_property_type
    property_type: str = "mall"
    # Set only by scrapers whose source publishes coordinates. Everything else
    # is resolved later against the committed registry; see geocode.py.
    lat: float | None = None
    lon: float | None = None
    geo_source: str | None = None   # "operator" | "osm" | "nominatim" | None
    geo_precision: str | None = None  # "exact" | "address" | "locality" | None
    extra: dict = field(default_factory=dict)

    def to_row(self) -> dict:
        row = asdict(self)
        row.pop("extra")
        return row


@dataclass
class Store:
    chain: str
    mall_id: str
    store_name_raw: str
    category: str | None = None
    floor: str | None = None
    building: str | None = None
    phone: str | None = None
    source: str | None = None      # "sm-api" | "robinsons-drupal" | "robinsons-vmd"

    def to_row(self) -> dict:
        return asdict(self)
