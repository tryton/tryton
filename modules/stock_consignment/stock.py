# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from functools import wraps

from trytond.model import ModelView, Workflow, fields
from trytond.transaction import Transaction
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

__all__ = ['Location', 'LocationLeadTime',
    'Move', 'ShipmentInternal', 'Inventory', 'OrderPoint']


class Location(metaclass=PoolMeta):
    __name__ = 'stock.location'

    consignment_party = fields.Many2One(
        'party.party', "Consignment Party",
        states={
            'invisible': ~Eval('type').in_(['supplier', 'storage']),
            },
        depends=['type'],
        help="The party invoiced when consignment stock is used.")

    @classmethod
    def _parent_domain(cls):
        domain = super(Location, cls)._parent_domain()
        domain['supplier'].append('storage')
        domain['storage'].append('customer')
        return domain


class LocationLeadTime(metaclass=PoolMeta):
    __name__ = 'stock.location.lead_time'

    @classmethod
    def __setup__(cls):
        super(LocationLeadTime, cls).__setup__()
        cls.warehouse_to.domain = ['OR',
            cls.warehouse_to.domain,
            ('type', '=', 'storage'),
            ]


def set_origin_consignment(func):
    @wraps(func)
    def wrapper(cls, moves):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')
        lines = {}
        for move in moves:
            if not move.origin:
                line = move.get_invoice_line_consignment()
                if line:
                    lines[move] = line
        if lines:
            InvoiceLine.save(list(lines.values()))
            for move, line in lines.items():
                move.origin = line
            cls.save(list(lines.keys()))
        return func(cls, moves)
    return wrapper


