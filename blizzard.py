import datetime
import glob
import logging
import os
import pickle

from cytoolz import groupby

from hxxp import Requester
from hxxp import DefaultHandlers
from kvstore import InefficientKVStore
from tokens import BlizzardToken
from _keys import blizzard_client_id
from _keys import blizzard_client_secret


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


_json = DefaultHandlers.raise_or_return_json


blizzard_tok = BlizzardToken(blizzard_client_id, blizzard_client_secret)
blizzard_static = Requester(
    "https://us.api.blizzard.com",
    token=blizzard_tok,
    common_extra_headers={"Battlenet-Namespace": "static-classic-us"},
)
blizzard_dynamic = Requester(
    "https://us.api.blizzard.com",
    token=blizzard_tok,
    common_extra_headers={"Battlenet-Namespace": "dynamic-classic-us"},
)


def _normalize_name(name):
    return name.lower()


def _paginate(bliz, path, subkey=None, **kwargs):
    if "params" in kwargs:
        base_params = kwargs.pop("params")
    else:
        base_params = {}

    data = _json(bliz.request("GET", path, params=base_params, **kwargs))
    if subkey:
        yield from data[subkey]
    else:
        yield data

    for page in range(2, data["pageCount"]):
        params = {"_page": page, **base_params}
        result = _json(bliz.request("GET", path, params=params, **kwargs))
        if subkey:
            yield from result[subkey]
        else:
            yield result


def item_search_by_name(terms):
    return _paginate(
        blizzard_static,
        "/data/wow/search/item",
        subkey="results",
        params={"name.en_US": terms},
    )


def item_search_names(terms):
    return (
        item["data"]["name"]["en_US"]
        for item in item_search_by_name(terms)
    )


UNSET = object()


def item_search_single_by_name(name, default=UNSET):
    results = [
        (x["data"]["name"]["en_US"], x)
        for x in item_search_by_name(name)
    ]
    norm_name = _normalize_name(name)
    found = next(
        (
            result for (name_, result) in results
            if _normalize_name(name_) == norm_name
        ),
        None,
    )
    if found:
        return found
    else:
        if default is not UNSET:
            return default
        else:
            raise LookupError(name)


def item_search_single_id_by_name(name, default=UNSET):
    results = [
        (x["data"]["name"]["en_US"], x)
        for x in item_search_by_name(name)
    ]
    lower_name = name.lower()
    found = [
        result for (name_, result) in results
        if name_.lower() == lower_name
    ]
    if len(found) == 1:
        return found[0]["data"]["id"]
    elif len(found) > 1:
        names_found = [x["data"]["name"]["en_US"] for x in found]
        raise LookupError(
            f"Item name search for '{name}' did not yield unique value!  "
            f"Found (next line):\n{names_found}"
        )
    else:
        if default is not UNSET:
            return default
        else:
            raise LookupError(name)


def item_search_id_by_name(terms):
    results = [
        (x["data"]["name"]["en_US"], x["data"]["id"])
        for x in item_search_by_name(terms)
    ]
    return next(
        (name, id_) for (name, id_) in results
        if name.lower().replace(" ", "") == terms.lower().replace(" ", "")
    )


def item_query(query):
    return _paginate(
        blizzard_static,
        "/data/wow/search/item",
        subkey="results",
        params=query,
    )


def auction_data(blizzard_realm_id, blizzard_ah_id):
    res = _json(
        blizzard_dynamic.request(
            "GET",
            (
                f"/data/wow/connected-realm/"
                f"{blizzard_realm_id}/auctions/{blizzard_ah_id}"
            )
        )
    )
    timestamp = datetime.datetime.now().isoformat()
    auctions = [
        {
            "auction_id": a["id"],
            "item_id": a["item"]["id"],
            "price": a["buyout"],
            "quantity": a["quantity"],
            "timestamp": timestamp,
        }
        for a in res["auctions"]
    ]
    auctions_by_item = groupby(lambda x: x["item_id"], auctions)
    return auctions_by_item


def p(pct, sorted_lst):
    num = len(sorted_lst)
    idx = int(pct/100*num)
    return sorted_lst[idx]


def expand_repetition(value_count_seq):
    for (value, count) in value_count_seq:
        for _ in range(count):
            yield value


def auction_summary(auctions):
    num = len(auctions)
    quantity = sum(x["quantity"] for x in auctions)
    weight_avg_sell = \
        sum(x["price"]*x["quantity"] for x in auctions) / quantity
    avg_sell = sum(x["price"] for x in auctions) / num
    prices_counts = [(x["price"], x["quantity"]) for x in auctions]
    sorted_pcs = sorted(prices_counts, key=lambda x: x[0])
    sorted_prices_expanded = list(expand_repetition(sorted_pcs))
    sorted_prices = [price for (price, quant) in sorted_pcs]
    return {
        "num": num,
        "quantity": quantity,
        "weight_sell": weight_avg_sell,
        "avg_sell": avg_sell,
        "max": sorted_prices[-1],
        "p80": p(80, sorted_prices),
        "p50": p(50, sorted_prices),
        "p20": p(20, sorted_prices),
        "wp80": p(80, sorted_prices_expanded),
        "wp50": p(50, sorted_prices_expanded),
        "wp20": p(20, sorted_prices_expanded),
        "min": sorted_prices[0],
    }


class ItemLookup:
    
    def __init__(self, cache: InefficientKVStore, reverse_cache: InefficientKVStore):
        self.bliz = blizzard_static
        self.cache = cache
        self.reverse_cache = reverse_cache

    def stage(self, id_, name):
        self.cache.put(id_, name)
        self.reverse_cache.put(_normalize_name(name), id_)

    def commit(self):
        self.cache.commit()
        self.reverse_cache.commit()
    
    def get_name(self, id_):
        if self.cache.get(id_) is None:
            self.stage(id_, self._name_from_id_api(id_))
            self.commit()
        return self.cache.get(id_)

    def get_multiple_names(self, ids):
        result = []
        try:
            for id_ in ids:
                if self.cache.get(id_) is None:
                    self.stage(id_, self._name_from_id_api(id_))
                result.append(self.cache.get(id_))
        # Commit whatever we've staged so far, even if one fails partway
        # through
        finally:
            self.commit()
        return result

    def get_id(self, name):
        norm_name = _normalize_name(name)
        if self.reverse_cache.get(norm_name) is None:
            item_id = item_search_single_id_by_name(norm_name)
            self.stage(item_id, norm_name)
            self.commit()
        return self.reverse_cache.get(norm_name)
    
    def get_multiple_ids(self, names):
        result = []
        try:
            for name in names:
                norm_name = _normalize_name(name)
                if self.reverse_cache.get(norm_name) is None:
                    item_id = item_search_single_id_by_name(norm_name)
                    self.stage(item_id, norm_name)
                result.append(self.reverse_cache.get(norm_name))
        # Commit whatever we've staged so far, even if one fails partway
        # through
        finally:
            self.commit()
        return result

    def get_item(self, item_id=None, item_name=None):
        if item_id:
            return _json(self.bliz.request("GET", f"/data/wow/item/{item_id}"))
        elif item_name:
            item_id = self.get_id(item_name)
            return _json(self.bliz.request("GET", f"/data/wow/item/{item_id}"))
        else:
            raise TypeError("Need to provide item_id or item_name")

    def _name_from_id_api(self, id_):
        data = self.get_item(item_id=id_)
        return _normalize_name(data["name"]["en_US"])
