import uuid
import re

from combined import And, Or, Empty, Impossible
from combined import dnf
from formal_vector import FormalVector
from kvstore import InefficientKVStore
from blizzard import ItemLookup


class CraftingComponents(FormalVector):

    _ZERO = "CraftingComponents.zero"

    def component_ids(self):
        return list(set(self.basis.values()))

    def component_names(self):
        return list(set(self.basis.keys()))


class Procure:

    def __init__(self, item: CraftingComponents):
        self.item = item

    def __repr__(self):
        return f"Procure({self.item})"


class SpecificProcure(Procure):

    def __init__(self, name, item: CraftingComponents):
        self.name = "".join(c.title() for c in name.split())
        self.item = item

    def __repr__(self):
        return f"{self.name}({self.item})"


class Craft:

    def __init__(self, item: CraftingComponents):
        self.item = item

    def __repr__(self):
        return f"Craft({self.item})"


class Recipes:

    def __init__(self, items: ItemLookup):
        self.items = items
        self.storage = {}
        self.in_index = {}
        self.out_index = {}

    def read_from_file(self, f):
        r_out = None
        for line in f:
            if line.strip() and not line.strip().startswith("#"):
                if r_out:
                    self.recipe_from_strings(r_out, line.strip())
                    r_out = None
                else:
                    r_out = line.strip()
        return self

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

    def tree(self, item: CraftingComponents, path=None):
        path = path or []

        if len(item.components) > 1:
            return And.flat(
                self.tree(item.project(k)) for k in item.components
            )

        (name, count, item_id) = item.pure()

        # We track which items we are crafting in this branch of the tree so
        # we can quit if we end up in a loop
        if item_id in path:
            return Empty

        recipes = self.lookup(item_id=item_id)
        
        if not recipes:
            return Procure(item)

        # Some recipes produce multiple outputs for the given input.  E.G. flasks.
        # So because we are looking specifically for `count` outputs, we scale the
        # reagents
        scaled_recipes = [
            (count/item_.pure()[1]) * ingredients
            for (item_, ingredients) in recipes
        ]

        return Or(
            Procure(item),
            Or.flat(
                And(
                    Craft(item),
                    And.flat(
                        self.tree(recipe.project(ingredient), path=path + [item_id])
                        for ingredient in recipe.components
                    ).reduced()
                ).reduced()
                for recipe in scaled_recipes
            ).reduced()
        ).reduced()


def coalesce_(ops):
    by_item = {}
    for op in ops:
        t = type(op)

        if t not in by_item:
            by_item[t] = {}
        
        if isinstance(op, (Craft, Procure)):
            k = op.item.pure()[-1]
            if k in by_item:
                by_item[t][k] += op.item
            else:
                by_item[t][k] = op.item

    for t in by_item:
        for total in by_item[t].values():
            yield t(total)


def coalesce(ops):
    return list(coalesce_(ops))


def _procure_decider(purchase_modes, item):
    (name, count, item_id) = item.pure()
    
    modes = {k: v for (k, v) in purchase_modes(item).items() if v is not None}

    if not modes:
        return (0, Procure(item), [])
    
    available = []
    for op in modes:
        available.append((-count * modes[op], SpecificProcure(op, item)))
    best_op = min(modes, key=lambda x: modes[x])
    return (
        -count * modes[best_op],
        SpecificProcure(best_op, item),
        available,
    )


def procurement_options(purchase_modes, tree):
    methods = (coalesce(x) for x in dnf(tree))

    for method in methods:

        method_cost = 0
        method_result = []
        for op in method:
            if isinstance(op, Procure):
                (op_cost, specific_op, options) = _procure_decider(purchase_modes, op.item)
            else:
                (op_cost, specific_op, options) = (0, op, [])

            method_cost += op_cost
            method_result.append((op_cost, specific_op, options))
        
        yield (method_cost, method_result)

