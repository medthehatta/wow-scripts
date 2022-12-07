import datetime
import glob
import logging
import os
import pickle
from requests import HTTPError

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def _newest_snapshot_and_time(directory, snap_format):
    try:
        newest_snapshot = max(glob.glob(os.path.join(directory, "*")))
        newest_time = datetime.datetime.strptime(
            newest_snapshot,
            os.path.join(directory, snap_format),
        )
        return (newest_snapshot, newest_time)
    except ValueError:
        return (None, None)


class SnapshotProcessor:

    def __init__(self, fetch_func, cache_dir, snap_prefix="snap"):
        self.fetch_func = fetch_func
        self.cache_dir = cache_dir
        self.snap_format = "-".join([snap_prefix, "%Y-%m-%dT%H-%M-%S"])
        self._data = None

    def get(self, max_age_seconds=3000, fallback_to_cache=True):
        (snap_path, last_update) = \
            _newest_snapshot_and_time(self.cache_dir, self.snap_format)
        now = datetime.datetime.now()

        # First get ever
        if snap_path is None:
            self._data = self.fetch_func()
            snap_filename = now.strftime(self.snap_format)
            os.makedirs(self.cache_dir, exist_ok=True)
            with open(os.path.join(self.cache_dir, snap_filename), "wb") as f:
                pickle.dump(self._data, f)

        # Last snap too old
        # (same as first get ever, but fallback to cache is available)
        elif now > last_update + datetime.timedelta(seconds=max_age_seconds):
            try:
                self._data = self.fetch_func()
            except Exception:
                logger.warning(
                    f"Could not fetch data with '{self.fetch_func.__name__}', "
                    f"falling back to cached "
                    f"'{snap_path}' from '{last_update}' as requested."
                )
                with open(snap_path, "rb") as f:
                    self._data = pickle.load(f)
            else:
                snap_filename = now.strftime(self.snap_format)
                with open(os.path.join(self.cache_dir, snap_filename), "wb") as f:
                    pickle.dump(self._data, f)

        # Last snap sufficient, but haven't loaded it into memory yet
        elif self._data is None:
            with open(snap_path, "rb") as f:
                self._data = pickle.load(f)

        # Return snap data from in-memory cache
        return self._data
