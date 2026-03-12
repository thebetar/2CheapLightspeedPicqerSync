"""Tests for main.py — run_sync orchestration."""

import os
from unittest.mock import MagicMock, patch

import pytest
import requests

import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MOCK_FIELD_IDS = {"Beschikbaar": 10, "Verzend": 20}
MOCK_TAG_MAP = {"DHL Small": 2}
MOCK_SHOP = {"name": "TestShop", "api_key": "ls-key", "api_secret": "ls-secret"}
MOCK_SHOP_NO_CREDS = {"name": "TestShop", "api_key": "", "api_secret": ""}


def _make_variant(sku="SKU-001", **kwargs):
    base = {
        "sku": sku,
        "weight": 100,
        "weightUnit": "g",
        "stockTracking": "indicator",
        "product_fulltitle": "Test Product",
    }
    base.update(kwargs)
    return base


def _make_picqer_product(productcode="SKU-001", **kwargs):
    base = {
        "idproduct": 1,
        "productcode": productcode,
        "name": "Test Product",
        "weight": 100,
        "productfields": [],
    }
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_picqer_instance():
    client = MagicMock()
    client.get_field_ids.return_value = MOCK_FIELD_IDS
    client.get_tag_map.return_value = MOCK_TAG_MAP
    client.fetch_all_products.return_value = []
    return client


@pytest.fixture
def patched_run(mock_picqer_instance):
    """Full set of patches for a standard (non-cache) sync run."""
    with (
        patch.dict(os.environ, {"USE_CACHE": "false", "DRY_RUN": "false"}),
        patch("main.PICQER_BASE_URL", "https://test.picqer.com"),
        patch("main.PICQER_API_KEY", "test-key"),
        patch("main.PicqerClient", return_value=mock_picqer_instance),
        patch("main.LightspeedClient") as MockLS,
        patch("main.sync_product", return_value=True) as mock_sync,
    ):
        MockLS.return_value.fetch_variants.return_value = ([], {})
        yield {
            "MockLS": MockLS,
            "picqer": mock_picqer_instance,
            "sync_product": mock_sync,
        }


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------


class TestRunSyncConfigValidation:

    def test_raises_when_picqer_url_missing(self):
        with patch("main.PICQER_BASE_URL", ""), patch("main.PICQER_API_KEY", "key"):
            with pytest.raises(RuntimeError, match="PICQER_BASE_URL"):
                main.run_sync(MOCK_SHOP)

    def test_raises_when_picqer_key_missing(self):
        with (
            patch("main.PICQER_BASE_URL", "https://x.com"),
            patch("main.PICQER_API_KEY", ""),
        ):
            with pytest.raises(RuntimeError, match="PICQER_API_KEY"):
                main.run_sync(MOCK_SHOP)

    def test_raises_when_lightspeed_credentials_missing(self):
        with (
            patch.dict(os.environ, {"USE_CACHE": "false"}),
            patch("main.PICQER_BASE_URL", "https://x.com"),
            patch("main.PICQER_API_KEY", "key"),
        ):
            with pytest.raises(RuntimeError, match="Lightspeed API credentials"):
                main.run_sync(MOCK_SHOP_NO_CREDS)


# ---------------------------------------------------------------------------
# Variant filtering / skipping
# ---------------------------------------------------------------------------


