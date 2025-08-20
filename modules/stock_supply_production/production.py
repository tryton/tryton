# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from collections import defaultdict

from trytond.model import ModelSQL, ValueMixin, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import TimeDelta
from trytond.tools import grouped_slice
from trytond.transaction import Transaction

supply_period = fields.TimeDelta(
    "Supply Period",
    domain=['OR',
        ('supply_period', '=', None),
        ('supply_period', '>=', TimeDelta()),
        ])


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
        Product = pool.get('product.product')
        Location = pool.get('stock.location')
        Date = pool.get('ir.date')
        User = pool.get('res.user')
        company = User(Transaction().user).company
        if not company:
            return

        if clean:
            reqs = cls.search([
                    ('state', '=', 'request'),
                    ('company', '=', company.id),
                    ('origin', 'like', 'stock.order_point,%'),
                    ])
            if warehouses:
                reqs = [r for r in reqs if r.warehouse in warehouses]
            cls.delete(reqs)

        if warehouses is None:
            # fetch warehouse
            warehouses = Location.search([
                    ('type', '=', 'warehouse'),
                    ])
        warehouse_ids = [w.id for w in warehouses]

        # fetch goods
        products = Product.search([
                ('type', '=', 'goods'),
                ('consumable', '=', False),
                ('producible', '=', True),
                ])
        # compute requests
        today = Date.today()

        # aggregate product by supply period
        date2products = defaultdict(list)
        for product in products:
            min_date = today
            max_date = today + product.get_supply_period()
            date2products[min_date, max_date].append(product)

        requests = []
        for (min_date, max_date), dates_products in date2products.items():
            for sub_products in grouped_slice(products):
                sub_products = Product.browse(sub_products)

                product2ops = {}
                product2ops_other = {}
                for product in sub_products:
                    for order_point in product.order_points:
                        if (order_point.company != company
                                or not order_point.warehouse_location):
                            continue
                        if order_point.type == 'production':
                            dict_ = product2ops
                        else:
                            dict_ = product2ops_other
                        dict_[
                            (order_point.warehouse_location.id,
                                order_point.product.id)
                            ] = order_point

                product_ids = [p.id for p in sub_products]
                with Transaction().set_context(
                        forecast=True,
                        stock_date_end=min_date):
                    pbl = Product.products_by_location(
                        warehouse_ids,
                        with_childs=True,
                        grouping_filter=(product_ids,))

                for warehouse in warehouses:
                    min_date_qties = defaultdict(int,
                        ((x, pbl.pop((warehouse.id, x), 0))
                            for x in product_ids))
                    # Do not compute shortage for product
                    # with different order point
                    product_ids = [
                        p.id for p in sub_products
                        if (warehouse.id, p.id) not in product2ops_other]
                    # Search for shortage between min-max
                    shortages = cls.get_shortage(
                        warehouse.id, product_ids, min_date, max_date,
                        min_date_qties=min_date_qties,
                        order_points=product2ops)

                    for product in sub_products:
                        if product.id not in shortages:
                            continue
                        for date, quantity in shortages[product.id]:
                            order_point = product2ops.get(
                                (warehouse.id, product.id))
                            req = cls.compute_request(product, warehouse,
                                quantity, date, company, order_point)
                            req.set_planned_start_date()
                            requests.append(req)
        cls.save(requests)
        cls.set_moves(requests)
        return requests

    @classmethod
    def compute_request(
            cls, product, warehouse, quantity, date, company,
            order_point=None, bom_pattern=None):
        """
        Return the value of the production request.
        """
        pool = Pool()
        UoM = pool.get('product.uom')
        Date = pool.get('ir.date')
        with Transaction().set_context(company=company.id):
            today = Date.today()
        if date <= today:
            date = today
        else:
            date -= datetime.timedelta(1)
        pbom = product.get_bom(bom_pattern)
        unit = product.default_uom
        if pbom:
            for output in pbom.bom.outputs:
                if output.product == product:
                    # Use output unit to ensure the quantity requested is
                    # not floored to 0
                    unit = output.unit
                    quantity = UoM.compute_qty(
                        product.default_uom, quantity, unit, round=False)
                    break
        quantity = unit.ceil(quantity)
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
            bom=pbom.bom if pbom else None,
            unit=unit,
            quantity=quantity,
            state='request',
            origin=origin,
            )

    @classmethod
    def get_shortage(cls, location_id, product_ids, min_date, max_date,
            min_date_qties, order_points):
        """
        Return for each product a list of dates where the stock quantity is
        less than the minimal quantity and the quantity to reach the maximal
        quantity over the period.

        The minimal and maximal quantities come from the order point or are
        zero.

        min_date_qty is the quantities for each product at the min date.
        order_points is a dictionary that links products to order points.
        """
        pool = Pool()
        Product = pool.get('product.product')

        shortages = defaultdict(list)
        min_quantities = defaultdict(float)
        target_quantities = defaultdict(float)
        for product_id in product_ids:
            order_point = order_points.get((location_id, product_id))
            if order_point:
                min_quantities[product_id] = order_point.min_quantity
                target_quantities[product_id] = order_point.target_quantity

        with Transaction().set_context(
                forecast=True,
                stock_date_start=min_date,
                stock_date_end=max_date):
            pbl = Product.products_by_location(
                [location_id],
                with_childs=True,
                grouping=('date', 'product'),
                grouping_filter=(None, product_ids))
        pbl_dates = defaultdict(dict)
        for key, qty in pbl.items():
            date, product_id = key[1:]
            pbl_dates[date][product_id] = qty

        current_date = min_date
        current_qties = min_date_qties.copy()
        products_to_check = product_ids.copy()
        while (current_date < max_date) or (current_date == min_date):
            for product_id in products_to_check:
                current_qty = current_qties[product_id]
                min_quantity = min_quantities[product_id]
                if min_quantity is not None and current_qty < min_quantity:
                    target_quantity = target_quantities[product_id]
                    quantity = target_quantity - current_qty
                    shortages[product_id].append((current_date, quantity))
                    current_qties[product_id] += quantity

            if current_date == datetime.date.max:
                break
            current_date += datetime.timedelta(1)

            pbl = pbl_dates[current_date]
            products_to_check.clear()
            for product_id, qty in pbl.items():
                current_qties[product_id] += qty
                products_to_check.append(product_id)

        return shortages
