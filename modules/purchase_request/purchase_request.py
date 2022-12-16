# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from decimal import Decimal
from itertools import groupby
from functools import partial

from sql import Null
from sql.conditionals import Case

from trytond import backend
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.pyson import If, In, Eval, Bool
from trytond.transaction import Transaction
from trytond.pool import Pool

__all__ = ['PurchaseRequest',
    'CreatePurchaseAskParty', 'CreatePurchase',
    'HandlePurchaseCancellationException',
    'HandlePurchaseCancellationExceptionStart',
    ]

STATES = {
    'readonly': Eval('state') != 'draft',
    }
DEPENDS = ['state']


class PurchaseRequest(ModelSQL, ModelView):
    'Purchase Request'
    __name__ = 'purchase.request'

    product = fields.Many2One('product.product', 'Product',
        select=True, readonly=True, domain=[('purchasable', '=', True)])
    description = fields.Text('Description', readonly=True,
        states={
            'required': ~Eval('product'),
            'readonly': STATES['readonly'],
            },
        depends=['product'] + DEPENDS)
    party = fields.Many2One('party.party', 'Party', select=True, states=STATES,
        depends=DEPENDS)
    quantity = fields.Float('Quantity', required=True, states=STATES,
        digits=(16, Eval('uom_digits', 2)), depends=DEPENDS + ['uom_digits'])
    uom = fields.Many2One('product.uom', 'UOM', select=True,
        states={
            'required': Bool(Eval('product')),
            'readonly': STATES['readonly'],
            },
        depends=['product'] + DEPENDS)
    uom_digits = fields.Function(fields.Integer('UOM Digits'),
        'on_change_with_uom_digits')
    computed_quantity = fields.Float('Computed Quantity', readonly=True)
    computed_uom = fields.Many2One('product.uom', 'Computed UOM',
        readonly=True)
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
        'Purchase'), 'get_purchase', searcher='search_purchase')
    company = fields.Many2One('company.company', 'Company', required=True,
            readonly=True, domain=[
                ('id', If(In('company', Eval('context', {})), '=', '!='),
                    Eval('context', {}).get('company', -1)),
            ])
    origin = fields.Reference('Origin', selection='get_origin', readonly=True)
    exception_ignored = fields.Boolean('Ignored Exception')
    state = fields.Function(fields.Selection([
        ('purchased', 'Purchased'),
        ('done', 'Done'),
        ('draft', 'Draft'),
        ('cancel', 'Cancel'),
        ('exception', 'Exception'),
        ], 'State'), 'get_state', searcher='search_state')

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
        cls._buttons.update({
                'handle_purchase_cancellation_exception': {
                    'invisible': Eval('state') != 'exception',
                    },
                })

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        TableHandler = backend.get('TableHandler')
        model_data = ModelData.__table__()
        super(PurchaseRequest, cls).__register__(module_name)

        # Migration from 3.6: removing the constraint on the quantity
        tablehandler = TableHandler(cls, module_name)
        tablehandler.drop_constraint('check_purchase_request_quantity')

        # Migration from 3.8: renaming module of Purchase Request group entry
        cursor = Transaction().connection.cursor()
        cursor.execute(*model_data.update(
                columns=[model_data.module],
                values=['purchase_request'],
                where=((model_data.fs_id == 'group_purchase_request')
                    & (model_data.module == 'stock_supply'))))

        # Migration from 4.0: remove required on product and uom
        tablehandler.not_null_action('product', action='remove')
        tablehandler.not_null_action('uom', action='remove')

    def get_rec_name(self, name):
        product_name = (self.product.name if self.product else
            self.description.splitlines()[0])
        if self.warehouse:
            return "%s@%s" % (product_name, self.warehouse.name)
        else:
            return product_name

    @classmethod
    def search_rec_name(cls, name, clause):
        res = []
        names = clause[2].split('@', 1)
        res.append(('product.template.name', clause[1], names[0]))
        if len(names) != 1 and names[1]:
            res.append(('warehouse', clause[1], names[1]))
        return ['OR', res,
            ('description',) + tuple(clause[1:]),
            ]

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_exception_ignored():
        return False

    def get_purchase(self, name):
        if self.purchase_line:
            return self.purchase_line.purchase.id

    @classmethod
    def search_purchase(cls, name, clause):
        return [('purchase_line.' + clause[0],) + tuple(clause[1:])]

    @property
    def currency(self):
        return self.company.currency

    def get_state(self, name):
        if self.purchase_line:
            if (self.purchase_line.purchase.state == 'cancel'
                    and not self.exception_ignored):
                return 'exception'
            elif self.purchase_line.purchase.state == 'cancel':
                return 'cancel'
            elif self.purchase_line.purchase.state == 'done':
                return 'done'
            else:
                return 'purchased'
        return 'draft'

    @classmethod
    def search_state(cls, name, clause):
        pool = Pool()
        Purchase = pool.get('purchase.purchase')
        PurchaseLine = pool.get('purchase.line')

        request = cls.__table__()
        purchase_line = PurchaseLine.__table__()
        purchase = Purchase.__table__()

        _, operator_, state = clause
        Operator = fields.SQL_OPERATORS[operator_]
        state_case = Case(
            ((purchase.state == 'cancel')
                & (request.exception_ignored == False), 'exception'),
            ((purchase.state == 'cancel')
                & (request.exception_ignored == True), 'cancel'),
            (purchase.state == 'done', 'done'),
            (request.purchase_line != Null, 'purchased'),
            else_='draft')
        state_query = request.join(
            purchase_line, type_='LEFT',
            condition=request.purchase_line == purchase_line.id
            ).join(purchase, type_='LEFT',
            condition=purchase_line.purchase == purchase.id
            ).select(
            request.id,
            where=Operator(state_case, state))

        return [('id', 'in', state_query)]

    def get_warehouse_required(self, name):
        return self.product and self.product.type in ('goods', 'assets')

    @fields.depends('uom')
    def on_change_with_uom_digits(self, name=None):
        if self.uom:
            return self.uom.digits
        return 2

    @fields.depends('product')
    def on_change_with_default_uom_digits(self, name=None):
        if self.product:
            return self.product.default_uom.digits
        return 2

    @classmethod
    def _get_origin(cls):
        'Return the set of Model names for origin Reference'
        return set()

    @classmethod
    def get_origin(cls):
        pool = Pool()
        IrModel = pool.get('ir.model')
        models = IrModel.search([
                ('model', 'in', list(cls._get_origin())),
                ])
        return [(m.model, m.name) for m in models]

    @classmethod
    def create(cls, vlist):
        for vals in vlist:
            for field_name in ('quantity', 'company'):
                if vals.get(field_name) is None:
                    cls.raise_user_error('create_request')
        return super(PurchaseRequest, cls).create(vlist)

    @classmethod
    def delete(cls, requests):
        if any(r.purchase_line for r in requests):
            cls.raise_user_error('delete_purchase_line')
        super(PurchaseRequest, cls).delete(requests)

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
    @ModelView.button_action(
        'purchase_request.wizard_purchase_cancellation_handle_exception')
    def handle_purchase_cancellation_exception(cls, purchases):
        pass