class TestRunSyncSkipping:

    def test_skips_variant_with_no_sku(self, patched_run):
        patched_run["MockLS"].return_value.fetch_variants.return_value = (
            [{"id": 99}],
            {},
        )
        main.run_sync(MOCK_SHOP)
        patched_run["sync_product"].assert_not_called()

    def test_skips_variant_not_found_in_picqer(self, patched_run):
        patched_run["MockLS"].return_value.fetch_variants.return_value = (
            [_make_variant("MISSING-SKU")],
            {},
        )
        patched_run["picqer"].fetch_all_products.return_value = []
        main.run_sync(MOCK_SHOP)
        patched_run["sync_product"].assert_not_called()

    def test_skips_when_test_skus_filter_active(self, patched_run):
        patched_run["MockLS"].return_value.fetch_variants.return_value = (
            [_make_variant("OTHER-SKU")],
            {},
        )
        patched_run["picqer"].fetch_all_products.return_value = [
            _make_picqer_product("OTHER-SKU")
        ]
        with patch("main.TEST_SKUS", ["ALLOWED-SKU"]):
            main.run_sync(MOCK_SHOP)
        patched_run["sync_product"].assert_not_called()

    def test_does_not_skip_when_test_skus_empty(self, patched_run):
        patched_run["MockLS"].return_value.fetch_variants.return_value = (
            [_make_variant("SKU-001")],
            {},
        )
        patched_run["picqer"].fetch_all_products.return_value = [
            _make_picqer_product("SKU-001")
        ]
        with patch("main.TEST_SKUS", []):
            main.run_sync(MOCK_SHOP)
        patched_run["sync_product"].assert_called_once()


# ---------------------------------------------------------------------------
# Updated / skipped / error counting
# ---------------------------------------------------------------------------


class TestRunSyncCounting:

    def test_sync_product_called_with_correct_args(self, patched_run):
        product = _make_picqer_product("SKU-001")
        variant = _make_variant("SKU-001")
        patched_run["MockLS"].return_value.fetch_variants.return_value = ([variant], {})
        patched_run["picqer"].fetch_all_products.return_value = [product]

        main.run_sync(MOCK_SHOP)

        args = patched_run["sync_product"].call_args[0]
        assert args[1] is variant
        assert args[2] is product
        assert args[3] == MOCK_FIELD_IDS
        assert args[4] == MOCK_TAG_MAP
        assert args[5] is False  # dry_run

    def test_updated_when_sync_returns_true(self, patched_run):
        patched_run["MockLS"].return_value.fetch_variants.return_value = (
            [_make_variant("SKU-001")],
            {},
        )
        patched_run["picqer"].fetch_all_products.return_value = [
            _make_picqer_product("SKU-001")
        ]
        patched_run["sync_product"].return_value = True
        main.run_sync(MOCK_SHOP)  # completes without error; updated=1

    def test_skipped_when_sync_returns_false(self, patched_run):
        patched_run["MockLS"].return_value.fetch_variants.return_value = (
            [_make_variant("SKU-001")],
            {},
        )
        patched_run["picqer"].fetch_all_products.return_value = [
            _make_picqer_product("SKU-001")
        ]
        patched_run["sync_product"].return_value = False
        main.run_sync(MOCK_SHOP)  # completes without error; skipped counted

    def test_request_exception_does_not_crash_run(self, patched_run):
        patched_run["MockLS"].return_value.fetch_variants.return_value = (
            [_make_variant("SKU-001")],
            {},
        )
        patched_run["picqer"].fetch_all_products.return_value = [
            _make_picqer_product("SKU-001")
        ]
        patched_run["sync_product"].side_effect = requests.RequestException("timeout")
        main.run_sync(MOCK_SHOP)  # must not raise; errors=1

    def test_unexpected_exception_does_not_crash_run(self, patched_run):
        patched_run["MockLS"].return_value.fetch_variants.return_value = (
            [_make_variant("SKU-001")],
            {},
        )
        patched_run["picqer"].fetch_all_products.return_value = [
            _make_picqer_product("SKU-001")
        ]
        patched_run["sync_product"].side_effect = ValueError("unexpected")
        main.run_sync(MOCK_SHOP)  # must not raise; errors=1

    def test_continues_after_error(self, patched_run):
        """A failing variant should not prevent subsequent variants from syncing."""
        products = [_make_picqer_product("SKU-001"), _make_picqer_product("SKU-002")]
        variants = [_make_variant("SKU-001"), _make_variant("SKU-002")]
        patched_run["MockLS"].return_value.fetch_variants.return_value = (variants, {})
        patched_run["picqer"].fetch_all_products.return_value = products
        patched_run["sync_product"].side_effect = [
            requests.RequestException("fail"),
            True,
        ]
        main.run_sync(MOCK_SHOP)
        assert patched_run["sync_product"].call_count == 2

    def test_mixed_results(self, patched_run):
        """updated=1, skipped=1, errors=1 across three variants."""
        products = [
            _make_picqer_product("SKU-001"),
            _make_picqer_product("SKU-002"),
            _make_picqer_product("SKU-003"),
        ]
        variants = [
            _make_variant("SKU-001"),
            _make_variant("SKU-002"),
            _make_variant("SKU-003"),
        ]
        patched_run["MockLS"].return_value.fetch_variants.return_value = (variants, {})
        patched_run["picqer"].fetch_all_products.return_value = products
        patched_run["sync_product"].side_effect = [
            True,
            False,
            requests.RequestException("err"),
        ]
        main.run_sync(MOCK_SHOP)
        assert patched_run["sync_product"].call_count == 3


