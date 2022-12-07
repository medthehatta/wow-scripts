class FormalVector:
    _ZERO = "FormalVector.zero()"
    _registry = {}

    @classmethod
    def named(cls, name, content=None):
        if name not in cls._registry:
            cls._registry[name] = cls(
                components={name: 1},
                basis={name: content},
                name=name,
            )
        return cls._registry[name]

    @classmethod
    def zero(cls):
        name = cls._ZERO
        if name not in cls._registry:
            cls._registry[name] = cls(
                components={},
                basis={},
                name=name,
            )
        return cls._registry[name]

    @classmethod
    def sum(cls, vectors):
        return sum(vectors, start=cls.zero())

    def __init__(self, components=None, basis=None, name=None):
        self.name = name
        self.components = components
        self.basis = basis
        if self.components.keys() != self.basis.keys():
            raise ValueError(
                f"Component keys and basis keys do not match! "
                f"components={components.keys()}, basis={basis.keys()}"
            )

    def is_leaf(self):
        return self.components == {self.name: 1}

    @property
    def content(self):
        if self.is_leaf():
            return self.basis[self.name]
        else:
            return self

    def pairs(self):
        return [(self.components[k], self.basis[k]) for k in self.components]

    def triples(self):
        return [
            (k, self.components[k], self.basis[k]) for k in self.components
        ]

    def project(self, k):
        return self.components[k] * FormalVector.named(k, self.basis[k])

    def __getitem__(self, item):
        return self.components[item]

    def __add__(self, other):
        components = {}
        basis = {}
        keys = set(
            list(self.components.keys()) +
            list(other.components.keys())
        )
        for k in keys:
            components[k] = (
                self.components.get(k, 0) +
                other.components.get(k, 0)
            )
            basis[k] = self.basis.get(k) or other.basis.get(k)
        return FormalVector(components=components, basis=basis)

    def __rmul__(self, alpha):
        return FormalVector(
            components={k: alpha*v for (k, v) in self.components.items()},
            basis=self.basis,
        )

    def __sub__(self, other):
        return self + (-1) * other

    def __neg__(self):
        return (-1) * self

    def __repr__(self):
        if self.name:
            return self.name
        elif self.components == {}:
            return self._ZERO
        else:
            return " + ".join(
                f"{k}" if v == 1 else
                f"-{k}" if v == -1 else
                f"{v}*{k}"
                for (k, v) in self.components.items()
            )


