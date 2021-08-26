# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
from decimal import Decimal
from functools import wraps

from trytond.model import ModelStorage, ModelView, Workflow, fields
from trytond.pool import Pool
from trytond.pyson import Eval


def get_shipments_returns(model_name):
    def _get_shipments_returns(func):
        @wraps(func)
        def wrapper(self, name):
            pool = Pool()
            Model = pool.get(model_name)
            shipments = set(func(self, name))
            for line in self.lines:
                for component in line.components:
                    for move in component.moves:
                        if isinstance(move.shipment, Model):
                            shipments.add(move.shipment.id)
            return list(shipments)
        return wrapper
    return _get_shipments_returns


def search_shipments_returns(model_name):
    def _search_shipments_returns(func):
        @wraps(func)
        def wrapper(cls, name, clause):
            domain = func(cls, name, clause)
            nested = clause[0].lstrip(name)
            if nested:
                return ['OR',
                    domain,
                    ('lines.components.moves.shipment' + nested,)
                    + tuple(clause[1:3]) + (model_name,) + tuple(clause[3:]),
                    ]
            else:
                if isinstance(clause[2], str):
                    target = 'rec_name'
                else:
                    target = 'id'
                return ['OR',
                    domain,
                    ('lines.components.moves.shipment.' + target,)
                    + tuple(clause[1:3]) + (model_name,)]
        return wrapper
    return _search_shipments_returns


def order_mixin(prefix):
    class OrderMixin(ModelStorage):

        @classmethod
        def copy(cls, records, default=None):
            pool = Pool()
            Line = pool.get(prefix + '.line')
            if default is None:
                default = {}
            else:
                default = default.copy()
            default.setdefault(
                'lines.component_parent',
                lambda data: data['component_parent'])
            records = super().copy(records, default=default)
            lines = []
            for record in records:
                for line in record.lines:
                    if line.component_parent:
                        lines.append(line)
            Line.delete(lines)
            return records

        @classmethod
        @ModelView.button
        @Workflow.transition('draft')
        def draft(cls, records):
            pool = Pool()
            Line = pool.get(prefix + '.line')
            to_delete = []
            to_save = []
            for record in records:
                for line in record.lines:
                    if line.component_parent:
                        to_delete.append(line)
                    elif line.components:
                        line.components = None
                        to_save.append(line)
            Line.save(to_save)
            super().draft(records)
            Line.delete(to_delete)

        @classmethod
        @ModelView.button
        @Workflow.transition('quotation')
        def quote(cls, records):
            pool = Pool()
            Line = pool.get(prefix + '.line')
            removed = []
            for record in records:
                removed.extend(record.set_components())
            Line.delete(removed)
            cls.save(records)
            super().quote(records)

        def set_components(self):
            pool = Pool()
            Component = pool.get(prefix + '.line.component')
            removed = []
            lines = []
            sequence = 0
            for line in self.lines:
                if line.component_parent:
                    removed.append(line)
                    continue
                sequence += 1
                line.sequence = sequence
                lines.append(line)
                if line.product and line.product.components_used:
                    if line.product.type == 'kit':
                        components = []
                        for component in line.product.components_used:
                            components.append(line.get_component(component))
                        Component.set_price_ratio(components)
                        line.components = components
                    else:
                        for component in line.product.components_used:
                            order_line = line.get_component_order_line(
                                component)
                            sequence += 1
                            order_line.sequence = sequence
                            order_line.component_parent = line
                            lines.append(order_line)
            self.lines = lines
            return removed
    return OrderMixin


