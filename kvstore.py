import pickle

class InefficientKVStore:
    
    def __init__(self, cache_path: str):
        self.cache_path = cache_path
        self._data = self.slurp()
        self._remove = []
    
    def slurp(self):
        try:
            with open(self.cache_path, "rb") as f:
                return pickle.load(f)
        except OSError:
            return {}
    
    def commit(self):
        # Insertions / Updates
        to_write = {**self.slurp(), **self._data}
        # Deletions
        for k in self._remove:
            to_write.pop(k)
        self._remove = []
        # Save
        with open(self.cache_path, "wb") as f:
            pickle.dump(to_write, f)
            self._data = to_write

    def get(self, id_):
        return self._data.get(id_)

    def put(self, id_, value):
        self._data[id_] = value

    def pop(self, id_):
        self._remove.append(id_)
        val = self.get(id_)
        self._data.pop(id_)
        return val
