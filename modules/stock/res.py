# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta


class User(metaclass=PoolMeta):
    __name__ = 'res.user'

    warehouse = fields.Many2One('stock.location',
        "Current Warehouse",
        domain=[('type', '=', 'warehouse')],
        help="The warehouse that the user works at.")

    @classmethod
    def __setup__(cls):
        super(User, cls).__setup__()
        cls._context_fields.insert(0, 'warehouse')

    @classmethod
    def _get_preferences(cls, user, context_only=False):
        preferences = super()._get_preferences(user, context_only=context_only)
        if user.warehouse:
            preferences['warehouse'] = user.warehouse.id
        return preferences
