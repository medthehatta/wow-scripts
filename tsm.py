import datetime
import glob
import logging
import os
import pickle
from requests import HTTPError

from hxxp import Requester
from hxxp import DefaultHandlers
from tokens import TSMToken
from _keys import tsm_key


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


_json = DefaultHandlers.raise_or_return_json


tok = TSMToken(tsm_key)
realm_api = Requester("https://realm-api.tradeskillmaster.com", token=tok)
price_api = Requester("https://pricing-api.tradeskillmaster.com", token=tok)


def auction_house_snapshot(region_id, realm_id, ah_id):
    ah = _json(ah1_res := price_api.request("GET", f"/ah/{ah_id}"))
    reg = _json(reg1_res := price_api.request("GET", f"/region/{region_id}"))

    ah_index = {a["itemId"]: a for a in ah}
    reg_index = {a["itemId"]: a for a in reg}
    return {
        x["itemId"]: {**x, "region": reg_index[x["itemId"]]}
        for x in ah_index.values()
    }
