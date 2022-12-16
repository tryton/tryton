# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Null

from trytond.i18n import gettext
from trytond.model import fields, ModelSQL, ModelView, Workflow
from trytond.model.exceptions import ValidationError
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, If, Bool
from trytond.tools import grouped_slice, reduce_ids
from trytond.transaction import Transaction


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
        ondelete='CASCADE', select=True, required=True)
    lot = fields.Many2One(
        'stock.lot', "Lot", ondelete='CASCADE', select=True, required=True,
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
            ('subscription_services', '=', Eval('service')),
            ],
        states={
            'required': ((Eval('subscription_state') == 'running')
                & Eval('asset_lot_required')),
            'invisible': ~Eval('asset_lot_required'),
            'readonly': Eval('subscription_state') != 'draft',
            },
        depends=['service', 'subscription_state', 'asset_lot_required'])
    asset_lot_required = fields.Function(
        fields.Boolean("Asset Lot Required"),
        'on_change_with_asset_lot_required')

    @classmethod
    def __setup__(cls):
        super(SubscriptionLine, cls).__setup__()

        cls.quantity.domain = [
            cls.quantity.domain,
            If(Bool(Eval('asset_lot')),
                ('quantity', '=', 1),
                ()),
            ]
        cls.quantity.depends.append('asset_lot')

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
        default.setdefault('lot')
        return super(SubscriptionLine, cls).copy(lines, default)

    @classmethod
    def validate(cls, lines):
        super(SubscriptionLine, cls).validate(lines)
        cls._validate_dates(lines)

    @classmethod
    def _validate_dates(cls, lines):
        transaction = Transaction()
        connection = transaction.connection
        cursor = connection.cursor()

        transaction.database.lock(connection, cls._table)

        line = cls.__table__()
        other = cls.__table__()
        overlap_where = (
            ((line.end_date == Null)
                & ((other.end_date == Null)
                    | (other.start_date > line.start_date)
                    | (other.end_date > line.start_date)))
            | ((line.end_date != Null)
                & ((
                        (other.end_date == Null)
                        & (other.start_date < line.end_date))
                    | ((other.end_date != Null)
                        & ((
                                (other.end_date >= line.start_date)
                                & (other.end_date < line.end_date))
                            | ((other.start_date >= line.start_date)
                                & (other.start_date < line.end_date)))))))
        for sub_lines in grouped_slice(lines):
            sub_ids = [l.id for l in sub_lines]
            cursor.execute(*line.join(other,
                    condition=((line.id != other.id)
                        & (line.asset_lot == other.asset_lot))
                    ).select(line.id, other.id,
                    where=((line.asset_lot != Null)
                        & reduce_ids(line.id, sub_ids)
                        & overlap_where),
                    limit=1))
            overlapping = cursor.fetchone()
            if overlapping:
                sline1, sline2 = cls.browse(overlapping)
                raise ValidationError(
                    gettext('sale_subscription_asset.msg_asset_line_overlap',
                        line1=sline1.rec_name,
                        line2=sline2.rec_name))
