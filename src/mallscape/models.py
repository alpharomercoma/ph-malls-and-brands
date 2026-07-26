"""Normalized data model shared by all chain scrapers."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict


@dataclass
class Mall:
    chain: str          # "sm" | "robinsons" | future chains
    mall_id: str        # stable slug, unique within chain
    mall_name: str
    region: str | None = None
    address: str | None = None
    mall_code: str | None = None   # chain-internal code (SM API mallCode)
    source_url: str | None = None
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
