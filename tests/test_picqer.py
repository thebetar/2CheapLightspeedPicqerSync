"""Tests for modules/picqer.py — PicqerClient."""

from unittest.mock import patch, MagicMock

import pytest
import requests

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


class TestFetchAllProducts:

    @patch("modules.picqer.requests.get")
    def test_single_page(self, mock_get, client):
        mock_get.return_value = MagicMock(status_code=200)
        mock_get.return_value.json.return_value = [
            {"idproduct": 1, "productcode": "SKU1"},
            {"idproduct": 2, "productcode": "SKU2"},
        ]

        result = client.fetch_all_products()

        assert len(result) == 2
        assert mock_get.call_count == 1

    @patch("modules.picqer.requests.get")
    def test_multiple_pages(self, mock_get, client):
        page1 = MagicMock(status_code=200)
        page1.json.return_value = [{"idproduct": i} for i in range(100)]

        page2 = MagicMock(status_code=200)
        page2.json.return_value = [{"idproduct": 100}]

        mock_get.side_effect = [page1, page2]

        result = client.fetch_all_products()

        assert len(result) == 101
        assert mock_get.call_count == 2

    @patch("modules.picqer.requests.get")
    def test_empty(self, mock_get, client):
        mock_get.return_value = MagicMock(status_code=200)
        mock_get.return_value.json.return_value = []

        result = client.fetch_all_products()

        assert result == []


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


class TestLoadProductsFromCache:

    def test_loads_json_from_file(self, tmp_path):
        cache_file = tmp_path / "products.json"
        cache_file.write_text('[{"idproduct": 1, "productcode": "SKU-1"}]')

        result = PicqerClient.load_products_from_cache(str(cache_file))

        assert result == [{"idproduct": 1, "productcode": "SKU-1"}]


# -- _request retry logic ----------------------------------------------------


class TestRequestRetry:

    def _make_response(self, status_code: int, body=None):
        r = MagicMock(status_code=status_code)
        r.json.return_value = body or {}
        r.raise_for_status.return_value = None
        return r

    def _make_429(self):
        r = MagicMock(status_code=429)
        return r

    @patch("modules.picqer.time.sleep")
    @patch("modules.picqer.requests.put")
    def test_retries_once_after_429_and_succeeds(self, mock_put, mock_sleep, client):
        mock_put.side_effect = [
            self._make_429(),
            self._make_response(200, {"idproduct": 1}),
        ]

        result = client.update_product(1, {"name": "Test"})

        assert result == {"idproduct": 1}
        assert mock_put.call_count == 2
        mock_sleep.assert_called_once_with(60)

    @patch("modules.picqer.time.sleep")
    @patch("modules.picqer.requests.get")
    def test_retries_on_429_for_get_products(self, mock_get, mock_sleep, client):
        ok = self._make_response(200, [{"idproduct": 1, "productcode": "A"}])
        mock_get.side_effect = [self._make_429(), ok]

        result = client.get_product_tags(1)

        assert result == [{"idproduct": 1, "productcode": "A"}]
        assert mock_get.call_count == 2
        mock_sleep.assert_called_once_with(60)

    @patch("modules.picqer.time.sleep")
    @patch("modules.picqer.requests.put")
    def test_raises_after_5_retries(self, mock_put, mock_sleep, client):
        mock_put.return_value = self._make_429()

        with pytest.raises(RuntimeError, match="Rate limited after 5 retries"):
            client.update_product(1, {"name": "Test"})

        assert mock_put.call_count == 5
        assert mock_sleep.call_count == 4  # sleeps between attempts 1-4, not after 5th

    @patch("modules.picqer.time.sleep")
    @patch("modules.picqer.requests.put")
    def test_no_sleep_on_success(self, mock_put, mock_sleep, client):
        mock_put.return_value = self._make_response(200, {"idproduct": 1})

        client.update_product(1, {"name": "Test"})

        mock_sleep.assert_not_called()

    @patch("modules.picqer.time.sleep")
    @patch("modules.picqer.requests.put")
    def test_non_429_error_raises_immediately(self, mock_put, mock_sleep, client):
        r = MagicMock(status_code=500)
        r.raise_for_status.side_effect = requests.HTTPError("500 Server Error")
        mock_put.return_value = r

        with pytest.raises(requests.HTTPError):
            client.update_product(1, {"name": "Test"})

        assert mock_put.call_count == 1
        mock_sleep.assert_not_called()

    @patch("modules.picqer.time.sleep")
    @patch("modules.picqer.requests.put")
    def test_succeeds_on_fifth_attempt(self, mock_put, mock_sleep, client):
        mock_put.side_effect = [
            self._make_429(),
            self._make_429(),
            self._make_429(),
            self._make_429(),
            self._make_response(200, {"idproduct": 99}),
        ]

        result = client.update_product(99, {"name": "Last Try"})

        assert result == {"idproduct": 99}
        assert mock_put.call_count == 5
        assert mock_sleep.call_count == 4
