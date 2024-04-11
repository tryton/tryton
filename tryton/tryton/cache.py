# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from collections import OrderedDict


class CacheDict(OrderedDict):

    def __init__(self, *args, cache_len=10, default_factory=None, **kwargs):
        assert cache_len > 0
        self.cache_len = cache_len
        self.default_factory = default_factory

        super().__init__(*args, **kwargs)

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self.move_to_end(key)

        while len(self) > self.cache_len:
            oldkey = next(iter(self))
            self.__delitem__(oldkey)

    def __getitem__(self, key):
        value = super().__getitem__(key)
        self.move_to_end(key)
        return value

    def __missing__(self, key):
        if self.default_factory is None:
            raise KeyError(key)
        value = self.default_factory()
        self[key] = value
        return value
