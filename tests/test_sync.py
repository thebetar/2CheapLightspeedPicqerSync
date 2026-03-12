"""Tests for modules/sync.py — weight, shipping, tag management, and product sync."""

from typing import Dict, List
from unittest.mock import MagicMock, call, patch
from datetime import datetime

import pytest

from modules.sync import (
    get_weight_grams,
    determine_shipping_option,
    build_product_fields,
    manage_shipping_tags,
    sync_product,
)


class TestGetWeightGrams:

    def test_normal_grams(self):
        assert get_weight_grams({"weight": 25, "weightUnit": "g"}) == 25

    def test_kilograms(self):
        assert get_weight_grams({"weight": 1.5, "weightUnit": "kg"}) == 1500

    def test_zero_returns_none(self):
        assert get_weight_grams({"weight": 0, "weightUnit": "g"}) is None

    def test_none_returns_none(self):
        assert get_weight_grams({"weight": None, "weightUnit": "g"}) is None

    def test_missing_weight_returns_none(self):
        assert get_weight_grams({}) is None

    def test_default_unit_is_grams(self):
        assert get_weight_grams({"weight": 100}) == 100


# -- determine_shipping_option -----------------------------------------------


class TestDetermineShippingOption:

    @pytest.mark.parametrize(
        "weight, expected",
        [
            (2, "Briefpost"),
            (25, "DHL Small"),
            (1001, "DPD"),
            (10000, "DHL XXL"),
            (50000, "Speciaal Transport"),
        ],
    )
    def test_exact_matches(self, weight, expected):
        assert determine_shipping_option(weight) == expected

    def test_none_returns_unknown(self):
        assert determine_shipping_option(None) == "VERZENDTYPE ONBEKEND"

    def test_zero_returns_unknown(self):
        assert determine_shipping_option(0) == "VERZENDTYPE ONBEKEND"

    @pytest.mark.parametrize(
        "weight, expected",
        [
            (1, "Briefpost"),
            (5, "Briefpost"),
            (24, "Briefpost"),
            (500, "DHL Small"),
            (1000, "DHL Small"),
            (5000, "DPD"),
            (9999, "DPD"),
            (30000, "DHL XXL"),
            (49999, "DHL XXL"),
            (100000, "Speciaal Transport"),
        ],
    )
    def test_range_fallbacks(self, weight, expected):
        assert determine_shipping_option(weight) == expected


# -- build_product_fields ----------------------------------------------------


class TestBuildProductFields:

    def test_all_fields_present_when_changed(self):
        field_ids = {
            "Beschikbaar": 10,
            "Verzend": 20,
            "Beschikbaar - Aangemaakt op": 30,
        }

        result = build_product_fields(
            field_ids, "DHL Small", "LEVERTIJD", beschikbaar_changed=True
        )

        assert {"idproductfield": 10, "value": "LEVERTIJD"} in result
        assert {"idproductfield": 20, "value": "DHL Small"} in result
        assert any(f["idproductfield"] == 30 and f["value"] != "" for f in result)

    def test_no_timestamp_when_unchanged(self):
        field_ids = {
            "Beschikbaar": 10,
            "Verzend": 20,
            "Beschikbaar - Aangemaakt op": 30,
        }

        result = build_product_fields(
            field_ids, "Briefpost", "", beschikbaar_changed=False
        )

        assert {"idproductfield": 10, "value": ""} in result
        assert {"idproductfield": 20, "value": "Briefpost"} in result
        assert not any(f["idproductfield"] == 30 for f in result)

    def test_no_timestamp_when_changed_to_empty(self):
        field_ids = {
            "Beschikbaar": 10,
            "Verzend": 20,
            "Beschikbaar - Aangemaakt op": 30,
        }

        result = build_product_fields(
            field_ids, "Briefpost", "", beschikbaar_changed=True
        )

        assert {"idproductfield": 10, "value": ""} in result
        assert {"idproductfield": 20, "value": "Briefpost"} in result
        assert not any(f["idproductfield"] == 30 for f in result)

    def test_no_timestamp_when_unchanged_and_levertijd_with_existing_aangemaakt(self):
        field_ids = {
            "Beschikbaar": 10,
            "Verzend": 20,
            "Beschikbaar - Aangemaakt op": 30,
        }

        result = build_product_fields(
            field_ids,
            "Briefpost",
            "LEVERTIJD",
            beschikbaar_changed=False,
            current_aangemaakt="2026-01-01 00:00:00",
        )

        assert not any(f["idproductfield"] == 30 for f in result)

    def test_timestamp_when_levertijd_unchanged_but_aangemaakt_empty(self):
        field_ids = {
            "Beschikbaar": 10,
            "Verzend": 20,
            "Beschikbaar - Aangemaakt op": 30,
        }

        result = build_product_fields(
            field_ids,
            "DHL Small",
            "LEVERTIJD",
            beschikbaar_changed=False,
            current_aangemaakt="",
        )

        assert any(f["idproductfield"] == 30 and f["value"] != "" for f in result)

    def test_empty_values_for_indicator(self):
        field_ids = {"Beschikbaar": 10, "Verzend": 20}

        result = build_product_fields(
            field_ids, "Briefpost", "", beschikbaar_changed=False
        )

        assert result == [
            {"idproductfield": 10, "value": ""},
            {"idproductfield": 20, "value": "Briefpost"},
        ]

    def test_missing_fields_skipped(self):
        result = build_product_fields({}, "DPD", "LEVERTIJD", beschikbaar_changed=True)
        assert result == []

    def test_timestamp_cleared_when_not_levertijd_with_existing_timestamp(self):
        field_ids = {
            "Beschikbaar": 10,
            "Verzend": 20,
            "Beschikbaar - Aangemaakt op": 30,
        }

        result = build_product_fields(
            field_ids,
            "Briefpost",
            "",
            beschikbaar_changed=True,
            current_aangemaakt="2026-01-01 00:00:00",
        )

        assert {"idproductfield": 30, "value": ""} in result

    def test_timestamp_not_cleared_when_not_levertijd_and_no_existing_timestamp(self):
        field_ids = {
            "Beschikbaar": 10,
            "Verzend": 20,
            "Beschikbaar - Aangemaakt op": 30,
        }

        result = build_product_fields(
            field_ids,
            "Briefpost",
            "",
            beschikbaar_changed=False,
            current_aangemaakt="",
        )

        assert not any(f["idproductfield"] == 30 for f in result)


