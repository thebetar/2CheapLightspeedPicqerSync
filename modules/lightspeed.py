import json

import requests

from modules.config import log


class LightspeedClient:

    def __init__(self, base_url: str, api_key: str, api_secret: str):
        self.base_url = base_url.rstrip("/")
        self.auth = (api_key, api_secret)

    def fetch_all(self, resource: str) -> list:
        page = 1
        all_items: list = []

        while True:
            url = f"{self.base_url}/nl/{resource}.json"
            resp = requests.get(
                url, auth=self.auth, params={"limit": 250, "page": page}
            )
            resp.raise_for_status()
            items = resp.json().get(resource, [])

            if not items:
                break

            all_items.extend(items)
            log.info("Fetched %d %s (total: %d)", len(items), resource, len(all_items))

            if len(items) < 250:
                break

            page += 1

        return all_items

    def fetch_variants(self) -> list[dict]:
        log.info("Fetching Lightspeed products...")
        products = self.fetch_all("products")
        product_map = {p["id"]: p for p in products}

        log.info("Fetching Lightspeed variants...")
        variants = self.fetch_all("variants")

        for v in variants:
            pid = v["product"]["resource"]["id"]
            product = product_map.get(pid, {})

            v["product_title"] = product.get("title", "")
            v["product_fulltitle"] = product.get("fulltitle", "")
            v["product_data01"] = product.get("data01", "")

        log.info("Total variants to sync: %d", len(variants))
        return variants

    @staticmethod
    def load_variants_from_cache(path: str = "lightspeed_variants.json") -> list[dict]:
        with open(path, "r") as f:
            return json.load(f)
