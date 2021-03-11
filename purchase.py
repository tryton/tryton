# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from functools import wraps
from itertools import groupby
from sql.conditionals import Case

from trytond.i18n import gettext
from trytond.model import Workflow, ModelView, fields, ModelSQL
from trytond.modules.company import CompanyReport
from trytond.modules.product import price_digits
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Bool, If
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateTransition, Button

from .exceptions import PreviousQuotation


def process_request(func):
    @wraps(func)
    def wrapper(cls, quotations):
        pool = Pool()
        Request = pool.get('purchase.request')
        func(cls, quotations)
        requests = [l.request for q in quotations for l in q.lines]
        Request.update_state(requests)
    return wrapper


class Configuration(metaclass=PoolMeta):
    __name__ = 'purchase.configuration'
    purchase_request_quotation_sequence = fields.MultiValue(fields.Many2One(
            'ir.sequence', 'Purchase Request Quotation Sequence',
            required=True,
            domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('code', '=', 'purchase.request.quotation'),
                ]))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'purchase_request_quotation_sequence':
            return pool.get('purchase.configuration.sequence')
        return super(Configuration, cls).multivalue_model(field)

    @classmethod
    def default_purchase_request_quotation_sequence(cls, **pattern):
        return cls.multivalue_model('purchase_request_quotation_sequence'
            ).default_purchase_request_quotation_sequence()


class ConfigurationSequence(metaclass=PoolMeta):
    __name__ = 'purchase.configuration.sequence'
    purchase_request_quotation_sequence = fields.Many2One(
            'ir.sequence', 'Purchase Request Quotation Sequence',
            required=True,
            domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('code', '=', 'purchase.request.quotation'),
                ],
            depends=['company'])

    @classmethod
    def default_purchase_request_quotation_sequence(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        try:
            return ModelData.get_id(
                'purchase_request_quotation',
                'sequence_purchase_request_quotation')
        except KeyError:
            return None


class Quotation(Workflow, ModelSQL, ModelView):
    "Purchase Request For Quotation"
    __name__ = 'purchase.request.quotation'
    _rec_name = 'number'

    number = fields.Char('Number', readonly=True,
        states={
            'required': ~Eval('state').in_(['draft', 'cancelled'])
            },
        depends=['state'],
        help="The unique identifier of the quotation.")
    revision = fields.Integer('Revision', readonly=True,
        help="Number incremented each time the quotation is sent.")
    reference = fields.Char('Reference', select=True,
        help="The reference used by the supplier.")
    company = fields.Many2One('company.company', 'Company', required=True,
        readonly=True, select=True, domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ])
    warehouse = fields.Many2One('stock.location', 'Warehouse',
        domain=[('type', '=', 'warehouse')])
    supplier = fields.Many2One('party.party', 'Supplier', required=True,
        states={
            'readonly': Eval('lines', [0]) & Eval('supplier'),
            },)
    supplier_address = fields.Many2One('party.address', 'Supplier Address',
        domain=[
            ('party', '=', Eval('supplier')),
            ],
        depends=['supplier'])
    lines = fields.One2Many('purchase.request.quotation.line', 'quotation',
        'Lines', states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['state'])
    state = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('rejected', 'Rejected'),
        ('received', 'Received'),
        ('cancelled', 'Cancelled'),
        ], 'State', readonly=True, required=True)

    @classmethod
    def __setup__(cls):
        super(Quotation, cls).__setup__()
        cls._transitions |= set((
                ('draft', 'cancelled'),
                ('cancelled', 'draft'),
                ('draft', 'sent'),
                ('sent', 'rejected'),
                ('sent', 'received'),
                ('sent', 'draft'),
                ('received', 'rejected'),
                ('rejected', 'received'),
                ))
        cls._buttons.update({
                'cancel': {
                    'invisible': Eval('state') != 'draft',
                    },
                'draft': {
                    'invisible': ~Eval('state').in_(['cancelled', 'sent']),
                    'icon': If(Eval('state') == 'cancelled',
                        'tryton-undo',
                        'tryton-back'),
                    },
                'send': {
                    'invisible': ((Eval('state') != 'draft')
                        | ~Eval('lines', [])),
                    'readonly': ~Eval('lines', []),
                    },
                'receive': {
                    'invisible': ~Eval('state').in_(['sent', 'rejected']),
                    },
                'reject': {
                    'invisible': ~Eval('state').in_(['sent', 'received']),
                    },
                })

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_state(cls):
        return 'draft'

    @classmethod
    def default_revision(cls):
        return 1

    @classmethod
    def default_warehouse(cls):
        Location = Pool().get('stock.location')
        return Location.get_default_warehouse()

    @classmethod
    def set_number(cls, quotations):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Config = pool.get('purchase.configuration')

        config = Config(1)
        for quotation in quotations:
            if quotation.number:
                quotation.revision += 1
            else:
                quotation.number = Sequence.get_id(
                    config.purchase_request_quotation_sequence.id)
        cls.save(quotations)

    @fields.depends('supplier')
    def on_change_supplier(self):
        self.supplier_address = None
        if self.supplier:
            self.supplier_address = self.supplier.address_get()

    @classmethod
    def copy(cls, groups, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('number', None)
        default.setdefault('revision', cls.default_revision())
        default.setdefault('request_quotations', None)
        return super(Quotation, cls).copy(groups, default=default)

    @property
    def delivery_full_address(self):
        if self.warehouse and self.warehouse.address:
            return self.warehouse.address.full_address
        return ''

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, quotations):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, quotations):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('sent')
    def send(cls, quotations):
        cls.set_number(quotations)

    @classmethod
    @ModelView.button
    @process_request
    @Workflow.transition('received')
    def receive(cls, quotations):
        pass

    @classmethod
    @ModelView.button
    @process_request
    @Workflow.transition('rejected')
    def reject(cls, quotations):
        pass


