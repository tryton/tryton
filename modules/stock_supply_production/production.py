# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from collections import defaultdict

from trytond.model import ModelSQL, ValueMixin, fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.tools import grouped_slice

supply_period = fields.TimeDelta("Supply Period")


class Configuration(metaclass=PoolMeta):
    __name__ = 'production.configuration'
    supply_period = fields.MultiValue(supply_period)


class ConfigurationSupplyPeriod(ModelSQL, ValueMixin):
    "Production Configuration Supply Period"
    __name__ = 'production.configuration.supply_period'
    supply_period = supply_period


class Production(metaclass=PoolMeta):
    __name__ = 'production'

    @classmethod
    def _get_origin(cls):
        origins = super()._get_origin()
        return origins | {'stock.order_point'}

    @classmethod
    def generate_requests(cls, clean=True, warehouses=None):
        """
        For each product compute the production request that must be created
        today to meet product outputs.

        If clean is set, it will remove all previous requests.

        If warehouses is specified it will compute the production requests
        only for the selected warehouses.
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
                    ('origin', 'like', 'stock.order_point,%'),
                    ])
            cls.delete(reqs)

        if warehouses is None:
            # fetch warehouse
            warehouses = Location.search([
                    ('type', '=', 'warehouse'),
                    ])
        warehouse_ids = [w.id for w in warehouses]
        # fetch order points
        order_points = OrderPoint.search([
                ('warehouse_location', '!=', None),
                ('company', '=', company.id if company else None),
                ])
        # index them by product
        product2ops = {}
        product2ops_other = {}
        for order_point in order_points:
            if order_point.type == 'production':
                dict_ = product2ops
            else:
                dict_ = product2ops_other
            dict_[
                (order_point.warehouse_location.id, order_point.product.id)
                ] = order_point

        # fetch goods
        products = Product.search([
                ('type', '=', 'goods'),
                ('consumable', '=', False),
                ('producible', '=', True),
                ])
        # compute requests
        today = Date.today()
        requests = []
        for sub_products in grouped_slice(products):
            sub_products = list(sub_products)
            product_ids = [p.id for p in sub_products]
            with Transaction().set_context(forecast=True,
                    stock_date_end=today):
                pbl = Product.products_by_location(
                    warehouse_ids,
                    with_childs=True,
                    grouping_filter=(product_ids,))

            # order product by supply period
            products_period = sorted((p.get_supply_period(), p)
                for p in sub_products)

            for warehouse in warehouses:
                quantities = defaultdict(int,
                    ((x, pbl.pop((warehouse.id, x), 0)) for x in product_ids))
                # Do not compute shortage for product
                # with different order point
                product_ids = [
                    p.id for p in sub_products
                    if (warehouse.id, p.id) not in product2ops_other]
                shortages = cls.get_shortage(warehouse.id, product_ids, today,
                    quantities, products_period, product2ops)

                for product in sub_products:
                    if product.id not in shortages:
                        continue
                    for date, quantity in shortages[product.id]:
                        order_point = product2ops.get(
                            (warehouse.id, product.id))
                        req = cls.compute_request(product, warehouse,
                            quantity, date, company, order_point)
                        req.planned_start_date = (
                            req.on_change_with_planned_start_date())
                        requests.append(req)
        cls.save(requests)
        cls.set_moves(requests)
        return requests

    @classmethod
    def compute_request(
            cls, product, warehouse, quantity, date, company,
            order_point=None):
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
        uom = product.default_uom
        quantity = uom.ceil(quantity)
        if order_point:
            origin = str(order_point)
        else:
            origin = 'stock.order_point,-1'
        return cls(
            planned_date=date,
            company=company,
            warehouse=warehouse,
            location=warehouse.production_location,
            product=product,
            bom=product.boms[0].bom if product.boms else None,
            uom=uom,
            quantity=quantity,
            state='request',
            origin=origin,
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
        target_quantities = {}
        for product_id in product_ids:
            order_point = order_points.get((location_id, product_id))
            if order_point:
                min_quantities[product_id] = order_point.min_quantity
                target_quantities[product_id] = order_point.target_quantity
            else:
                min_quantities[product_id] = 0.0
                target_quantities[product_id] = 0.0
            shortages[product_id] = []

        products_period = products_period[:]
        current_date = date
        current_qties = quantities.copy()
        product_ids = product_ids[:]
        while product_ids:
            for product_id in product_ids:
                current_qty = current_qties[product_id]
                min_quantity = min_quantities[product_id]
                if min_quantity is not None and current_qty < min_quantity:
                    target_quantity = target_quantities[product_id]
                    quantity = target_quantity - current_qty
                    shortages[product_id].append((current_date, quantity))
                    current_qties[product_id] += quantity

            # Remove product with smaller period
            while (products_period
                    and products_period[0][0] <= (current_date - date)):
                _, product = products_period.pop(0)
                try:
                    product_ids.remove(product.id)
                except ValueError:
                    # product may have been already removed on get_shortages
                    pass
            current_date += datetime.timedelta(1)

            # Update current quantities with next moves
            with Transaction().set_context(forecast=True,
                    stock_date_start=current_date,
                    stock_date_end=current_date):
                pbl = Product.products_by_location(
                    [location_id],
                    with_childs=True,
                    grouping_filter=(product_ids,))
            for key, qty in pbl.items():
                _, product_id = key
                current_qties[product_id] += qty

        return shortages
