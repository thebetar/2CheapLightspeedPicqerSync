"""Tests for modules/picqer.py — PicqerClient."""

from unittest.mock import patch, MagicMock

import pytest

from modules.picqer import PicqerClient


@pytest.fixture
def client():
    return PicqerClient("https://test.picqer.com", "test-api-key")


class TestPicqerClientInit:

    def test_strips_trailing_slash(self):
        c = PicqerClient("https://test.picqer.com/", "key")
        assert c.base_url == "https://test.picqer.com"

    def test_auth_tuple(self):
        c = PicqerClient("https://test.picqer.com", "mykey")
        assert c.auth == ("mykey", "")


class TestPicqerClientFieldIds:

    @patch("modules.picqer.requests.get")
    def test_caches_after_first_call(self, mock_get, client):
        mock_get.return_value = MagicMock(status_code=200)
        mock_get.return_value.json.return_value = [
            {"title": "Levertijd", "name": "levertijd", "idproductfield": 10},
            {"title": "Verzend", "name": "verzend", "idproductfield": 20},
        ]

        first = client.get_field_ids()
        second = client.get_field_ids()

        assert first is second
        assert mock_get.call_count == 1  # only one API call

    @patch("modules.picqer.requests.get")
    def test_indexes_by_title_and_name(self, mock_get, client):
        mock_get.return_value = MagicMock(status_code=200)
        mock_get.return_value.json.return_value = [
            {"title": "Levertijd", "name": "levertijd_field", "idproductfield": 10},
        ]

        ids = client.get_field_ids()

        assert ids["Levertijd"] == 10
        assert ids["levertijd_field"] == 10


class TestPicqerClientTagMap:

    @patch("modules.picqer.requests.get")
    def test_returns_name_to_id_map(self, mock_get, client):
        mock_get.return_value = MagicMock(status_code=200)
        mock_get.return_value.json.return_value = [
            {"name": "Briefpost", "idtag": 1},
            {"name": "DHL Small", "idtag": 2},
        ]

        tags = client.get_tag_map()

        assert tags == {"Briefpost": 1, "DHL Small": 2}


class TestFindProductBySku:

    @patch("modules.picqer.requests.get")
    def test_returns_first_match(self, mock_get, client):
        mock_get.return_value = MagicMock(status_code=200)
        mock_get.return_value.json.return_value = [
            {"idproduct": 42, "productcode": "SKU1"}
        ]

        result = client.find_product_by_sku("SKU1")

        assert result == {"idproduct": 42, "productcode": "SKU1"}

    @patch("modules.picqer.requests.get")
    def test_returns_none_when_empty(self, mock_get, client):
        mock_get.return_value = MagicMock(status_code=200)
        mock_get.return_value.json.return_value = []

        result = client.find_product_by_sku("NONEXISTENT")

        assert result is None
