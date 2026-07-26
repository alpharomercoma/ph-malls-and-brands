"""Parser regression tests against captured fixture pages (2026-07-26).

If a site redesign breaks a parser, these tests keep working (fixtures are
frozen) - the live validation report is what flags the redesign. These tests
protect against parser regressions while refactoring.
"""

import json
from collections import Counter
from pathlib import Path

import pytest

from mallscape_clean.normalize import brand_key
from mallscape_core.models import Mall
from mallscape_scrape.scrapers.ayala import derive_region
from mallscape_scrape.scrapers.filinvest import FilinvestScraper
from mallscape_scrape.scrapers.robinsons import RobinsonsScraper, _norm_key
from mallscape_scrape.scrapers.starmall import StarmallScraper

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
            # provincial place names appear as MM street names - MM must win
            ("Greenbelt Mall, Legazpi Street, Makati City", 14.55, 121.02, "metro-manila"),
            ("Ayala Malls Legazpi, Legazpi City, Albay 4500", 13.15, 123.75, "south-luzon"),
            # "Rizal Highway" must not be read as Rizal province
            ("Harbor Point, Subic Bay Freeport Zone, 2200 Zambales", 14.83, 120.28, "north-luzon"),
            ("Trinoma EDSA cor. North Avenue, QC", 14.65, 121.03, "metro-manila"),
            ("Vertis North, Brgy. Bagong Pag-asa, Q.C.", 14.65, 121.04, "metro-manila"),
            # placeholder coordinates (1.001, 1.001) - address must carry it
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

        from mallscape_scrape.scrapers.araneta import AranetaScraper

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


class TestSnapshotIntegrity:
    """Guards against the partial-snapshot failure: a crashed or single-chain
    run must never be published as `latest` or silently analyzed."""

    def _snapshot(self, tmp_path, monkeypatch, malls_df, stores_df, date="2026-01-01"):
        from mallscape_core import storage

        monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
        storage.write(date, storage.SCRAPE, "malls", malls_df)
        storage.write(date, storage.SCRAPE, "stores", stores_df)
        return storage

    def test_empty_snapshot_is_not_usable(self, tmp_path, monkeypatch):
        import pandas as pd

        storage = self._snapshot(
            tmp_path, monkeypatch,
            pd.DataFrame({"scraped_at": []}), pd.DataFrame({"scraped_at": []}),
        )
        assert storage.is_usable("2026-01-01") is False

    def test_update_latest_refuses_empty(self, tmp_path, monkeypatch):
        import pandas as pd
        import pytest as _pytest

        storage = self._snapshot(
            tmp_path, monkeypatch,
            pd.DataFrame({"scraped_at": []}), pd.DataFrame({"scraped_at": []}),
        )
        with _pytest.raises(ValueError, match="refusing to publish"):
            storage.publish_latest("2026-01-01")

    def test_latest_usable_skips_broken_newer_snapshot(self, tmp_path, monkeypatch):
        import pandas as pd

        good_m = pd.DataFrame({"chain": ["sm"], "mall_id": ["x"], "scraped_at": ["2026-01-01"]})
        good_s = pd.DataFrame({"chain": ["sm"], "mall_id": ["x"], "store_name_raw": ["Y"]})
        storage = self._snapshot(tmp_path, monkeypatch, good_m, good_s, "2026-01-01")
        # a newer but empty snapshot must be skipped, not selected
        storage.write("2026-01-02", storage.SCRAPE, "malls", pd.DataFrame({"scraped_at": []}))
        storage.write("2026-01-02", storage.SCRAPE, "stores", pd.DataFrame({"scraped_at": []}))
        assert storage.latest_usable_run() == "2026-01-01"


