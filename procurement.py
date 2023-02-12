from dataclasses import dataclass, field
from typing import List
from functools import partial
from crafting import CraftingComponents
import itertools
from cytoolz import groupby
from cytoolz import topk
from blizzard import ItemLookup
from bliz_tsm_join import ItemInfoAggregator
from crafting import Recipes


class Combined:
        
    def __init__(self, *items):
        self.items = items
    
    def __repr__(self):
        return f"{self.__class__.__name__}{self.items}"
    
    def __iter__(self):
        return iter(self.items)
    
    def __eq__(self, other):
        return self.items == other.items
    
    def __getitem__(self, key):
        return self.items[key]
    
    @classmethod
    def flat(cls, seq):
        s = itertools.chain.from_iterable(
            x.items if isinstance(x, cls) else [x] for x in seq
        )
        return cls(*list(s))

    
class Or(Combined):
    
    def reduced(self):
        return Or.flat(
            x for x in self.items
            if all([
                not isinstance(x, EmptyProcurement),
                not isinstance(x, ImpossibleProcurement),
            ])
        )


class And(Combined):
    
    def reduced(self):
        impossibles = [x for x in self.items if isinstance(x, ImpossibleProcurement)]
        if impossibles:
            return ImpossibleProcurement(trace=impossibles)
        else:
            return self
        
        
def _same_or_die(seq):
    lst = list(seq)
    if not lst:
        raise ValueError("empty list")
    first = lst[0]
    if not all(s == first for s in lst[1:]):
        raise ValueError("Not all values identical: {set(lst)}")
    else:
        return first
    

@dataclass
class Procurement:
    item: CraftingComponents


@dataclass
class EmptyProcurement(Procurement):
    pass


@dataclass
class ImpossibleProcurement(Procurement):
    message: str = ""
    trace: List[Procurement] = field(default_factory=lambda: [])
        
    @classmethod
    def sum(cls, seq):
        return cls(
            item=CraftingComponents.sum(x.item for x in seq),
            message="; ".join(x.message for x in seq),
            trace=sum((x.trace for x in seq), []),
        )

    
@dataclass
class ManualProcurement(Procurement):
    message: str = ""
        
    @classmethod
    def sum(cls, seq):
        return cls(
            item=CraftingComponents.sum(x.item for x in seq),
            message="; ".join(x.message for x in seq),
        )        
        

        
@dataclass
class Gather(Procurement):
    where: str
    minutes: float
        
    @classmethod
    def sum(cls, seq):
        return cls(
            item=CraftingComponents.sum(x.item for x in seq),
            where=_same_or_die(x.where for x in seq),
            minutes=sum(x.minutes for x in seq),
        )

        
@dataclass
class AHBuy(Procurement):
    cost_method: callable
    gold: float

    @classmethod
    def sum(cls, seq):
        return cls(
            item=CraftingComponents.sum(x.item for x in seq),
            cost_method=_same_or_die(x.cost_method for x in seq),
            gold=sum(x.gold for x in seq),
        )


@dataclass
class VendorBuy(Procurement):
    who: str
    where: str
    gold: float

    @classmethod
    def sum(cls, seq):
        return cls(
            item=CraftingComponents.sum(x.item for x in seq),
            who=_same_or_die(x.who for x in seq),
            where=_same_or_die(x.where for x in seq),
            gold=sum(x.gold for x in seq),
        )
    
        
@dataclass
class Craft(Procurement):
    ingredients: CraftingComponents

    @classmethod
    def sum(cls, seq):
        return cls(
            item=CraftingComponents.sum(x.item for x in seq),
            ingredients=CraftingComponents.sum(x.ingredients for x in seq),
        )


