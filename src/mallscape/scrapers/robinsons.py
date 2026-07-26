"""Robinsons Malls scraper.

Two complementary sources (verified 2026-07):

1. Drupal site ``robinsonsmalls.com/mall-info/<slug>`` — primary. The store
   directory is embedded inline: ``<li class="store-name level-N">Name | phone</li>``
   grouped under ``div.field--name-field-level-N`` blocks whose
   ``h4.field--label`` holds the floor label. Floor + phone, no category.
2. VMD site ``vmd.robinsonsmalls.com`` (Google Sites on a custom domain) —
   canonical region-grouped mall list at ``/list-of-malls`` and a fallback
   store directory (category sections + "📍 <floor>" markers) for malls that
   have no Drupal page yet (e.g. The Plaza Bagong Silang).

Mall discovery reconciles a verified slug registry
(``registry/robinsons_malls.json``) against both live sources plus the
``chat_widget.chatbots`` roster embedded in every Drupal page, so brand-new
malls surface as warnings instead of being silently missed.
"""

from __future__ import annotations

import json
import re
import unicodedata
from importlib import resources

from selectolax.parser import HTMLParser

from ..models import Mall, Store
from .base import MallChainScraper

DRUPAL_BASE = "https://robinsonsmalls.com/mall-info/"
VMD_BASE = "https://vmd.robinsonsmalls.com"
SLUG_PATTERNS = ("robinsons-place-{}", "robinsons-{}", "{}")


