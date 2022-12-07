eternals = {
    x.lower(): (f"Eternal {x}", f"Crystallized {x}")
    for x in ["Life", "Earth", "Air", "Fire", "Water", "Shadow"]
}

primals = {
    x.lower(): (f"Primal {x}", f"Mote of {x}")
    for x in ["Life", "Earth", "Air", "Fire", "Water", "Shadow"]
}

essences = {
    x.lower(): (f"Greater {x} Essence", f"Lesser {x} Essence")
    for x in ["Eternal", "Cosmic", "Nether", "Planar", "Astral", "Magic", "Mystic"]
}


statuses = [
    (10000000, "definitely"),
    (7000000, "yes"),
    (5000000, "maybe"),
    (3000000, "meh"),
    (1, "nah"),
]


def headroom(item):
    return (
        item["region"]["soldPerDay"]/(item["region"]["salePct"]/100) -
        item["quantity"]
    )


def arbitrage(
    big,
    small,
    multiplier,
    reverse_ok=True,
    price_param="marketValue",
):
    if reverse_ok:
        arb = (big[price_param] - multiplier*small[price_param])
    else:
        arb = max(big[price_param] - multiplier*small[price_param], 0)
        
    big_space = headroom(big)
    small_space = headroom(small)
    
    profit_big = max(big_space*big["region"]["salePct"]/100*arb, 0)
    profit_small = max(small_space*small["region"]["salePct"]/100*(-arb), 0)

    diagnostics = {
        "arb": arb,
        "big_space": big_space,
        "small_space": small_space,
        "profit_big": profit_big,
        "profit_small": profit_small,
        "big": big,
        "small": small,
    }
    
    big_data = {
        "direction": "sb",
        "headroom": big_space,
        "unit-profit": arb,
        "saturated-profit": profit_big,
        "big": big,
        "small": small,
    }
    small_data = {
        "direction": "bs",
        "headroom": small_space,
        "unit-profit": -arb,
        "saturated-profit": profit_small,
        "small": small,
        "small": small,
    }

    for (profit, name) in statuses:
        if big_space > 0 and profit_big > profit:
            return {"execute": name, **big_data}
        elif small_space > 0 and profit_small > profit:
            return {"execute": name, **small_data}
    
    # Neither is profitable:
    if profit_small <= 0 and profit_big <= 0:
        return {"execute": "no", **diagnostics}
    
    # How can we possibly get here?  Anyway it's wtf
    else:
        return {"execute": "wtf?", **diagnostics}


def pair_arbitrage(tsm_ah, items, pair, *args, **kwargs):
    (big_name, small_name) = pair
    (big_id, small_id) = items.get_multiple_ids(pair)
    return arbitrage(tsm_ah[big_id], tsm_ah[small_id], *args, **kwargs)


def summary(name, arb, cutoff=2):
    a = arb
    if a["execute"] in [s[1] for s in statuses[:cutoff]]:
        return " ".join([
            f"{a['execute'].upper(): <12}",
            f"{a['direction'].upper()}",
            f"{name}",
            f"(unit profit: {a['unit-profit']},"
            f"headroom: {int(a['headroom'])})",
        ])
    else:
        return f"SKIP        {name}"


def print_elemental_arbitrage_report(tsm_ah, items):
    for (name, pair) in eternals.items():
        print(summary(f"eternal-{name}", pair_arbitrage(tsm_ah, items, pair, 10), cutoff=2))

    for (name, pair) in primals.items():
        print(summary(f"primal-{name}", pair_arbitrage(tsm_ah, items, pair, 10, reverse_ok=False), cutoff=2))

    for (name, pair) in essences.items():
        print(summary(f"essence-{name}", pair_arbitrage(tsm_ah, items, pair, 3), cutoff=2))