# -- manage_shipping_tags ----------------------------------------------------


class TestManageShippingTags:

    TAG_MAP = {
        "Briefpost": 1,
        "DHL Small": 2,
        "DHL XXL": 3,
        "DPD": 4,
        "Speciaal Transport": 5,
        "VERZENDTYPE ONBEKEND": 6,
    }

    def _make_picqer(self, current_tags: List[Dict]) -> MagicMock:
        picqer = MagicMock()
        picqer.get_product_tags.return_value = current_tags
        return picqer

    def test_adds_tag_when_none_present(self):
        picqer = self._make_picqer([])

        manage_shipping_tags(picqer, 100, "DHL Small", self.TAG_MAP)

        picqer.add_product_tag.assert_called_once_with(100, 2)
        picqer.remove_product_tag.assert_not_called()

    def test_removes_wrong_tag_and_adds_correct(self):
        picqer = self._make_picqer([{"idtag": 1}])  # has Briefpost

        manage_shipping_tags(picqer, 100, "DPD", self.TAG_MAP)

        picqer.remove_product_tag.assert_called_once_with(100, 1)
        picqer.add_product_tag.assert_called_once_with(100, 4)

    def test_leaves_correct_tag_alone(self):
        picqer = self._make_picqer([{"idtag": 4}])  # already DPD

        manage_shipping_tags(picqer, 100, "DPD", self.TAG_MAP)

        picqer.remove_product_tag.assert_not_called()
        picqer.add_product_tag.assert_not_called()

    def test_ignores_non_shipping_tags(self):
        picqer = self._make_picqer([{"idtag": 999}])  # some other tag

        manage_shipping_tags(picqer, 100, "Briefpost", self.TAG_MAP)

        picqer.remove_product_tag.assert_not_called()
        picqer.add_product_tag.assert_called_once_with(100, 1)

    def test_removes_multiple_wrong_tags(self):
        picqer = self._make_picqer(
            [{"idtag": 1}, {"idtag": 2}]
        )  # Briefpost + DHL Small

        manage_shipping_tags(picqer, 100, "DPD", self.TAG_MAP)

        assert picqer.remove_product_tag.call_count == 2
        picqer.add_product_tag.assert_called_once_with(100, 4)

    def test_dry_run_makes_no_changes(self):
        picqer = self._make_picqer([{"idtag": 1}])

        manage_shipping_tags(picqer, 100, "DPD", self.TAG_MAP, dry_run=True)

        picqer.remove_product_tag.assert_not_called()
        picqer.add_product_tag.assert_not_called()


# -- sync_product ------------------------------------------------------------


