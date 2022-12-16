# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from trytond.model import ModelView
from trytond.wizard import (Wizard, StateView, StateAction, StateTransition,
    Button)

__all__ = ['StockSupply', 'StockSupplyStart']


class StockSupply(Wizard):
    "Supply Stock"
    __name__ = 'stock.supply'
    start = StateView(
        'stock.supply.start',
        'stock_supply.supply_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Create', 'create_', 'tryton-ok', default=True),
            ])
    create_ = StateTransition()
    internal = StateAction('stock.act_shipment_internal_form')
    purchase = StateAction('purchase_request.act_purchase_request_form')

    @classmethod
    def __setup__(cls):
        super(StockSupply, cls).__setup__()
        cls._error_messages.update({
                'late_supplier_moves': 'There are some late supplier moves.',
                'late_customer_moves': 'There are some late customer moves.',
                })

    @classmethod
    def types(cls):
        return ['internal', 'purchase']

    @classmethod
    def next_action(cls, name):
        types = cls.types()
        try:
            return types[types.index(name) + 1]
        except IndexError:
            return 'end'

    def transition_create_(self):
        pool = Pool()
        Move = pool.get('stock.move')
        ShipmentInternal = pool.get('stock.shipment.internal')
        Date = pool.get('ir.date')
        today = Date.today()
        if Move.search([
                    ('from_location.type', '=', 'supplier'),
                    ('to_location.type', '=', 'storage'),
                    ('state', '=', 'draft'),
                    ('planned_date', '<', today),
                    ], order=[]):
            self.raise_user_warning('%s.supplier@%s' % (self.__name__, today),
                'late_supplier_moves')
        if Move.search([
                    ('from_location.type', '=', 'storage'),
                    ('to_location.type', '=', 'customer'),
                    ('state', '=', 'draft'),
                    ('planned_date', '<', today),
                    ], order=[]):
            self.raise_user_warning('%s.customer@%s' % (self.__name__, today),
                'late_customer_moves')

        first = True
        created = False
        while created or first:
            created = False
            for type_ in self.types():
                created |= bool(getattr(self, 'generate_%s' % type_)(first))
            first = False

        # Remove transit split of request
        shipments = ShipmentInternal.search([
                ('state', '=', 'request'),
                ])
        Move.delete([m for s in shipments for m in s.moves
                if m.from_location == s.transit_location])
        for shipment in shipments:
            Move.write([m for m in shipment.moves], {
                    'from_location': shipment.from_location.id,
                    'to_location': shipment.to_location.id,
                    'planned_date': shipment.planned_date,
                    })

        return self.types()[0]

    def generate_internal(self, clean):
        pool = Pool()
        ShipmentInternal = pool.get('stock.shipment.internal')
        return ShipmentInternal.generate_internal_shipment(clean=clean)

    def transition_internal(self):
        return self.next_action('internal')

    @property
    def _purchase_parameters(self):
        return {}

    def generate_purchase(self, clean):
        pool = Pool()
        PurchaseRequest = pool.get('purchase.request')
        PurchaseRequest.generate_requests(**self._purchase_parameters)
        return False

    def transition_purchase(self):
        return self.next_action('purchase')


class StockSupplyStart(ModelView):
    "Supply Stock"
    __name__ = 'stock.supply.start'
