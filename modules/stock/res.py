# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction


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

    def get_status_bar(self, name):
        pool = Pool()
        Location = pool.get('stock.location')
        status = super().get_status_bar(name)

        if (self.warehouse
                and len(Location.search([('type', '=', 'warehouse')])) > 1):
            status += ' - %s' % self.warehouse.rec_name
        return status

    @classmethod
    def read(cls, ids, fields_names):
        context = Transaction().context
        user_id = Transaction().user
        if user_id == 0 and 'user' in Transaction().context:
            user_id = Transaction().context['user']
        result = super().read(ids, fields_names)
        if ('warehouse' in fields_names
                and context.get('warehouse')
                and user_id in ids):
            for values in result:
                if values['id'] == user_id:
                    values['warehouse'] = context['warehouse']
        return result
