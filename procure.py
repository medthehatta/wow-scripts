#!/usr/bin/env python


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
from procurement import purchase_modes
from snapshot import SnapshotProcessor
from tsm import auction_house_snapshot


items = ItemLookup(
    InefficientKVStore(blizzard_item_cache),
    InefficientKVStore(blizzard_item_reverse_cache),
)

r = Recipes(items)


def format_gold(copper_cost):
    if copper_cost == 0:
        return f"0"

    val = str(int(abs(copper_cost)))
    g = val[:-4]
    s = val[-4:-2]
    c = val[-2:]
    return " ".join([
        f"{g}g" if g else "",
        f"{s}s" if s else "",
        f"{c}c" if c else "",
    ])


def format_op_pricing(cost, op):
    (_, count, _) = op.item.pure()
    if count != 1 and cost != 0:
        each = cost / count
        return f"{format_gold(cost)}  {op}  (ea: {format_gold(each)})"
    else:
        return f"{format_gold(cost)}  {op}"


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-k", "--topk", type=int, default=5)
    parser.add_argument("-r", "--recipes", default="recipes.txt")
    parser.add_argument("arg")
    parsed = parser.parse_args()

    k = parsed.topk
    recipes_path = parsed.recipes
    arg = parsed.arg

    with open(recipes_path) as f:
        r.read_from_file(f)

    results = topk(
        k,
        procurement_options(
            purchase_modes,
            r.tree(r.ingredients(arg)),
        ),
        key=lambda x: x[0],
    )

    num = len(results)

    for (j, result) in enumerate(results, start=1):
        (total, operations) = result
        print(f"({j}/{num}) Total gold: {format_gold(total)}")
        for operation in operations:
            (cost, op, alts) = operation
            print(f"- {format_op_pricing(cost, op)}")
            for (alt_cost, alt) in sorted(alts, key=lambda x: -x[0]):
                print(f"      alt: {format_op_pricing(alt_cost, alt)}")
        print("\n")


if __name__ == "__main__":
    main()

