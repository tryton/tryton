# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from ..cache import Cache
from ..model import ModelSQL, fields, Unique
from ..rpc import RPC
from ..transaction import Transaction


class _Calendar(ModelSQL):
    _order_name = 'index'
    index = fields.Integer("Index", required=True)
    name = fields.Char("Name", required=True, translate=True)
    abbreviation = fields.Char("Abbreviation", required=True, translate=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls.__rpc__.update({
                'read': RPC(),
                'search': RPC(),
                'search_count': RPC(),
                'search_read': RPC(),
                })
        cls.index.domain = [
            ('index', '>=', cls._min_index),
            ('index', '<=', cls._max_index),
            ]
        cls._order = [('index', 'ASC')]
        cls._sql_constraints = [
            ('index_unique', Unique(t, t.index),
                "The index must by unique.")
            ]

    @classmethod
    def locale(cls, language=None, field='name'):
        transaction = Transaction()
        if language is None:
            language = transaction.language
        elif isinstance(language, ModelSQL):
            language = language.code
        key = (language, field)
        result = cls._cache_locale.get(key)
        if not result:
            with transaction.set_context(language=language):
                records = cls.search([])
            result = [None] * cls._min_index
            result += [getattr(r, field) for r in records]
            cls._cache_locale.set(key, result)
        return result


class Month(_Calendar):
    "Month"
    __name__ = 'ir.calendar.month'
    _min_index = 1
    _max_index = 12
    _cache_locale = Cache('ir.calendar.month')


class Day(_Calendar):
    "Day"
    __name__ = 'ir.calendar.day'
    _min_index = 0
    _max_index = 6
    _cache_locale = Cache('ir.calendar.day')
