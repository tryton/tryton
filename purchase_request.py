# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import operator
from itertools import groupby
from functools import partial
from decimal import Decimal
from collections import defaultdict
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard, StateView, StateAction, StateTransition, \
    Button
from trytond.pyson import If, In, Eval
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.tools import grouped_slice

__all__ = ['PurchaseRequest',
    'CreatePurchaseRequestStart', 'CreatePurchaseRequest',
    'CreatePurchaseAskParty', 'CreatePurchase']

STATES = {
    'readonly': Eval('state') != 'draft',
    }
DEPENDS = ['state']


class PurchaseRequest(ModelSQL, ModelView):
    'Purchase Request'
    __name__ = 'purchase.request'
    product = fields.Many2One('product.product', 'Product', required=True,
        select=True, readonly=True, domain=[('purchasable', '=', True)])
    party = fields.Many2One('party.party', 'Party', select=True, states=STATES,
        depends=DEPENDS)
    quantity = fields.Float('Quantity', required=True, states=STATES,
        digits=(16, Eval('uom_digits', 2)), depends=DEPENDS + ['uom_digits'])
    uom = fields.Many2One('product.uom', 'UOM', required=True, select=True,
        states=STATES, depends=DEPENDS)
    uom_digits = fields.Function(fields.Integer('UOM Digits'),
        'on_change_with_uom_digits')
    computed_quantity = fields.Float('Computed Quantity', readonly=True,
        digits=(16, Eval('computed_uom_digits', 2)),
        depends=['computed_uom_digits'])
    computed_uom = fields.Many2One('product.uom', 'Computed UOM',
        readonly=True)
    computed_uom_digits = fields.Function(fields.Integer(
            'Computed UOM Digits'),
        'on_change_with_computed_uom_digits')
    purchase_date = fields.Date('Best Purchase Date', readonly=True)
    supply_date = fields.Date('Expected Supply Date', readonly=True)
    default_uom_digits = fields.Function(fields.Integer('Default UOM Digits'),
        'on_change_with_default_uom_digits')
    stock_level = fields.Float('Stock at Supply Date', readonly=True,
        digits=(16, Eval('default_uom_digits', 2)),
        depends=['default_uom_digits'])
    warehouse = fields.Many2One(
        'stock.location', "Warehouse",
        states={
            'required': Eval('warehouse_required', False),
            },
        domain=[('type', '=', 'warehouse')], depends=['warehouse_required'],
        readonly=True)
    warehouse_required = fields.Function(fields.Boolean('Warehouse Required'),
        'get_warehouse_required')
    purchase_line = fields.Many2One('purchase.line', 'Purchase Line',
        readonly=True)
    purchase = fields.Function(fields.Many2One('purchase.purchase',
        'Purchase'), 'get_purchase')
    company = fields.Many2One('company.company', 'Company', required=True,
            readonly=True, domain=[
                ('id', If(In('company', Eval('context', {})), '=', '!='),
                    Eval('context', {}).get('company', -1)),
            ])
    origin = fields.Reference('Origin', selection='get_origin', readonly=True,
            required=True)
    state = fields.Function(fields.Selection([
        ('purchased', 'Purchased'),
        ('done', 'Done'),
        ('draft', 'Draft'),
        ('cancel', 'Cancel'),
        ], 'State'), 'get_state')

    @classmethod
    def __setup__(cls):
        super(PurchaseRequest, cls).__setup__()
        cls._order[0] = ('id', 'DESC')
        cls._error_messages.update({
                'create_request': ('Purchase requests are only created '
                    'by the system.'),
                'delete_purchase_line': ('You can not delete purchased '
                    'request.'),
                })
        cls._sql_constraints += [
            ('check_purchase_request_quantity', 'CHECK(quantity > 0)',
                'The requested quantity must be greater than 0'),
            ]

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor
        sql_table = cls.__table__()
        super(PurchaseRequest, cls).__register__(module_name)

        # Migration from 2.0: empty order point origin is -1 instead of 0
        cursor.execute(*sql_table.update(
                columns=[sql_table.origin],
                values=['stock.order_point,-1'],
                where=sql_table.origin == 'stock.order_point,0'))

    def get_rec_name(self, name):
        if self.warehouse:
            return "%s@%s" % (self.product.name, self.warehouse.name)
        else:
            return self.product.name

    @classmethod
    def search_rec_name(cls, name, clause):
        res = []
        names = clause[2].split('@', 1)
        res.append(('product.template.name', clause[1], names[0]))
        if len(names) != 1 and names[1]:
            res.append(('warehouse', clause[1], names[1]))
        return res

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    def get_purchase(self, name):
        if self.purchase_line:
            return self.purchase_line.purchase.id

    @property
    def currency(self):
        return self.company.currency

    def get_state(self, name):
        if self.purchase_line:
            if self.purchase_line.purchase.state == 'cancel':
                return 'cancel'
            elif self.purchase_line.purchase.state == 'done':
                return 'done'
            else:
                return 'purchased'
        return 'draft'

    def get_warehouse_required(self, name):
        return self.product.type in ('goods', 'assets')

    @fields.depends('uom')
    def on_change_with_uom_digits(self, name=None):
        if self.uom:
            return self.uom.digits
        return 2

    @fields.depends('computed_uom')
    def on_change_with_computed_uom_digits(self, name=None):
        if self.computed_uom:
            return self.computed_uom.digits
        return 2

    @fields.depends('product')
    def on_change_with_default_uom_digits(self, name=None):
        if self.product:
            return self.product.default_uom.digits
        return 2

    @staticmethod
    def _get_origin():
        'Return the set of Model names for origin Reference'
        return {'stock.order_point'}

    @classmethod
    def get_origin(cls):
        pool = Pool()
        IrModel = pool.get('ir.model')
        models = IrModel.search([
                ('model', 'in', list(cls._get_origin())),
                ])
        return [(m.model, m.name) for m in models]

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
        for new_req in new_requests:
            if new_req.supply_date == datetime.date.max:
                new_req.supply_date = None
            if new_req.quantity > 0.0:
                new_req.save()

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
            req_qty = Uom.compute_qty(request.uom, request.quantity,
                    pline.unit)
            if req_qty < pline.quantity:
                quantity = request.quantity
                uom = request.uom
            else:
                quantity = pline.quantity
                uom = pline.unit

            existing_req.setdefault(
                (request.product.id, request.warehouse.id),
                []).append({
                        'supply_date': (
                            request.supply_date or datetime.date.max),
                        'quantity': quantity,
                        'uom': uom,
                        })

        for i in existing_req.itervalues():
            i.sort(lambda r, s: cmp(r['supply_date'], s['supply_date']))

        # Update new requests to take existing requests into account
        new_requests.sort(key=operator.attrgetter('supply_date'))
        for new_req in new_requests:
            for old_req in existing_req.get(
                    (new_req.product.id, new_req.warehouse.id), []):
                if old_req['supply_date'] <= new_req.supply_date:
                    quantity = Uom.compute_qty(old_req['uom'],
                        old_req['quantity'], new_req.uom)
                    new_req.quantity = max(0.0, new_req.quantity - quantity)
                    new_req.computed_quantity = new_req.quantity
                    old_req['quantity'] = Uom.compute_qty(new_req.uom,
                        max(0.0, quantity - new_req.quantity), old_req['uom'])
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
            # TODO next_day is by default today + 1 but should depends
            # on the CRON activity
            next_day = today + datetime.timedelta(1)
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
    def find_best_supplier(cls, product, date):
        '''
        Return the best supplier and purchase_date for the product.
        '''
        Date = Pool().get('ir.date')

        supplier = None
        today = Date.today()
        for product_supplier in product.product_suppliers:
            supply_date = product_supplier.compute_supply_date(date=today)
            timedelta = date - supply_date
            if not supplier and timedelta >= datetime.timedelta(0):
                supplier = product_supplier.party
                break

        if supplier:
            purchase_date = product_supplier.compute_purchase_date(date)
        else:
            purchase_date = today
        return supplier, purchase_date

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
        quantity = Uom.compute_qty(product.default_uom,
                max_quantity - product_quantity,
                product.purchase_uom or product.default_uom)

        if order_point:
            origin = 'stock.order_point,%s' % order_point.id
        else:
            origin = 'stock.order_point,-1'
        return Request(product=product,
            party=supplier and supplier or None,
            quantity=quantity,
            uom=product.purchase_uom or product.default_uom,
            computed_quantity=quantity,
            computed_uom=product.purchase_uom or product.default_uom,
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

    @classmethod
    def create(cls, vlist):
        for vals in vlist:
            for field_name in ('product', 'quantity', 'uom', 'company'):
                if not vals.get(field_name):
                    cls.raise_user_error('create_request')
        return super(PurchaseRequest, cls).create(vlist)

    @classmethod
    def delete(cls, requests):
        if any(r.purchase_line for r in requests):
            cls.raise_user_error('delete_purchase_line')
        super(PurchaseRequest, cls).delete(requests)


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
    create_ = StateAction('stock_supply.act_purchase_request_form')

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


class CreatePurchaseAskParty(ModelView):
    'Create Purchase Ask Party'
    __name__ = 'purchase.request.create_purchase.ask_party'
    product = fields.Many2One('product.product', 'Product', readonly=True)
    company = fields.Many2One('company.company', 'Company', readonly=True)
    party = fields.Many2One('party.party', 'Supplier', required=True)


class CreatePurchase(Wizard):
    'Create Purchase'
    __name__ = 'purchase.request.create_purchase'
    start = StateTransition()
    ask_party = StateView('purchase.request.create_purchase.ask_party',
        'stock_supply.purchase_request_create_purchase_ask_party', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Continue', 'start', 'tryton-go-next', default=True),
            ])

    @classmethod
    def __setup__(cls):
        super(CreatePurchase, cls).__setup__()
        cls._error_messages.update({
                'missing_price': 'Purchase price is missing for product "%s".',
                'please_update': ('This price is necessary for creating '
                    'purchases.'),
                })

    def default_ask_party(self, fields):
        Request = Pool().get('purchase.request')
        requests = Request.browse(Transaction().context['active_ids'])
        for request in requests:
            if request.purchase_line:
                continue
            if not request.party:
                return {
                    'product': request.product.id,
                    'company': request.company.id,
                    }
        return {
            'product': request.product.id,
            'company': request.company.id,
            }

    @staticmethod
    def _group_purchase_key(requests, request):
        '''
        The key to group lines by purchases
        A list of key-value as tuples of the purchase
        '''
        return (
            ('company', request.company),
            ('party', request.party),
            ('payment_term', request.party.supplier_payment_term),
            ('warehouse', request.warehouse),
            ('currency', request.currency),
            ('invoice_address', request.party.address_get(type='invoice')),
            )

    def transition_start(self):
        pool = Pool()
        Request = pool.get('purchase.request')
        Purchase = pool.get('purchase.purchase')
        Date = pool.get('ir.date')

        request_ids = Transaction().context['active_ids']

        if (getattr(self.ask_party, 'product', None)
                and getattr(self.ask_party, 'party', None)
                and getattr(self.ask_party, 'company', None)):
            reqs = Request.search([
                    ('id', 'in', request_ids),
                    ('party', '=', None),
                    ])
            if reqs:
                Request.write(reqs, {
                        'party': self.ask_party.party.id,
                        })
            self.ask_party.product = None
            self.ask_party.party = None
            self.ask_party.company = None

        reqs = Request.search([
                ('id', 'in', request_ids),
                ('purchase_line', '=', None),
                ('party', '=', None),
                ])
        if reqs:
            return 'ask_party'

        today = Date.today()
        requests = Request.browse(request_ids)

        requests = [r for r in requests if not r.purchase_line]

        keyfunc = partial(self._group_purchase_key, requests)
        requests = sorted(requests, key=keyfunc)

        for key, grouped_requests in groupby(requests, key=keyfunc):
            grouped_requests = list(grouped_requests)
            try:
                purchase_date = min(r.purchase_date
                    for r in grouped_requests
                    if r.purchase_date)
            except ValueError:
                purchase_date = today
            if purchase_date < today:
                purchase_date = today
            purchase = Purchase(purchase_date=purchase_date)
            for f, v in key:
                setattr(purchase, f, v)
            purchase.save()
            for request in grouped_requests:
                line = self.compute_purchase_line(request, purchase)
                line.purchase = purchase
                line.save()
                Request.write([request], {
                        'purchase_line': line.id,
                        })
        return 'end'

    @staticmethod
    def _get_tax_rule_pattern(request):
        '''
        Get tax rule pattern
        '''
        return {}

    @classmethod
    def compute_purchase_line(cls, request, purchase):
        pool = Pool()
        Product = pool.get('product.product')
        Line = pool.get('purchase.line')

        line = Line(
            product=request.product,
            unit=request.uom,
            quantity=request.quantity,
            description=request.product.name,
            )

        # XXX purchase with several lines of the same product
        with Transaction().set_context(uom=request.uom.id,
                supplier=request.party.id,
                currency=request.currency.id):
            product_price = Product.get_purchase_price(
                [request.product], request.quantity)[request.product.id]
            product_price = product_price.quantize(
                Decimal(1) / 10 ** Line.unit_price.digits[1])

        if product_price is None:
            cls.raise_user_error('missing_price', (request.product.rec_name,),
                'please_update')
        line.unit_price = product_price

        taxes = []
        for tax in request.product.supplier_taxes_used:
            if request.party and request.party.supplier_tax_rule:
                pattern = cls._get_tax_rule_pattern(request)
                tax_ids = request.party.supplier_tax_rule.apply(tax, pattern)
                if tax_ids:
                    taxes.extend(tax_ids)
                continue
            taxes.append(tax.id)
        line.taxes = taxes
        return line
