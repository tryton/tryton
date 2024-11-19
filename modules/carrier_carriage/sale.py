# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from decimal import Decimal

from trytond.model import ModelSQL, ModelView, fields, sequence_ordered
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If
from trytond.transaction import Transaction


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    _states = {
        'readonly': Eval('state') != 'draft',
        }

    carriages = fields.One2Many(
        'sale.carriage', 'sale', "Carriages", readonly=True)
    before_carriages = fields.One2Many(
        'sale.carriage', 'sale', "Before Carriages",
        filter=[
            ('type', '=', 'before'),
            ],
        states=_states,
        help="Carriages before the main carrier.")
    after_carriages = fields.One2Many(
        'sale.carriage', 'sale', "After Carriages",
        filter=[
            ('type', '=', 'after'),
            ],
        states=_states,
        help="Carriages after the main carrier.")

    del _states

    def set_shipment_cost(self):
        removed = super().set_shipment_cost()
        lines = list(self.lines or [])
        for carriage in self.carriages:
            if carriage.cost_method:
                cost = self.compute_shipment_cost(carriage.carrier)
                if cost is not None:
                    unit_price = None
                    for line in removed:
                        if line.shipment_cost == cost:
                            unit_price = (
                                line.unit_price * Decimal(str(line.quantity)))
                    lines.append(self.get_shipment_cost_line(
                            carriage.carrier, cost, unit_price=unit_price))
        self.lines = lines
        return removed

    def _get_shipment_sale(self, Shipment, key):
        pool = Pool()
        ShipmentCarriage = pool.get('stock.shipment.carriage')
        ShipmentOut = pool.get('stock.shipment.out')
        shipment = super()._get_shipment_sale(Shipment, key)
        if isinstance(shipment, ShipmentOut):
            shipment.carriages = [
                ShipmentCarriage.from_sale(carriage)
                for carriage in self.carriages]
        return shipment

    @fields.depends('before_carriages', 'after_carriages')
    def _get_incoterm_pattern(self):
        pattern = super()._get_incoterm_pattern()

        def cost_methods(carriages):
            for carriage in carriages:
                yield getattr(carriage, 'cost_method', None)

        def negate(iterable):
            for i in iterable:
                yield not i

        if self.before_carriages:
            if any(cost_methods(self.before_carriages)):
                pattern['before_carrier'] = 'seller'
            elif all(negate(cost_methods(self.before_carriages))):
                pattern['before_carrier'] = 'buyer'

        if self.after_carriages:
            if any(cost_methods(self.after_carriages)):
                pattern['after_carrier'] = 'seller'
            elif all(negate(cost_methods(self.after_carriages))):
                pattern['after_carrier'] = 'buyer'
        return pattern

    @classmethod
    def copy(cls, sales, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('before_carriages')
        default.setdefault('after_carriages')
        return super().copy(sales, default=default)

    @property
    def _cost_shipments(self):
        shipments = super()._cost_shipments
        for shipment in self.shipments:
            shipments.extend(shipment.carriages)
        return shipments


class Line(metaclass=PoolMeta):
    __name__ = 'sale.line'

    def get_invoice_line(self):
        context = Transaction().context
        shipment_cost_invoiced = context.get('_shipment_cost_invoiced')
        if shipment_cost_invoiced is not None:
            # Make a copy to still detect new shipment after super call
            shipment_cost_invoiced = list(shipment_cost_invoiced)
        lines = super().get_invoice_line()
        if (self.shipment_cost
                and shipment_cost_invoiced is not None):
            for shipment in self.sale.shipments:
                if (shipment.state == 'done'
                        and shipment.id not in shipment_cost_invoiced):
                    invoice = self.sale._get_invoice_sale()
                    for carriage in shipment.carriages:
                        # XXX: self is not necessary linked to carriage
                        invoice_line = carriage.get_cost_sale_invoice_line(
                            invoice, origin=self)
                        if invoice_line:
                            lines.append(invoice_line)
        return lines


class Carriage(sequence_ordered(), ModelSQL, ModelView):
    __name__ = 'sale.carriage'

    _states = {
        'readonly': Eval('sale_state') != 'draft',
        }

    sale = fields.Many2One(
        'sale.sale', "Sale",
        required=True, ondelete='CASCADE', states=_states)
    type = fields.Selection([
            ('before', "Before"),
            ('after', "After"),
            ], "Type", sort=False, required=True, states=_states)
    carrier = fields.Many2One(
        'carrier', "Carrier", required=True,
        domain=[
            If(Eval('sale_state') == 'draft', [
                    ('carrier_product.salable', '=', True),
                    ('id', 'in', Eval('available_carriers', [])),
                    ],
                []),
            ],
        states=_states)
    cost_method = fields.Selection(
        'get_cost_methods', "Cost Method", states=_states)
    from_ = fields.Many2One('party.address', "From", states=_states)
    to = fields.Many2One('party.address', "To", states=_states)

    sale_state = fields.Function(
        fields.Selection('get_sale_states', "Sale State"),
        'on_change_with_sale_state')
    available_carriers = fields.Function(
        fields.Many2Many('carrier', None, None, "Available Carriers"),
        'on_change_with_available_carriers')

    del _states

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('sale')
        cls._order.insert(0, ('type', 'ASC'))

    @classmethod
    def get_cost_methods(cls):
        pool = Pool()
        Sale = pool.get('sale.sale')
        fieldname = 'shipment_cost_method'
        return Sale.fields_get([fieldname])[fieldname]['selection']

    @classmethod
    def get_sale_states(cls):
        pool = Pool()
        Sale = pool.get('sale.sale')
        return Sale.fields_get(['state'])['state']['selection']

    @fields.depends('sale', '_parent_sale.state')
    def on_change_with_sale_state(self, name=None):
        if self.sale:
            return self.sale.state

    @classmethod
    def default_available_carriers(cls):
        pool = Pool()
        CarrierSelection = pool.get('carrier.selection')
        carriers = CarrierSelection.get_carriers({})
        return [c.id for c in carriers]

    @fields.depends(methods=['_get_carrier_selection_pattern'])
    def on_change_with_available_carriers(self, name=None):
        pool = Pool()
        CarrierSelection = pool.get('carrier.selection')

        pattern = self._get_carrier_selection_pattern()
        return CarrierSelection.get_carriers(pattern)

    @fields.depends('from_', 'to')
    def _get_carrier_selection_pattern(self):
        pattern = {}
        if self.from_ and self.from_.country:
            pattern['from_country'] = self.from_.country.id
        else:
            pattern['from_country'] = None
        if self.to and self.to.country:
            pattern['to_country'] = self.to.country.id
        else:
            pattern['to_country'] = None
        return pattern

    @fields.depends(methods=['_on_change_pattern'])
    def on_change_from_(self):
        self._on_change_pattern()

    @fields.depends(methods=['_on_change_pattern'])
    def on_change_to(self):
        self._on_change_pattern()

    @fields.depends('carrier', methods=['on_change_with_available_carriers'])
    def _on_change_pattern(self):
        self.available_carriers = self.on_change_with_available_carriers()
        if self.carrier and self.carrier not in self.available_carriers:
            self.carrier = None

    def get_rec_name(self, name):
        return f'{self.carrier.rec_name} @ {self.sale.rec_name}'
