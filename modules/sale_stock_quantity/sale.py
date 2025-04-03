# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime
from collections import defaultdict
from itertools import groupby
from operator import attrgetter

from trytond.i18n import gettext
from trytond.model import ModelView, Workflow, fields
from trytond.pool import Pool, PoolMeta
from trytond.tools import grouped_slice, sortable_values
from trytond.transaction import Transaction

from .exceptions import StockQuantityError, StockQuantityWarning


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    @classmethod
    @ModelView.button
    @Workflow.transition('quotation')
    def quote(cls, sales):
        # Check before setting the number
        cls._check_stock_quantity(sales)
        super().quote(sales)

    @classmethod
    @ModelView.button
    @Workflow.transition('confirmed')
    def confirm(cls, sales):
        # Check before queueing the process task
        cls._check_stock_quantity(sales)
        super().confirm(sales)

    @classmethod
    def _check_stock_quantity(cls, sales):
        for sale in sales:
            sale.check_stock_quantity()

    @classmethod
    def _stock_quantity_states(cls):
        return ['quotation', 'confirmed']

    @classmethod
    def _stock_quantity_next_supply_date(cls, product):
        pool = Pool()
        try:
            PurchaseRequest = pool.get('purchase.request')
        except KeyError:
            PurchaseRequest = None

        if (getattr(PurchaseRequest, 'get_supply_dates', None)
                and product.purchasable):
            return PurchaseRequest.get_supply_dates(product)[0]
        else:
            # TODO compute supply date for production
            return datetime.date.max

    def check_stock_quantity(self):
        pool = Pool()
        Product = pool.get('product.product')
        Date = pool.get('ir.date')
        Uom = pool.get('product.uom')
        Group = pool.get('res.group')
        User = pool.get('res.user')
        ModelData = pool.get('ir.model.data')
        Lang = pool.get('ir.lang')
        Line = pool.get('sale.line')
        Warning = pool.get('res.user.warning')

        if not self.warehouse:
            return

        transaction = Transaction()

        def in_group():
            group = Group(ModelData.get_id('sale_stock_quantity',
                    'group_sale_stock_quantity'))
            user_id = transaction.user
            if user_id == 0:
                user_id = transaction.context.get('user', user_id)
            if user_id == 0:
                return True
            user = User(user_id)
            return group in user.groups

        def filter_line(line):
            return (line.warehouse
                and line.product
                and line.product.type == 'goods'
                and not line.product.consumable
                and line.quantity > 0
                # Use getattr as supply_on_sale comes from sale_supply module
                and not getattr(line, 'supply_on_sale', False))

        def get_delta(date, warehouse, products):
            'Compute quantity delta at the date'
            if date in date2delta:
                return date2delta[warehouse][date]

            with transaction.set_context(forecast=True,
                    stock_date_start=date,
                    stock_date_end=date):
                pbl = defaultdict(int)
                for sub_products in grouped_slice(products):
                    sub_product_ids = [p.id for p in sub_products]
                    pbl.update(Product.products_by_location(
                            [warehouse.id],
                            with_childs=True,
                            grouping_filter=(sub_product_ids,)))
            delta = {}
            for key, qty in pbl.items():
                _, product_id = key
                delta[product_id] = qty
            date2delta[warehouse][date] = delta
            return delta
        date2delta = defaultdict(dict)

        def raise_(line_id, message_values):
            if not in_group():
                raise StockQuantityError(
                    gettext('sale_stock_quantity.msg_sale_stock_quantity',
                        **message_values))
            warning_name = 'stock_quantity_warning_%s' % line_id
            if Warning.check(warning_name):
                raise StockQuantityWarning(warning_name,
                    gettext('sale_stock_quantity.msg_sale_stock_quantity',
                        **message_values))

        with Transaction().set_context(company=self.company.id):
            today = Date.today()
        lang = Lang.get()

        lines = filter(filter_line, self.lines)
        lines = list(lines)

        quantities = defaultdict(lambda: defaultdict(int))
        w_getter = attrgetter('warehouse', 'shipping_date')
        w_products = {}
        for (warehouse, shipping_date), w_lines in groupby(
                sorted(lines, key=sortable_values(w_getter)), key=w_getter):
            if shipping_date is None:
                shipping_date = today
            w_products[warehouse] = products = {l.product for l in w_lines}
            with transaction.set_context(
                    locations=[warehouse.id],
                    stock_date_end=shipping_date,
                    stock_assign=True):
                products = Product.browse(products)
            quantities[warehouse].update(
                (p, p.forecast_quantity) for p in products)

            # Remove quantities from other sales
            for sub_products in grouped_slice(products):
                other_lines = Line.search([
                        ('sale.company', '=', self.company.id),
                        ('sale.state', 'in', self._stock_quantity_states()),
                        ('sale.id', '!=', self.id),
                        ('product', 'in', sub_products),
                        ('quantity', '>', 0),
                        ])
                for line in other_lines:
                    if line.warehouse != warehouse:
                        continue
                    if (line.shipping_date
                            and line.shipping_date > shipping_date):
                        continue
                    product = line.product
                    date = line.sale.sale_date or today
                    if date > today:
                        continue
                    quantity = Uom.compute_qty(line.unit, line.quantity,
                        product.default_uom, round=False)
                    quantities[line.warehouse][product] -= quantity

        for line in lines:
            warehouse = line.warehouse
            product = line.product
            quantity = Uom.compute_qty(line.unit, line.quantity,
                product.default_uom, round=False)
            shipping_date = line.shipping_date or today
            next_supply_date = self._stock_quantity_next_supply_date(product)
            message_values = {
                'line': line.rec_name,
                'forecast_quantity': lang.format_number_symbol(
                    quantities[warehouse][product],
                    product.default_uom, product.default_uom.digits),
                'quantity': lang.format_number_symbol(
                    line.quantity, line.unit, line.unit.digits),
                }
            if (quantities[warehouse][product] < quantity
                    and shipping_date < next_supply_date):
                raise_(line.id, message_values)
            # Update quantities if the same product is many times in lines
            quantities[warehouse][product] -= quantity

            # Check other dates until next supply date
            if next_supply_date != datetime.date.max:
                products = w_products[warehouse]
                forecast_quantity = quantities[warehouse][product]
                date = shipping_date + datetime.timedelta(1)
                while date < next_supply_date:
                    delta = get_delta(date, warehouse, products)
                    forecast_quantity += delta.get(product.id, 0)
                    if forecast_quantity < 0:
                        message_values['forecast_quantity'] = forecast_quantity
                        raise_(line.id, message_values)
                    date += datetime.timedelta(1)


