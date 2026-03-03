import requests

from modules.config import log


class PicqerClient:

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.auth = (api_key, "")

        self._field_ids: dict[str, int] | None = None
        self._tag_map: dict[str, int] | None = None

    def get_field_ids(self) -> dict[str, int]:
        if self._field_ids is not None:
            return self._field_ids

        url = f"{self.base_url}/api/v1/productfields"
        response = requests.get(url, auth=self.auth)
        response.raise_for_status()
        fields = response.json()

        self._field_ids = {}

        for f in fields:
            self._field_ids[f["title"]] = f["idproductfield"]

        log.info("Cached %d product field IDs", len(self._field_ids))
        return self._field_ids

    def get_tag_map(self) -> dict[str, int]:
        if self._tag_map is not None:
            return self._tag_map

        url = f"{self.base_url}/api/v1/tags"
        response = requests.get(url, auth=self.auth)
        response.raise_for_status()
        tags = response.json()

        self._tag_map = {t["title"]: t["idtag"] for t in tags}

        log.info("Cached %d tag IDs", len(self._tag_map))
        return self._tag_map

    def find_product_by_sku(self, sku: str) -> dict | None:
        url = f"{self.base_url}/api/v1/products"
        response = requests.get(url, auth=self.auth, params={"productcode": sku})
        response.raise_for_status()

        results = response.json()

        if not isinstance(results, list) or not results:
            return None

        return results[0]

    def update_product(self, idproduct: int, payload: dict):
        url = f"{self.base_url}/api/v1/products/{idproduct}"
        response = requests.put(url, auth=self.auth, json=payload)
        response.raise_for_status()
        return response.json()

    def get_product_tags(self, idproduct: int) -> list[dict]:
        url = f"{self.base_url}/api/v1/products/{idproduct}/tags"
        response = requests.get(url, auth=self.auth)
        response.raise_for_status()
        return response.json()

    def add_product_tag(self, idproduct: int, idtag: int):
        url = f"{self.base_url}/api/v1/products/{idproduct}/tags"
        response = requests.post(url, auth=self.auth, json={"idtag": idtag})
        response.raise_for_status()

    def remove_product_tag(self, idproduct: int, idtag: int):
        url = f"{self.base_url}/api/v1/products/{idproduct}/tags/{idtag}"
        response = requests.delete(url, auth=self.auth)
        response.raise_for_status()