def order_line_mixin(prefix):
    class OrderLineMixin(ModelStorage, ModelView):

        component_parent = fields.Many2One(
            prefix + '.line', "Component Parent",
            readonly=True,
            states={
                'invisible': ~Eval('component_parent'),
                })
        component_children = fields.One2Many(
            prefix + '.line', 'component_parent', "Component Children",
            readonly=True,
            states={
                'invisible': ~Eval('component_children'),
                })

        components = fields.One2Many(
            prefix + '.line.component', 'line', "Components", readonly=True,
            states={
                'invisible': ~Eval('components', []),
                })

        @classmethod
        def view_attributes(cls):
            return super().view_attributes() + [
                ('//page[@id="components"]', 'states', {
                        'invisible': (
                            ~Eval('components', [])
                            & ~Eval('component_children', [])),
                        }),
                ]

        @classmethod
        def copy(cls, lines, default=None):
            if default is None:
                default = {}
            else:
                default = default.copy()
            default.setdefault('component_parent')
            default.setdefault('component_children')
            default.setdefault('components')
            return super().copy(lines, default=default)

        def get_component(self, component, **kwargs):
            pool = Pool()
            Component = pool.get(prefix + '.line.component')
            line = component.get_line(
                Component, self.quantity, self.unit, **kwargs)
            line.fixed = component.fixed
            if not line.fixed:
                line.quantity_ratio = component.quantity
            return line

        def get_component_order_line(self, component, **values):
            Line = self.__class__
            line = component.get_line(
                Line, self.quantity, self.unit, **values)
            line.type = 'line'
            line.on_change_product()
            return line

        def get_move(self, type_):
            move = super().get_move(type_)
            if self.components:
                move = None
            return move

        def get_move_done(self, name):
            done = super().get_move_done(name)
            if self.components:
                done = all(c.move_done for c in self.components)
            return done

        def get_move_exception(self, name):
            exception = super().get_move_exception(name)
            if self.components:
                exception = any(c.move_exception for c in self.components)
            return exception

        def _get_invoice_line_quantity(self):
            quantity = super()._get_invoice_line_quantity()
            if (getattr(self, prefix).invoice_method == 'shipment'
                    and self.components):
                ratio = min(c.get_moved_ratio() for c in self.components)
                quantity = self.unit.round(self.quantity * ratio)
            return quantity
    return OrderLineMixin