class QuotationLine(ModelSQL, ModelView):
    "Purchase Request For Quotation Line"
    __name__ = 'purchase.request.quotation.line'

    supplier = fields.Function(fields.Many2One('party.party', 'Supplier'),
        'get_supplier')
    supply_date = fields.Date('Supply Date',
        help="When it should be delivered.")
    product = fields.Function(fields.Many2One('product.product', 'Product'),
        'get_product', searcher='search_product')
    description = fields.Text('Description',
        states={
            'required': ~Eval('product')
            },
        depends=['product'])
    quantity = fields.Float(
        'Quantity', digits=(16, Eval('unit_digits', 2)), required=True,
        depends=['unit_digits'])
    unit = fields.Many2One(
        'product.uom', 'Unit', ondelete='RESTRICT',
        states={
            'required': Bool(Eval('product')),
            },
        domain=[
            If(Bool(Eval('product_uom_category')),
                ('category', '=', Eval('product_uom_category')),
                ('category', '!=', -1)),
        ],
        depends=['product', 'product_uom_category'])
    unit_digits = fields.Function(
        fields.Integer('Unit Digits'), 'on_change_with_unit_digits')
    product_uom_category = fields.Function(
        fields.Many2One('product.uom.category', 'Product Uom Category'),
        'on_change_with_product_uom_category')
    unit_price = fields.Numeric('Unit Price', digits=price_digits)
    currency = fields.Many2One('currency.currency', 'Currency',
        states={
            'required': Bool(Eval('unit_price')),
            },
        depends=['unit_price'])
    currency_digits = fields.Function(
        fields.Integer('Currency Digits'), 'on_change_with_currency_digits')
    request = fields.Many2One('purchase.request', 'Request',
        ondelete='CASCADE', select=True, required=True,
        domain=[
            If(Eval('quotation_state') == 'draft',
                ('state', 'in', ['draft', 'quotation', 'received']), (), ),
        ],
        states={
            'readonly': Eval('quotation_state') != 'draft'
            },
        depends=['quotation_state'],
        help="The request which this line belongs to.")
    quotation = fields.Many2One('purchase.request.quotation', 'Quotation',
        ondelete='CASCADE', required=True,
        domain=[
               ('supplier', '=', Eval('supplier')),
        ],
        depends=['supplier'])
    quotation_state = fields.Function(fields.Selection(
            'get_quotation_state', 'Quotation State'),
        'on_change_with_quotation_state', searcher='search_quotation_state')

    @staticmethod
    def order_quotation_state(tables):
        pool = Pool()
        Quotation = pool.get('purchase.request.quotation')
        quotation_line, _ = tables[None]
        quotation = Quotation.__table__()
        tables['purchase.request.quotation'] = {
            None: (quotation, quotation_line.quotation == quotation.id),
            }
        return [Case((quotation.state == 'received', 0), else_=1),
            quotation.state]

    def get_supplier(self, name):
        if self.quotation and self.quotation.supplier:
            return self.quotation.supplier.id

    @fields.depends('request',
        '_parent_request.product', '_parent_request.description',
        '_parent_request.quantity', '_parent_request.uom',
        '_parent_request.company', '_parent_request.supply_date')
    def on_change_request(self):
        if self.request:
            self.product = self.request.product
            self.description = self.request.description
            self.quantity = self.request.quantity
            self.unit = self.request.uom
            if self.request.company:
                self.currency = self.request.company.currency
            self.supply_date = self.request.supply_date or datetime.date.max

    @fields.depends('unit')
    def on_change_with_unit_digits(self, name=None):
        if self.unit:
            return self.unit.digits
        return None

    @fields.depends('product')
    def on_change_with_product_uom_category(self, name=None):
        if self.product:
            return self.product.default_uom_category.id

    @fields.depends('currency')
    def on_change_with_currency_digits(self, name=None):
        if self.currency:
            return self.currency.digits
        return None

    @classmethod
    def get_quotation_state(cls):
        pool = Pool()
        Quotation = pool.get('purchase.request.quotation')
        return (Quotation.fields_get(
            ['state'])['state']['selection'])

    @fields.depends('quotation', '_parent_quotation.state')
    def on_change_with_quotation_state(self, name=None):
        pool = Pool()
        Quotation = pool.get('purchase.request.quotation')
        if self.quotation:
            return self.quotation.state
        return Quotation.default_state()

    @classmethod
    def search_quotation_state(cls, name, clause):
        return [('quotation.state',) + tuple(clause[1:])]

    def get_rec_name(self, name):
        return '%s - %s' % (self.quotation.rec_name, self.supplier.rec_name)

    @classmethod
    def search_rec_name(cls, name, clause):
        names = clause[2].split(' - ', 1)
        res = [('quotation', clause[1], names[0])]
        if len(names) != 1 and names[1]:
            res.append(('supplier', clause[1], names[1]))
        return res

    @classmethod
    def delete(cls, quotationlines):
        pool = Pool()
        Request = pool.get('purchase.request')
        requests = [l.request for l in quotationlines]
        super(QuotationLine, cls).delete(quotationlines)
        Request.update_state(requests)

    def get_product(self, name):
        if self.request and self.request.product:
            return self.request.product.id

    @classmethod
    def search_product(cls, name, clause):
        return [('request.' + clause[0],) + tuple(clause[1:])]


