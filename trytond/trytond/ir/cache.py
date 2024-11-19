# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, Unique, fields


class Cache(ModelSQL):
    __name__ = 'ir.cache'
    name = fields.Char('Name', required=True)
    timestamp = fields.Timestamp("Timestamp")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('name_unique', Unique(t, t.name), 'ir.msg_cache_name_unique'),
            ]