class CreatePurchaseAskParty(ModelView):
    'Create Purchase Ask Party'
    __name__ = 'purchase.request.create_purchase.ask_party'
    product = fields.Many2One('product.product', 'Product', readonly=True)
    description = fields.Text('Description', readonly=True)
    company = fields.Many2One('company.company', 'Company', readonly=True)
    party = fields.Many2One('party.party', 'Supplier', required=True)


class CreatePurchase(Wizard):
    'Create Purchase'
    __name__ = 'purchase.request.create_purchase'
    start = StateTransition()
    ask_party = StateView('purchase.request.create_purchase.ask_party',
        'purchase_request.purchase_request_create_purchase_ask_party', [
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
                break
        return {
            'product': request.product.id if request.product else None,
            'description': request.description,
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

    def _group_purchase_line_key(self, request):
        '''
        The key to group requests by lines
        A list of key-value as tuples of the purchase line
        '''
        return (
            ('product', request.product),
            ('description', request.description),
            ('unit', request.uom),
            )

    def transition_start(self):
        pool = Pool()
        Request = pool.get('purchase.request')
        Purchase = pool.get('purchase.purchase')
        Date = pool.get('ir.date')

        request_ids = Transaction().context['active_ids']

        if (getattr(self.ask_party, 'party', None)
                and getattr(self.ask_party, 'company', None)):
            reqs = Request.search([
                    ('id', 'in', request_ids),
                    ('purchase_line', '=', None),
                    ('party', '=', None),
                    ('product', '=', (self.ask_party.product.id
                            if self.ask_party.product else None)),
                    ('description', '=', self.ask_party.description),
                    ])
            if reqs:
                Request.write(reqs, {
                        'party': self.ask_party.party.id,
                        })
            self.ask_party.product = None
            self.ask_party.description = None
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
            for line_key, line_requests in groupby(
                    grouped_requests, key=self._group_purchase_line_key):
                line_requests = list(line_requests)
                line = self.compute_purchase_line(
                    line_key, line_requests, purchase)
                line.purchase = purchase
                line.save()
                Request.write(line_requests, {
                        'purchase_line': line.id,
                        })
        return 'end'

    @staticmethod
    def _get_tax_rule_pattern(line, purchase):
        '''
        Get tax rule pattern
        '''
        return {}

    @classmethod
    def compute_purchase_line(cls, key, requests, purchase):
        pool = Pool()
        Product = pool.get('product.product')
        Line = pool.get('purchase.line')

        line = Line()
        for f, v in key:
            setattr(line, f, v)
        if not line.description:
            line.description = line.product.name
        line.quantity = sum(r.quantity for r in requests)

        if not getattr(line, 'unit_price', None):
            if line.product and line.unit:
                with Transaction().set_context(uom=line.unit.id,
                        supplier=purchase.party.id,
                        currency=purchase.currency.id):
                    product_price = Product.get_purchase_price(
                        [line.product], line.quantity)[line.product.id]
            else:
                product_price = Decimal(0)
            product_price = product_price.quantize(
                Decimal(1) / 10 ** Line.unit_price.digits[1])
            line.unit_price = product_price

        taxes = []
        pattern = cls._get_tax_rule_pattern(line, purchase)
        if line.product:
            for tax in line.product.supplier_taxes_used:
                if purchase.party and purchase.party.supplier_tax_rule:
                    tax_ids = purchase.party.supplier_tax_rule.apply(
                        tax, pattern)
                    if tax_ids:
                        taxes.extend(tax_ids)
                    continue
                taxes.append(tax.id)
        if purchase.party and purchase.party.supplier_tax_rule:
            tax_ids = purchase.party.supplier_tax_rule.apply(None, pattern)
            if tax_ids:
                taxes.extend(tax_ids)
            line.taxes = taxes
        return line


class HandlePurchaseCancellationException(Wizard):
    'Handle Purchase Cancellation Exception'
    __name__ = 'purchase.request.handle.purchase.cancellation'

    start = StateView('purchase.request.handle.purchase.cancellation.start',
        'purchase_request.handle_purchase_cancellation_start', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Reset to draft', 'reset', 'tryton-clear'),
            Button('Cancel Request', 'cancel_request', 'tryton-delete',
                default=True),
            ])
    reset = StateTransition()
    cancel_request = StateTransition()

    def transition_reset(self):
        pool = Pool()
        PurchaseRequest = pool.get('purchase.request')

        requests = PurchaseRequest.browse(Transaction().context['active_ids'])
        PurchaseRequest.write(requests, {
                'purchase_line': None,
                })
        return 'end'

    def transition_cancel_request(self):
        pool = Pool()
        PurchaseRequest = pool.get('purchase.request')

        requests = PurchaseRequest.browse(Transaction().context['active_ids'])
        PurchaseRequest.write(requests, {
                'exception_ignored': True,
                })
        return 'end'


class HandlePurchaseCancellationExceptionStart(ModelView):
    'Handle Purchase Cancellation Exception - Start'
    __name__ = 'purchase.request.handle.purchase.cancellation.start'
