"""The single place that maps a chain id to its scraper class.

Kept out of the CLI so any stage or test can enumerate chains without
importing the command-line layer.
"""

from __future__ import annotations

from mallscape_scrape.scrapers.araneta import AranetaScraper
from mallscape_scrape.scrapers.ayala import AyalaScraper
from mallscape_scrape.scrapers.base import MallChainScraper
from mallscape_scrape.scrapers.filinvest import FilinvestScraper
from mallscape_scrape.scrapers.fishermall import FishermallScraper
from mallscape_scrape.scrapers.megaworld import MegaworldScraper
from mallscape_scrape.scrapers.ortigas import OrtigasScraper
from mallscape_scrape.scrapers.robinsons import RobinsonsScraper
from mallscape_scrape.scrapers.sm import SMScraper
from mallscape_scrape.scrapers.starmall import StarmallScraper
from mallscape_scrape.scrapers.waltermart import WaltermartScraper
from mallscape_scrape.scrapers.xentro import XentroScraper

SCRAPERS: dict[str, type[MallChainScraper]] = {
    "sm": SMScraper,
    "robinsons": RobinsonsScraper,
    "ayala": AyalaScraper,
    "megaworld": MegaworldScraper,
    "filinvest": FilinvestScraper,
    "starmall": StarmallScraper,
    "waltermart": WaltermartScraper,
    "araneta": AranetaScraper,
    "fishermall": FishermallScraper,
    "ortigas": OrtigasScraper,
    "xentro": XentroScraper,
}
