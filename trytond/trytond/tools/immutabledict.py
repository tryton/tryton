# This file is part of Tryton.  The COPYRIGHT file at the toplevel of this
# repository contains the full copyright notices and license terms.
from copy import deepcopy


class ImmutableDict(dict):

    __slots__ = ()

    def _not_allowed(cls, *args, **kwargs):
        raise TypeError("Operation not allowed on ImmutableDict")

    def __deepcopy__(self, memo):
        return ImmutableDict(
            (k, deepcopy(v, memo=memo)) for k, v in self.items())

    __setitem__ = _not_allowed
    __delitem__ = _not_allowed
    __ior__ = _not_allowed
    clear = _not_allowed
    pop = _not_allowed
    popitem = _not_allowed
    setdefault = _not_allowed
    update = _not_allowed

    del _not_allowed
