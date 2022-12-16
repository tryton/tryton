# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta


class User(metaclass=PoolMeta):
    __name__ = 'res.user'

    @classmethod
    def _get_preferences(cls, user, context_only=False):
        preferences = super()._get_preferences(user, context_only=context_only)
        if user.company:
            preferences['cost_price_warehouse'] = (
                user.company.cost_price_warehouse)
        return preferences