class ProcurementPlanner:
    
    def __init__(
        self,
        item_info: ItemInfoAggregator,
        recipes: Recipes,
        vendor: dict,
        ah_cost_methods: list,
    ):
        self.ah_info = item_ah_info_getter
        self.recipes = recipes
        self.vendor = vendor
        self.ah_methods = ah_cost_methods
        self.approaches = [
            self.vendor_price,
            self.gather,
            self.craft,
            self.ah_buy,
        ]
    
    def ah_buy(self, item, path=None):
        (name, count, item_id) = item.pure()

        ah_buy_methods = []
        for price in self.ah_cost_methods:
            try:
                ah_buy_methods.append(
                    AHBuy(item, count*price(item_id))
                )
            except Exception:
                ah_buy_methods.append(
                    ImpossibleProcurement(price.__name__, item)
                )

        return Or.flat(ah_buy_methods)

    def vendor_price(self, item, path=None):
        (name, count, _) = item.pure()
        if name in self.vendor:
            return VendorBuy(item, "vendor", "somewhere", self.vendor[name])
        else:
            return ImpossibleProcurement(item)

    def gather(self, item, path=None):
        return EmptyProcurement(item)
        #return Gather(item, "Sholazar Basin", minutes=1)

    def craft(self, item, path=None):
        path = path or []
        (name, count, _) = item.pure()

        if name in path:
            return EmptyProcurement(item)

        recipes = self.recipes.lookup(item_name=name)
        
        if not recipes:
            return EmptyProcurement(item)

        # Some recipes produce multiple outputs for the given input.  E.G. flasks.
        # So because we are looking specifically for a single input, we scale the
        # reagents down
        scaled_ingredients = [
            (count/item.pure()[1]) * ingredients
            for (item, ingredients) in recipes
        ]
        
        return Or.flat(
            And(
                Craft(item, ingredients),
                self.obtain(ingredients, path=path + [name]),
            ).reduced()
            for ingredients in scaled_ingredients
        ).reduced()

    def obtain(self, item: CraftingComponents, path=None):
        path = path or []
        if len(item.components) == 1:
            return Or.flat(approach(item, path=path) for approach in self.approaches).reduced()
            
        else:
            components = [item.project(k) for k in item.components]
            return And.flat(self.obtain(component, path=path) for component in components).reduced()


def dnf(tree):
    if isinstance(tree, Or):
        return Or.flat(dnf(x) for x in tree.items)
    
    elif isinstance(tree, And):
        product = itertools.product(*[dnf(y).items for y in tree.items])
        return Or.flat(And.flat(x) for x in product)
    
    else:
        return Or(And(tree))

    
def test_dnf():
    assert dnf(1) == Or(And(1))
    assert dnf(Or(1)) == Or(And(1))
    assert dnf(Or(And(1))) == Or(And(1))
    assert dnf(Or(Or(1))) == Or(And(1))
    assert dnf(And(And(1))) == Or(And(1))
    assert dnf(And(Or(1))) == Or(And(1))
    assert dnf(And(Or(1, 2))) == Or(And(1), And(2))
    assert dnf(And(Or(1, 2), 3)) == Or(And(1, 3), And(2, 3))
    assert dnf(And(Or(1, 2), And(3, 4))) == Or(And(1, 3, 4), And(2, 3, 4))
    assert dnf(And(Or(1, 2), Or(3, 4))) == Or(And(1, 3), And(1, 4), And(2, 3), And(2, 4))
    

def by_item(ops):
    g = groupby(lambda x: (x.item.pure()[0], type(x)), ops)
    return [v[0].sum(v) for v in g.values()]


def cost(reqs):
    return sum(x.gold if hasattr(x, "gold") else 0 for x in reqs)


def topk_procurements(pp, items, k=4):
    dnf_ = dnf(pp.obtain(items))
    methods = [
        by_item(ops)
        for ops in topk(k, dnf_, key=lambda x: -cost(x))
    ]
    return [(cost(m), m) for m in methods]


def best_procurement(pp, items):
    dnf_ = dnf(pp.obtain(items))
    return min(dnf_, key=lambda x: cost(x))
