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
            {"title": "Beschikbaar", "idproductfield": 360},
            {"title": "Verzend", "idproductfield": 1079},
        ]

        first = client.get_field_ids()
        second = client.get_field_ids()

        assert first is second
        assert mock_get.call_count == 1

    @patch("modules.picqer.requests.get")
    def test_indexes_by_title(self, mock_get, client):
        mock_get.return_value = MagicMock(status_code=200)
        mock_get.return_value.json.return_value = [
            {"title": "Beschikbaar", "idproductfield": 360},
            {"title": "Verzend", "idproductfield": 1079},
        ]

        ids = client.get_field_ids()

        assert ids["Beschikbaar"] == 360
        assert ids["Verzend"] == 1079


class TestPicqerClientTagMap:

    @patch("modules.picqer.requests.get")
    def test_returns_name_to_id_map(self, mock_get, client):
        mock_get.return_value = MagicMock(status_code=200)
        mock_get.return_value.json.return_value = [
            {"title": "Briefpost", "idtag": 8125},
            {"title": "DHL Small", "idtag": 11964},
        ]

        tags = client.get_tag_map()

        assert tags == {"Briefpost": 8125, "DHL Small": 11964}


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


class TestUpdateProduct:

    @patch("modules.picqer.requests.put")
    def test_sends_put_and_returns_json(self, mock_put, client):
        mock_put.return_value = MagicMock(status_code=200)
        mock_put.return_value.json.return_value = {"idproduct": 1}

        result = client.update_product(1, {"name": "Test"})

        mock_put.assert_called_once_with(
            "https://test.picqer.com/api/v1/products/1",
            auth=("test-api-key", ""),
            json={"name": "Test"},
        )
        assert result == {"idproduct": 1}


class TestGetProductTags:

    @patch("modules.picqer.requests.get")
    def test_returns_tag_list(self, mock_get, client):
        mock_get.return_value = MagicMock(status_code=200)
        mock_get.return_value.json.return_value = [{"idtag": 1, "name": "Briefpost"}]

        result = client.get_product_tags(42)

        mock_get.assert_called_once_with(
            "https://test.picqer.com/api/v1/products/42/tags",
            auth=("test-api-key", ""),
        )
        assert result == [{"idtag": 1, "name": "Briefpost"}]


class TestAddProductTag:

    @patch("modules.picqer.requests.post")
    def test_sends_post_with_idtag(self, mock_post, client):
        mock_post.return_value = MagicMock(status_code=200)

        client.add_product_tag(42, 5)

        mock_post.assert_called_once_with(
            "https://test.picqer.com/api/v1/products/42/tags",
            auth=("test-api-key", ""),
            json={"idtag": 5},
        )


class TestRemoveProductTag:

    @patch("modules.picqer.requests.delete")
    def test_sends_delete(self, mock_delete, client):
        mock_delete.return_value = MagicMock(status_code=200)

        client.remove_product_tag(42, 5)

        mock_delete.assert_called_once_with(
            "https://test.picqer.com/api/v1/products/42/tags/5",
            auth=("test-api-key", ""),
        )
