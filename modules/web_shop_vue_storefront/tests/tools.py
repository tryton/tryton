# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.


class AnyDictWith(dict):
    def __eq__(self, other):
        if not isinstance(other, dict):
            return False
        items = list(sorted(filter(lambda i: i[0] in self, other.items())))
        return list(sorted(self.items())) == items
