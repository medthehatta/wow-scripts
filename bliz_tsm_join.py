from blizzard import auction_summary


def _w_gold(copper_price):
    return {"gold": round(copper_price/1e4, 2), "copper": copper_price}


def item_info(items, bliz_ah, tsm_ah, item_name=None, item_id=None):
    if item_name:
        item_id = items.get_id(item_name)
        item_name_actual = items.get_name(item_id)
    elif item_id:
        item_name_actual = items.get_name(item_id)
    else:
        raise TypeError("Must provide item_name or item_id")

    bliz_info = auction_summary(bliz_ah[item_id])
    tsm_info = tsm_ah[item_id]

    num_auctions = bliz_info.pop("num")
    return {
        "id": item_id,
        "name": item_name_actual,
        "num_auctions": num_auctions,
        "quantity": bliz_info["quantity"],
        "weight_sell": _w_gold(bliz_info["weight_sell"]),
        "avg_sell": _w_gold(bliz_info["avg_sell"]),
        "max": _w_gold(bliz_info["max"]),
        "p90": _w_gold(bliz_info["p90"]),
        "p50": _w_gold(bliz_info["p50"]),
        "p20": _w_gold(bliz_info["p20"]),
        "wp90": _w_gold(bliz_info["wp90"]),
        "wp50": _w_gold(bliz_info["wp50"]),
        "wp20": _w_gold(bliz_info["wp20"]),
        "min": _w_gold(bliz_info["min"]),
        "realm_market_value": _w_gold(tsm_info["marketValue"]),
        "realm_historical": _w_gold(tsm_info["historical"]),
        "region_historical": _w_gold(tsm_info["region"]["historical"]),
        "region_avg_sale_price": _w_gold(tsm_info["region"]["avgSalePrice"]),
        "sale_pct": tsm_info["region"]["salePct"],
        "sold_per_day": tsm_info["region"]["soldPerDay"],
        "headroom": tsm_info["region"]["soldPerDay"] - bliz_info["quantity"],
        "market_skew_pct": round(
            (
                100*(tsm_info["marketValue"] - tsm_info["historical"]) /
                tsm_info["historical"]
            ),
            2,
        ),
        "auction_skew_pct": round(
            (
                100*(bliz_info["min"] - tsm_info["marketValue"]) /
                tsm_info["marketValue"]
            ),
            2,
        )
    }


def item_info_getter(items, bliz_ah_snap, tsm_ah_snap, max_age_seconds=3000):

    def _item_info(*args, **kwargs):
        bliz_ah = bliz_ah_snap.get(max_age_seconds=max_age_seconds)
        tsm_ah = tsm_ah_snap.get(max_age_seconds=max_age_seconds)

        return item_info(items, bliz_ah, tsm_ah, *args, **kwargs)

    return _item_info