# ---------------------------------------------------------------------------
# Cache mode
# ---------------------------------------------------------------------------


class TestRunSyncCacheMode:

    def test_uses_lightspeed_cache_and_skips_constructor(self):
        with (
            patch.dict(os.environ, {"USE_CACHE": "true", "DRY_RUN": "false"}),
            patch("main.PICQER_BASE_URL", "https://x.com"),
            patch("main.PICQER_API_KEY", "key"),
            patch("main.PicqerClient") as MockPicqer,
            patch("main.LightspeedClient") as MockLS,
            patch("main.sync_product"),
        ):
            MockPicqer.return_value.get_field_ids.return_value = MOCK_FIELD_IDS
            MockPicqer.return_value.get_tag_map.return_value = MOCK_TAG_MAP
            MockLS.load_variants_from_cache.return_value = []
            MockPicqer.load_products_from_cache.return_value = []

            main.run_sync(MOCK_SHOP)

            MockLS.load_variants_from_cache.assert_called_once()
            MockLS.assert_not_called()  # constructor never invoked

    def test_uses_picqer_cache_and_skips_fetch(self):
        with (
            patch.dict(os.environ, {"USE_CACHE": "true", "DRY_RUN": "false"}),
            patch("main.PICQER_BASE_URL", "https://x.com"),
            patch("main.PICQER_API_KEY", "key"),
            patch("main.PicqerClient") as MockPicqer,
            patch("main.LightspeedClient") as MockLS,
            patch("main.sync_product"),
        ):
            MockPicqer.return_value.get_field_ids.return_value = MOCK_FIELD_IDS
            MockPicqer.return_value.get_tag_map.return_value = MOCK_TAG_MAP
            MockLS.load_variants_from_cache.return_value = []
            MockPicqer.load_products_from_cache.return_value = []

            main.run_sync(MOCK_SHOP)

            MockPicqer.load_products_from_cache.assert_called_once()
            MockPicqer.return_value.fetch_all_products.assert_not_called()


# ---------------------------------------------------------------------------
# Dry-run mode
# ---------------------------------------------------------------------------


class TestRunSyncDryRun:

    def test_dry_run_flag_passed_to_sync_product(self):
        product = _make_picqer_product("SKU-001")
        with (
            patch.dict(os.environ, {"USE_CACHE": "false", "DRY_RUN": "true"}),
            patch("main.PICQER_BASE_URL", "https://x.com"),
            patch("main.PICQER_API_KEY", "key"),
            patch("main.PicqerClient") as MockPicqer,
            patch("main.LightspeedClient") as MockLS,
            patch("main.sync_product", return_value=True) as mock_sync,
        ):
            MockPicqer.return_value.get_field_ids.return_value = MOCK_FIELD_IDS
            MockPicqer.return_value.get_tag_map.return_value = MOCK_TAG_MAP
            MockPicqer.return_value.fetch_all_products.return_value = [product]
            MockLS.return_value.fetch_variants.return_value = (
                [_make_variant("SKU-001")],
                {},
            )

            main.run_sync(MOCK_SHOP)

            dry_run_arg = mock_sync.call_args[0][5]
            assert dry_run_arg is True
