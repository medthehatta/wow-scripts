from blizzard import auction_summary


def item_info(items, bliz_ah, tsm_ah, item_name=None, item_id=None):
    if item_name:
        item_id = items.get_id(item_name)
        item_name_actual = items.get_name(item_id)
    elif item_id:
        item_name_actual = items.get_name(item_id)
    else:
        raise TypeError("Must provide item_name or item_id")

    if item_id in bliz_ah:
        bliz_info = auction_summary(bliz_ah[item_id])
    else:
        itemdata = items.get_item(item_id=item_id)
        # Vendor price in gold
        vendor_price = itemdata["purchase_price"] / 1e4
        bliz_info = {
            "quantity": 9999,
            "num": 9999,
            "weight_sell": vendor_price,
            "avg_sell": vendor_price,
            "max": vendor_price,
            "p80": vendor_price,
            "p50": vendor_price,
            "p20": vendor_price,
            "wp80": vendor_price,
            "wp50": vendor_price,
            "wp20": vendor_price,
            "min": vendor_price,
        }
    tsm_info = tsm_ah[item_id]

    try:
        headroom = int(
            tsm_info["region"]["soldPerDay"]/(tsm_info["region"]["salePct"]/100) -
            bliz_info["quantity"]
        )
    except ZeroDivisionError:
        headroom = None

    market_skew_pct = round(
        (
            100*(tsm_info["marketValue"] - tsm_info["historical"]) /
            tsm_info["historical"]
        ),
        2,
    )
    auction_skew_pct = round(
        (
            100*(bliz_info["min"] - tsm_info["marketValue"]) /
            tsm_info["marketValue"]
        ),
        2,
    )

    num_auctions = bliz_info.pop("num")
    return {
        "id": item_id,
        "name": item_name_actual,
        "num_auctions": num_auctions,
        "quantity": bliz_info["quantity"],
        "weight_sell": bliz_info["weight_sell"],
        "avg_sell": bliz_info["avg_sell"],
        "max": bliz_info["max"],
        "p80": bliz_info["p80"],
        "p50": bliz_info["p50"],
        "p20": bliz_info["p20"],
        "wp80": bliz_info["wp80"],
        "wp50": bliz_info["wp50"],
        "wp20": bliz_info["wp20"],
        "min": bliz_info["min"],
        # TSM price values are in copper and we don't have a summary layer
        # (like auction_summary() for blizard data), so we convert to gold here
        "realm_market_value": tsm_info["marketValue"] / 1e4,
        "realm_historical": tsm_info["historical"] / 1e4,
        "region_historical": tsm_info["region"]["historical"] / 1e4,
        "region_avg_sale_price": tsm_info["region"]["avgSalePrice"] / 1e4,
        "sale_pct": tsm_info["region"]["salePct"],
        "sold_per_day": tsm_info["region"]["soldPerDay"],
        "headroom": headroom,
        "market_skew_pct": market_skew_pct,
        "auction_skew_pct": auction_skew_pct,
    }


def item_info_getter(items, bliz_ah_snap, tsm_ah_snap, max_age_seconds=3000):

    def _item_info(*args, **kwargs):
        bliz_ah = bliz_ah_snap.get(max_age_seconds=max_age_seconds)
        tsm_ah = tsm_ah_snap.get(max_age_seconds=max_age_seconds)

        return item_info(items, bliz_ah, tsm_ah, *args, **kwargs)

    return _item_info
