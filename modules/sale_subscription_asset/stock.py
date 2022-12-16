# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.tools import grouped_slice
from trytond.transaction import Transaction


class Lot(metaclass=PoolMeta):
    __name__ = 'stock.lot'

    subscription_services = fields.Many2Many(
        'sale.subscription.service-stock.lot.asset',
        'lot', 'service', "Services")
    subscription_lines = fields.One2Many(
        'sale.subscription.line', 'asset_lot', "Subscription Lines")
    subscribed = fields.Function(
        fields.Many2One('sale.subscription.line', "Subscribed"),
        'get_subscribed', searcher='search_subscribed')

    @classmethod
    def get_subscribed(cls, lots, name):
        pool = Pool()
        Date = pool.get('ir.date')
        SubscriptionLine = pool.get('sale.subscription.line')

        subscribed_lines = {l.id: None for l in lots}
        date = Transaction().context.get('date', Date.today())
        for sub_lots in grouped_slice(lots):
            lines = SubscriptionLine.search([
                    ('asset_lot', 'in', [l.id for l in sub_lots]),
                    [
                        ('start_date', '<=', date),
                        ['OR',
                            ('end_date', '=', None),
                            ('end_date', '>', date),
                            ],
                        ]
                    ])
            subscribed_lines.update((s.asset_lot.id, s.id) for s in lines)
        return subscribed_lines

    @classmethod
    def search_subscribed(cls, name, clause):
        pool = Pool()
        Date = pool.get('ir.date')

        name, operator, value = clause[:3]
        date = Transaction().context.get('date', Date.today())
        domain = [
            ('asset_lot', '!=', None),
            ('start_date', '<=', date),
            ['OR',
                ('end_date', '=', None),
                ('end_date', '>', date),
                ],
            ]
        if '.' in name:
            _, target_name = name.split('.', 1)
            domain.append((target_name,) + tuple(clause[1:]))
            return [('subscription_lines', 'where', domain)]
        else:
            if (operator, value) == ('=', None):
                return [('subscription_lines', 'not where', domain)]
            elif (operator, value) == ('!=', None):
                return [('subscription_lines', 'where', domain)]
            else:
                if isinstance(value, str):
                    target_name = 'rec_name'
                else:
                    target_name = 'id'
                domain.append((target_name,) + tuple(clause[1:]))
                return [('subscription_lines', 'where', domain)]