def unset_origin_consignment(func):
    @wraps(func)
    def wrapper(cls, moves):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')
        lines, to_save = [], []
        for move in moves:
            if (isinstance(move.origin, InvoiceLine)
                    and move.origin.origin == move):
                lines.append(move.origin)
                move.origin = None
                to_save.append(move)
        if lines:
            InvoiceLine.delete(lines)
            cls.save(to_save)
        return func(cls, moves)
    return wrapper


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'

    @classmethod
    def _get_origin(cls):
        return super(Move, cls)._get_origin() + ['account.invoice.line']

    @fields.depends('from_location')
    def on_change_with_assignation_required(self, name=None):
        required = super(Move, self).on_change_with_assignation_required(
            name=name)
        if self.from_location:
            if (self.from_location.type == 'supplier'
                    and self.from_location.warehouse):
                required = True
        return required

    def _get_tax_rule_pattern(self):
        return {}

    def get_invoice_line_consignment(self):
        if (self.from_location.type == 'supplier'
                and self.to_location.type in {'storage', 'production'}
                and self.from_location.consignment_party):
            return self._get_supplier_invoice_line_consignment()
        elif (self.from_location.type in {'storage', 'production'}
                and self.to_location.type == 'customer'
                and self.from_location.consignment_party):
            return self._get_customer_invoice_line_consignment()

    def _get_supplier_invoice_line_consignment(self):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')
        Product = pool.get('product.product')
        ProductSupplier = pool.get('purchase.product_supplier')

        with Transaction().set_context(
                supplier=self.from_location.consignment_party.id):
            pattern = ProductSupplier.get_pattern()
        for product_supplier in self.product.product_suppliers:
            if product_supplier.match(pattern):
                currency = product_supplier.currency
                break
        else:
            currency = self.company.currency

        line = InvoiceLine()
        line.invoice_type = 'in'
        line.type = 'line'
        line.company = self.company
        line.party = self.from_location.consignment_party
        line.currency = currency
        line.product = self.product
        line.description = self.product.name
        line.quantity = self.quantity
        line.unit = self.uom
        line.account = self.product.account_expense_used
        line.stock_moves = [self]
        line.origin = self

        taxes = []
        pattern = self._get_tax_rule_pattern()
        for tax in line.product.supplier_taxes_used:
            if line.party.supplier_tax_rule:
                tax_ids = line.party.supplier_tax_rule.apply(tax, pattern)
                if tax_ids:
                    taxes.extend(tax_ids)
                continue
            taxes.append(tax.id)
        if line.party.supplier_tax_rule:
            tax_ids = line.party.supplier_tax_rule.apply(None, pattern)
            if tax_ids:
                taxes.extend(tax_ids)
        line.taxes = taxes

        with Transaction().set_context(
                currency=line.currency.id,
                supplier=line.party.id,
                uom=line.unit,
                taxes=[t.id for t in line.taxes]):
            line.unit_price = Product.get_purchase_price(
                [line.product], line.quantity)[line.product.id]
            line.unit_price = line.unit_price.quantize(
                Decimal(1) / 10 ** line.__class__.unit_price.digits[1])
        return line

    def _get_customer_invoice_line_consignment(self):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')
        Product = pool.get('product.product')

        line = InvoiceLine()
        line.invoice_type = 'out'
        line.type = 'line'
        line.company = self.company
        line.party = self.from_location.consignment_party
        line.currency = self.company.currency
        line.product = self.product
        line.description = self.product.name
        line.quantity = self.quantity
        line.unit = self.uom
        line.account = self.product.account_revenue_used
        line.stock_moves = [self]
        line.origin = self

        taxes = []
        pattern = self._get_tax_rule_pattern()
        for tax in line.product.customer_taxes_used:
            if line.party.customer_tax_rule:
                tax_ids = line.party.customer_tax_rule.apply(tax, pattern)
                if tax_ids:
                    taxes.extend(tax_ids)
                continue
            taxes.append(tax.id)
        if line.party.customer_tax_rule:
            tax_ids = line.party.customer_tax_rule.apply(None, pattern)
            if tax_ids:
                taxes.extend(tax_ids)
        line.taxes = taxes

        with Transaction().set_context(
                currency=line.currency.id,
                customer=line.party.id,
                uom=line.unit,
                taxes=[t.id for t in line.taxes]):
            line.unit_price = Product.get_sale_price(
                [line.product], line.quantity)[line.product.id]
            line.unit_price = line.unit_price.quantize(
                Decimal(1) / 10 ** line.__class__.unit_price.digits[1])
        return line

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    @unset_origin_consignment
    def draft(cls, moves):
        super(Move, cls).draft(moves)

    @classmethod
    @ModelView.button
    @Workflow.transition('assigned')
    @set_origin_consignment
    def assign(cls, moves):
        super(Move, cls).assign(moves)

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    @set_origin_consignment
    def do(cls, moves):
        super(Move, cls).do(moves)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    @unset_origin_consignment
    def cancel(cls, moves):
        super(Move, cls).cancel(moves)

    @classmethod
    def copy(cls, moves, default=None):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')
        moves = super(Move, cls).copy(moves, default=default)
        if not Transaction().context.get('_stock_move_split'):
            to_save = []
            for move in moves:
                if isinstance(move.origin, InvoiceLine):
                    move.origin = None
                    to_save.append(move)
            if to_save:
                cls.save(to_save)
        return moves


class ShipmentInternal(metaclass=PoolMeta):
    __name__ = 'stock.shipment.internal'

    @classmethod
    def __setup__(cls):
        super(ShipmentInternal, cls).__setup__()
        cls.from_location.domain = ['OR',
            cls.from_location.domain,
            ('type', '=', 'supplier'),
            ]
        cls.to_location.domain = ['OR',
            cls.to_location.domain,
            ('type', 'in', ['supplier', 'customer']),
            ]

    @fields.depends('to_location')
    def on_change_with_planned_start_date(self, pattern=None):
        if pattern is None:
            pattern = {}
        if self.to_location and not self.to_location.warehouse:
            pattern.setdefault('location_to', self.to_location.id)
        return super(ShipmentInternal, self).on_change_with_planned_start_date(
            pattern=pattern)


class Inventory(metaclass=PoolMeta):
    __name__ = 'stock.inventory'

    @classmethod
    def __setup__(cls):
        super(Inventory, cls).__setup__()
        cls.location.domain = ['OR',
            cls.location.domain,
            ('type', '=', 'supplier'),
            ]


class OrderPoint(metaclass=PoolMeta):
    __name__ = 'stock.order_point'

    @classmethod
    def __setup__(cls):
        super(OrderPoint, cls).__setup__()
        cls.provisioning_location.domain = ['OR',
            cls.provisioning_location.domain,
            ('type', '=', 'supplier'),
            ]