class TestSyncProduct:

    TAG_MAP = {
        "Briefpost": 1,
        "DHL Small": 2,
        "DHL XXL": 3,
        "DPD": 4,
        "Speciaal Transport": 5,
        "VERZENDTYPE ONBEKEND": 6,
    }

    FIELD_IDS = {
        "Beschikbaar": 10,
        "Verzend": 20,
        "Beschikbaar - Aangemaakt op": 30,
    }

    def _make_picqer(self) -> MagicMock:
        picqer = MagicMock()
        picqer.get_product_tags.return_value = []
        return picqer

    def _make_product(self, **overrides) -> dict:
        base = {"idproduct": 42, "productfields": []}
        base.update(overrides)
        return base

    def _make_variant(self, **overrides) -> dict:
        base = {
            "sku": "TEST-SKU-001",
            "weight": 25,
            "weightUnit": "g",
            "stockTracking": "indicator",
            "product_fulltitle": "Test Product Title",
        }
        base.update(overrides)
        return base

    def test_skips_variant_without_sku(self):
        picqer = self._make_picqer()
        product = self._make_product()
        result = sync_product(
            picqer, {"weight": 25}, product, self.FIELD_IDS, self.TAG_MAP
        )

        assert result is True
        picqer.update_product.assert_called_once()

    def test_updates_product_with_correct_payload(self):
        picqer = self._make_picqer()
        product = self._make_product()
        variant = self._make_variant(weight=1001, stockTracking="indicator")

        result = sync_product(picqer, variant, product, self.FIELD_IDS, self.TAG_MAP)

        assert result is True

        payload = picqer.update_product.call_args[0][1]
        assert payload["name"] == "Test Product Title"
        assert payload["weight"] == 1001
        assert {"idproductfield": 20, "value": "DPD"} in payload["productfields"]
        assert {"idproductfield": 10, "value": ""} in payload["productfields"]

    def test_enabled_stock_tracking_sets_beschikbaar(self):
        picqer = self._make_picqer()
        product = self._make_product()
        variant = self._make_variant(stockTracking="enabled")

        sync_product(picqer, variant, product, self.FIELD_IDS, self.TAG_MAP)

        payload = picqer.update_product.call_args[0][1]

        beschikbaar = next(
            f for f in payload["productfields"] if f["idproductfield"] == 10
        )
        assert beschikbaar["value"] == "LEVERTIJD"

        aangemaakt = next(
            f for f in payload["productfields"] if f["idproductfield"] == 30
        )
        assert aangemaakt["value"] != ""

    def test_indicator_stock_tracking_clears_beschikbaar(self):
        picqer = self._make_picqer()
        product = self._make_product()
        variant = self._make_variant(stockTracking="indicator")

        sync_product(picqer, variant, product, self.FIELD_IDS, self.TAG_MAP)

        payload = picqer.update_product.call_args[0][1]

        beschikbaar = next(
            f for f in payload["productfields"] if f["idproductfield"] == 10
        )
        assert beschikbaar["value"] == ""

    def test_no_timestamp_when_beschikbaar_unchanged(self):
        picqer = self._make_picqer()
        product = self._make_product(
            productfields=[
                {"title": "Beschikbaar", "value": "LEVERTIJD"},
                {
                    "title": "Beschikbaar - Aangemaakt op",
                    "value": "2026-01-01 00:00:00",
                },
            ],
        )
        variant = self._make_variant(stockTracking="enabled")

        sync_product(picqer, variant, product, self.FIELD_IDS, self.TAG_MAP)

        payload = picqer.update_product.call_args[0][1]
        assert not any(f["idproductfield"] == 30 for f in payload["productfields"])

    def test_timestamp_set_when_levertijd_unchanged_but_aangemaakt_empty(self):
        picqer = self._make_picqer()
        product = self._make_product(
            productfields=[
                {"title": "Beschikbaar", "value": "LEVERTIJD"},
                {"title": "Beschikbaar - Aangemaakt op", "value": ""},
            ],
        )
        variant = self._make_variant(stockTracking="enabled")

        sync_product(picqer, variant, product, self.FIELD_IDS, self.TAG_MAP)

        payload = picqer.update_product.call_args[0][1]
        aangemaakt = next(
            f for f in payload["productfields"] if f["idproductfield"] == 30
        )
        assert aangemaakt["value"] != ""

    def test_timestamp_set_when_beschikbaar_changes(self):
        picqer = self._make_picqer()
        product = self._make_product(
            productfields=[{"title": "Beschikbaar", "value": ""}],
        )
        variant = self._make_variant(stockTracking="enabled")

        sync_product(picqer, variant, product, self.FIELD_IDS, self.TAG_MAP)

        payload = picqer.update_product.call_args[0][1]
        aangemaakt = next(
            f for f in payload["productfields"] if f["idproductfield"] == 30
        )
        assert aangemaakt["value"] != ""

    def test_no_timestamp_when_beschikbaar_changes_away_from_levertijd(self):
        picqer = self._make_picqer()
        product = self._make_product(
            productfields=[{"title": "Beschikbaar", "value": "LEVERTIJD"}],
        )
        variant = self._make_variant(stockTracking="indicator")

        sync_product(picqer, variant, product, self.FIELD_IDS, self.TAG_MAP)

        payload = picqer.update_product.call_args[0][1]
        beschikbaar = next(
            f for f in payload["productfields"] if f["idproductfield"] == 10
        )
        assert beschikbaar["value"] == ""
        assert not any(f["idproductfield"] == 30 for f in payload["productfields"])

    def test_timestamp_cleared_when_changing_away_from_levertijd_with_existing_timestamp(
        self,
    ):
        picqer = self._make_picqer()
        product = self._make_product(
            productfields=[
                {"title": "Beschikbaar", "value": "LEVERTIJD"},
                {
                    "title": "Beschikbaar - Aangemaakt op",
                    "value": "2026-01-01 00:00:00",
                },
            ],
        )
        variant = self._make_variant(stockTracking="indicator")

        sync_product(picqer, variant, product, self.FIELD_IDS, self.TAG_MAP)

        payload = picqer.update_product.call_args[0][1]
        aangemaakt = next(
            f for f in payload["productfields"] if f["idproductfield"] == 30
        )
        assert aangemaakt["value"] == ""

    def test_not_skipped_when_levertijd_set_but_timestamp_missing(self):
        picqer = self._make_picqer()
        product = self._make_product(
            name="Test Product Title",
            weight=25,
            productfields=[
                {"title": "Beschikbaar", "value": "LEVERTIJD"},
                {"title": "Beschikbaar - Aangemaakt op", "value": ""},
                {"title": "Verzend", "value": "DHL Small"},
            ],
        )
        variant = self._make_variant(stockTracking="enabled")

        result = sync_product(picqer, variant, product, self.FIELD_IDS, self.TAG_MAP)

        assert result is True
        picqer.update_product.assert_called_once()
        payload = picqer.update_product.call_args[0][1]
        aangemaakt = next(
            f for f in payload["productfields"] if f["idproductfield"] == 30
        )
        assert aangemaakt["value"] != ""

    def test_not_skipped_when_stale_timestamp_needs_clearing(self):
        picqer = self._make_picqer()
        product = self._make_product(
            name="Test Product Title",
            weight=25,
            productfields=[
                {"title": "Beschikbaar", "value": ""},
                {
                    "title": "Beschikbaar - Aangemaakt op",
                    "value": "2026-01-01 00:00:00",
                },
                {"title": "Verzend", "value": "DHL Small"},
            ],
        )
        variant = self._make_variant(stockTracking="indicator")

        result = sync_product(picqer, variant, product, self.FIELD_IDS, self.TAG_MAP)

        assert result is True
        picqer.update_product.assert_called_once()
        payload = picqer.update_product.call_args[0][1]
        aangemaakt = next(
            f for f in payload["productfields"] if f["idproductfield"] == 30
        )
        assert aangemaakt["value"] == ""

    def test_null_weight_sends_zero_and_unknown_shipping(self):
        picqer = self._make_picqer()
        product = self._make_product()
        variant = self._make_variant(weight=0)

        sync_product(picqer, variant, product, self.FIELD_IDS, self.TAG_MAP)

        payload = picqer.update_product.call_args[0][1]
        assert payload["weight"] == 0

        verzend = next(f for f in payload["productfields"] if f["idproductfield"] == 20)
        assert verzend["value"] == "VERZENDTYPE ONBEKEND"

    def test_dry_run_does_not_call_api(self):
        picqer = self._make_picqer()
        product = self._make_product()
        variant = self._make_variant()

        result = sync_product(
            picqer, variant, product, self.FIELD_IDS, self.TAG_MAP, dry_run=True
        )

        assert result is True
        picqer.update_product.assert_not_called()

    def test_returns_false_when_nothing_changed(self):
        picqer = self._make_picqer()
        product = self._make_product(
            name="Test Product Title",
            weight=25,
            productfields=[
                {"title": "Beschikbaar", "value": ""},
                {"title": "Verzend", "value": "DHL Small"},
            ],
        )
        variant = self._make_variant()  # weight=25, stockTracking="indicator"

        result = sync_product(picqer, variant, product, self.FIELD_IDS, self.TAG_MAP)

        assert result is False
        picqer.update_product.assert_not_called()
        picqer.get_product_tags.assert_not_called()

    def test_manage_shipping_tags_skipped_when_shipping_unchanged(self):
        picqer = self._make_picqer()
        product = self._make_product(
            name="Old Name",
            weight=25,
            productfields=[
                {"title": "Beschikbaar", "value": ""},
                {"title": "Verzend", "value": "DHL Small"},
            ],
        )
        variant = self._make_variant()  # name changed, shipping unchanged

        result = sync_product(picqer, variant, product, self.FIELD_IDS, self.TAG_MAP)

        assert result is True
        picqer.update_product.assert_called_once()
        picqer.get_product_tags.assert_not_called()
