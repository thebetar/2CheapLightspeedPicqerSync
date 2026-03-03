"""Tests for modules/lightspeed.py — LightspeedClient."""

from unittest.mock import patch, MagicMock

import pytest

from modules.lightspeed import LightspeedClient


@pytest.fixture
def client():
    return LightspeedClient("https://api.webshopapp.com", "key", "secret")


class TestLightspeedClientInit:

    def test_strips_trailing_slash(self):
        c = LightspeedClient("https://api.webshopapp.com/", "k", "s")
        assert c.base_url == "https://api.webshopapp.com"

    def test_auth_tuple(self):
        c = LightspeedClient("https://api.webshopapp.com", "mykey", "mysecret")
        assert c.auth == ("mykey", "mysecret")


class TestFetchAll:

    @patch("modules.lightspeed.requests.get")
    def test_single_page(self, mock_get, client):
        mock_get.return_value = MagicMock(status_code=200)
        mock_get.return_value.json.return_value = {"products": [{"id": 1}, {"id": 2}]}

        result = client.fetch_all("products")

        assert result == [{"id": 1}, {"id": 2}]
        assert mock_get.call_count == 1

    @patch("modules.lightspeed.requests.get")
    def test_multiple_pages(self, mock_get, client):
        page1 = MagicMock(status_code=200)
        page1.json.return_value = {"items": [{"id": i} for i in range(250)]}

        page2 = MagicMock(status_code=200)
        page2.json.return_value = {"items": [{"id": 250}]}

        mock_get.side_effect = [page1, page2]

        result = client.fetch_all("items")

        assert len(result) == 251
        assert mock_get.call_count == 2

    @patch("modules.lightspeed.requests.get")
    def test_empty_resource(self, mock_get, client):
        mock_get.return_value = MagicMock(status_code=200)
        mock_get.return_value.json.return_value = {"products": []}

        result = client.fetch_all("products")

        assert result == []


class TestFetchVariants:

    @patch("modules.lightspeed.requests.get")
    def test_merges_product_fields_into_variants(self, mock_get, client):
        products_resp = MagicMock(status_code=200)
        products_resp.json.return_value = {
            "products": [
                {
                    "id": 100,
                    "title": "Short",
                    "fulltitle": "Brand Short",
                    "data01": "3-5 dagen",
                },
            ]
        }

        variants_resp = MagicMock(status_code=200)
        variants_resp.json.return_value = {
            "variants": [
                {
                    "id": 1,
                    "sku": "SKU-001",
                    "weight": 25,
                    "product": {"resource": {"id": 100}},
                },
            ]
        }

        mock_get.side_effect = [products_resp, variants_resp]

        result = client.fetch_variants()

        assert len(result) == 1
        assert result[0]["product_title"] == "Short"
        assert result[0]["product_fulltitle"] == "Brand Short"
        assert result[0]["product_data01"] == "3-5 dagen"

    @patch("modules.lightspeed.requests.get")
    def test_missing_product_uses_empty_strings(self, mock_get, client):
        products_resp = MagicMock(status_code=200)
        products_resp.json.return_value = {"products": []}

        variants_resp = MagicMock(status_code=200)
        variants_resp.json.return_value = {
            "variants": [
                {
                    "id": 1,
                    "sku": "ORPHAN",
                    "product": {"resource": {"id": 999}},
                },
            ]
        }

        mock_get.side_effect = [products_resp, variants_resp]

        result = client.fetch_variants()

        assert result[0]["product_fulltitle"] == ""