class PurchaseRequestQuotationReport(CompanyReport):
    __name__ = 'purchase.request.quotation'

    @classmethod
    def execute(cls, ids, data):
        with Transaction().set_context(address_with_party=True):
            return super(
                PurchaseRequestQuotationReport, cls).execute(ids, data)

    @classmethod
    def get_context(cls, records, data):
        pool = Pool()
        Date = pool.get('ir.date')
        context = super(PurchaseRequestQuotationReport, cls).get_context(
            records, data)
        context['today'] = Date.today()
        return context


class CreatePurchaseRequestQuotationAskSuppliers(ModelView):
    'Create Purchase Request Quotation Ask Suppliers'
    __name__ = 'purchase.request.quotation.create.ask_suppliers'

    suppliers = fields.Many2Many('party.party', None, None, 'Suppliers',
                    required=True)


class CreatePurchaseRequestQuotationSucceed(ModelView):
    'Create Purchase Request Quotation Succeed'
    __name__ = 'purchase.request.quotation.create.succeed'

    number_quotations = fields.Integer('Number of Created Quotations',
        readonly=True)


class CreatePurchaseRequestQuotation(Wizard):
    'Create Purchase Request Quotation'
    __name__ = 'purchase.request.quotation.create'

    start = StateTransition()
    ask_suppliers = StateView(
        'purchase.request.quotation.create.ask_suppliers',
        'purchase_request_quotation.'
        'purchase_request_quotation_create_ask_suppliers', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Process', 'create_quotations', 'tryton-ok', default=True),
            ])
    create_quotations = StateTransition()
    succeed = StateView(
        'purchase.request.quotation.create.succeed',
        'purchase_request_quotation.'
        'purchase_request_quotation_create_succeed', [
            Button('Close', 'end', 'tryton-close', True),
            ])

    def transition_start(self):
        pool = Pool()
        Warning = pool.get('res.user.warning')

        reqs = [r for r in self.records if r.state in {'draft', 'quotation'}]
        if reqs:
            for r in reqs:
                if r.state == 'quotation':
                    if Warning.check(str(r)):
                        raise PreviousQuotation(str(r),
                            gettext('purchase_request_quotation'
                                '.msg_previous_quotation',
                                request=r.rec_name))
            return 'ask_suppliers'
        return 'end'

    def default_ask_suppliers(self, fields):
        reqs = [
            r for r in self.records
            if r.party and r.state in ['draft', 'quotation']]
        return {
            'suppliers': [r.party.id for r in reqs],
            }

    def default_succeed(self, fields):
        return {
            'number_quotations': self.succeed.number_quotations,
            }

    def filter_request(self, request, supplier):
        return request

    def _group_request_key(self, request):
        return (('company', request.company),)

    def transition_create_quotations(self):
        pool = Pool()
        Quotation = pool.get('purchase.request.quotation')
        QuotationLine = pool.get('purchase.request.quotation.line')
        quotations = []
        lines = []

        reqs = [r for r in self.records if r.state in ['draft', 'quotation']]
        for supplier in self.ask_suppliers.suppliers:
            quotation = Quotation()
            quotation.supplier = supplier
            quotation.supplier_address = supplier.address_get()
            reqs = [r for r in reqs if self.filter_request(r, supplier)]
            sorted_reqs = sorted(reqs, key=lambda r: r.company)
            for key, grouped_requests in groupby(sorted_reqs,
                    key=self._group_request_key):
                for f, v in key:
                    setattr(quotation, f, v)
                quotations.append(quotation)
                for r in grouped_requests:
                    line = self.get_quotation_line(r)
                    line.quotation = quotation
                    lines.append(line)
        QuotationLine.save(lines)
        Quotation.save(quotations)

        self.model.update_state(reqs)
        self.succeed.number_quotations = len(quotations)
        return 'succeed'

    def get_quotation_line(self, request):
        pool = Pool()
        QuotationLine = pool.get('purchase.request.quotation.line')
        quotation_line = QuotationLine()
        quotation_line.request = request
        quotation_line.description = request.description
        quotation_line.quantity = request.quantity
        quotation_line.unit = request.uom
        quotation_line.currency = request.currency
        quotation_line.supply_date = request.supply_date or datetime.date.max
        return quotation_line


