#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import datetime
from decimal import Decimal

from trytond.model import Model, ModelView, fields
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateAction, Button


class Configuration(Model):
    _name = 'production.configuration'

    supply_period = fields.Property(fields.Numeric('Supply Period',
            digits=(16, 0), help='In number of days', required=True))

    def default_supply_period(self):
        return Decimal(0)

Configuration()


class Production(Model):
    _name = 'production'

    def generate_requests(self, clean=True):
        """
        For each product compute the production request that must be created
        today to meet product outputs.

        If clean is set, it will remove all previous requests.
        """
        pool = Pool()
        order_point_obj = pool.get('stock.order_point')
        product_obj = pool.get('product.product')
        location_obj = pool.get('stock.location')
        date_obj = pool.get('ir.date')
        user_obj = pool.get('res.user')
        company = user_obj.browse(Transaction().user).company

        if clean:
            req_ids = self.search([
                    ('state', '=', 'request'),
                    ])
            self.delete(req_ids)

        # fetch warehouse
        warehouse_ids = location_obj.search([
                ('type', '=', 'warehouse'),
                ])
        warehouses = location_obj.browse(warehouse_ids)
        # fetch order points
        order_point_ids = order_point_obj.search([
                ('type', '=', 'production'),
                ])
        # index them by product
        product2ops = {}
        for order_point in order_point_obj.browse(order_point_ids):
            product2ops[
                (order_point.warehouse_location.id, order_point.product.id)
                ] = order_point

        # fetch goods
        product_ids = product_obj.search([
                ('type', '=', 'goods'),
                ('consumable', '=', False),
                ('purchasable', '=', False),
                ])
        products = product_obj.browse(product_ids)

        # compute requests
        cursor = Transaction().cursor
        today = date_obj.today()
        requests = []
        for i in range(0, len(products), cursor.IN_MAX):
            product_ids = [p.id for p in products[i:i + cursor.IN_MAX]]
            with Transaction().set_context(forecast=True,
                    stock_date_end=today):
                pbl = product_obj.products_by_location(warehouse_ids,
                    product_ids, with_childs=True, skip_zero=False)

            # order product by supply period
            products_period = sorted([(product_obj.get_supply_period(p), p)
                    for p in products[i:i + cursor.IN_MAX]])

            for warehouse in warehouses:
                quantities = dict((x, pbl.pop((warehouse.id, x)))
                    for x in product_ids)
                shortages = self.get_shortage(warehouse.id, product_ids, today,
                    quantities, products_period, product2ops)

                for product in products[i:i + cursor.IN_MAX]:
                    for date, quantity in shortages[product.id]:
                        req_values = self.compute_request(product, warehouse,
                            quantity, date, company)
                        req_id = self.create(req_values)
                        self.set_moves(self.browse(req_id))
                        requests.append(req_id)
        if requests:
            self.generate_requests(clean=False)
        return requests

    def compute_request(self, product, warehouse, quantity, date, company):
        """
        Return the value of the production request.
        """
        pool = Pool()
        date_obj = pool.get('ir.date')
        today = date_obj.today()
        if date <= today:
            date = today
        else:
            date -= datetime.timedelta(1)
        return {
            'planned_date': date,
            'company': company.id,
            'warehouse': warehouse.id,
            'location': warehouse.production_location.id,
            'product': product.id,
            'bom': product.boms[0].bom.id if product.boms else None,
            'uom': product.default_uom.id,
            'quantity': quantity,
            'state': 'request',
            }

    def get_shortage(self, location_id, product_ids, date, quantities,
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
        product_obj = pool.get('product.product')

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
                pbl = product_obj.products_by_location([location_id],
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

Production()


class CreateProductionRequestStart(ModelView):
    'Create Production Request'
    _name = 'production.create_request.start'
    _description = __doc__

CreateProductionRequestStart()


class CreateProductionRequest(Wizard):
    'Create Production Request'
    _name = 'production.create_request'

    start = StateView('production.create_request.start',
        'stock_supply_production.production_create_request_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Create', 'create_', 'tryton-ok', default=True),
            ])
    create_ = StateAction('production.act_production_request')

    def do_create_(self, session, action):
        pool = Pool()
        production_obj = pool.get('production')
        production_obj.generate_requests()
        return action, {}

    def transition_create_(self, session):
        return 'end'

CreateProductionRequest()
