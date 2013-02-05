#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import datetime
from decimal import Decimal

from trytond.model import ModelView, fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateAction, Button

__all__ = ['Configuration', 'Production',
    'CreateProductionRequestStart', 'CreateProductionRequest']
__metaclass__ = PoolMeta


class Configuration:
    __name__ = 'production.configuration'
    supply_period = fields.Property(fields.Numeric('Supply Period',
            digits=(16, 0), help='In number of days', required=True))

    @staticmethod
    def default_supply_period():
        return Decimal(0)


class Production:
    __name__ = 'production'

    @classmethod
    def generate_requests(cls, clean=True):
        """
        For each product compute the production request that must be created
        today to meet product outputs.

        If clean is set, it will remove all previous requests.
        """
        pool = Pool()
        OrderPoint = pool.get('stock.order_point')
        Product = pool.get('product.product')
        Location = pool.get('stock.location')
        Date = pool.get('ir.date')
        User = pool.get('res.user')
        company = User(Transaction().user).company

        if clean:
            reqs = cls.search([
                    ('state', '=', 'request'),
                    ])
            cls.delete(reqs)

        # fetch warehouse
        warehouses = Location.search([
                ('type', '=', 'warehouse'),
                ])
        warehouse_ids = [w.id for w in warehouses]
        # fetch order points
        order_points = OrderPoint.search([
                ('type', '=', 'production'),
                ])
        # index them by product
        product2ops = {}
        for order_point in order_points:
            product2ops[
                (order_point.warehouse_location.id, order_point.product.id)
                ] = order_point

        # fetch goods
        products = Product.search([
                ('type', '=', 'goods'),
                ('consumable', '=', False),
                ('purchasable', '=', False),
                ])
        # compute requests
        cursor = Transaction().cursor
        today = Date.today()
        requests = []
        for i in range(0, len(products), cursor.IN_MAX):
            product_ids = [p.id for p in products[i:i + cursor.IN_MAX]]
            with Transaction().set_context(forecast=True,
                    stock_date_end=today):
                pbl = Product.products_by_location(warehouse_ids,
                    product_ids, with_childs=True, skip_zero=False)

            # order product by supply period
            products_period = sorted([(p.get_supply_period(), p)
                    for p in products[i:i + cursor.IN_MAX]])

            for warehouse in warehouses:
                quantities = dict((x, pbl.pop((warehouse.id, x)))
                    for x in product_ids)
                shortages = cls.get_shortage(warehouse.id, product_ids, today,
                    quantities, products_period, product2ops)

                for product in products[i:i + cursor.IN_MAX]:
                    for date, quantity in shortages[product.id]:
                        req = cls.compute_request(product, warehouse,
                            quantity, date, company)
                        req.save()
                        req.set_moves()
                        requests.append(req)
        if requests:
            cls.generate_requests(clean=False)
        return requests

    @classmethod
    def compute_request(cls, product, warehouse, quantity, date, company):
        """
        Return the value of the production request.
        """
        pool = Pool()
        Date = pool.get('ir.date')
        today = Date.today()
        if date <= today:
            date = today
        else:
            date -= datetime.timedelta(1)
        return cls(
            planned_date=date,
            company=company,
            warehouse=warehouse,
            location=warehouse.production_location,
            product=product,
            bom=product.boms[0].bom if product.boms else None,
            uom=product.default_uom,
            quantity=quantity,
            state='request',
            )

    @classmethod
    def get_shortage(cls, location_id, product_ids, date, quantities,
            products_period, order_points):
        """
        Return for each product a list of dates where the stock quantity is
        less than the minimal quantity and the quantity to reach the maximal
        quantity over the period.

        The minimal and maximal quantities come from the order point or are
        zero.

        quantities is the quantities for each product at the date.
        products_period is an ordered list of periods and products.
        order_points is a dictionary that links products to order points.
        """
        pool = Pool()
        Product = pool.get('product.product')

        shortages = {}

        min_quantities = {}
        max_quantities = {}
        for product_id in product_ids:
            order_point = order_points.get((location_id, product_id))
            if order_point:
                min_quantities[product_id] = order_point.min_quantity
                max_quantities[product_id] = order_point.max_quantity
            else:
                min_quantities[product_id] = 0.0
                max_quantities[product_id] = 0.0
            shortages[product_id] = []

        products_period = products_period[:]
        current_date = date
        current_qties = quantities.copy()
        product_ids = product_ids[:]
        while product_ids:
            for product_id in product_ids:
                current_qty = current_qties[product_id]
                min_quantity = min_quantities[product_id]
                if current_qty < min_quantity:
                    max_quantity = max_quantities[product_id]
                    quantity = max_quantity - current_qty
                    shortages[product_id].append((current_date, quantity))
                    current_qties[product_id] += quantity

            # Update current quantities
            with Transaction().set_context(stock_date_start=current_date,
                    stock_date_end=current_date):
                pbl = Product.products_by_location([location_id],
                    product_ids, with_childs=True, skip_zero=False)
            for key, qty in pbl.iteritems():
                _, product_id = key
                current_qties[product_id] += qty

            # Remove product with smaller period
            while (products_period
                    and products_period[0][0] <= (current_date - date).days):
                _, product = products_period.pop(0)
                product_ids.remove(product.id)
            current_date += datetime.timedelta(1)

        return shortages


class CreateProductionRequestStart(ModelView):
    'Create Production Request'
    __name__ = 'production.create_request.start'


class CreateProductionRequest(Wizard):
    'Create Production Request'
    __name__ = 'production.create_request'
    start = StateView('production.create_request.start',
        'stock_supply_production.production_create_request_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Create', 'create_', 'tryton-ok', default=True),
            ])
    create_ = StateAction('stock_supply_production.act_production_request')

    def do_create_(self, action):
        pool = Pool()
        Production = pool.get('production')
        Production.generate_requests()
        return action, {}

    def transition_create_(self):
        return 'end'
