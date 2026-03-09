import os
import json
import time
from typing import Dict, List, Optional
import requests
from dotenv import load_dotenv

load_dotenv()

from modules.config import log


class PicqerClient:

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.auth = (api_key, "")

        self.productfields_title_id_map: Optional[Dict[str, int]] = None
        self.tags_title_id_map: Optional[Dict[str, int]] = None

    def _request(self, method, url: str, **kwargs):
        """Make an HTTP request, retrying up to 5 times on 429 with a 60-second wait."""
        for attempt in range(1, 6):
            response = method(url, **kwargs)
            if response.status_code != 429:
                response.raise_for_status()
                return response
            if attempt < 5:
                log.warning(
                    "Rate limited (429) on %s, waiting 60 s before retry %d/5...",
                    url,
                    attempt,
                )
                time.sleep(60)
        raise RuntimeError(f"Rate limited after 5 retries: {url}")

    def get_field_ids(self) -> Dict[str, int]:
        if self.productfields_title_id_map is not None:
            return self.productfields_title_id_map

        url = f"{self.base_url}/api/v1/productfields"
        response = self._request(requests.get, url, auth=self.auth)
        fields = response.json()

        with open("data/picqer_fields.json", "w") as f:
            json.dump(fields, f, indent=2)

        self.productfields_title_id_map = {}

        for f in fields:
            self.productfields_title_id_map[f["title"]] = f["idproductfield"]

        with open("data/picqer_field_ids.json", "w") as f:
            json.dump(self.productfields_title_id_map, f, indent=2)

        log.info("Cached %d product field IDs", len(self.productfields_title_id_map))
        return self.productfields_title_id_map

    def get_tag_map(self) -> Dict[str, int]:
        if self.tags_title_id_map is not None:
            return self.tags_title_id_map

        url = f"{self.base_url}/api/v1/tags"
        response = self._request(requests.get, url, auth=self.auth)
        tags = response.json()

        with open("data/picqer_tags.json", "w") as f:
            json.dump(tags, f, indent=2)

        self.tags_title_id_map = {t["title"]: t["idtag"] for t in tags}

        with open("data/picqer_tag_ids.json", "w") as f:
            json.dump(self.tags_title_id_map, f, indent=2)

        log.info("Cached %d tag IDs", len(self.tags_title_id_map))
        return self.tags_title_id_map

    def fetch_all_products(self) -> List[Dict]:
        url = f"{self.base_url}/api/v1/products"
        all_products: List[Dict] = []
        offset = 0

        while True:
            response = self._request(
                requests.get, url, auth=self.auth, params={"offset": offset}
            )
            products = response.json()

            if not products:
                break

            all_products.extend(products)
            log.info(
                "Fetched %d Picqer products (total: %d)",
                len(products),
                len(all_products),
            )

            if len(products) < 100:
                break

            offset = len(all_products)

        with open("data/picqer_products.json", "w") as f:
            json.dump(all_products, f, indent=2)

        return all_products

    @staticmethod
    def load_products_from_cache(path: str = "data/picqer_products.json") -> List[Dict]:
        with open(path, "r") as f:
            return json.load(f)

    def update_product(self, idproduct: int, payload: dict):
        url = f"{self.base_url}/api/v1/products/{idproduct}"
        response = self._request(requests.put, url, auth=self.auth, json=payload)
        return response.json()

    def get_product_tags(self, idproduct: int) -> List[Dict]:
        url = f"{self.base_url}/api/v1/products/{idproduct}/tags"
        response = self._request(requests.get, url, auth=self.auth)
        return response.json()

    def add_product_tag(self, idproduct: int, idtag: int):
        url = f"{self.base_url}/api/v1/products/{idproduct}/tags"
        self._request(requests.post, url, auth=self.auth, json={"idtag": idtag})

    def remove_product_tag(self, idproduct: int, idtag: int):
        url = f"{self.base_url}/api/v1/products/{idproduct}/tags/{idtag}"
        self._request(requests.delete, url, auth=self.auth)


if __name__ == "__main__":  # pragma: no cover
    picqer_url = os.getenv("PICQER_BASE_URL")
    picqer_key = os.getenv("PICQER_API_KEY")

    picqer = PicqerClient(base_url=picqer_url, api_key=picqer_key)

    field_ids = picqer.get_field_ids()
    tag_map = picqer.get_tag_map()

    # 3) Load all Picqer products into a map by SKU
    products = picqer.fetch_all_products()
    products_by_sku = {p["productcode"]: p for p in products}
    log.info("Loaded %d Picqer products into SKU map", len(products_by_sku))
