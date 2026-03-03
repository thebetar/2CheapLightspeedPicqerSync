#!/usr/bin/env python3
"""
Lightspeed → Picqer product sync.

Runs 2–4× per day via cron. Idempotent.

Usage:
    python main.py
    USE_CACHE=true python main.py
    DRY_RUN=true python main.py
"""

import json
import os

import requests

from modules.config import (
    LIGHTSPEED_API_KEY,
    LIGHTSPEED_API_SECRET,
    LIGHTSPEED_BASE_URL,
    PICQER_API_KEY,
    PICQER_BASE_URL,
    SHIPPING_OPTIONS,
    log,
)
from modules.lightspeed import LightspeedClient
from modules.picqer import PicqerClient
from modules.sync import sync_product


def run_sync():
    use_cache = os.getenv("USE_CACHE", "false").lower() == "true"
    dry_run = os.getenv("DRY_RUN", "false").lower() == "true"

    if dry_run:
        log.info("=== DRY RUN MODE — no changes will be made ===")

    if not PICQER_BASE_URL or not PICQER_API_KEY:
        raise RuntimeError("PICQER_BASE_URL and PICQER_API_KEY must be set in .env")

    # 1) Load Lightspeed data

    if use_cache:
        log.info("Loading Lightspeed data from cache...")
        variants = LightspeedClient.load_variants_from_cache()
    else:
        if not LIGHTSPEED_API_KEY or not LIGHTSPEED_API_SECRET:
            raise RuntimeError(
                "LIGHTSPEED_API_KEY and LIGHTSPEED_API_SECRET must be set in .env"
            )

        lightspeed = LightspeedClient(
            LIGHTSPEED_BASE_URL, LIGHTSPEED_API_KEY, LIGHTSPEED_API_SECRET
        )
        variants = lightspeed.fetch_variants()

    # 2) Initialise Picqer client & cache lookups

    picqer = PicqerClient(PICQER_BASE_URL, PICQER_API_KEY)
    field_ids = picqer.get_field_ids()
    tag_map = picqer.get_tag_map()

    log.info("Product fields: %s", json.dumps(field_ids, indent=2))
    log.info("Tags: %s", json.dumps(tag_map, indent=2))

    for field in ["Beschikbaar", "Verzend"]:
        if field not in field_ids:
            log.warning("Required product field '%s' not found in Picqer!", field)

    for tag in SHIPPING_OPTIONS:
        if tag not in tag_map:
            log.warning("Required tag '%s' not found in Picqer!", tag)

    # 3) Sync each variant

    updated = 0
    skipped = 0
    errors = 0
    total = len(variants)

    for i, variant in enumerate(variants, 1):
        try:
            if sync_product(picqer, variant, field_ids, tag_map, dry_run):
                updated += 1
            else:
                skipped += 1

        except requests.RequestException as e:
            errors += 1
            log.error("Error syncing SKU %s: %s", variant.get("sku", "?"), e)

        except Exception as e:
            errors += 1
            log.error(
                "Unexpected error syncing SKU %s: %s",
                variant.get("sku", "?"),
                e,
                exc_info=True,
            )

        if i % 100 == 0:
            log.info(
                "Progress: %d/%d (updated=%d, skipped=%d, errors=%d)",
                i,
                total,
                updated,
                skipped,
                errors,
            )

    log.info(
        "Sync complete. Total=%d, Updated=%d, Skipped=%d, Errors=%d",
        total,
        updated,
        skipped,
        errors,
    )


if __name__ == "__main__":
    run_sync()
