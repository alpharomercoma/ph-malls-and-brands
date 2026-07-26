"""Parser regression tests against captured fixture pages (2026-07-26).

If a site redesign breaks a parser, these tests keep working (fixtures are
frozen) — the live validation report is what flags the redesign. These tests
protect against parser regressions while refactoring.
"""

import json
from collections import Counter
from pathlib import Path

import pytest

from mallscape.models import Mall
from mallscape.normalize import brand_key
from mallscape.scrapers.ayala import derive_region
from mallscape.scrapers.filinvest import FilinvestScraper
from mallscape.scrapers.starmall import StarmallScraper
from mallscape.scrapers.robinsons import RobinsonsScraper, _norm_key

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def scraper():
    s = RobinsonsScraper.__new__(RobinsonsScraper)
    s.warnings = []
    return s


@pytest.fixture
def mall():
    return Mall(chain="robinsons", mall_id="test", mall_name="Test")


class TestDrupalParser:
    def test_malolos_full_directory(self, scraper, mall):
        html = (FIXTURES / "rob-malolos.html").read_text()
        stores = scraper._parse_drupal(mall, html)
        assert len(stores) == 204
        assert {s.floor for s in stores} == {"Level 1", "Level 2", "Level 3", "Level 4"}

    def test_phone_split(self, scraper, mall):
        html = (FIXTURES / "rob-malolos.html").read_text()
        stores = scraper._parse_drupal(mall, html)
        bonchon = next(s for s in stores if s.store_name_raw == "Bonchon")
        assert bonchon.phone == "044-794-3116"
        assert bonchon.floor == "Level 1"
        no_phone = next(s for s in stores if s.store_name_raw == "Argentee")
        assert no_phone.phone is None

    def test_manila_large_mall(self, scraper, mall):
        html = (FIXTURES / "rob-manila.html").read_text()
        stores = scraper._parse_drupal(mall, html)
        assert len(stores) > 600

    def test_galleria_non_level_floors(self, scraper, mall):
        # flagship mall using basement/upper-ground/lower-ground field names
        html = (FIXTURES / "rob-galleria.html").read_text()
        stores = scraper._parse_drupal(mall, html)
        assert len(stores) == 404
        floors = {s.floor for s in stores}
        assert any("asement" in (f or "") for f in floors)
        assert mall.address is not None


class TestVMDParser:
    def test_plaza_categories_and_floors(self, scraper, mall):
        html = (FIXTURES / "vmd-plaza.html").read_text()
        stores = scraper._parse_vmd(mall, html)
        assert len(stores) == 19
        by_cat = {}
        for s in stores:
            by_cat.setdefault(s.category, []).append(s)
        assert set(by_cat) == {"shop", "dine", "recharge"}
        greenwich = next(s for s in stores if s.store_name_raw == "GREENWICH")
        assert greenwich.category == "dine"
        assert greenwich.floor == "Ground Floor"

    def test_no_header_junk(self, scraper, mall):
        html = (FIXTURES / "vmd-plaza.html").read_text()
        stores = scraper._parse_vmd(mall, html)
        names = [s.store_name_raw for s in stores]
        assert not any("10AM" in n or "Daily" in n for n in names)

    def test_manila_scale(self, scraper, mall):
        html = (FIXTURES / "vmd-manila.html").read_text()
        stores = scraper._parse_vmd(mall, html)
        assert len(stores) > 550
        assert any(s.category == "lingkod pinoy" for s in stores)


class TestNormalize:
    def test_case_and_punctuation(self):
        assert brand_key("UNIQLO") == brand_key("Uniqlo")
        assert brand_key("Conti's") == brand_key("CONTIS")

    def test_phone_leftover(self):
        assert brand_key("Bonchon | 044-794-3116") == "bonchon"

    def test_branch_suffix(self):
        assert brand_key("BDO - ATM") == "bdo"
        assert brand_key("Potato Corner (Center Atrium)") == "potato corner"

    def test_aliases(self):
        assert brand_key("McDo") == brand_key("McDonald's")
        assert brand_key("BDO Unibank") == brand_key("BDO")


class TestRegistryMatching:
    def test_norm_key_strips_chain_words(self):
        assert _norm_key("Robinsons Place Malolos") == _norm_key("Malolos")
        assert _norm_key("Robinsons Town Mall Malabon") == _norm_key("Malabon")