def order_line_component_mixin(prefix):
    class OrderLineComponentMixin(ModelStorage):

        line = fields.Many2One(
            prefix + '.line', "Line", required=True, ondelete='CASCADE',
            domain=[
                ('product.type', '=', 'kit'),
                ])
        moves = fields.One2Many('stock.move', 'origin', 'Moves', readonly=True)
        moves_ignored = fields.Many2Many(
            prefix + '.line.component-ignored-stock.move',
            'component', 'move', "Ignored Moves", readonly=True)
        moves_recreated = fields.Many2Many(
            prefix + '.line.component-recreated-stock.move',
            'component', 'move', "Recreated Moves", readonly=True)
        move_done = fields.Function(
            fields.Boolean('Moves Done'), 'get_move_done')
        move_exception = fields.Function(
            fields.Boolean('Moves Exception'), 'get_move_exception')
        quantity_ratio = fields.Float(
            "Quantity Ratio", readonly=True,
            states={
                'required': ~Eval('fixed', False),
                },
            depends=['fixed'])
        price_ratio = fields.Numeric(
            "Price Ratio", readonly=True, required=True)

        @classmethod
        def __setup__(cls):
            super().__setup__()
            cls.__access__.add('line')

        @fields.depends('line', '_parent_line.product')
        def on_change_with_parent_type(self, name=None):
            if self.line and self.line.product:
                return self.line.product.type

        @classmethod
        def set_price_ratio(cls, components):
            "Set price ratio between components"
            pool = Pool()
            Uom = pool.get('product.uom')
            list_prices = defaultdict(Decimal)
            sum_ = 0
            for component in components:
                product = component.product
                list_price = Uom.compute_price(
                    product.default_uom, product.list_price,
                    component.unit) * Decimal(str(component.quantity))
                list_prices[component] = list_price
                sum_ += list_price

            for component in components:
                if sum_:
                    ratio = list_prices[component] / sum_
                else:
                    ratio = 1 / len(components)
                component.price_ratio = ratio

        def get_move(self, type_):
            raise NotImplementedError

        def _get_shipped_quantity(self, shipment_type):
            'Return the quantity already shipped'
            pool = Pool()
            Uom = pool.get('product.uom')

            quantity = 0
            skips = set(self.moves_recreated)
            for move in self.moves:
                if move not in skips:
                    quantity += Uom.compute_qty(
                        move.uom, move.quantity, self.unit)
            return quantity

        @property
        def _move_remaining_quantity(self):
            "Compute the remaining quantity to ship"
            pool = Pool()
            Uom = pool.get('product.uom')
            ignored = set(self.moves_ignored)
            quantity = abs(self.quantity)
            for move in self.moves:
                if move.state == 'done' or move in ignored:
                    quantity -= Uom.compute_qty(
                        move.uom, move.quantity, self.unit)
            return quantity

        def get_move_done(self, name):
            quantity = self._move_remaining_quantity
            if quantity is None:
                return True
            else:
                return self.unit.round(quantity) <= 0

        def get_move_exception(self, name):
            skips = set(self.moves_ignored)
            skips.update(self.moves_recreated)
            for move in self.moves:
                if move.state == 'cancelled' and move not in skips:
                    return True
            return False

        def get_moved_ratio(self):
            pool = Pool()
            Uom = pool.get('product.uom')

            quantity = 0
            for move in self.moves:
                if move.state != 'done':
                    continue
                qty = Uom.compute_qty(move.uom, move.quantity, self.unit)
                dest_type = self.line.to_location.type
                if (move.to_location.type == dest_type
                        and move.from_location.type != dest_type):
                    quantity += qty
                elif (move.from_location.type == dest_type
                        and move.to_location.type != dest_type):
                    quantity -= qty
            if self.quantity < 0:
                quantity *= -1
            return quantity / self.quantity

        def get_rec_name(self, name):
            return super().get_rec_name(name) + (
                ' @ %s' % self.line.rec_name)

        @classmethod
        def search_rec_name(cls, name, clause):
            return super().search_rec_name(name, clause) + [
                ('line.rec_name',) + tuple(clause[1:]),
                ]
    return OrderLineComponentMixin


def handle_shipment_exception_mixin(prefix):
    class HandleShipmentExceptionMixin:
        def default_ask(self, fields):
            values = super().default_ask(fields)
            moves = values['domain_moves']
            for line in self.record.lines:
                for component in line.components:
                    skips = set(component.moves_ignored)
                    skips.update(component.moves_recreated)
                    for move in component.moves:
                        if move.state == 'cancelled' and move not in skips:
                            moves.append(move.id)
            return values

        def transition_handle(self):
            pool = Pool()
            Component = pool.get(prefix + '.line.component')

            result = super().transition_handle()

            to_write = []
            for line in self.record.lines:
                for component in line.components:
                    moves_ignored = []
                    moves_recreated = []
                    skips = set(component.moves_ignored)
                    skips.update(component.moves_recreated)
                    for move in component.moves:
                        if move not in self.ask.domain_moves or move in skips:
                            continue
                        if move in self.ask.recreate_moves:
                            moves_recreated.append(move.id)
                        else:
                            moves_ignored.append(move.id)

                    if moves_ignored or moves_recreated:
                        to_write.append([component])
                        to_write.append({
                                'moves_ignored': [('add', moves_ignored)],
                                'moves_recreated': [('add', moves_recreated)],
                                })
            if to_write:
                Component.write(*to_write)
            return result
    return HandleShipmentExceptionMixin


class AmendmentLineMixin:

    def _apply_line(self, record, line):
        pool = Pool()
        Uom = pool.get('product.uom')
        super()._apply_line(record, line)
        if line.components:
            quantity = Uom.compute_qty(
                line.unit, line.quantity,
                line.product.default_uom, round=False)
            for component in line.components:
                if not component.fixed:
                    component.quantity = component.unit.round(
                        quantity * component.quantity_ratio)
            line.components = line.components
