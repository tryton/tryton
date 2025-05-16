# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from functools import wraps

from trytond.model import ModelView, Workflow, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction, inactive_records


class Location(metaclass=PoolMeta):
    __name__ = 'stock.location'

    consignment_party = fields.Many2One(
        'party.party', "Consignment Party",
        states={
            'invisible': ~Eval('type').in_(['supplier', 'storage']),
            },
        help="The party invoiced when consignment stock is used.")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.lost_found_location.states['invisible'] &= (
            ~Eval('type').in_(['supplier', 'customer']))

    @classmethod
    def _parent_domain(cls):
        domain = super()._parent_domain()
        domain['supplier'].append('storage')
        domain['storage'].append('customer')
        return domain

    @property
    def lost_found_used(self):
        lost_found = super().lost_found_used
        if not lost_found and not self.warehouse and self.type == 'storage':
            location = self.parent
            while location:
                if location.type in {'supplier', 'storage'}:
                    lost_found = location.lost_found_location
                    break
                location = location.parent
        return lost_found


class LocationLeadTime(metaclass=PoolMeta):
    __name__ = 'stock.location.lead_time'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.warehouse_to.domain = ['OR',
            cls.warehouse_to.domain,
            ('type', '=', 'storage'),
            ]


def set_origin_consignment(state):
    def decorator(func):
        @wraps(func)
        def wrapper(cls, moves):
            pool = Pool()
            InvoiceLine = pool.get('account.invoice.line')
            to_save = []
            move2line = {}
            for move in moves:
                if not move.consignment_invoice_lines:
                    lines = move.get_invoice_lines_consignment()
                    if lines:
                        to_save.extend(lines)
                        move2line[move] = lines[0]
            if to_save:
                InvoiceLine.save(to_save)
                for move, line in move2line.items():
                    if not move.origin:
                        move.origin = line
                    original_state, move.state = move.state, state
                    if (move.on_change_with_unit_price_required()
                            and move.unit_price is None):
                        move.unit_price = line.unit_price
                        move.currency = line.currency
                    else:
                        move.unit_price = None
                        move.currency = None
                    move.state = original_state
                cls.save(list(move2line.keys()))
            return func(cls, moves)
        return wrapper
    return decorator