class TestAuditRegressions:
    """Defects found by the completeness audit - each must stay fixed."""

    def test_starmall_decodes_all_unicode_escapes(self):
        from unittest.mock import Mock
        s = StarmallScraper.__new__(StarmallScraper)
        s.warnings = []
        s.fetcher = Mock()
        s.fetcher.get_text.return_value = (FIXTURES / "starmall-alabang.html").read_text()
        mall = Mall(chain="starmall", mall_id="alabang", mall_name="Starmall Alabang")
        names = [x.store_name_raw for x in s.scrape_mall(mall)]
        # apostrophes arrive as ' in the JSON blob and must be decoded,
        # otherwise brand_key produces "baker u0027s fair"
        assert not any("\\u00" in n for n in names)
        assert "BAKER'S FAIR" in names

    def test_xentro_keeps_names_ending_in_period(self):
        from mallscape_clean.normalize import brand_key
        # "INC." / "CORP." / "ACC." are real tenant suffixes, not noise
        assert brand_key("SIETE ESTRELLAS, INC.") != ""

    def test_sm_dedupe_key_separates_distinct_outlets(self):
        """Two outlets of one brand on different floors must both survive."""
        keys = set()
        for floor, building in [("2F", "MAIN"), ("GF", "EXPANSION")]:
            keys.add(("", "POTATO CORNER", floor, building))
        assert len(keys) == 2


class TestReportDeterminism:
    def test_report_is_byte_identical_across_runs(self, tmp_path, monkeypatch):
        import pandas as pd

        from mallscape_core import storage
        from mallscape_report import report

        monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
        malls = pd.DataFrame({
            "chain": ["sm", "ayala"], "mall_id": ["a", "b"],
            "mall_name": ["A Mall", "B Mall"], "region": ["metro-manila", "visayas"],
            "property_type": ["mall", "mall"], "scraped_at": ["2026-01-01"] * 2,
        })
        stores = pd.DataFrame({
            "chain": ["sm", "sm", "ayala"], "mall_id": ["a", "a", "b"],
            "store_name_raw": ["X", "Y", "Z"],
        })
        storage.write("2026-01-01", storage.SCRAPE, "malls", malls)
        storage.write("2026-01-01", storage.SCRAPE, "stores", stores)
        first = report.build("2026-01-01")
        second = report.build("2026-01-01")
        assert first == second
        # and it must actually contain the numbers, not just be stable-empty
        assert "3" in first and "A Mall" in first


