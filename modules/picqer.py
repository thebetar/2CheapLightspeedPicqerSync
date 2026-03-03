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
        resp = requests.get(url, auth=self.auth)
        resp.raise_for_status()
        fields = resp.json()

        self._field_ids = {}
        for f in fields:
            title = f.get("title", f.get("name", ""))
            self._field_ids[title] = f["idproductfield"]
            if f.get("name"):
                self._field_ids[f["name"]] = f["idproductfield"]

        log.info("Cached %d product field IDs", len(self._field_ids))
        return self._field_ids

    def get_tag_map(self) -> dict[str, int]:
        if self._tag_map is not None:
            return self._tag_map

        url = f"{self.base_url}/api/v1/tags"
        resp = requests.get(url, auth=self.auth)
        resp.raise_for_status()
        self._tag_map = {t["name"]: t["idtag"] for t in resp.json()}

        log.info("Cached %d tag IDs", len(self._tag_map))
        return self._tag_map

    def find_product_by_sku(self, sku: str) -> dict | None:
        url = f"{self.base_url}/api/v1/products"
        resp = requests.get(url, auth=self.auth, params={"productcode": sku})
        resp.raise_for_status()
        results = resp.json()

        if not isinstance(results, list) or not results:
            return None

        return results[0]

    def update_product(self, idproduct: int, payload: dict):
        url = f"{self.base_url}/api/v1/products/{idproduct}"
        resp = requests.put(url, auth=self.auth, json=payload)
        resp.raise_for_status()
        return resp.json()

    def get_product_tags(self, idproduct: int) -> list[dict]:
        url = f"{self.base_url}/api/v1/products/{idproduct}/tags"
        resp = requests.get(url, auth=self.auth)
        resp.raise_for_status()
        return resp.json()

    def add_product_tag(self, idproduct: int, idtag: int):
        url = f"{self.base_url}/api/v1/products/{idproduct}/tags"
        resp = requests.post(url, auth=self.auth, json={"idtag": idtag})
        resp.raise_for_status()

    def remove_product_tag(self, idproduct: int, idtag: int):
        url = f"{self.base_url}/api/v1/products/{idproduct}/tags/{idtag}"
        resp = requests.delete(url, auth=self.auth)
        resp.raise_for_status()
