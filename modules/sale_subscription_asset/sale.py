# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql.operators import Equal

from trytond.model import Exclude, ModelSQL, ModelView, Workflow, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval, If
from trytond.sql.functions import DateRange
from trytond.sql.operators import RangeOverlap


class SubscriptionService(metaclass=PoolMeta):
    __name__ = 'sale.subscription.service'

    asset_lots = fields.Many2Many(
        'sale.subscription.service-stock.lot.asset',
        'service', 'lot', "Asset Lots",
        domain=[
            ('product.type', '=', 'assets'),
            ])
    asset_lots_available = fields.Many2Many(
        'sale.subscription.service-stock.lot.asset',
        'service', 'lot', "Available Asset Lots", readonly=True,
        domain=[
            ('product.type', '=', 'assets'),
            ],
        filter=[
            ('subscribed', '=', None),
            ])


class SubscriptionServiceStockLot(ModelSQL):
    "Subscription Service - Stock Lot Asset"
    __name__ = 'sale.subscription.service-stock.lot.asset'

    service = fields.Many2One(
        'sale.subscription.service', "Service",
        ondelete='CASCADE', required=True)
    lot = fields.Many2One(
        'stock.lot', "Lot", ondelete='CASCADE', required=True,
        domain=[
            ('product.type', '=', 'assets'),
            ])


class Subscription(metaclass=PoolMeta):
    __name__ = 'sale.subscription'

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, subscriptions):
        pool = Pool()
        SubscriptionLine = pool.get('sale.subscription.line')

        sub_lines = [l for s in subscriptions for l in s.lines if l.asset_lot]
        SubscriptionLine.write(sub_lines, {'asset_lot': None})

        super(Subscription, cls).cancel(subscriptions)

    @classmethod
    @ModelView.button
    @Workflow.transition('running')
    def run(cls, subscriptions):
        pool = Pool()
        Line = pool.get('sale.subscription.line')
        super(Subscription, cls).run(subscriptions)
        lines = [l for s in subscriptions for l in s.lines]
        Line._validate(lines, ['asset_lot'])


class SubscriptionLine(metaclass=PoolMeta):
    __name__ = 'sale.subscription.line'

    asset_lot = fields.Many2One('stock.lot', "Asset Lot",
        domain=[
            ('subscription_services', '=', Eval('service', -1)),
            ],
        states={
            'required': ((Eval('subscription_state') == 'running')
                & Eval('asset_lot_required')),
            'invisible': ~Eval('asset_lot_required'),
            'readonly': Eval('subscription_state') != 'draft',
            })
    asset_lot_required = fields.Function(
        fields.Boolean("Asset Lot Required"),
        'on_change_with_asset_lot_required')

    @classmethod
    def __setup__(cls):
        super(SubscriptionLine, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('dates_asset_lot_overlap',
                Exclude(t,
                    (t.asset_lot, Equal),
                    (DateRange(t.start_date, t.end_date, '[)'), RangeOverlap),
                    ),
                'sale_subscription_asset.msg_asset_line_overlap'),
            ]

        cls.quantity.domain = [
            cls.quantity.domain,
            If(Bool(Eval('asset_lot')),
                ('quantity', '=', 1),
                ()),
            ]

    @fields.depends('service')
    def on_change_with_asset_lot_required(self, name=None):
        if not self.service:
            return False
        return bool(self.service.asset_lots)

    @classmethod
    def copy(cls, lines, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('asset_lot')
        return super(SubscriptionLine, cls).copy(lines, default)