def _norm_key(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", " ", s.lower())
    s = re.sub(r"\b(robinsons|place|town|mall|the)\b", " ", s)
    return re.sub(r"\s+", "", s)


def load_registry() -> list[dict]:
    raw = resources.files("mallscape.registry").joinpath("robinsons_malls.json").read_text()
    return json.loads(raw)["malls"]


class RobinsonsScraper(MallChainScraper):
    chain = "robinsons"

    # ---------- discovery ----------

    def _live_vmd_slugs(self) -> dict[str, str]:
        """slug -> region from the VMD list-of-malls page."""
        html = self.fetcher.get_text(f"{VMD_BASE}/list-of-malls")
        found = {}
        for region, slug in re.findall(r'href="/list-of-malls/([a-z-]+)/([a-z0-9-]+)"', html):
            found[slug] = region
        return found

    def _live_chatbot_roster(self) -> dict[str, str]:
        """mall display name -> region from drupal-settings-json chat widget."""
        html = self.fetcher.get_text("https://robinsonsmalls.com/mall-info")
        m = re.search(
            r'data-drupal-selector="drupal-settings-json">(.*?)</script>', html, re.S
        )
        if not m:
            self.warn("could not find drupal-settings-json on /mall-info")
            return {}
        settings = json.loads(m.group(1))
        roster = {}
        for region, bots in settings.get("chat_widget", {}).get("chatbots", {}).items():
            for bot in bots:
                roster[bot["name"]] = region.replace("_", "-")
        return roster

    def discover_malls(self) -> list[Mall]:
        registry = load_registry()
        by_key = {_norm_key(entry["name"]): entry for entry in registry}
        known_vmd = {e["vmd_slug"] for e in registry if e["vmd_slug"]}
        known_drupal = {e["drupal_slug"] for e in registry if e["drupal_slug"]}

        # New malls on the VMD site that the registry doesn't know yet.
        live_vmd = self._live_vmd_slugs()
        for slug, region in live_vmd.items():
            if slug in known_vmd:
                continue
            entry = {
                "name": slug.replace("-", " ").title(),
                "region": region,
                "drupal_slug": self._resolve_drupal_slug(slug),
                "vmd_slug": slug,
            }
            registry.append(entry)
            self.warn(
                f"NEW mall on VMD not in registry: {slug} ({region}) — "
                f"drupal_slug={entry['drupal_slug']} — add it to robinsons_malls.json"
            )

        # Chatbot roster names that match nothing we know → likely a new mall
        # that hasn't reached the VMD site either.
        for name, region in self._live_chatbot_roster().items():
            key = _norm_key(name)
            # prefix match: the widget uses short names ("The Plaza", "Gen San")
            if not any(k.startswith(key) or key.startswith(k) for k in by_key):
                self.warn(f"chat-widget mall not matched to registry: {name} ({region})")

        malls = []
        for entry in registry:
            mall_id = entry["vmd_slug"] or entry["drupal_slug"]
            source = (
                DRUPAL_BASE + entry["drupal_slug"]
                if entry["drupal_slug"]
                else f"{VMD_BASE}/list-of-malls/{entry['region']}/{entry['vmd_slug']}"
            )
            malls.append(
                Mall(
                    chain=self.chain,
                    mall_id=mall_id,
                    mall_name=entry["name"],
                    region=entry["region"],
                    source_url=source,
                    extra={"drupal_slug": entry["drupal_slug"], "vmd_slug": entry["vmd_slug"]},
                )
            )
        return malls

    def _resolve_drupal_slug(self, vmd_slug: str) -> str | None:
        """Try the known Drupal slug patterns for a newly discovered mall."""
        stem = re.sub(r"^robinsons-", "", vmd_slug)
        for pattern in SLUG_PATTERNS:
            candidate = pattern.format(stem)
            try:
                html = self.fetcher.get_text(DRUPAL_BASE + candidate)
            except Exception:
                continue
            if "store-name" in html:
                return candidate
        return None

    # ---------- per-mall scraping ----------

    def scrape_mall(self, mall: Mall) -> list[Store]:
        drupal_slug = mall.extra.get("drupal_slug")
        stores: list[Store] = []
        if drupal_slug:
            html = self.fetcher.get_text(DRUPAL_BASE + drupal_slug)
            stores = self._parse_drupal(mall, html)
        if not stores and mall.extra.get("vmd_slug"):
            url = f"{VMD_BASE}/list-of-malls/{mall.region}/{mall.extra['vmd_slug']}"
            html = self.fetcher.get_text(url)
            stores = self._parse_vmd(mall, html)
        return stores

    def _parse_drupal(self, mall: Mall, html: str) -> list[Store]:
        tree = HTMLParser(html)
        stores: list[Store] = []
        # floors are separate Drupal fields with varying names: field-level-N,
        # field-basement-N, field-upper-ground, field-linkod-pinoy, ... —
        # match any field block that actually contains store items
        address = tree.css_first("div[class*='field--name-field-address'] .field--item")
        if address is not None and not mall.address:
            mall.address = re.sub(r"\s+", " ", address.text(separator=" ", strip=True)) or None
        for block in tree.css("div[class*='field--name-field-']"):
            items = block.css("li.store-name")
            if not items:
                continue
            label_node = block.css_first("h4.field--label")
            floor = label_node.text(strip=True) if label_node else None
            for item in items:
                text = re.sub(r"\s+", " ", item.text(separator=" ", strip=True))
                if not text:
                    continue
                name, _, phone = (p.strip() for p in text.partition("|"))
                stores.append(
                    Store(
                        chain=self.chain,
                        mall_id=mall.mall_id,
                        store_name_raw=name,
                        floor=floor,
                        phone=phone or None,
                        source="robinsons-drupal",
                    )
                )
        return stores

    def _parse_vmd(self, mall: Mall, html: str) -> list[Store]:
        """Parse a Google Sites mall page: category headings (SHOP/DINE/...)
        followed by store-name paragraphs with '📍 <floor>' markers."""
        tree = HTMLParser(html)
        stores: list[Store] = []
        category: str | None = None
        pending: str | None = None

        def clean(node) -> str:
            return re.sub(r"\s+", " ", node.text(deep=True, separator=" ")).strip()

        # traverse manually: a grouped css() query does not preserve document
        # order across selectors, which would scramble category attribution
        nodes = []
        for node in tree.root.traverse(include_text=False):
            if node.tag in ("h2", "h3") or (
                node.tag == "p" and "zfr3Q" in (node.attributes.get("class") or "")
            ):
                nodes.append(node)

        for node in nodes:
            text = clean(node)
            if not text:
                continue
            if node.tag in ("h2", "h3"):
                if len(text) <= 30:
                    category = text.lower()
                pending = None
                continue
            if "📍" in text:
                name_part, _, floor_part = text.partition("📍")
                name = name_part.strip(" |") or pending
                floor = floor_part.strip(" |") or None
                # skip page-header junk: hours/address blocks before the first
                # real category section, and 📍-marked street addresses
                is_junk = (
                    category in (None, "mall hours")
                    or (floor and "," in floor and len(floor) > 35)
                )
                if name and not is_junk:
                    stores.append(
                        Store(
                            chain=self.chain,
                            mall_id=mall.mall_id,
                            store_name_raw=name,
                            category=category,
                            floor=floor,
                            source="robinsons-vmd",
                        )
                    )
                pending = None
            elif stores and not pending and re.fullmatch(r"(?i)(floor|level|bldg\.?|building|\d+f?)", text):
                # floor phrase split across paragraphs by Google Sites markup
                last = stores[-1]
                last.floor = f"{last.floor} {text}".strip() if last.floor else text
            elif len(text) <= 60:
                pending = text
        return stores
