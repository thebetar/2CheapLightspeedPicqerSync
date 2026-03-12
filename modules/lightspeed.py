import os
import json
import time
from typing import Dict, List, Tuple
import requests
from dotenv import load_dotenv

load_dotenv()

from modules.config import log


class LightspeedClient:

    def __init__(self, base_url: str, api_key: str, api_secret: str):
        self.base_url = base_url.rstrip("/")
        self.auth = (api_key, api_secret)

    def fetch_all(self, resource: str) -> list:
        page = 1
        all_items: list = []

        while True:
            try:
                url = f"{self.base_url}/nl/{resource}.json"
                resp = requests.get(
                    url, auth=self.auth, params={"limit": 250, "page": page}, timeout=30
                )
                resp.raise_for_status()
                items = resp.json().get(resource, [])

                if not items:
                    break

                all_items.extend(items)
                log.info(
                    "Fetched %d %s (total: %d)", len(items), resource, len(all_items)
                )

                if len(items) < 250:
                    break

                page += 1
            except requests.RequestException as e:
                # Check if 429 and log retry time if available
                if e.response is not None and e.response.status_code == 429:
                    log.warning(
                        "Rate limited when fetching %s page %d. No retry time provided (sleeping for 120 seconds).",
                        resource,
                        page,
                    )
                    time.sleep(120)

                log.error("Error fetching %s page %d: %s", resource, page, e)
                break

        return all_items

    def fetch_variants(self) -> Tuple[List[Dict], List[Dict]]:
        log.info("Fetching Lightspeed products...")
        products = self.fetch_all("products")
        product_map = {p["id"]: p for p in products}

        with open("data/lightspeed_products.json", "w") as f:
            json.dump(products, f, indent=2)

        log.info("Fetching Lightspeed variants...")
        variants = self.fetch_all("variants")

        for v in variants:
            pid = v["product"]["resource"]["id"]
            product = product_map.get(pid, {})

            v["product_title"] = product.get("title", "")
            v["product_fulltitle"] = product.get("fulltitle", "")
            v["product_data01"] = product.get("data01", "")

        with open("data/lightspeed_variants.json", "w") as f:
            json.dump(variants, f, indent=2)

        log.info("Total variants to sync: %d", len(variants))
        return variants, products

    @staticmethod
    def load_variants_from_cache(
        path: str = "data/lightspeed_variants.json",
    ) -> List[Dict]:
        with open(path, "r") as f:
            return json.load(f)


if __name__ == "__main__":  # pragma: no cover
    url = os.getenv("LIGHTSPEED_BASE_URL")
    key = os.getenv("2CHEAP_LIGHTSPEED_API_KEY")
    secret = os.getenv("2CHEAP_LIGHTSPEED_API_SECRET")

    lightspeed = LightspeedClient(url, key, secret)
    variants = lightspeed.fetch_variants()
    log.info("Fetched %d variants", len(variants))
