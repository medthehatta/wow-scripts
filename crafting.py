import uuid
import re

from formal_vector import FormalVector
from kvstore import InefficientKVStore
from blizzard import ItemLookup


class CraftingComponents(FormalVector):

    _ZERO = "CraftingComponents.zero"

    def component_ids(self):
        return list(set(self.basis.values()))

    def component_names(self):
        return list(set(self.basis.keys()))


class Recipes:

    def __init__(self, items: ItemLookup):
        self.items = items
        self.storage = {}
        self.in_index = {}
        self.out_index = {}

    def ingredient(self, item_name=None, item_id=None):
        if item_name is not None:
            item_id = self.items.get_id(item_name)
            # Normalize the name
            item_name = self.items.get_name(item_id)
        elif item_id is not None:
            item_name = self.items.get_name(item_id)
        else:
            raise TypeError("Must provide item_id or item_name")

        return CraftingComponents.named(item_name, item_id)

    def lookup(self, item: CraftingComponents=None, item_id=None, item_name=None):
        if item is not None:
            if len(item.basis) == 1:
                return self.lookup(item_id=list(item.basis.values())[0])
            else:
                raise ValueError("item argument must have a single component")
        elif item_id is not None:
            ids = self.out_index.get(item_id, [])
            return [self.storage.get(id_) for id_ in ids]
        elif item_name is not None:
            return self.lookup(item_id=self.items.get_id(item_name))
        else:
            raise TypeError("Must provide item, item_id, or item_name")

    def recipe(self, outputs, inputs):
        id_ = uuid.uuid4()
        self.storage[id_] = (outputs, inputs)
        for inp in inputs.basis.values():
            self.in_index[inp] = self.in_index.get(inp, []) + [id_]
        for outp in outputs.basis.values():
            self.out_index[outp] = self.out_index.get(outp, []) + [id_]
        return (id_, outputs, inputs)

    def ingredients(self, s):
        components = [
            re.search(r"(\d+)?\s*[*]?\s*(.*)", y.strip()).groups()
            for y in re.split(r"\s*[+]\s*", s)
        ]
        if len(components) == 1:
            x = components[0]
            return (
                int(x[0])*self.ingredient(x[1]) if x[0] else
                self.ingredient(x[1])
            )
        else:
            return CraftingComponents.sum(
                (
                    int(x[0])*self.ingredient(x[1]) if x[0] else
                    self.ingredient(x[1])
                )
                for x in components
            )

    def recipe_from_strings(self, outs, ins):
        return self.recipe(self.ingredients(outs), self.ingredients(ins))


def copper(key):
    def _copper(item_inf):
        return item_inf.get(key, {})*1e4
    return _copper


def gold(key):
    def _gold(item_inf):
        return item_inf.get(key, {})
    return _gold


def purchase_price(
    item_info,
    components: CraftingComponents,
    price_method=gold("realm_market_value"),
):
    return sum(
        count*price_method(item_info(item_id=item_id))
        for (name, count, item_id) in components.triples()
    )


def crafting_price(
    item_info,
    recipe,
    in_price_method=gold("realm_market_value"),
    out_price_method=gold("realm_market_value"),
):
    (outputs, inputs) = recipe
    input_breakdown = {
        name: {
            "count": count,
            "price": in_price_method(item_info(item_id=item_id)),
            "total": count*in_price_method(item_info(item_id=item_id)),
        }
        for (name, count, item_id) in inputs.triples()
    }
    input_breakdown["TOTAL"] = sum(v["total"] for v in input_breakdown.values())
    output_breakdown = {
        name: {
            "count": count,
            "price": out_price_method(item_info(item_id=item_id)),
            "total": count*out_price_method(item_info(item_id=item_id)),
        }
        for (name, count, item_id) in outputs.triples()
    }
    output_breakdown["TOTAL"] = sum(v["total"] for v in output_breakdown.values())
    profit = output_breakdown["TOTAL"] - input_breakdown["TOTAL"]
    result = {
        "profit": profit,
        "recipe": recipe,
        "input_price_method": in_price_method,
        "output_price_method": out_price_method,
        "input_breakdown": input_breakdown,
        "output_breakdown": output_breakdown,
    }
    return result
