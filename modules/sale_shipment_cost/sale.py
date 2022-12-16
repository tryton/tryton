# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, Workflow, fields
from trytond.transaction import Transaction
from trytond.pyson import Eval, Bool
from trytond.pool import Pool, PoolMeta

__all__ = ['Configuration', 'Sale', 'SaleLine']


class Configuration:
    __metaclass__ = PoolMeta
    __name__ = 'sale.configuration'
    sale_carrier = fields.Property(fields.Many2One('carrier', 'Carrier',
        domain=[('carrier_product.salable', '=', True)],
    ))
    sale_shipment_cost_method = fields.Property(fields.Selection([
                ('order', 'On Order'),
                ('shipment', 'On Shipment'),
                ], 'Sale Shipment Cost Method',
            states={
                'required': Bool(Eval('context', {}).get('company')),
                }))

    @staticmethod
    def default_sale_shipment_cost_method():
        return 'shipment'


class Sale:
    __metaclass__ = PoolMeta
    __name__ = 'sale.sale'
    carrier = fields.Many2One('carrier', 'Carrier',
        domain=[('carrier_product.salable', '=', True)],
        states={
            'readonly': Eval('state') != 'draft',
        },
        depends=['state'])
    shipment_cost_method = fields.Selection([
        ('order', 'On Order'),
        ('shipment', 'On Shipment'),
        ], 'Shipment Cost Method', required=True, states={
            'readonly': Eval('state') != 'draft',
            }, depends=['state'])

    @staticmethod
    def default_carrier():
        Config = Pool().get('sale.configuration')
        config = Config(1)
        return config.sale_carrier.id if config.sale_carrier else None

    @staticmethod
    def default_shipment_cost_method():
        Config = Pool().get('sale.configuration')
        config = Config(1)
        return config.sale_shipment_cost_method

    @classmethod
    @ModelView.button
    @Workflow.transition('quotation')
    def quote(cls, sales):
        super(Sale, cls).quote(sales)
        for sale in sales:
            sale.set_shipment_cost()
        cls.save(sales)

    def _get_carrier_context(self):
        return {}

    def set_shipment_cost(self):
        pool = Pool()
        Date = pool.get('ir.date')
        Currency = pool.get('currency.currency')

        cost, currency_id = 0, None
        if self.carrier:
            with Transaction().set_context(self._get_carrier_context()):
                cost, currency_id = self.carrier.get_sale_price()

        cost_line = None
        products = [line.product for line in self.lines or []
                if getattr(line, 'product', None)]
        stockable = any(product.type in ('goods', 'assets')
            for product in products)
        if cost and currency_id and stockable:
            today = Date.today()
            date = self.sale_date or today
            with Transaction().set_context(date=date):
                cost = Currency.compute(Currency(currency_id), cost,
                    self.currency)
            cost_line = self.get_shipment_cost_line(cost)

        lines = list(self.lines or [])
        for line in self.lines:
            if line.type != 'line' or not line.shipment_cost:
                continue
            if cost_line and line.shipment_cost == cost:
                cost_line = None
            else:
                lines.remove(line)
        if cost_line:
            lines.append(cost_line)
        self.lines = lines

    def get_shipment_cost_line(self, cost):
        pool = Pool()
        SaleLine = pool.get('sale.line')

        product = self.carrier.carrier_product

        sequence = None
        if self.lines:
            last_line = self.lines[-1]
            if last_line.sequence is not None:
                sequence = last_line.sequence + 1

        cost_line = SaleLine(
            sale=self,
            sequence=sequence,
            type='line',
            product=product,
            quantity=1,  # XXX
            unit=product.sale_uom,
            shipment_cost=cost,
            )
        cost_line.on_change_product()
        cost_line.unit_price = cost_line.amount = cost
        return cost_line

    def create_shipment(self, shipment_type):
        Shipment = Pool().get('stock.shipment.out')

        shipments = super(Sale, self).create_shipment(shipment_type)
        if shipment_type == 'out' and shipments and self.carrier:
            for shipment in shipments:
                shipment.carrier = self.carrier
                with Transaction().set_context(
                        shipment.get_carrier_context()):
                    cost, currency_id = self.carrier.get_sale_price()
                Shipment.write([shipment], {
                        'carrier': self.carrier.id,
                        'cost': cost,
                        'cost_currency': currency_id,
                        })
        return shipments

    def create_invoice(self):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        Shipment = pool.get('stock.shipment.out')

        invoice = super(Sale, self).create_invoice()
        if invoice and self.shipment_cost_method == 'shipment':
            for shipment in self.shipments:
                if (shipment.state == 'done'
                        and shipment.carrier
                        and shipment.cost
                        and not shipment.cost_invoice_line):
                    invoice_line = shipment.get_cost_invoice_line(invoice)
                    if not invoice_line:
                        continue
                    invoice_line.invoice = invoice
                    invoice_line.save()
                    Shipment.write([shipment], {
                            'cost_invoice_line': invoice_line.id,
                            })
            Invoice.update_taxes([invoice])
        return invoice


class SaleLine:
    __metaclass__ = PoolMeta
    __name__ = 'sale.line'
    shipment_cost = fields.Numeric('Shipment Cost',
        digits=(16, Eval('_parent_sale', {}).get('currency_digits', 2)))

    def _get_invoice_line_quantity(self):
        quantity = super(SaleLine, self)._get_invoice_line_quantity()
        if (self.shipment_cost
                and self.sale.shipment_cost_method == 'shipment'):
            return 0
        return quantity