def unset_origin_consignment(state):
    def decorator(func):
        @wraps(func)
        def wrapper(cls, moves):
            pool = Pool()
            InvoiceLine = pool.get('account.invoice.line')
            lines, to_save = [], set()
            for move in moves:
                for invoice_line in move.consignment_invoice_lines:
                    lines.append(invoice_line)
                    if move.origin == move:
                        move.origin = None
                    to_save.add(move)
                if (not move.on_change_with_unit_price_required()
                        and (move.unit_price or move.currency)):
                    move.unit_price = None
                    move.currency = None
                    to_save.add(move)
            if lines:
                InvoiceLine.delete(lines)
            if to_save:
                cls.save(list(to_save))
            return func(cls, moves)
        return wrapper
    return decorator


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'

    consignment_invoice_lines = fields.One2Many(
        'account.invoice.line', 'origin', "Consignment Invoice Lines",
        readonly=True,
        states={
            'invisible': ~Eval('consignment_invoice_lines'),
            })

    @fields.depends(
        'state', 'from_location', 'to_location', 'unit_price', 'currency')
    def on_change_with_unit_price_required(self, name=None):
        required = super().on_change_with_unit_price_required(name)
        if (required
                and self.state in {'staging', 'draft'}
                and self.from_location
                and self.to_location
                and ((
                        self.from_location.type == 'supplier'
                        and self.to_location.type in {
                            'storage', 'production', 'customer'})
                    or (self.from_location.type in {
                            'storage', 'production', 'supplier'}
                        and self.to_location.type == 'customer'))
                and self.from_location.consignment_party):
            # Keep the requirement to allow origin consignment decorators to
            # set the unit price before changing the move state
            required = (self.unit_price is not None) and self.currency
        return required

    @classmethod
    def _get_origin(cls):
        return super()._get_origin() + ['account.invoice.line']

    @fields.depends('from_location')
    def on_change_with_assignation_required(self, name=None):
        required = super().on_change_with_assignation_required(
            name=name)
        if self.from_location:
            if (self.quantity
                    and self.from_location.type == 'supplier'
                    and self.from_location.warehouse):
                required = True
        return required

    @classmethod
    def search_assignation_required(cls, name, clause):
        pool = Pool()
        Location = pool.get('stock.location')
        _, operator, operand = clause
        domain = super().search_assignation_required(name, clause)
        reverse = {
            '=': '!=',
            '!=': '=',
            }
        if operator in reverse:
            with inactive_records():
                warehouses = Location.search([
                        ('type', '=', 'warehouse'),
                        ])
                warehouse_ids = list(map(int, warehouses))
            if operator == '!=':
                bool_op = 'AND'
                warehouse_op = 'not child_of'
            else:
                bool_op = 'OR'
                warehouse_op = 'child_of'
            if not operand:
                operator = reverse[operator]
            domain = [bool_op,
                domain,
                [('quantity', '!=', 0),
                    ('from_location.type', operator, 'supplier'),
                    ('from_location', warehouse_op, warehouse_ids, 'parent'),
                    ],
                ]
        return domain

    @property
    def is_supplier_consignment(self):
        return (self.from_location.type == 'supplier'
            and self.to_location.type in {'storage', 'production', 'customer'}
            and self.from_location.consignment_party)

    @property
    def is_customer_consignment(self):
        return (
            self.from_location.type in {'storage', 'production', 'supplier'}
            and self.to_location.type == 'customer'
            and self.from_location.consignment_party)

    def get_invoice_lines_consignment(self):
        lines = []
        if self.is_supplier_consignment:
            lines.append(self._get_supplier_invoice_line_consignment())
        if self.is_customer_consignment:
            lines.append(self._get_customer_invoice_line_consignment())
        return lines

    def _get_supplier_invoice_line_consignment(self):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')
        Product = pool.get('product.product')
        ProductSupplier = pool.get('purchase.product_supplier')

        with Transaction().set_context(
                supplier=self.from_location.consignment_party.id):
            pattern = ProductSupplier.get_pattern()
        for product_supplier in self.product.product_suppliers_used(**pattern):
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
        line.quantity = self.quantity
        line.unit = self.unit
        line.stock_moves = [self]
        line.origin = self
        line.on_change_product()

        with Transaction().set_context(
                currency=line.currency.id,
                supplier=line.party.id,
                uom=line.unit.id,
                taxes=[t.id for t in line.taxes]):
            line.unit_price = Product.get_purchase_price(
                [line.product], line.quantity)[line.product.id]
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
        line.quantity = self.quantity
        line.unit = self.unit
        line.stock_moves = [self]
        line.origin = self
        line.on_change_product()

        with Transaction().set_context(
                currency=line.currency.id,
                customer=line.party.id,
                uom=line.unit.id,
                taxes=[t.id for t in line.taxes]):
            line.unit_price = Product.get_sale_price(
                [line.product], line.quantity)[line.product.id]
        return line

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    @unset_origin_consignment('draft')
    def draft(cls, moves):
        super().draft(moves)

    @classmethod
    @ModelView.button
    @Workflow.transition('assigned')
    @set_origin_consignment('assigned')
    def assign(cls, moves):
        super().assign(moves)

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    @set_origin_consignment('done')
    def do(cls, moves):
        super().do(moves)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    @unset_origin_consignment('cancelled')
    def cancel(cls, moves):
        super().cancel(moves)

    @classmethod
    def copy(cls, moves, default=None):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')

        default = default.copy() if default is not None else {}
        consigment_moves = {
            m.id for m in moves if isinstance(m.origin, InvoiceLine)}

        def consigment_moves_cleared(name, default):
            default = default.copy()

            def default_value(data):
                if data['id'] in consigment_moves:
                    return None
                elif name in default:
                    if callable(default[name]):
                        return default[name](data)
                    else:
                        return default[name]
                else:
                    return data.get(name)
            return default_value

        default['origin'] = consigment_moves_cleared('origin', default)
        default['unit_price'] = consigment_moves_cleared('unit_price', default)
        default['currency'] = consigment_moves_cleared('currency', default)

        moves = super().copy(moves, default=default)
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
        super().__setup__()
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
        return super().on_change_with_planned_start_date(
            pattern=pattern)


class Inventory(metaclass=PoolMeta):
    __name__ = 'stock.inventory'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.location.domain = ['OR',
            cls.location.domain,
            ('type', '=', 'supplier'),
            ]


class OrderPoint(metaclass=PoolMeta):
    __name__ = 'stock.order_point'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.provisioning_location.domain = ['OR',
            cls.provisioning_location.domain,
            ('type', '=', 'supplier'),
            ]
