from bliz_tsm_join import ItemInfoAggregator
from blizzard import ItemLookup
from blizzard import auction_data
from blizzard import auction_summary
from blizzard import collapse_languages
from combined import dnf
from config import blizzard_ah_id
from config import blizzard_cache_dir
from config import blizzard_item_cache
from config import blizzard_item_reverse_cache
from config import blizzard_realm_id
from config import tsm_ah_id
from config import tsm_cache_dir
from config import tsm_realm_id
from config import tsm_region_id
from crafting import Craft
from crafting import Procure
from crafting import Recipes
from crafting import SpecificProcure
from crafting import coalesce
from crafting import procurement_options
from cytoolz import groupby
from cytoolz import topk
from functools import partial
from kvstore import InefficientKVStore
from pprint import pprint
from snapshot import SnapshotProcessor
from tsm import auction_house_snapshot


def tsm_ah_snapper():
    return auction_house_snapshot(tsm_region_id, tsm_realm_id, tsm_ah_id)

tsm_ah_snap = SnapshotProcessor(tsm_ah_snapper, cache_dir=tsm_cache_dir)
tsm_ah = tsm_ah_snap.get(max_age_seconds=3000)

def bliz_ah_snapper():
    return auction_data(blizzard_realm_id, blizzard_ah_id)

bliz_ah_snap = SnapshotProcessor(bliz_ah_snapper, cache_dir=blizzard_cache_dir)
bliz_ah = bliz_ah_snap.get(max_age_seconds=3000)

items = ItemLookup(
    InefficientKVStore(blizzard_item_cache),
    InefficientKVStore(blizzard_item_reverse_cache),
)

iii = ItemInfoAggregator(items, bliz_ah, tsm_ah, InefficientKVStore("aggregator.pkl"))

r = Recipes(items)


vendor = [
    "wild spineleaf",
    "enchanted vial",
    "imbued vial",
    "crystal vial",
    "leaded vial",
    "empty vial",
    "weak flux",
    "light parchment",
    "resilient parchment",
]


roxi = {
    "goblin-machined piston": 1000e4,
    "salvaged iron golem parts": 3000e4,
    "elementium-plated exhaust pipe": 1500e4,
}


def nullable_avg(a, b):
    if a is None:
        return None
    elif b is None:
        return None
    else:
        return (a + b) / 2


def purchase_modes(item):
    (name, count, item_id) = item.pure()
    p = partial(iii.get_property, item=item, default=None)
    return {
        "buy now": p("min") or None,
        "buy market": p("marketValue"),
        "buy vendor": p("purchase_price") if name in vendor else None,
        "long avg": nullable_avg(p(["historical"]), p(["region_historical"])),
        "roxi ramrocket": roxi.get(name),
    }
