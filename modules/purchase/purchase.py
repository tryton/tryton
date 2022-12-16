#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import datetime
from itertools import chain
from decimal import Decimal
from sql import Table, Literal
from sql.functions import Overlay, Position
from sql.aggregate import Count
from sql.operators import Concat

from trytond.model import Workflow, ModelView, ModelSQL, fields
from trytond.modules.company import CompanyReport
from trytond.wizard import Wizard, StateAction, StateView, StateTransition, \
    Button
from trytond import backend
from trytond.pyson import Eval, Bool, If, PYSONEncoder, Id
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta

__all__ = ['Purchase', 'PurchaseIgnoredInvoice',
    'PurchaseRecreadtedInvoice', 'PurchaseLine', 'PurchaseLineTax',
    'PurchaseLineIgnoredMove', 'PurchaseLineRecreatedMove', 'PurchaseReport',
    'OpenSupplier', 'HandleShipmentExceptionAsk', 'HandleShipmentException',
    'HandleInvoiceExceptionAsk', 'HandleInvoiceException']
__metaclass__ = PoolMeta

_STATES = {
    'readonly': Eval('state') != 'draft',
    }
_DEPENDS = ['state']
_ZERO = Decimal(0)


class Purchase(Workflow, ModelSQL, ModelView):
    'Purchase'
    __name__ = 'purchase.purchase'
    _rec_name = 'reference'
    company = fields.Many2One('company.company', 'Company', required=True,
        states={
            'readonly': (Eval('state') != 'draft') | Eval('lines', [0]),
            },
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ],
        depends=['state'], select=True)
    reference = fields.Char('Reference', size=None, readonly=True, select=True)
    supplier_reference = fields.Char('Supplier Reference', select=True)
    description = fields.Char('Description', size=None, states=_STATES,
        depends=_DEPENDS)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('quotation', 'Quotation'),
        ('confirmed', 'Confirmed'),
        ('processing', 'Processing'),
        ('done', 'Done'),
        ('cancel', 'Canceled'),
    ], 'State', readonly=True, required=True)
    purchase_date = fields.Date('Purchase Date',
        states={
            'readonly': ~Eval('state').in_(['draft', 'quotation']),
            'required': ~Eval('state').in_(['draft', 'quotation', 'cancel']),
            },
        depends=['state'])
    payment_term = fields.Many2One('account.invoice.payment_term',
        'Payment Term', states={
            'readonly': ~Eval('state').in_(['draft', 'quotation']),
            'required': ~Eval('state').in_(['draft', 'quotation', 'cancel']),
            },
        depends=['state'])
    party = fields.Many2One('party.party', 'Party', required=True,
        states={
            'readonly': ((Eval('state') != 'draft')
                | (Eval('lines', [0]) & Eval('party'))),
            },
        select=True, depends=['state'])
    party_lang = fields.Function(fields.Char('Party Language'),
        'on_change_with_party_lang')
    invoice_address = fields.Many2One('party.address', 'Invoice Address',
        domain=[('party', '=', Eval('party'))],
        states={
            'readonly': Eval('state') != 'draft',
            'required': ~Eval('state').in_(['draft', 'quotation', 'cancel']),
            },
        depends=['state', 'party'])
    warehouse = fields.Many2One('stock.location', 'Warehouse',
        domain=[('type', '=', 'warehouse')], states=_STATES,
        depends=_DEPENDS)
    currency = fields.Many2One('currency.currency', 'Currency', required=True,
        states={
            'readonly': ((Eval('state') != 'draft')
                | (Eval('lines', [0]) & Eval('currency'))),
            },
        depends=['state'])
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    lines = fields.One2Many('purchase.line', 'purchase', 'Lines',
        states=_STATES, depends=_DEPENDS)
    comment = fields.Text('Comment')
    untaxed_amount = fields.Function(fields.Numeric('Untaxed',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']), 'get_amount')
    untaxed_amount_cache = fields.Numeric('Untaxed Cache',
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    tax_amount = fields.Function(fields.Numeric('Tax',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']), 'get_amount')
    tax_amount_cache = fields.Numeric('Tax Cache',
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    total_amount = fields.Function(fields.Numeric('Total',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']), 'get_amount')
    total_amount_cache = fields.Numeric('Total Cache',
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    invoice_method = fields.Selection([
            ('manual', 'Manual'),
            ('order', 'Based On Order'),
            ('shipment', 'Based On Shipment'),
            ], 'Invoice Method', required=True, states=_STATES,
        depends=_DEPENDS)
    invoice_state = fields.Selection([
            ('none', 'None'),
            ('waiting', 'Waiting'),
            ('paid', 'Paid'),
            ('exception', 'Exception'),
            ], 'Invoice State', readonly=True, required=True)
    invoices = fields.Function(fields.One2Many('account.invoice', None,
            'Invoices'), 'get_invoices', searcher='search_invoices')
    invoices_ignored = fields.Many2Many(
            'purchase.purchase-ignored-account.invoice',
            'purchase', 'invoice', 'Ignored Invoices', readonly=True)
    invoices_recreated = fields.Many2Many(
            'purchase.purchase-recreated-account.invoice',
            'purchase', 'invoice', 'Recreated Invoices', readonly=True)
    shipment_state = fields.Selection([
            ('none', 'None'),
            ('waiting', 'Waiting'),
            ('received', 'Received'),
            ('exception', 'Exception'),
            ], 'Shipment State', readonly=True, required=True)
    shipments = fields.Function(fields.One2Many('stock.shipment.in', None,
            'Shipments'), 'get_shipments')
    shipment_returns = fields.Function(
        fields.One2Many('stock.shipment.in.return', None, 'Shipment Returns'),
        'get_shipment_returns')
    moves = fields.Function(fields.One2Many('stock.move', None, 'Moves'),
        'get_moves')

    @classmethod
    def __setup__(cls):
        super(Purchase, cls).__setup__()
        cls._order.insert(0, ('purchase_date', 'DESC'))
        cls._order.insert(1, ('id', 'DESC'))
        cls._error_messages.update({
                'warehouse_required': ('A warehouse must be defined for '
                    'quotation of purchase "%s".'),
                'missing_account_payable': ('Missing "Account Payable" on '
                    'party "%s".'),
                'delete_cancel': ('Purchase "%s" must be cancelled before '
                    'deletion.'),
                })
        cls._transitions |= set((
                ('draft', 'quotation'),
                ('quotation', 'confirmed'),
                ('confirmed', 'processing'),
                ('processing', 'processing'),
                ('processing', 'done'),
                ('done', 'processing'),
                ('draft', 'cancel'),
                ('quotation', 'cancel'),
                ('quotation', 'draft'),
                ('cancel', 'draft'),
                ))
        cls._buttons.update({
                'cancel': {
                    'invisible': ~Eval('state').in_(['draft', 'quotation']),
                    },
                'draft': {
                    'invisible': ~Eval('state').in_(['cancel', 'quotation']),
                    'icon': If(Eval('state') == 'cancel', 'tryton-clear',
                        'tryton-go-previous'),
                    },
                'quote': {
                    'pre_validate': [
                        ('purchase_date', '!=', None),
                        ('payment_term', '!=', None),
                        ('invoice_address', '!=', None),
                        ],
                    'invisible': Eval('state') != 'draft',
                    'readonly': ~Eval('lines', []),
                    },
                'confirm': {
                    'invisible': Eval('state') != 'quotation',
                    },
                'process': {
                    'invisible': Eval('state') != 'confirmed',
                    },
                'handle_invoice_exception': {
                    'invisible': ((Eval('invoice_state') != 'exception')
                        | (Eval('state') == 'cancel')),
                    'readonly': ~Eval('groups', []).contains(
                        Id('purchase', 'group_purchase')),
                    },
                'handle_shipment_exception': {
                    'invisible': ((Eval('shipment_state') != 'exception')
                        | (Eval('state') == 'cancel')),
                    'readonly': ~Eval('groups', []).contains(
                        Id('purchase', 'group_purchase')),
                    },
                })
        # The states where amounts are cached
        cls._states_cached = ['confirmed', 'done', 'cancel']

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        PurchaseLine = pool.get('purchase.line')
        Move = pool.get('stock.move')
        InvoiceLine = pool.get('account.invoice.line')
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor
        model_data = Table('ir_model_data')
        model_field = Table('ir_model_field')
        sql_table = cls.__table__()

        # Migration from 1.2: packing renamed into shipment
        cursor.execute(*model_data.update(
                columns=[model_data.fs_id],
                values=[Overlay(model_data.fs_id, 'shipment',
                        Position('packing', model_data.fs_id),
                        len('packing'))],
                where=model_data.fs_id.like('%packing%')
                & (model_data.module == module_name)))
        cursor.execute(*model_field.update(
                columns=[model_field.relation],
                values=[Overlay(model_field.relation, 'shipment',
                        Position('packing', model_field.relation),
                        len('packing'))],
                where=model_field.relation.like('%packing%')
                & (model_field.module == module_name)))
        cursor.execute(*model_field.update(
                columns=[model_field.name],
                values=[Overlay(model_field.name, 'shipment',
                        Position('packing', model_field.name),
                        len('packing'))],
                where=model_field.name.like('%packing%')
                & (model_field.module == module_name)))
        table = TableHandler(cursor, cls, module_name)
        table.column_rename('packing_state', 'shipment_state')

        super(Purchase, cls).__register__(module_name)

        # Migration from 1.2: rename packing to shipment in
        # invoice_method values
        cursor.execute(*sql_table.update(
                columns=[sql_table.invoice_method],
                values=['shipment'],
                where=sql_table.invoice_method == 'packing'))

        table = TableHandler(cursor, cls, module_name)
        # Migration from 2.2: warehouse is no more required
        table.not_null_action('warehouse', 'remove')

        # Migration from 2.2: purchase_date is no more required
        table.not_null_action('purchase_date', 'remove')

        # Migration from 3.2
        # state confirmed splitted into confirmed and processing
        if (TableHandler.table_exist(cursor, PurchaseLine._table)
                and TableHandler.table_exist(cursor, Move._table)
                and TableHandler.table_exist(cursor, InvoiceLine._table)):
            purchase_line = PurchaseLine.__table__()
            move = Move.__table__()
            invoice_line = InvoiceLine.__table__()
            # Wrap subquery inside an other inner subquery because MySQL syntax
            # doesn't allow update a table and select from the same table in a
            # subquery.
            sub_query = sql_table.join(purchase_line,
                condition=purchase_line.purchase == sql_table.id
                ).join(invoice_line, 'LEFT',
                    condition=(invoice_line.origin ==
                        Concat(PurchaseLine.__name__ + ',', purchase_line.id))
                    ).join(move, 'LEFT',
                        condition=(move.origin == Concat(
                                PurchaseLine.__name__ + ',', purchase_line.id))
                        ).select(sql_table.id,
                            where=((sql_table.state == 'confirmed')
                                & ((invoice_line.id != None)
                                    | (move.id != None))))
            cursor.execute(*sql_table.update(
                    columns=[sql_table.state],
                    values=['processing'],
                    where=sql_table.id.in_(sub_query.select(sub_query.id))))

        # Add index on create_date
        table = TableHandler(cursor, cls, module_name)
        table.index_action('create_date', action='add')

    @classmethod
    def default_payment_term(cls):
        PaymentTerm = Pool().get('account.invoice.payment_term')
        payment_terms = PaymentTerm.search(cls.payment_term.domain)
        if len(payment_terms) == 1:
            return payment_terms[0].id

    @classmethod
    def default_warehouse(cls):
        Location = Pool().get('stock.location')
        locations = Location.search(cls.warehouse.domain)
        if len(locations) == 1:
            return locations[0].id

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_currency():
        Company = Pool().get('company.company')
        company = Transaction().context.get('company')
        if company:
            company = Company(company)
            return company.currency.id

    @staticmethod
    def default_currency_digits():
        Company = Pool().get('company.company')
        company = Transaction().context.get('company')
        if company:
            company = Company(company)
            return company.currency.digits
        return 2

    @staticmethod
    def default_invoice_method():
        Configuration = Pool().get('purchase.configuration')
        configuration = Configuration(1)
        return configuration.purchase_invoice_method

    @staticmethod
    def default_invoice_state():
        return 'none'

    @staticmethod
    def default_shipment_state():
        return 'none'

    @fields.depends('party', 'payment_term', 'lines')
    def on_change_party(self):
        pool = Pool()
        PaymentTerm = pool.get('account.invoice.payment_term')
        Currency = pool.get('currency.currency')
        cursor = Transaction().cursor
        table = self.__table__()
        changes = {
            'invoice_address': None,
            'payment_term': None,
            }
        if not self.lines:
            changes['currency'] = self.default_currency()
            changes['currency_digits'] = self.default_currency_digits()
        invoice_address = None
        payment_term = None
        if self.party:
            invoice_address = self.party.address_get(type='invoice')
            if self.party.supplier_payment_term:
                payment_term = self.party.supplier_payment_term

            if not self.lines:
                subquery = table.select(table.currency,
                    where=table.party == self.party.id,
                    order_by=table.id,
                    limit=10)
                cursor.execute(*subquery.select(subquery.currency,
                        group_by=subquery.currency,
                        order_by=Count(Literal(1)).desc))
                row = cursor.fetchone()
                if row:
                    currency_id, = row
                    currency = Currency(currency_id)
                    changes['currency'] = currency.id
                    changes['currency_digits'] = currency.digits

        if invoice_address:
            changes['invoice_address'] = invoice_address.id
            changes['invoice_address.rec_name'] = invoice_address.rec_name
        else:
            changes['invoice_address'] = None
        if payment_term:
            changes['payment_term'] = payment_term.id
            changes['payment_term.rec_name'] = payment_term.rec_name
        else:
            changes['payment_term'] = self.default_payment_term()
            if changes['payment_term']:
                changes['payment_term.rec_name'] = PaymentTerm(
                    changes['payment_term']).rec_name
        return changes

    @fields.depends('currency')
    def on_change_with_currency_digits(self, name=None):
        if self.currency:
            return self.currency.digits
        return 2

    @fields.depends('party')
    def on_change_with_party_lang(self, name=None):
        Config = Pool().get('ir.configuration')
        if self.party:
            if self.party.lang:
                return self.party.lang.code
        return Config.get_language()

    def get_tax_context(self):
        context = {}
        if self.party and self.party.lang:
            context['language'] = self.party.lang.code
        return context

    @fields.depends('lines', 'currency', 'party')
    def on_change_lines(self):
        pool = Pool()
        Tax = pool.get('account.tax')
        Invoice = pool.get('account.invoice')
        Configuration = pool.get('account.configuration')

        config = Configuration(1)

        changes = {
            'untaxed_amount': Decimal('0.0'),
            'tax_amount': Decimal('0.0'),
            'total_amount': Decimal('0.0'),
            }
        if self.lines:
            context = self.get_tax_context()
            taxes = {}

            def round_taxes():
                if self.currency:
                    for key, value in taxes.iteritems():
                        taxes[key] = self.currency.round(value)

            for line in self.lines:
                if getattr(line, 'type', 'line') != 'line':
                    continue
                changes['untaxed_amount'] += (getattr(line, 'amount', None)
                    or Decimal(0))

                with Transaction().set_context(context):
                    tax_list = Tax.compute(getattr(line, 'taxes', []),
                        getattr(line, 'unit_price', None) or Decimal('0.0'),
                        getattr(line, 'quantity', None) or 0.0)
                for tax in tax_list:
                    key, val = Invoice._compute_tax(tax, 'in_invoice')
                    if key not in taxes:
                        taxes[key] = val['amount']
                    else:
                        taxes[key] += val['amount']
                if config.tax_rounding == 'line':
                    round_taxes()
            if config.tax_rounding == 'document':
                round_taxes()
            changes['tax_amount'] = sum(taxes.itervalues(), Decimal('0.0'))
        if self.currency:
            changes['untaxed_amount'] = self.currency.round(
                changes['untaxed_amount'])
            changes['tax_amount'] = self.currency.round(changes['tax_amount'])
        changes['total_amount'] = (changes['untaxed_amount']
            + changes['tax_amount'])
        if self.currency:
            changes['total_amount'] = self.currency.round(
                changes['total_amount'])
        return changes

    def get_tax_amount(self):
        pool = Pool()
        Tax = pool.get('account.tax')
        Invoice = pool.get('account.invoice')
        Configuration = pool.get('account.configuration')

        config = Configuration(1)

        context = self.get_tax_context()
        taxes = {}

        def round_taxes():
            for key, value in taxes.iteritems():
                taxes[key] = self.currency.round(value)

        for line in self.lines:
            if line.type != 'line':
                continue
            with Transaction().set_context(context):
                tax_list = Tax.compute(line.taxes, line.unit_price,
                    line.quantity)
            for tax in tax_list:
                key, val = Invoice._compute_tax(tax, 'in_invoice')
                if key not in taxes:
                    taxes[key] = val['amount']
                else:
                    taxes[key] += val['amount']
            if config.tax_rounding == 'line':
                round_taxes()
        if config.tax_rounding == 'document':
            round_taxes()
        return sum(taxes.itervalues(), _ZERO)

    @classmethod
    def get_amount(cls, purchases, names):
        untaxed_amount = {}
        tax_amount = {}
        total_amount = {}

        if {'tax_amount', 'total_amount'} & set(names):
            compute_taxes = True
        else:
            compute_taxes = False
        # Sort cached first and re-instanciate to optimize cache management
        purchases = sorted(purchases,
            key=lambda p: p.state in cls._states_cached, reverse=True)
        purchases = cls.browse(purchases)
        for purchase in purchases:
            if (purchase.state in cls._states_cached
                    and purchase.untaxed_amount_cache is not None
                    and purchase.tax_amount_cache is not None
                    and purchase.total_amount_cache is not None):
                untaxed_amount[purchase.id] = purchase.untaxed_amount_cache
                if compute_taxes:
                    tax_amount[purchase.id] = purchase.tax_amount_cache
                    total_amount[purchase.id] = purchase.total_amount_cache
            else:
                untaxed_amount[purchase.id] = sum(
                    (line.amount for line in purchase.lines
                        if line.type == 'line'), _ZERO)
                if compute_taxes:
                    tax_amount[purchase.id] = purchase.get_tax_amount()
                    total_amount[purchase.id] = (
                        untaxed_amount[purchase.id] + tax_amount[purchase.id])

        result = {
            'untaxed_amount': untaxed_amount,
            'tax_amount': tax_amount,
            'total_amount': total_amount,
            }
        for key in result.keys():
            if key not in names:
                del result[key]
        return result

    def get_invoices(self, name):
        invoices = set()
        for line in self.lines:
            for invoice_line in line.invoice_lines:
                if invoice_line.invoice:
                    invoices.add(invoice_line.invoice.id)
        return list(invoices)

    @classmethod
    def search_invoices(cls, name, clause):
        return [('lines.invoice_lines.invoice.id',) + tuple(clause[1:])]

    def get_invoice_state(self):
        '''
        Return the invoice state for the purchase.
        '''
        skip_ids = set(x.id for x in self.invoices_ignored)
        skip_ids.update(x.id for x in self.invoices_recreated)
        invoices = [i for i in self.invoices if i.id not in skip_ids]
        if invoices:
            if any(i.state == 'cancel' for i in invoices):
                return 'exception'
            elif all(i.state == 'paid' for i in invoices):
                return 'paid'
            else:
                return 'waiting'
        return 'none'

    def set_invoice_state(self):
        '''
        Set the invoice state.
        '''
        state = self.get_invoice_state()
        if self.invoice_state != state:
            self.write([self], {
                    'invoice_state': state,
                    })

    def get_shipments_returns(model_name):
        "Computes the returns or shipments"
        def method(self, name):
            Model = Pool().get(model_name)
            shipments = set()
            for line in self.lines:
                for move in line.moves:
                    if isinstance(move.shipment, Model):
                        shipments.add(move.shipment.id)
            return list(shipments)
        return method

    get_shipments = get_shipments_returns('stock.shipment.in')
    get_shipment_returns = get_shipments_returns('stock.shipment.in.return')

    def get_moves(self, name):
        return [m.id for l in self.lines for m in l.moves]

    def get_shipment_state(self):
        '''
        Return the shipment state for the purchase.
        '''
        if self.moves:
            if any(l.move_exception for l in self.lines):
                return 'exception'
            elif all(l.move_done for l in self.lines):
                return 'received'
            else:
                return 'waiting'
        return 'none'

    def set_shipment_state(self):
        '''
        Set the shipment state.
        '''
        state = self.get_shipment_state()
        if self.shipment_state != state:
            self.write([self], {
                    'shipment_state': state,
                    })

    def get_rec_name(self, name):
        return (self.reference or str(self.id)
            + ' - ' + self.party.name)

    @classmethod
    def search_rec_name(cls, name, clause):
        _, operator, value = clause
        names = value.split(' - ', 1)
        domain = ['OR',
            ('reference', operator, names[0]),
            ('supplier_reference', operator, names[0]),
            ]
        if len(names) != 1 and names[1]:
            domain = [domain, ('party', operator, names[1])]
        return domain

    @classmethod
    def copy(cls, purchases, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default['state'] = 'draft'
        default['reference'] = None
        default['invoice_state'] = 'none'
        default['invoices_ignored'] = None
        default['shipment_state'] = 'none'
        default.setdefault('purchase_date', None)
        return super(Purchase, cls).copy(purchases, default=default)

    def check_for_quotation(self):
        for line in self.lines:
            if (not line.to_location
                    and line.product
                    and line.product.type in ('goods', 'assets')):
                self.raise_user_error('warehouse_required', (self.rec_name,))

    @classmethod
    def set_reference(cls, purchases):
        '''
        Fill the reference field with the purchase sequence
        '''
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Config = pool.get('purchase.configuration')

        config = Config(1)
        for purchase in purchases:
            if purchase.reference:
                continue
            reference = Sequence.get_id(config.purchase_sequence.id)
            cls.write([purchase], {
                    'reference': reference,
                    })

    @classmethod
    def set_purchase_date(cls, purchases):
        Date = Pool().get('ir.date')
        for purchase in purchases:
            if not purchase.purchase_date:
                cls.write([purchase], {
                        'purchase_date': Date.today(),
                        })

    @classmethod
    def store_cache(cls, purchases):
        for purchase in purchases:
            cls.write([purchase], {
                    'untaxed_amount_cache': purchase.untaxed_amount,
                    'tax_amount_cache': purchase.tax_amount,
                    'total_amount_cache': purchase.total_amount,
                    })

    def _get_invoice_line_purchase_line(self, invoice_type):
        '''
        Return invoice line for each purchase lines
        '''
        res = {}
        for line in self.lines:
            val = line.get_invoice_line(invoice_type)
            if val:
                res[line.id] = val
        return res

    def _get_invoice_purchase(self, invoice_type):
        '''
        Return invoice of type invoice_type
        '''
        pool = Pool()
        Journal = pool.get('account.journal')
        Invoice = pool.get('account.invoice')

        journals = Journal.search([
                ('type', '=', 'expense'),
                ], limit=1)
        if journals:
            journal, = journals
        else:
            journal = None

        return Invoice(
            company=self.company,
            type=invoice_type,
            journal=journal,
            party=self.party,
            invoice_address=self.invoice_address,
            currency=self.currency,
            account=self.party.account_payable,
            payment_term=self.payment_term,
            )

    def create_invoice(self, invoice_type):
        '''
        Create an invoice for the purchase and return it
        '''
        pool = Pool()
        Invoice = pool.get('account.invoice')

        if self.invoice_method == 'manual':
            return

        if not self.party.account_payable:
            self.raise_user_error('missing_account_payable',
                    error_args=(self.party.rec_name,))

        invoice_lines = self._get_invoice_line_purchase_line(invoice_type)
        if not invoice_lines:
            return

        invoice = self._get_invoice_purchase(invoice_type)
        invoice.lines = list(chain.from_iterable(
                invoice_lines[l.id] for l in self.lines
                if l.id in invoice_lines))
        invoice.save()

        Invoice.update_taxes([invoice])
        return invoice

    def create_move(self, move_type):
        '''
        Create move for each purchase lines
        '''
        new_moves = []
        for line in self.lines:
            if (line.quantity >= 0) != (move_type == 'in'):
                continue
            move = line.create_move()
            if move:
                new_moves.append(move)
        return new_moves

    def _get_return_shipment(self):
        ShipmentInReturn = Pool().get('stock.shipment.in.return')
        return ShipmentInReturn(
            company=self.company,
            from_location=self.warehouse.storage_location,
            to_location=self.party.supplier_location,
            )

    def create_return_shipment(self, return_moves):
        '''
        Create return shipment and return the shipment id
        '''
        ShipmentInReturn = Pool().get('stock.shipment.in.return')
        return_shipment = self._get_return_shipment()
        return_shipment.moves = return_moves
        return_shipment.save()
        ShipmentInReturn.wait([return_shipment])
        return return_shipment

    def is_done(self):
        return ((self.invoice_state == 'paid'
                or self.invoice_state == 'none')
            and (self.shipment_state == 'received'
                or self.shipment_state == 'none'
                or all(l.product.type == 'service'
                    for l in self.lines if l.product)))

    @classmethod
    def delete(cls, purchases):
        # Cancel before delete
        cls.cancel(purchases)
        for purchase in purchases:
            if purchase.state != 'cancel':
                cls.raise_user_error('delete_cancel', purchase.rec_name)
        super(Purchase, cls).delete(purchases)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, purchases):
        cls.store_cache(purchases)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, purchases):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('quotation')
    def quote(cls, purchases):
        for purchase in purchases:
            purchase.check_for_quotation()
        cls.set_reference(purchases)

    @classmethod
    @ModelView.button
    @Workflow.transition('confirmed')
    def confirm(cls, purchases):
        cls.set_purchase_date(purchases)
        cls.store_cache(purchases)

    @classmethod
    @Workflow.transition('processing')
    def proceed(cls, purchases):
        pass

    @classmethod
    @ModelView.button_action('purchase.wizard_invoice_handle_exception')
    def handle_invoice_exception(cls, purchases):
        pass

    @classmethod
    @ModelView.button_action('purchase.wizard_shipment_handle_exception')
    def handle_shipment_exception(cls, purchases):
        pass

    @classmethod
    @ModelView.button
    def process(cls, purchases):
        process, done = [], []
        for purchase in purchases:
            purchase.create_invoice('in_invoice')
            purchase.create_invoice('in_credit_note')
            purchase.set_invoice_state()
            purchase.create_move('in')
            return_moves = purchase.create_move('return')
            if return_moves:
                purchase.create_return_shipment(return_moves)
            purchase.set_shipment_state()
            if purchase.is_done():
                done.append(purchase)
            elif purchase.state != 'processing':
                process.append(purchase)
        if process:
            cls.proceed(process)
        if done:
            cls.write(done, {
                    'state': 'done',
                    })


class PurchaseIgnoredInvoice(ModelSQL):
    'Purchase - Ignored Invoice'
    __name__ = 'purchase.purchase-ignored-account.invoice'
    _table = 'purchase_invoice_ignored_rel'
    purchase = fields.Many2One('purchase.purchase', 'Purchase',
            ondelete='CASCADE', select=True, required=True)
    invoice = fields.Many2One('account.invoice', 'Invoice',
            ondelete='RESTRICT', select=True, required=True)


class PurchaseRecreadtedInvoice(ModelSQL):
    'Purchase - Recreated Invoice'
    __name__ = 'purchase.purchase-recreated-account.invoice'
    _table = 'purchase_invoice_recreated_rel'
    purchase = fields.Many2One('purchase.purchase', 'Purchase',
            ondelete='CASCADE', select=True, required=True)
    invoice = fields.Many2One('account.invoice', 'Invoice',
            ondelete='RESTRICT', select=True, required=True)


class PurchaseLine(ModelSQL, ModelView):
    'Purchase Line'
    __name__ = 'purchase.line'
    _rec_name = 'description'
    purchase = fields.Many2One('purchase.purchase', 'Purchase',
            ondelete='CASCADE', select=True, required=True)
    sequence = fields.Integer('Sequence')
    type = fields.Selection([
        ('line', 'Line'),
        ('subtotal', 'Subtotal'),
        ('title', 'Title'),
        ('comment', 'Comment'),
        ], 'Type', select=True, required=True)
    quantity = fields.Float('Quantity',
        digits=(16, Eval('unit_digits', 2)),
        states={
            'invisible': Eval('type') != 'line',
            'required': Eval('type') == 'line',
            'readonly': ~Eval('_parent_purchase'),
            },
        depends=['unit_digits', 'type'])
    unit = fields.Many2One('product.uom', 'Unit',
        states={
            'required': Bool(Eval('product')),
            'invisible': Eval('type') != 'line',
            'readonly': ~Eval('_parent_purchase'),
            },
        domain=[
            If(Bool(Eval('product_uom_category')),
                ('category', '=', Eval('product_uom_category')),
                ('category', '!=', -1)),
            ],
        depends=['product', 'type', 'product_uom_category'])
    unit_digits = fields.Function(fields.Integer('Unit Digits'),
        'on_change_with_unit_digits')
    product = fields.Many2One('product.product', 'Product',
        domain=[('purchasable', '=', True)],
        states={
            'invisible': Eval('type') != 'line',
            'readonly': ~Eval('_parent_purchase'),
            },
        context={
            'locations': If(Bool(Eval('_parent_purchase', {}).get(
                        'warehouse')),
                [Eval('_parent_purchase', {}).get('warehouse', None)],
                []),
            'stock_date_end': Eval('_parent_purchase', {}).get(
                'purchase_date'),
            'stock_skip_warehouse': True,
            }, depends=['type'])
    product_uom_category = fields.Function(
        fields.Many2One('product.uom.category', 'Product Uom Category'),
        'on_change_with_product_uom_category')
    unit_price = fields.Numeric('Unit Price', digits=(16, 4),
        states={
            'invisible': Eval('type') != 'line',
            'required': Eval('type') == 'line',
            }, depends=['type'])
    amount = fields.Function(fields.Numeric('Amount',
            digits=(16,
                Eval('_parent_purchase', {}).get('currency_digits', 2)),
            states={
                'invisible': ~Eval('type').in_(['line', 'subtotal']),
                'readonly': ~Eval('_parent_purchase'),
                },
            depends=['type']), 'get_amount')
    description = fields.Text('Description', size=None, required=True)
    note = fields.Text('Note')
    taxes = fields.Many2Many('purchase.line-account.tax',
        'line', 'tax', 'Taxes',
        domain=[('parent', '=', None), ['OR',
                ('group', '=', None),
                ('group.kind', 'in', ['purchase', 'both'])],
            ],
        states={
            'invisible': Eval('type') != 'line',
            }, depends=['type'])
    invoice_lines = fields.One2Many('account.invoice.line', 'origin',
        'Invoice Lines', readonly=True)
    moves = fields.One2Many('stock.move', 'origin', 'Moves', readonly=True)
    moves_ignored = fields.Many2Many('purchase.line-ignored-stock.move',
            'purchase_line', 'move', 'Ignored Moves', readonly=True)
    moves_recreated = fields.Many2Many('purchase.line-recreated-stock.move',
            'purchase_line', 'move', 'Recreated Moves', readonly=True)
    move_done = fields.Function(fields.Boolean('Moves Done'), 'get_move_done')
    move_exception = fields.Function(fields.Boolean('Moves Exception'),
            'get_move_exception')
    from_location = fields.Function(fields.Many2One('stock.location',
            'From Location'), 'get_from_location')
    to_location = fields.Function(fields.Many2One('stock.location',
            'To Location'), 'get_to_location')
    delivery_date = fields.Function(fields.Date('Delivery Date',
            states={
                'invisible': ((Eval('type') != 'line')
                    | (If(Bool(Eval('quantity')), Eval('quantity', 0), 0)
                        <= 0)),
                },
            depends=['type', 'quantity']),
        'on_change_with_delivery_date')

    @classmethod
    def __setup__(cls):
        super(PurchaseLine, cls).__setup__()
        cls._order.insert(0, ('sequence', 'ASC'))
        cls._error_messages.update({
                'supplier_location_required': ('Purchase "%(purchase)s" '
                    'misses the supplier location for line "%(line)s".'),
                'missing_account_expense': ('Product "%(product)s" of '
                    'purchase %(purchase)s misses an expense account.'),
                'missing_account_expense_property': ('Purchase "%(purchase)s" '
                    'misses an "account expense" default property.'),
                })

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor
        sql_table = cls.__table__()
        super(PurchaseLine, cls).__register__(module_name)
        table = TableHandler(cursor, cls, module_name)

        # Migration from 1.0 comment change into note
        if table.column_exist('comment'):
            cursor.execute(*sql_table.update(
                    columns=[sql_table.note],
                    values=[sql_table.comment]))
            table.drop_column('comment', exception=True)

        # Migration from 2.4: drop required on sequence
        table.not_null_action('sequence', action='remove')

    @staticmethod
    def order_sequence(tables):
        table, _ = tables[None]
        return [table.sequence == None, table.sequence]

    @staticmethod
    def default_type():
        return 'line'

    def get_move_done(self, name):
        Uom = Pool().get('product.uom')
        done = True
        if self.type != 'line' or not self.product:
            return True
        if self.product.type == 'service':
            return True
        skip_ids = set(x.id for x in self.moves_recreated
            + self.moves_ignored)
        quantity = self.quantity
        for move in self.moves:
            if move.state != 'done' \
                    and move.id not in skip_ids:
                done = False
                break
            quantity -= Uom.compute_qty(move.uom, move.quantity, self.unit)
        if done:
            if quantity > 0.0:
                done = False
        return done

    def get_move_exception(self, name):
        skip_ids = set(x.id for x in self.moves_ignored
            + self.moves_recreated)
        for move in self.moves:
            if move.state == 'cancel' \
                    and move.id not in skip_ids:
                return True
        return False

    @fields.depends('unit')
    def on_change_with_unit_digits(self, name=None):
        if self.unit:
            return self.unit.digits
        return 2

    def _get_tax_rule_pattern(self):
        '''
        Get tax rule pattern
        '''
        return {}

    def _get_context_purchase_price(self):
        context = {}
        if getattr(self, 'purchase', None):
            if getattr(self.purchase, 'currency', None):
                context['currency'] = self.purchase.currency.id
            if getattr(self.purchase, 'party', None):
                context['supplier'] = self.purchase.party.id
            if getattr(self.purchase, 'purchase_date', None):
                context['purchase_date'] = self.purchase.purchase_date
        if self.unit:
            context['uom'] = self.unit.id
        else:
            self.product.purchase_uom.id
        return context

    @fields.depends('product', 'unit', 'quantity', 'description',
        '_parent_purchase.party', '_parent_purchase.currency',
        '_parent_purchase.purchase_date')
    def on_change_product(self):
        Product = Pool().get('product.product')

        if not self.product:
            return {}
        res = {}

        context = {}
        party = None
        if self.purchase and self.purchase.party:
            party = self.purchase.party
            if party.lang:
                context['language'] = party.lang.code

        category = self.product.purchase_uom.category
        if not self.unit or self.unit not in category.uoms:
            res['unit'] = self.product.purchase_uom.id
            self.unit = self.product.purchase_uom
            res['unit.rec_name'] = self.product.purchase_uom.rec_name
            res['unit_digits'] = self.product.purchase_uom.digits

        with Transaction().set_context(self._get_context_purchase_price()):
            res['unit_price'] = Product.get_purchase_price([self.product],
                abs(self.quantity or 0))[self.product.id]
            if res['unit_price']:
                res['unit_price'] = res['unit_price'].quantize(
                    Decimal(1) / 10 ** self.__class__.unit_price.digits[1])
        res['taxes'] = []
        pattern = self._get_tax_rule_pattern()
        for tax in self.product.supplier_taxes_used:
            if party and party.supplier_tax_rule:
                tax_ids = party.supplier_tax_rule.apply(tax, pattern)
                if tax_ids:
                    res['taxes'].extend(tax_ids)
                continue
            res['taxes'].append(tax.id)
        if party and party.supplier_tax_rule:
            tax_ids = party.supplier_tax_rule.apply(None, pattern)
            if tax_ids:
                res['taxes'].extend(tax_ids)

        if not self.description:
            with Transaction().set_context(context):
                res['description'] = Product(self.product.id).rec_name

        self.unit_price = res['unit_price']
        self.type = 'line'
        res['amount'] = self.on_change_with_amount()
        return res

    @fields.depends('product')
    def on_change_with_product_uom_category(self, name=None):
        if self.product:
            return self.product.default_uom_category.id

    @fields.depends('product', 'quantity', 'unit',
        '_parent_purchase.currency', '_parent_purchase.party',
        '_parent_purchase.purchase_date')
    def on_change_quantity(self):
        Product = Pool().get('product.product')

        if not self.product:
            return {}
        res = {}

        with Transaction().set_context(self._get_context_purchase_price()):
            res['unit_price'] = Product.get_purchase_price([self.product],
                abs(self.quantity or 0))[self.product.id]
            if res['unit_price']:
                res['unit_price'] = res['unit_price'].quantize(
                    Decimal(1) / 10 ** self.__class__.unit_price.digits[1])
        return res

    @fields.depends('product', 'quantity', 'unit',
        '_parent_purchase.currency', '_parent_purchase.party')
    def on_change_unit(self):
        return self.on_change_quantity()

    @fields.depends('type', 'quantity', 'unit_price', 'unit',
        '_parent_purchase.currency')
    def on_change_with_amount(self):
        if self.type == 'line':
            currency = self.purchase.currency if self.purchase else None
            amount = Decimal(str(self.quantity or '0.0')) * \
                (self.unit_price or Decimal('0.0'))
            if currency:
                return currency.round(amount)
            return amount
        return Decimal('0.0')

    def get_amount(self, name):
        if self.type == 'line':
            return self.on_change_with_amount()
        elif self.type == 'subtotal':
            amount = Decimal('0.0')
            for line2 in self.purchase.lines:
                if line2.type == 'line':
                    amount += line2.purchase.currency.round(
                        Decimal(str(line2.quantity)) * line2.unit_price)
                elif line2.type == 'subtotal':
                    if self == line2:
                        break
                    amount = Decimal('0.0')
            return amount
        return Decimal('0.0')

    def get_from_location(self, name):
        if self.quantity >= 0:
            return self.purchase.party.supplier_location.id
        elif self.purchase.warehouse:
            return self.purchase.warehouse.storage_location.id

    def get_to_location(self, name):
        if self.quantity >= 0:
            if self.purchase.warehouse:
                return self.purchase.warehouse.input_location.id
        else:
            return self.purchase.party.supplier_location.id

    @fields.depends('product', 'quantity',
        '_parent_purchase.purchase_date', '_parent_purchase.party')
    def on_change_with_delivery_date(self, name=None):
        if (self.product
                and self.quantity > 0
                and self.purchase and self.purchase.party
                and self.product.product_suppliers):
            date = self.purchase.purchase_date if self.purchase else None
            for product_supplier in self.product.product_suppliers:
                if product_supplier.party == self.purchase.party:
                    delivery_date = product_supplier.compute_supply_date(
                        date=date)
                    if delivery_date == datetime.date.max:
                        return None
                    return delivery_date

    def get_invoice_line(self, invoice_type):
        '''
        Return a list of invoice line for purchase line
        '''
        pool = Pool()
        Uom = pool.get('product.uom')
        Property = pool.get('ir.property')
        InvoiceLine = pool.get('account.invoice.line')

        invoice_line = InvoiceLine()
        invoice_line.type = self.type
        invoice_line.description = self.description
        invoice_line.note = self.note
        invoice_line.origin = self
        if self.type != 'line':
            if (self.purchase.invoice_method == 'order'
                    and not self.invoice_lines
                    and ((all(l.quantity >= 0 for l in self.purchase.lines
                                if l.type == 'line')
                            and invoice_type == 'in_invoice')
                        or (all(l.quantity <= 0 for l in self.purchase.lines
                                if l.type == 'line')
                            and invoice_type == 'in_credit_note'))):
                return [invoice_line]
            else:
                return []
        if (invoice_type == 'in_invoice') != (self.quantity >= 0):
            return []

        stock_moves = []
        if (self.purchase.invoice_method == 'order'
                or not self.product
                or self.product.type == 'service'):
            quantity = abs(self.quantity)
            stock_moves = self.moves
        else:
            quantity = 0.0
            for move in self.moves:
                if move.state == 'done':
                    quantity += Uom.compute_qty(move.uom, move.quantity,
                        self.unit)
                    if move.invoiced_quantity < move.quantity:
                        stock_moves.append(move)
        invoice_line.stock_moves = stock_moves

        skip_ids = set(l.id for i in self.purchase.invoices_recreated
            for l in i.lines)
        for old_invoice_line in self.invoice_lines:
            if old_invoice_line.type != 'line':
                continue
            if old_invoice_line.id not in skip_ids:
                quantity -= Uom.compute_qty(old_invoice_line.unit,
                        old_invoice_line.quantity, self.unit)

        rounding = self.unit.rounding if self.unit else 0.01
        invoice_line.quantity = Uom.round(quantity, rounding)
        if invoice_line.quantity <= 0:
            return []

        invoice_line.unit = self.unit
        invoice_line.product = self.product
        invoice_line.unit_price = self.unit_price
        invoice_line.taxes = self.taxes
        invoice_line.invoice_type = invoice_type
        if self.product:
            invoice_line.account = self.product.account_expense_used
            if not invoice_line.account:
                self.raise_user_error('missing_account_expense', {
                        'product': invoice_line.product.rec_name,
                        'purchase': self.purchase.rec_name,
                        })
        else:
            for model in ('product.template', 'product.category'):
                invoice_line.account = Property.get('account_expense', model)
                if invoice_line.account:
                    break
            if not invoice_line.account:
                self.raise_user_error('missing_account_expense_property',
                    {'purchase': self.purchase.rec_name})
        return [invoice_line]

    @classmethod
    def copy(cls, lines, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default['moves'] = None
        default['moves_ignored'] = None
        default['moves_recreated'] = None
        default['invoice_lines'] = None
        return super(PurchaseLine, cls).copy(lines, default=default)

    def get_move(self):
        '''
        Return move values for purchase line
        '''
        pool = Pool()
        Uom = pool.get('product.uom')
        Move = pool.get('stock.move')

        if self.type != 'line':
            return
        if not self.product:
            return
        if self.product.type == 'service':
            return
        skip = set(self.moves_recreated)
        quantity = abs(self.quantity)
        for move in self.moves:
            if move not in skip:
                quantity -= Uom.compute_qty(move.uom, move.quantity,
                    self.unit)

        quantity = Uom.round(quantity, self.unit.rounding)
        if quantity <= 0:
            return

        if not self.purchase.party.supplier_location:
            self.raise_user_error('supplier_location_required', {
                    'purchase': self.purchase.rec_name,
                    'line': self.rec_name,
                    })
        move = Move()
        move.quantity = quantity
        move.uom = self.unit
        move.product = self.product
        move.from_location = self.from_location
        move.to_location = self.to_location
        move.state = 'draft'
        move.company = self.purchase.company
        move.unit_price = self.unit_price
        move.currency = self.purchase.currency
        move.planned_date = self.delivery_date
        move.invoice_lines = [l for l in self.invoice_lines
            if not l.stock_moves]
        move.origin = self
        return move

    def create_move(self):
        '''
        Create move line
        '''
        move = self.get_move()
        if not move:
            return
        move.save()
        return move


class PurchaseLineTax(ModelSQL):
    'Purchase Line - Tax'
    __name__ = 'purchase.line-account.tax'
    _table = 'purchase_line_account_tax'
    line = fields.Many2One('purchase.line', 'Purchase Line',
            ondelete='CASCADE', select=True, required=True,
            domain=[('type', '=', 'line')])
    tax = fields.Many2One('account.tax', 'Tax', ondelete='RESTRICT',
            select=True, required=True, domain=[('parent', '=', None)])


class PurchaseLineIgnoredMove(ModelSQL):
    'Purchase Line - Ignored Move'
    __name__ = 'purchase.line-ignored-stock.move'
    _table = 'purchase_line_moves_ignored_rel'
    purchase_line = fields.Many2One('purchase.line', 'Purchase Line',
            ondelete='CASCADE', select=True, required=True)
    move = fields.Many2One('stock.move', 'Move', ondelete='RESTRICT',
            select=True, required=True)


class PurchaseLineRecreatedMove(ModelSQL):
    'Purchase Line - Ignored Move'
    __name__ = 'purchase.line-recreated-stock.move'
    _table = 'purchase_line_moves_recreated_rel'
    purchase_line = fields.Many2One('purchase.line', 'Purchase Line',
            ondelete='CASCADE', select=True, required=True)
    move = fields.Many2One('stock.move', 'Move', ondelete='RESTRICT',
            select=True, required=True)


class PurchaseReport(CompanyReport):
    __name__ = 'purchase.purchase'


class OpenSupplier(Wizard):
    'Open Suppliers'
    __name__ = 'purchase.open_supplier'
    start_state = 'open_'
    open_ = StateAction('party.act_party_form')

    def do_open_(self, action):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        Wizard = pool.get('ir.action.wizard')
        Purchase = pool.get('purchase.purchase')
        cursor = Transaction().cursor
        purchase = Purchase.__table__()

        cursor.execute(*purchase.select(purchase.party,
                group_by=purchase.party))
        supplier_ids = [line[0] for line in cursor.fetchall()]
        action['pyson_domain'] = PYSONEncoder().encode(
            [('id', 'in', supplier_ids)])

        model_data, = ModelData.search([
                ('fs_id', '=', 'act_open_supplier'),
                ('module', '=', 'purchase'),
                ], limit=1)
        wizard = Wizard(model_data.db_id)

        action['name'] = wizard.name
        return action, {}


class HandleShipmentExceptionAsk(ModelView):
    'Handle Shipment Exception'
    __name__ = 'purchase.handle.shipment.exception.ask'
    recreate_moves = fields.Many2Many(
        'stock.move', None, None, 'Recreate Moves',
        domain=[('id', 'in', Eval('domain_moves'))], depends=['domain_moves'],
        help=('The selected moves will be recreated. '
            'The other ones will be ignored.'))
    domain_moves = fields.Many2Many(
        'stock.move', None, None, 'Domain Moves')

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor
        model = Table('ir_model')
        # Migration from 1.2: packing renamed into shipment
        cursor.execute(*model.update(
                columns=[model.model],
                values=[Overlay(model.model, 'shipment',
                        Position('packing', model.model),
                        len('packing'))],
                where=model.model.like('%packing%')
                & (model.module == module_name)))
        super(HandleShipmentExceptionAsk, cls).__register__(module_name)


class HandleShipmentException(Wizard):
    'Handle Shipment Exception'
    __name__ = 'purchase.handle.shipment.exception'
    start_state = 'ask'
    ask = StateView('purchase.handle.shipment.exception.ask',
        'purchase.handle_shipment_exception_ask_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Ok', 'handle', 'tryton-ok', default=True),
            ])
    handle = StateTransition()

    def default_ask(self, fields):
        Purchase = Pool().get('purchase.purchase')

        purchase = Purchase(Transaction().context['active_id'])

        moves = []
        for line in purchase.lines:
            skip = set(line.moves_ignored + line.moves_recreated)
            for move in line.moves:
                if move.state == 'cancel' and move not in skip:
                    moves.append(move.id)
        return {
            'recreate_moves': moves,
            'domain_moves': moves,
            }

    def transition_handle(self):
        pool = Pool()
        Purchase = pool.get('purchase.purchase')
        PurchaseLine = pool.get('purchase.line')
        to_recreate = self.ask.recreate_moves
        domain_moves = self.ask.domain_moves

        purchase = Purchase(Transaction().context['active_id'])

        for line in purchase.lines:
            moves_ignored = []
            moves_recreated = []
            skip = set(line.moves_ignored)
            skip.update(line.moves_recreated)
            for move in line.moves:
                if move not in domain_moves or move in skip:
                    continue
                if move in to_recreate:
                    moves_recreated.append(move.id)
                else:
                    moves_ignored.append(move.id)

            PurchaseLine.write([line], {
                'moves_ignored': [('add', moves_ignored)],
                'moves_recreated': [('add', moves_recreated)],
                })

        Purchase.process([purchase])
        return 'end'


class HandleInvoiceExceptionAsk(ModelView):
    'Handle Invoice Exception'
    __name__ = 'purchase.handle.invoice.exception.ask'
    recreate_invoices = fields.Many2Many(
        'account.invoice', None, None, 'Recreate Invoices',
        domain=[('id', 'in', Eval('domain_invoices'))],
        depends=['domain_invoices'],
        help=('The selected invoices will be recreated. '
            'The other ones will be ignored.'))
    domain_invoices = fields.Many2Many(
        'account.invoice', None, None, 'Domain Invoices')


class HandleInvoiceException(Wizard):
    'Handle Invoice Exception'
    __name__ = 'purchase.handle.invoice.exception'
    start_state = 'ask'
    ask = StateView('purchase.handle.invoice.exception.ask',
        'purchase.handle_invoice_exception_ask_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Ok', 'handle', 'tryton-ok', default=True),
            ])
    handle = StateTransition()

    def default_ask(self, fields):
        Purchase = Pool().get('purchase.purchase')

        purchase = Purchase(Transaction().context['active_id'])
        skip = set(purchase.invoices_ignored)
        skip.update(purchase.invoices_recreated)
        invoices = []
        for invoice in purchase.invoices:
            if invoice.state == 'cancel' and invoice not in skip:
                invoices.append(invoice.id)
        return {
            'recreate_invoices': invoices,
            'domain_invoices': invoices,
            }

    def transition_handle(self):
        Purchase = Pool().get('purchase.purchase')
        to_recreate = self.ask.recreate_invoices
        domain_invoices = self.ask.domain_invoices

        purchase = Purchase(Transaction().context['active_id'])

        skip = set(purchase.invoices_ignored)
        skip.update(purchase.invoices_recreated)
        invoices_ignored = []
        invoices_recreated = []
        for invoice in purchase.invoices:
            if invoice not in domain_invoices or invoice in skip:
                continue
            if invoice in to_recreate:
                invoices_recreated.append(invoice.id)
            else:
                invoices_ignored.append(invoice.id)

        Purchase.write([purchase], {
            'invoices_ignored': [('add', invoices_ignored)],
            'invoices_recreated': [('add', invoices_recreated)],
            })

        Purchase.process([purchase])
        return 'end'
