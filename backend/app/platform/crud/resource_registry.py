from collections.abc import Mapping


class ResourceRegistry(Mapping):
    """Registry for generic CRUD resource definitions."""

    def __init__(self):
        self._resources = {}
        self._aliases = {}

    def __getitem__(self, key):
        config = self.get(key)
        if config is None:
            raise KeyError(key)
        return config

    def __iter__(self):
        return iter(self._resources)

    def __len__(self):
        return len(self._resources)

    def reset(self):
        self._resources = {}

    def set_aliases(self, aliases):
        self._aliases = dict(aliases or {})

    def register_many(self, resources):
        for key, config in resources.items():
            if key in self._resources:
                raise ValueError(f"Duplicate resource key: {key}")
            self._resources[key] = dict(config)

    def resolve_key(self, key):
        return self._aliases.get(key, key)

    def get(self, key, default=None):
        return self._resources.get(self.resolve_key(key), default)

    def all(self):
        return self._resources.copy()


registry = ResourceRegistry()
