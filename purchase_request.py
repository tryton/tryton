# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import operator
from collections import defaultdict

from trytond.model import ModelView, fields
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta
from trytond.tools import grouped_slice

__all__ = ['PurchaseRequest', 'PurchaseConfiguration',
    'CreatePurchaseRequestStart', 'CreatePurchaseRequest',
    ]


class PurchaseConfiguration:
    __metaclass__ = PoolMeta
    __name__ = 'purchase.configuration'
    supply_period = fields.Property(fields.Integer('Supply Period',
            help='In number of days', required=True))


class PurchaseRequest:
    'Purchase Request'
    __name__ = 'purchase.request'
    __metaclass__ = PoolMeta

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        sql_table = cls.__table__()
        super(PurchaseRequest, cls).__register__(module_name)

        # Migration from 2.0: empty order point origin is -1 instead of 0
        cursor.execute(*sql_table.update(
                columns=[sql_table.origin],
                values=['stock.order_point,-1'],
                where=sql_table.origin == 'stock.order_point,0'))

    @classmethod
    def _get_origin(cls):
        origins = super(PurchaseRequest, cls)._get_origin()
        return origins | {'stock.order_point'}

    @classmethod
    def generate_requests(cls, products=None, warehouses=None):
        """
        For each product compute the purchase request that must be
        created today to meet product outputs.

        If products is specified it will compute the purchase requests
        for the selected products.

        If warehouses is specified it will compute the purchase request
        necessary for the selected warehouses.
        """
        pool = Pool()
        OrderPoint = pool.get('stock.order_point')
        Product = pool.get('product.product')
        Location = pool.get('stock.location')
        User = pool.get('res.user')
        company = User(Transaction().user).company

        if warehouses is None:
            # fetch warehouses:
            warehouses = Location.search([
                    ('type', '=', 'warehouse'),
                    ])
        warehouse_ids = [w.id for w in warehouses]
        # fetch order points
        order_points = OrderPoint.search([
            ('type', '=', 'purchase'),
            ('company', '=', company.id if company else None),
            ])
        # index them by product
        product2ops = {}
        for order_point in order_points:
            product2ops[
                (order_point.warehouse_location.id, order_point.product.id)
                ] = order_point

        if products is None:
            # fetch goods and assets
            # ordered by ids to speedup reduce_ids in products_by_location
            products = Product.search([
                    ('type', 'in', ['goods', 'assets']),
                    ('consumable', '=', False),
                    ('purchasable', '=', True),
                    ], order=[('id', 'ASC')])
        product_ids = [p.id for p in products]
        # aggregate product by minimum supply date
        date2products = {}
        for product in products:
            min_date, max_date = cls.get_supply_dates(product)
            date2products.setdefault((min_date, max_date), []).append(product)

        # compute requests
        new_requests = []
        for dates, dates_products in date2products.iteritems():
            min_date, max_date = dates
            for sub_products in grouped_slice(dates_products):
                sub_products = list(sub_products)
                product_ids = [p.id for p in sub_products]
                with Transaction().set_context(forecast=True,
                        stock_date_end=min_date or datetime.date.max):
                    pbl = Product.products_by_location(warehouse_ids,
                        product_ids, with_childs=True)
                for warehouse_id in warehouse_ids:
                    min_date_qties = defaultdict(lambda: 0,
                        ((x, pbl.pop((warehouse_id, x), 0))
                            for x in product_ids))
                    # Search for shortage between min-max
                    shortages = cls.get_shortage(warehouse_id, product_ids,
                        min_date, max_date, min_date_qties=min_date_qties,
                        order_points=product2ops)

                    for product in sub_products:
                        shortage_date, product_quantity = shortages[product.id]
                        if shortage_date is None or product_quantity is None:
                            continue
                        order_point = product2ops.get(
                            (warehouse_id, product.id))
                        # generate request values
                        request = cls.compute_request(product,
                            warehouse_id, shortage_date, product_quantity,
                            company, order_point)
                        new_requests.append(request)

        # delete purchase requests without a purchase line
        products = set(products)
        reqs = cls.search([
                ('purchase_line', '=', None),
                ('origin', 'like', 'stock.order_point,%'),
                ])
        reqs = [r for r in reqs if r.product in products]
        cls.delete(reqs)
        new_requests = cls.compare_requests(new_requests)

        cls.create_requests(new_requests)

    @classmethod
    def create_requests(cls, new_requests):
        to_save = []
        for new_req in new_requests:
            if new_req.supply_date == datetime.date.max:
                new_req.supply_date = None
            if new_req.computed_quantity > 0:
                to_save.append(new_req)
        cls.save(to_save)

    @classmethod
    def compare_requests(cls, new_requests):
        """
        Compare new_requests with already existing request to avoid
        to re-create existing requests.
        """
        pool = Pool()
        Uom = pool.get('product.uom')
        Request = pool.get('purchase.request')

        requests = Request.search([
                ('purchase_line.moves', '=', None),
                ('purchase_line.purchase.state', '!=', 'cancel'),
                ('origin', 'like', 'stock.order_point,%'),
                ])
        # Fetch data from existing requests
        existing_req = {}
        for request in requests:
            pline = request.purchase_line
            # Skip incoherent request
            if (request.product != pline.product
                    or request.warehouse != pline.purchase.warehouse):
                continue
            # Take smallest amount between request and purchase line
            pline_qty = Uom.compute_qty(pline.unit, pline.quantity,
                pline.product.default_uom, round=False)
            quantity = min(request.computed_quantity, pline_qty)

            existing_req.setdefault(
                (request.product.id, request.warehouse.id),
                []).append({
                        'supply_date': (
                            request.supply_date or datetime.date.max),
                        'quantity': quantity,
                        })

        for i in existing_req.itervalues():
            i.sort(key=lambda r: r['supply_date'])

        # Update new requests to take existing requests into account
        new_requests.sort(key=operator.attrgetter('supply_date'))
        for new_req in new_requests:
            for old_req in existing_req.get(
                    (new_req.product.id, new_req.warehouse.id), []):
                if old_req['supply_date'] <= new_req.supply_date:
                    new_req.computed_quantity = max(0.0,
                        new_req.computed_quantity - old_req['quantity'])
                    new_req.quantity = Uom.compute_qty(
                        new_req.product.default_uom, new_req.computed_quantity,
                        new_req.uom)
                    old_req['quantity'] = max(0.0,
                        old_req['quantity'] - new_req.computed_quantity)
                else:
                    break

        return new_requests

    @classmethod
    def get_supply_dates(cls, product):
        """
        Return the minimal interval of earliest supply dates for a product.
        """
        Date = Pool().get('ir.date')

        min_date = None
        max_date = None
        today = Date.today()

        for product_supplier in product.product_suppliers:
            supply_date = product_supplier.compute_supply_date(date=today)
            next_day = today + datetime.timedelta(
                product_supplier.get_supply_period())
            next_supply_date = product_supplier.compute_supply_date(
                date=next_day)
            if (not min_date) or supply_date < min_date:
                min_date = supply_date
            if (not max_date):
                max_date = next_supply_date
            if supply_date > min_date and supply_date < max_date:
                max_date = supply_date
            if next_supply_date < max_date:
                max_date = next_supply_date

        if not min_date:
            min_date = datetime.date.max
            max_date = datetime.date.max

        return (min_date, max_date)

    @classmethod
    def compute_request(cls, product, location_id, shortage_date,
            product_quantity, company, order_point=None):
        """
        Return the value of the purchase request which will answer to
        the needed quantity at the given date. I.e: the latest
        purchase date, the expected supply date and the prefered
        supplier.
        """
        pool = Pool()
        Uom = pool.get('product.uom')
        Request = pool.get('purchase.request')

        supplier, purchase_date = cls.find_best_supplier(product,
            shortage_date)

        max_quantity = order_point and order_point.max_quantity or 0.0
        computed_quantity = max_quantity - product_quantity
        quantity = Uom.compute_qty(product.default_uom, computed_quantity,
            product.purchase_uom or product.default_uom)

        if order_point:
            origin = 'stock.order_point,%s' % order_point.id
        else:
            origin = 'stock.order_point,-1'
        return Request(product=product,
            party=supplier and supplier or None,
            quantity=quantity,
            uom=product.purchase_uom or product.default_uom,
            computed_quantity=computed_quantity,
            computed_uom=product.default_uom,
            purchase_date=purchase_date,
            supply_date=shortage_date,
            stock_level=product_quantity,
            company=company,
            warehouse=location_id,
            origin=origin,
            )

    @classmethod
    def get_shortage(cls, location_id, product_ids, min_date, max_date,
            min_date_qties, order_points):
        """
        Return for each product the first date between min_date and max_date
        where the stock quantity is less than the minimal quantity and the
        smallest stock quantity in the interval or None if there is no date
        where stock quantity is less than the minimal quantity.

        The minimal quantity comes from the order point or is zero.

        min_date_qty is the quantities for each products at the min_date.
        order_points is a dictionary that links products to order point.
        """
        Product = Pool().get('product.product')

        res_dates = {}
        res_qties = {}

        min_quantities = {}
        for product_id in product_ids:
            order_point = order_points.get((location_id, product_id))
            if order_point:
                min_quantities[product_id] = order_point.min_quantity
            else:
                min_quantities[product_id] = 0.0

        current_date = min_date
        current_qties = min_date_qties.copy()
        while (current_date < max_date) or (current_date == min_date):
            for product_id in product_ids:
                current_qty = current_qties[product_id]
                min_quantity = min_quantities[product_id]
                res_qty = res_qties.get(product_id)
                res_date = res_dates.get(product_id)
                if current_qty < min_quantity:
                    if not res_date:
                        res_dates[product_id] = current_date
                    if (not res_qty) or (current_qty < res_qty):
                        res_qties[product_id] = current_qty

            if current_date == datetime.date.max:
                break
            current_date += datetime.timedelta(1)

            # Update current quantities with next moves
            with Transaction().set_context(forecast=True,
                    stock_date_start=current_date,
                    stock_date_end=current_date):
                pbl = Product.products_by_location([location_id],
                    product_ids, with_childs=True)
            for key, qty in pbl.iteritems():
                _, product_id = key
                current_qties[product_id] += qty

        return dict((x, (res_dates.get(x), res_qties.get(x)))
            for x in product_ids)


