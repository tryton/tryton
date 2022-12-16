# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import Index
from trytond.pool import PoolMeta


class PostalCode(metaclass=PoolMeta):
    __name__ = 'country.postal_code'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_indexes.update({
                Index(
                    t,
                    (Index.Unaccent(t.city), Index.Similarity()),
                    (t.country, Index.Equality()),
                    (t.subdivision, Index.Equality())),
                })
