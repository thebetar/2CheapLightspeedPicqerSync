import json
from datetime import datetime, timezone
from typing import Dict, List, Optional

from modules.config import SHIPPING_OPTIONS, WEIGHT_SHIPPING_MAP, log
from modules.picqer import PicqerClient


def get_weight_grams(variant: dict) -> Optional[int]:
    weight = variant.get("weight")

    if not weight:
        return None

    unit = variant.get("weightUnit", "g")

    if unit == "kg":
        return int(weight * 1000)

    return int(weight)


def determine_shipping_option(weight_grams: Optional[int]) -> str:
    if not weight_grams:
        return "VERZENDTYPE ONBEKEND"

    if weight_grams in WEIGHT_SHIPPING_MAP:
        return WEIGHT_SHIPPING_MAP[weight_grams]

    if weight_grams < 25:
        return "Briefpost"
    if weight_grams < 1001:
        return "DHL Small"
    if weight_grams < 10000:
        return "DPD"
    if weight_grams < 50000:
        return "DHL XXL"

    return "Speciaal Transport"


def manage_shipping_tags(
    picqer: PicqerClient,
    idproduct: int,
    target_option: str,
    tag_map: Dict[str, int],
    dry_run: bool = False,
):
    current_tags = picqer.get_product_tags(idproduct)
    current_tag_ids = {t["idtag"] for t in current_tags}

    shipping_tag_ids = {tag_map[opt]: opt for opt in SHIPPING_OPTIONS if opt in tag_map}

    for tag in current_tags:
        tid = tag["idtag"]

        if tid not in shipping_tag_ids:
            continue
        if shipping_tag_ids[tid] == target_option:
            continue

        if dry_run:
            log.info(
                "[DRY RUN] Would remove tag '%s' from product %d",
                shipping_tag_ids[tid],
                idproduct,
            )
        else:
            picqer.remove_product_tag(idproduct, tid)
            log.debug(
                "Removed tag '%s' from product %d", shipping_tag_ids[tid], idproduct
            )

    target_tag_id = tag_map.get(target_option)

    if not target_tag_id:
        log.error("Tag '%s' not found in Picqer!", target_option)
        return

    if target_tag_id in current_tag_ids:
        return

    if dry_run:
        log.info("[DRY RUN] Would add tag '%s' to product %d", target_option, idproduct)
    else:
        picqer.add_product_tag(idproduct, target_tag_id)
        log.debug("Added tag '%s' to product %d", target_option, idproduct)


def build_product_fields(
    field_ids: Dict[str, int],
    shipping_option: str,
    beschikbaar_value: str,
    beschikbaar_changed: bool,
    current_aangemaakt: str = "",
) -> List[Dict]:
    fields: List[Dict] = []

    if "Beschikbaar" in field_ids:
        fields.append(
            {"idproductfield": field_ids["Beschikbaar"], "value": beschikbaar_value}
        )

    if "Verzend" in field_ids:
        fields.append(
            {"idproductfield": field_ids["Verzend"], "value": shipping_option}
        )

    needs_timestamp = beschikbaar_value == "LEVERTIJD" and (
        beschikbaar_changed or not current_aangemaakt
    )

    if not needs_timestamp:
        return fields

    if "Beschikbaar - Aangemaakt op" in field_ids:
        fields.append(
            {
                "idproductfield": field_ids["Beschikbaar - Aangemaakt op"],
                "value": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            }
        )

    return fields


def sync_product(
    picqer: PicqerClient,
    variant: dict,
    picqer_product: dict,
    field_ids: Dict[str, int],
    tag_map: Dict[str, int],
    dry_run: bool = False,
) -> bool:
    sku = variant.get("sku")
    idproduct = picqer_product["idproduct"]

    weight_grams = get_weight_grams(variant)
    shipping_option = determine_shipping_option(weight_grams)
    stock_tracking = variant.get("stockTracking", "")
    title_long = variant.get("product_fulltitle", "")

    beschikbaar_value = "LEVERTIJD" if stock_tracking == "enabled" else ""

    current_beschikbaar = ""
    current_aangemaakt = ""
    current_verzend = ""
    for pf in picqer_product.get("productfields", []):
        if pf.get("title") == "Beschikbaar":
            current_beschikbaar = pf.get("value", "")
        if pf.get("title") == "Beschikbaar - Aangemaakt op":
            current_aangemaakt = pf.get("value", "")
        if pf.get("title") == "Verzend":
            current_verzend = pf.get("value", "")

    beschikbaar_changed = beschikbaar_value != current_beschikbaar
    name_changed = title_long != picqer_product.get("name", "")
    weight_changed = (weight_grams or 0) != picqer_product.get("weight", 0)
    shipping_changed = shipping_option != current_verzend

    product_fields = build_product_fields(
        field_ids=field_ids,
        shipping_option=shipping_option,
        beschikbaar_value=beschikbaar_value,
        beschikbaar_changed=beschikbaar_changed,
        current_aangemaakt=current_aangemaakt,
    )

    payload = {
        "name": title_long,
        "weight": weight_grams if weight_grams is not None else 0,
        "productfields": product_fields,
    }

    title_display = (title_long[:50] + "...") if len(title_long) > 50 else title_long

    if not any([name_changed, weight_changed, beschikbaar_changed, shipping_changed]):
        log.debug(
            "SKU %s unchanged (weight=%s, ship=%s, tracking=%s), skipping",
            sku,
            weight_grams,
            shipping_option,
            stock_tracking,
        )
        return False

    log.info(
        "SKU %s → weight=%s, ship=%s, tracking=%s, title=%s",
        sku,
        weight_grams,
        shipping_option,
        stock_tracking,
        title_display,
    )

    if dry_run:
        log.info(
            "[DRY RUN] Would PUT /api/v1/products/%d: %s",
            idproduct,
            json.dumps(payload, default=str),
        )
    else:
        picqer.update_product(idproduct, payload)

    if shipping_changed:
        manage_shipping_tags(picqer, idproduct, shipping_option, tag_map, dry_run)

    return True