class PurchaseRequest(metaclass=PoolMeta):
    __name__ = 'purchase.request'

    quotation_lines = fields.One2Many(
        'purchase.request.quotation.line', 'request', 'Quotation Lines',
        )
    quotation_lines_active = fields.One2Many(
        'purchase.request.quotation.line', 'request', 'Active Quotation Lines',
        filter=[('quotation.state', 'in', ['draft', 'sent', 'received'])],
        order=[('quotation_state', 'ASC'), ('unit_price', 'ASC')])
    best_quotation_line = fields.Function(fields.Many2One(
        'purchase.request.quotation.line', 'Best Quotation Line'),
        'get_best_quotation')
    preferred_quotation_line = fields.Many2One(
        'purchase.request.quotation.line', 'Preferred Quotation Line',
        domain=[
            ('quotation_state', '=', 'received'),
            ('request', '=', Eval('id'))
        ],
        depends=['id'],
        help="The quotation that will be chosen to create the purchase\n"
        "otherwise first ordered received quotation line will be selected.")

    @property
    def currency(self):
        currency = super(PurchaseRequest, self).currency
        if self.best_quotation_line:
            return self.best_quotation_line.currency
        return currency

    def get_best_quotation(self, name):
        if self.preferred_quotation_line:
            return self.preferred_quotation_line
        else:
            for line in self.quotation_lines_active:
                if line.quotation_state == 'received':
                    return line
            return None

    @classmethod
    def __setup__(cls):
        super(PurchaseRequest, cls).__setup__()
        selection = [('quotation', 'Quotation'), ('received', 'Received')]
        for s in selection:
            if s not in cls.state.selection:
                cls.state.selection.append(s)

    def get_state(self):
        state = super(PurchaseRequest, self).get_state()
        if state == 'draft' and self.quotation_lines:
            state = 'quotation'
            if any(l.quotation_state == 'received'
                    for l in self.quotation_lines):
                state = 'received'
        return state


class CreatePurchase(Wizard):
    'Create Purchase'
    __name__ = 'purchase.request.create_purchase'

    init = StateTransition()

    @classmethod
    def __setup__(cls):
        super(CreatePurchase, cls).__setup__()

    def transition_start(self):
        to_save = []
        reqs = [r for r in self.records
            if not r.purchase_line and r.quotation_lines]
        to_save = []
        for req in reqs:
            if req.best_quotation_line:
                to_save.append(self.apply_quotation(req))
        if to_save:
            self.model.save(to_save)
        state = super(CreatePurchase, self).transition_start()
        return state

    def apply_quotation(self, request):
        request.party = request.best_quotation_line.supplier.id
        request.description = request.best_quotation_line.description
        request.quantity = request.best_quotation_line.quantity
        if not request.preferred_quotation_line:
            request.preferred_quotation_line = request.best_quotation_line
        return request

    @classmethod
    def compute_purchase_line(cls, key, requests, purchase):
        line = super(CreatePurchase, cls).compute_purchase_line(key,
                    requests, purchase)
        try:
            line.unit_price = min(req.best_quotation_line.unit_price
                for req in requests if req.best_quotation_line)
        except ValueError:
            pass
        return line
