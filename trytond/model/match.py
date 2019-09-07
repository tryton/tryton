# This file is part of Tryton.  The COPYRIGHT file at the toplevel of this
# repository contains the full copyright notices and license terms.


class MatchMixin(object):
    __slots__ = ()

    def match(self, pattern, match_none=False):
        '''Match on pattern
        pattern is a dictionary with model field as key
        and matching value as value'''
        for field, pattern_value in pattern.items():
            value = getattr(self, field)
            if not match_none and value is None:
                continue
            if self._fields[field]._type == 'many2one':
                value = value.id if value else value
            if value != pattern_value:
                return False
        return True