class CreatePurchaseRequestStart(ModelView):
    'Create Purchase Request'
    __name__ = 'purchase.request.create.start'


class CreatePurchaseRequest(Wizard):
    'Create Purchase Requests'
    __name__ = 'purchase.request.create'
    start = StateView('purchase.request.create.start',
        'stock_supply.purchase_request_create_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Create', 'create_', 'tryton-ok', default=True),
            ])
    create_ = StateAction('purchase_request.act_purchase_request_form')

    @classmethod
    def __setup__(cls):
        super(CreatePurchaseRequest, cls).__setup__()
        cls._error_messages.update({
                'late_supplier_moves': 'There are some late supplier moves.',
                })

    @property
    def _requests_parameters(self):
        return {}

    def do_create_(self, action):
        pool = Pool()
        PurchaseRequest = pool.get('purchase.request')
        Move = pool.get('stock.move')
        Date = pool.get('ir.date')
        today = Date.today()
        if Move.search([
                    ('from_location.type', '=', 'supplier'),
                    ('to_location.type', '=', 'storage'),
                    ('state', '=', 'draft'),
                    ('planned_date', '<', today),
                    ], order=[]):
            self.raise_user_warning('%s@%s' % (self.__name__, today),
                'late_supplier_moves')
        PurchaseRequest.generate_requests(**self._requests_parameters)
        return action, {}

    def transition_create_(self):
        return 'end'
