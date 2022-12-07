import pickle

class InefficientKVStore:
    
    def __init__(self, cache_path: str):
        self.cache_path = cache_path
        self._data = self.slurp()
    
    def slurp(self):
        try:
            with open(self.cache_path, "rb") as f:
                return pickle.load(f)
        except OSError:
            return {}
    
    def commit(self):
        to_write = {**self.slurp(), **self._data}
        with open(self.cache_path, "wb") as f:
            pickle.dump(to_write, f)
            self._data = to_write

    def get(self, id_):
        return self._data.get(id_)

    def put(self, id_, value):
        self._data[id_] = value