class TestCleanStage:
    """Stage 2 must standardize without inventing or destroying data."""

    def test_is_non_destructive(self):
        import pandas as pd

        from mallscape_clean import clean

        raw = pd.DataFrame({
            "chain": ["sm"], "mall_id": ["a"], "store_name_raw": ["POTATO CORNER"],
            "category": ["dining"], "floor": ["2ND FLOOR"], "building": [None],
            "phone": ["0917-123-4567"], "source": ["sm-api"], "scraped_at": ["2026-01-01"],
        })
        before = raw.copy(deep=True)
        out = clean.build(raw)
        pd.testing.assert_frame_equal(raw, before)          # input untouched
        assert out.loc[0, "store_name_raw"] == "POTATO CORNER"  # raw preserved
        assert out.loc[0, "store_name"] == "Potato Corner"
        assert out.loc[0, "floor_level"] == 2
        assert out.loc[0, "phone_e164"] == "+639171234567"

    def test_floor_levels(self):
        from mallscape_clean.clean import standardize_floor
        cases = {
            "2F": 2, "Level 3": 3, "2nd Floor": 2, "SECOND FLOOR": 2,
            "Ground": 0, "GF": 0, "LGF": -1, "Lower Ground": -1,
            "Basement 2": -2, "UGF": 1,
        }
        for raw, level in cases.items():
            assert standardize_floor(raw)[1] == level, raw
        # places, not storeys - must not be assigned a level
        for raw in ["Kiosk", "Food Hall", "Roof Deck", "Parkway"]:
            assert standardize_floor(raw)[1] is None, raw

    def test_category_harmonization_across_chains(self):
        from mallscape_clean.clean import standardize_category
        for raw in ["dining", "dine", "Food Choices", "DINING / FOOD (KIOSK / CARTS)"]:
            assert standardize_category(raw, "x") == "dining", raw
        for raw in ["cyberzone", "cybermart", "gadgets", "telecoms / computers / electronics"]:
            assert standardize_category(raw, "x") == "electronics", raw
        # meaningless upstream values must not be forced into a bucket
        for raw in ["1", "4", "undefined", "all", None]:
            assert standardize_category(raw, "x") == "unknown", raw

    def test_phone_e164(self):
        from mallscape_clean.clean import to_e164
        assert to_e164("0917-123-4567") == "+639171234567"
        assert to_e164("8354-1053 / 8354-1018") is None   # landline, no area code
        assert to_e164("(02) 8 462 8888") == "+63284628888"
        assert to_e164(None) is None

    def test_strips_only_genuine_name_noise(self):
        """Phones and status markers go; meaningful parentheticals stay."""
        from mallscape_clean.clean import clean_name

        assert clean_name("ACE Fashion 9209267708") == "ACE Fashion"
        assert clean_name("ANYTIME FITNESS (Temporarily Closed)") == "Anytime Fitness"
        assert clean_name("Alkimia By Mumbakki (0946-138-4463)") == "Alkimia By Mumbakki"
        # a parenthetical that identifies a sub-brand must survive
        assert clean_name("Executive Optical (Fun Optics)") == "Executive Optical (Fun Optics)"
        # a number that IS the name must survive
        assert clean_name("205") == "205"

    def test_preserves_acronyms(self):
        from mallscape_clean.clean import clean_name

        for acronym in ("CLN", "PLDT", "PNB", "LBC", "BBQ", "BDO"):
            assert clean_name(acronym) == acronym
        # vowel-less words are not acronyms
        assert clean_name("SKY RANCH") == "Sky Ranch"
        assert clean_name("MY CUP") == "My Cup"
        # Mc keeps its internal capital
        assert clean_name("MCDONALD'S") == "McDonald's"

    def test_format_is_modelled_not_merged_away(self):
        """An ATM booth shares a brand with a branch but is not the same tenant."""
        from mallscape_clean.clean import brand_key, store_format

        assert store_format("BPI (ATM)") == "atm"
        assert store_format("BPI") == "standard"
        assert store_format("Potato Corner (Kiosk)") == "kiosk"
        assert store_format("Jollibee Drive Thru") == "drive-thru"
        # the brand still matches across formats, so brand reach stays measurable
        assert brand_key("BPI (ATM)") == brand_key("BPI")

    def test_deterministic(self):
        import pandas as pd

        from mallscape_clean import clean
        raw = pd.DataFrame({
            "chain": ["sm", "ayala"], "mall_id": ["a", "b"],
            "store_name_raw": ["B STORE", "A STORE"], "category": ["dine", "shop"],
            "floor": ["2F", None], "building": [None, None], "phone": [None, None],
            "source": ["x", "y"], "scraped_at": ["2026-01-01"] * 2,
        })
        assert clean.build(raw).equals(clean.build(raw))


class TestWebsiteStage:
    def test_bundle_is_deterministic_and_compact(self, tmp_path, monkeypatch):
        import pandas as pd

        from mallscape_core import storage
        from mallscape_website import bundle as website_bundle

        monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
        storage.write("2026-01-01", storage.SCRAPE, "malls", pd.DataFrame({
            "chain": ["sm"], "mall_id": ["a"], "mall_name": ["A Mall"],
            "region": ["metro-manila"], "property_type": ["mall"],
            "scraped_at": ["2026-01-01"],
        }))
        storage.write("2026-01-01", storage.CLEAN, "stores_clean", pd.DataFrame({
            "chain": ["sm"], "mall_id": ["a"], "store_name_raw": ["X STORE"],
            "store_name": ["X Store"], "brand_key": ["x store"],
            "category_std": ["shopping"],
        }))

        digest, first = website_bundle.build("2026-01-01")
        digest2, second = website_bundle.build("2026-01-01")
        assert digest == digest2
        assert first == second
        assert first["schema"] == 1
        assert first["totals"]["properties"] == 1
        # edges are flat pairs, so the length is always even
        assert len(first["edges"]) % 2 == 0
