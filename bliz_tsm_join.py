import time

from cytoolz import get_in

from blizzard import ItemLookup
from blizzard import auction_data
from blizzard import auction_summary
from blizzard import collapse_languages
from kvstore import InefficientKVStore
from snapshot import SnapshotProcessor
from tsm import auction_house_snapshot


def is_sequence(x):
    try:
        iter(x)
    except TypeError:
        return False

    return not isinstance(x, str)


def dict_paths(dic, prefix=None, bare_root=False):
    prefix = prefix or []
    for (k, v) in dic.items():
        if not isinstance(v, dict):
            if not prefix and bare_root:
                yield k
            else:
                yield prefix + [k]
        else:
            yield from dict_paths(v, prefix=prefix + [k])


_UNSET = object()


class ItemInfoAggregator:

    def __init__(
        self,
        items: ItemLookup,
        bliz_ah: dict,
        tsm_ah: dict,
        backing: InefficientKVStore,
        ttl_seconds=600,
    ):
        self.items = items
        self.bliz_ah = bliz_ah
        self.tsm_ah = tsm_ah
        self.backing = backing
        self.backing.slurp()
        self.ttl_seconds = ttl_seconds

    def get_id_name(self, item=None, item_name=None, item_id=None):
        if item_name:
            item_id = self.items.get_id(item_name)
            item_name_actual = self.items.get_name(item_id)
        elif item_id:
            item_name_actual = self.items.get_name(item_id)
        elif item:
            (_, _, item_id) = item.pure()
            item_name_actual = self.items.get_name(item_id)
        else:
            raise TypeError("Must provide item_name or item_id")

        return (item_id, item_name_actual)


    def get(self, item=None, item_name=None, item_id=None):
        (item_id, item_name_actual) = self.get_id_name(
            item=item,
            item_name=item_name,
            item_id=item_id,
        )

        if (
            not self.backing.get(item_id) or
            time.time() > self.backing.get(item_id)["_expiry_"]
        ):
            item_data = collapse_languages(self.items.get_item(item_id=item_id))
            bliz_data = auction_summary(self.bliz_ah.get(item_id))
            tsm_data = self.tsm_ah.get(item_id)
            self.backing.put(
                item_id,
                {
                    "_expiry_": time.time() + self.ttl_seconds,
                    **(item_data or {}),
                    **(bliz_data or {}),
                    **(tsm_data or {}),
                },
            )
            self.backing.commit()
        return self.backing.get(item_id)

    def get_property(
        self,
        prop,
        item=None,
        item_name=None,
        item_id=None,
        default=_UNSET,
    ):
        if not is_sequence(prop):
            prop = [prop]

        info = self.get(item=item, item_name=item_name, item_id=item_id)

        if default is _UNSET:
            return get_in(prop, info, no_default=True)
        else:
            return get_in(prop, info, default=default)

    def paths(
        self,
        item=None,
        item_name=None,
        item_id=None,
        bare_root=True,
    ):
        return dict_paths(
            self.get(item=item, item_name=item_name, item_id=item_id),
            bare_root=bare_root,
        )

    def refresh(self, item=None, item_name=None, item_id=None):
        (item_id, item_name_actual) = self.get_id_name(
            item=item,
            item_name=item_name,
            item_id=item_id,
        )
        self.backing.pop(item_id)
        self.backing.commit()
        return self.get(item_id=item_id)

    def prop(self, path):
        def _prop(item_id):
            return self.get_property(path, item_id=item_id, default=None)
        return _prop