class Line(metaclass=PoolMeta):
    __name__ = 'sale.line'

    @fields.depends(methods=['_notify_stock_quantity'])
    def on_change_notify(self):
        notifications = super().on_change_notify()
        notifications.extend(self._notify_stock_quantity())
        return notifications

    @fields.depends(
        'sale_state', 'product', 'quantity', 'unit', 'company',
        'shipping_date', 'sale', '_parent_sale.warehouse')
    def _notify_stock_quantity(self):
        pool = Pool()
        Date = pool.get('ir.date')
        Lang = pool.get('ir.lang')
        Move = pool.get('stock.move')
        Product = pool.get('product.product')
        UoM = pool.get('product.uom')
        lang = Lang.get()
        if (self.sale_state == 'draft'
                and self.sale
                and self.sale.warehouse
                and self.product
                and self.product.type in Move.get_product_types()
                and self.unit
                and self.quantity is not None):
            with Transaction().set_context(
                    company=self.company.id if self.company else None):
                today = Date.today()
            shipping_date = self.shipping_date or today
            locations = [self.sale.warehouse.id]
            with Transaction().set_context(
                    locations=locations,
                    stock_date_end=shipping_date):
                product = Product(self.product.id)
                quantity = UoM.compute_qty(
                    self.unit, self.quantity,
                    product.default_uom, round=False)
                if product.forecast_quantity < quantity:
                    yield ('warning', gettext(
                            'sale_stock_quantity'
                            '.msg_product_forecast_quantity_lower',
                            forecast_quantity=lang.format_number_symbol(
                                product.forecast_quantity, product.default_uom,
                                product.default_uom.digits),
                            product=self.product.rec_name,
                            quantity=lang.format_number_symbol(
                                self.quantity, self.unit,
                                self.unit.digits)))
