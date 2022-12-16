# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime as dt

from trytond.model import fields
from trytond.pool import PoolMeta, Pool


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    def create_shipment(self, shipment_type):
        if shipment_type == 'out':
            self.create_productions()
        return super().create_shipment(shipment_type)

    def create_productions(self):
        pool = Pool()
        Production = pool.get('production')
        productions = []
        for line in self.lines:
            production = line.get_production()
            if not production:
                continue
            production.planned_start_date = (
                production.on_change_with_planned_start_date())
            productions.append(production)
            assert not line.productions
        Production.save(productions)
        Production.set_moves(productions)


class Line(metaclass=PoolMeta):
    __name__ = 'sale.line'

    productions = fields.One2Many(
        'production', 'origin', "Productions", readonly=True)

    @property
    def has_supply(self):
        return super().has_supply or bool(self.productions)

    def get_supply_state(self, name):
        state = super().get_supply_state(name)
        if self.productions:
            states = {p.state for p in self.productions}
            if states <= {'running', 'done', 'cancelled'}:
                if states == {'cancelled'}:
                    state = 'cancelled'
                else:
                    state = 'supplied'
            else:
                state = 'requested'
        return state

    @classmethod
    def copy(cls, lines, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('productions', None)
        return super().copy(lines, default=default)

    def get_production(self):
        "Return production for the sale line"
        pool = Pool()
        Production = pool.get('production')
        Date = pool.get('ir.date')
        today = Date.today()

        if (not self.supply_on_sale
                or self.productions
                or not self.product.producible):
            return

        # Ensure to create the request for the maximum paid
        if self.sale.shipment_method == 'invoice':
            invoice_skips = (set(self.sale.invoices_ignored)
                | set(self.sale.invoices_recreated))
            invoice_lines = [l for l in self.invoice_lines
                if l.invoice not in invoice_skips]
            if (not invoice_lines
                    or any((not l.invoice) or l.invoice.state != 'paid'
                        for l in invoice_lines)):
                return

        date = self.shipping_date
        if date <= today:
            date = today
        else:
            date -= dt.timedelta(1)
        product = self.product
        quantity = self._get_move_quantity('out')
        return Production(
            planned_date=date,
            company=self.sale.company,
            warehouse=self.warehouse,
            location=self.warehouse.production_location,
            product=product,
            bom=product.boms[0].bom if product.boms else None,
            uom=self.unit,
            quantity=quantity,
            state='request',
            origin=self,
            )