class TestAyalaRegions:
    """Region derivation is the only inference in the Ayala path (its API
    publishes no region), so it carries the regression tests."""

    @pytest.mark.parametrize(
        "text,lat,lon,expected",
        [
            # provincial place names appear as MM street names — MM must win
            ("Greenbelt Mall, Legazpi Street, Makati City", 14.55, 121.02, "metro-manila"),
            ("Ayala Malls Legazpi, Legazpi City, Albay 4500", 13.15, 123.75, "south-luzon"),
            # "Rizal Highway" must not be read as Rizal province
            ("Harbor Point, Subic Bay Freeport Zone, 2200 Zambales", 14.83, 120.28, "north-luzon"),
            ("Trinoma EDSA cor. North Avenue, QC", 14.65, 121.03, "metro-manila"),
            ("Vertis North, Brgy. Bagong Pag-asa, Q.C.", 14.65, 121.04, "metro-manila"),
            # placeholder coordinates (1.001, 1.001) — address must carry it
            ("Ayala Pavilion Mall Bldg. A, Binan, Laguna", 1.001, 1.001, "south-luzon"),
            ("Serin, Silang Crossing East Tagaytay City, Cavite", 14.11, 120.26, "south-luzon"),
            ("Centrio Mall, Cagayan de Oro City 9000", 8.48, 124.65, "mindanao"),
            ("Ayala Center Cebu, Cebu Business Park, Cebu City", 10.32, 123.91, "visayas"),
            ("MarQuee Mall, Angeles City, Pampanga 2009", 15.16, 120.61, "north-luzon"),
        ],
    )
    def test_region_derivation(self, text, lat, lon, expected):
        assert derive_region(text, lat, lon) == expected

    def test_coordinate_fallback_when_address_unhelpful(self):
        assert derive_region("Some New Mall", 10.3, 123.9) == "visayas"

    def test_unknown_when_no_signal(self):
        assert derive_region("Some New Mall", None, None) is None


class TestAyalaFixtures:
    def test_all_malls_present(self):
        malls = json.loads((FIXTURES / "ayala-malls.json").read_text())
        assert len(malls) == 32
        assert {m["slugName"] for m in malls} >= {"ayala-glorietta", "ayala-trinoma"}

    def test_store_categories_sum_to_total(self):
        stores = json.loads((FIXTURES / "ayala-stores-abreeza.json").read_text())
        assert len(stores) == 297
        cats = Counter(s["category"] for s in stores)
        assert set(cats) == {"shop", "dine", "services", "essentials", "entertainment"}
        assert sum(cats.values()) == 297


class TestFilinvestParser:
    def test_festival_mall_full_table(self):
        s = FilinvestScraper.__new__(FilinvestScraper)
        s.warnings = []
        mall = Mall(chain="filinvest", mall_id="festival-mall", mall_name="Festival Mall")
        html = (FIXTURES / "fil-festival.html").read_text()
        stores = s.scrape_mall.__wrapped__(s, mall, html) if hasattr(
            s.scrape_mall, "__wrapped__"
        ) else _filinvest_parse(s, mall, html)
        assert len(stores) == 787
        # category header rows must propagate down to following rows
        acme = next(x for x in stores if x.store_name_raw == "Acme Jewelry")
        assert acme.category == "accessories"
        assert acme.floor == "Upper Ground Floor, West Wing"
        assert all(x.category for x in stores[:50])


def _filinvest_parse(scraper, mall, html):
    """Drive FilinvestScraper's table parsing against fixture HTML."""
    from unittest.mock import Mock

    scraper.fetcher = Mock()
    scraper.fetcher.get_text.return_value = html
    return scraper.scrape_mall(mall)


class TestStarmallParser:
    def test_alabang_gallery_blob(self):
        from unittest.mock import Mock

        s = StarmallScraper.__new__(StarmallScraper)
        s.warnings = []
        s.fetcher = Mock()
        s.fetcher.get_text.return_value = (FIXTURES / "starmall-alabang.html").read_text()
        mall = Mall(chain="starmall", mall_id="alabang", mall_name="Starmall Alabang")
        stores = s.scrape_mall(mall)
        assert len(stores) > 100
        names = {x.store_name_raw for x in stores}
        assert "ALL BANK" in names
        allbank = next(x for x in stores if x.store_name_raw == "ALL BANK")
        assert allbank.phone == "8842-7099"
        assert allbank.floor == "Level 2"


class TestWaltermartParser:
    def test_category_page_data_attributes(self):
        from selectolax.parser import HTMLParser

        html = (FIXTURES / "waltermart-category.html").read_text()
        nodes = HTMLParser(html).css("a.wm-store")
        names = [n.attributes.get("data-name") for n in nodes]
        assert "ADDAS" in names
        assert len(names) >= 10


class TestAranetaParser:
    def test_ali_mall_gallery_items(self):
        from unittest.mock import Mock

        from mallscape.scrapers.araneta import AranetaScraper

        s = AranetaScraper.__new__(AranetaScraper)
        s.warnings = []
        s.fetcher = Mock()
        s.fetcher.get_text.return_value = (FIXTURES / "araneta-ali-mall.html").read_text()
        mall = Mall(chain="araneta", mall_id="ali-mall", mall_name="Ali Mall", extra={"slug": "ali-mall"})
        stores = s.scrape_mall(mall)
        # must match the raw gallery-item count exactly (no silent dedupe)
        assert len(stores) == 88
        handyman = next(x for x in stores if x.store_name_raw == "HANDYMAN")
        assert handyman.floor == "LGF"
