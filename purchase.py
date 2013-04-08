#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import datetime
from itertools import chain
from decimal import Decimal
from trytond.model import Workflow, ModelView, ModelSQL, fields
from trytond.modules.company import CompanyReport
from trytond.wizard import Wizard, StateAction, StateView, StateTransition, \
    Button
from trytond.backend import TableHandler
from trytond.pyson import Eval, Bool, If, PYSONEncoder, Id
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta

__all__ = ['Purchase', 'PurchaseInvoice', 'PurchaseIgnoredInvoice',
    'PurchaseRecreadtedInvoice', 'PurchaseLine', 'PurchaseLineTax',
    'PurchaseLineIgnoredMove',
    'PurchaseLineRecreatedMove', 'PurchaseReport', 'Template', 'Product',
    'ProductSupplier', 'ProductSupplierPrice', 'ShipmentIn',
    'ShipmentInReturn', 'Move', 'OpenSupplier', 'HandleShipmentExceptionAsk',
    'HandleShipmentException', 'HandleInvoiceExceptionAsk',
    'HandleInvoiceException']
__metaclass__ = PoolMeta

_STATES = {
    'readonly': Eval('state') != 'draft',
    }
_DEPENDS = ['state']


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
                Eval('context', {}).get('company', 0)),
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
        'Payment Term', required=True, states=_STATES, depends=_DEPENDS)
    party = fields.Many2One('party.party', 'Party',
            required=True, states=_STATES, on_change=['party', 'payment_term'],
            select=True, depends=_DEPENDS)
    party_lang = fields.Function(fields.Char('Party Language',
            on_change_with=['party']), 'on_change_with_party_lang')
    invoice_address = fields.Many2One('party.address', 'Invoice Address',
        domain=[('party', '=', Eval('party'))], states=_STATES,
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
    currency_digits = fields.Function(fields.Integer('Currency Digits',
            on_change_with=['currency']), 'on_change_with_currency_digits')
    lines = fields.One2Many('purchase.line', 'purchase', 'Lines',
        states=_STATES, on_change=['lines', 'currency', 'party'],
        depends=_DEPENDS)
    comment = fields.Text('Comment')
    untaxed_amount = fields.Function(fields.Numeric('Untaxed',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']), 'get_untaxed_amount')
    untaxed_amount_cache = fields.Numeric('Untaxed Cache',
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    tax_amount = fields.Function(fields.Numeric('Tax',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']), 'get_tax_amount')
    tax_amount_cache = fields.Numeric('Tax Cache',
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    total_amount = fields.Function(fields.Numeric('Total',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']), 'get_total_amount')
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
    invoices = fields.Many2Many('purchase.purchase-account.invoice',
            'purchase', 'invoice', 'Invoices', readonly=True)
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
                'invoice_address_required': ('Invoice address must be '
                    'defined for quotation of sale "%s".'),
                'warehouse_required': ('A warehouse must be defined for '
                    'quotation of sale "%s".'),
                'missing_account_payable': ('Missing "Account Payable" on '
                    'party "%s".'),
                'delete_cancel': ('Purchase "%s" must be cancelled before '
                    'deletion.'),
                })
        cls._transitions |= set((
                ('draft', 'quotation'),
                ('quotation', 'confirmed'),
                ('confirmed', 'confirmed'),
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
                    'invisible': Eval('state') != 'draft',
                    'readonly': ~Eval('lines', []),
                    },
                'confirm': {
                    'invisible': Eval('state') != 'quotation',
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
        cursor = Transaction().cursor
        # Migration from 1.2: packing renamed into shipment
        cursor.execute("UPDATE ir_model_data "
            "SET fs_id = REPLACE(fs_id, 'packing', 'shipment') "
            "WHERE fs_id like '%%packing%%' AND module = %s",
            (module_name,))
        cursor.execute("UPDATE ir_model_field "
            "SET relation = REPLACE(relation, 'packing', 'shipment'), "
                "name = REPLACE(name, 'packing', 'shipment') "
            "WHERE (relation like '%%packing%%' "
                "OR name like '%%packing%%') AND module = %s",
            (module_name,))
        table = TableHandler(cursor, cls, module_name)
        table.column_rename('packing_state', 'shipment_state')

        super(Purchase, cls).__register__(module_name)

        # Migration from 1.2: rename packing to shipment in
        # invoice_method values
        cursor.execute("UPDATE " + cls._table + " "
            "SET invoice_method = 'shipment' "
            "WHERE invoice_method = 'packing'")

        table = TableHandler(cursor, cls, module_name)
        # Migration from 2.2: warehouse is no more required
        table.not_null_action('warehouse', 'remove')

        # Migration from 2.2: purchase_date is no more required
        table.not_null_action('purchase_date', 'remove')

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

    def on_change_party(self):
        pool = Pool()
        PaymentTerm = pool.get('account.invoice.payment_term')
        Currency = pool.get('currency.currency')
        cursor = Transaction().cursor
        changes = {
            'invoice_address': None,
            'payment_term': None,
            'currency': self.default_currency(),
            'currency_digits': self.default_currency_digits(),
            }
        invoice_address = None
        payment_term = None
        if self.party:
            invoice_address = self.party.address_get(type='invoice')
            if self.party.supplier_payment_term:
                payment_term = self.party.supplier_payment_term

            subquery = cursor.limit_clause('SELECT currency '
                'FROM "' + self._table + '" '
                'WHERE party = %s '
                'ORDER BY id DESC', 10)
            cursor.execute('SELECT currency FROM (' + subquery + ') AS p '
                'GROUP BY currency '
                'ORDER BY COUNT(1) DESC', (self.party.id,))
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

    def on_change_with_currency_digits(self, name=None):
        if self.currency:
            return self.currency.digits
        return 2

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

    def on_change_lines(self):
        pool = Pool()
        Tax = pool.get('account.tax')
        Invoice = pool.get('account.invoice')

        changes = {
            'untaxed_amount': Decimal('0.0'),
            'tax_amount': Decimal('0.0'),
            'total_amount': Decimal('0.0'),
            }
        if self.lines:
            context = self.get_tax_context()
            taxes = {}
            for line in self.lines:
                if getattr(line, 'type', 'line') != 'line':
                    continue
                changes['untaxed_amount'] += line.amount or Decimal(0)

                with Transaction().set_context(context):
                    tax_list = Tax.compute(getattr(line, 'taxes', []),
                        line.unit_price or Decimal('0.0'),
                        line.quantity or 0.0)
                for tax in tax_list:
                    key, val = Invoice._compute_tax(tax, 'in_invoice')
                    if not key in taxes:
                        taxes[key] = val['amount']
                    else:
                        taxes[key] += val['amount']
            if self.currency:
                for value in taxes.itervalues():
                    changes['tax_amount'] += self.currency.round(value)
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

    def get_untaxed_amount(self, name):
        '''
        Return the untaxed amount for each purchases
        '''
        if (self.state in self._states_cached
                and self.untaxed_amount_cache is not None):
            return self.untaxed_amount_cache
        amount = sum((l.amount for l in self.lines
                if l.type == 'line'), Decimal(0))
        return self.currency.round(amount)

    def get_tax_amount(self, name):
        pool = Pool()
        Tax = pool.get('account.tax')
        Invoice = pool.get('account.invoice')

        if (self.state in self._states_cached
                and self.tax_amount_cache is not None):
            return self.tax_amount_cache
        context = self.get_tax_context()
        taxes = {}
        for line in self.lines:
            if line.type != 'line':
                continue
            with Transaction().set_context(context):
                tax_list = Tax.compute(line.taxes, line.unit_price,
                    line.quantity)
            # Don't round on each line to handle rounding error
            for tax in tax_list:
                key, val = Invoice._compute_tax(tax, 'in_invoice')
                if not key in taxes:
                    taxes[key] = val['amount']
                else:
                    taxes[key] += val['amount']
        amount = sum((self.currency.round(tax) for tax in taxes.itervalues()),
            Decimal(0))
        return self.currency.round(amount)

    def get_total_amount(self, name):
        if (self.state in self._states_cached
                and self.total_amount_cache is not None):
            return self.total_amount_cache
        return self.currency.round(self.untaxed_amount + self.tax_amount)

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
        names = clause[2].split(' - ', 1)
        purchases = cls.search(['OR',
                ('reference', clause[1], names[0]),
                ('supplier_reference', clause[1], names[0]),
                ], order=[])
        res = [('id', 'in', [p.id for p in purchases])]
        if len(names) != 1 and names[1]:
            res.append(('party', clause[1], names[1]))
        return res

    @classmethod
    def copy(cls, purchases, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default['state'] = 'draft'
        default['reference'] = None
        default['invoice_state'] = 'none'
        default['invoices'] = None
        default['invoices_ignored'] = None
        default['shipment_state'] = 'none'
        default.setdefault('purchase_date', None)
        return super(Purchase, cls).copy(purchases, default=default)

    def check_for_quotation(self):
        if not self.invoice_address:
            self.raise_user_error('invoice_address_required', (self.rec_name,))
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

        with Transaction().set_user(0, set_context=True):
            return Invoice(
                company=self.company,
                type=invoice_type,
                reference=self.reference,
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
        invoice.lines = list(chain.from_iterable(invoice_lines.itervalues()))
        invoice.save()

        with Transaction().set_user(0, set_context=True):
            Invoice.update_taxes([invoice])

        self.write([self], {
                'invoices': [('add', [invoice.id])],
                })
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
        with Transaction().set_user(0, set_context=True):
            return ShipmentInReturn(
                company=self.company,
                reference=self.reference,
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
        with Transaction().set_user(0, set_context=True):
            ShipmentInReturn.wait([return_shipment])
        return return_shipment

    def is_done(self):
        return ((self.invoice_state == 'paid'
                or self.invoice_method == 'manual')
            and self.shipment_state == 'received')

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
        cls.process(purchases)

    @classmethod
    @ModelView.button_action('purchase.wizard_invoice_handle_exception')
    def handle_invoice_exception(cls, purchases):
        pass

    @classmethod
    @ModelView.button_action('purchase.wizard_shipment_handle_exception')
    def handle_shipment_exception(cls, purchases):
        pass

    @classmethod
    def process(cls, purchases):
        done = []
        for purchase in purchases:
            if purchase.state in ('done', 'cancel'):
                continue
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
        if done:
            cls.write(done, {
                    'state': 'done',
                    })


class PurchaseInvoice(ModelSQL):
    'Purchase - Invoice'
    __name__ = 'purchase.purchase-account.invoice'
    _table = 'purchase_invoices_rel'
    purchase = fields.Many2One('purchase.purchase', 'Purchase',
            ondelete='CASCADE', select=True, required=True)
    invoice = fields.Many2One('account.invoice', 'Invoice',
            ondelete='RESTRICT', select=True, required=True)


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
    sequence = fields.Integer('Sequence',
        order_field='(%(table)s.sequence IS NULL) %(order)s, '
        '%(table)s.sequence %(order)s')
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
            }, on_change=['product', 'quantity', 'unit',
            '_parent_purchase.currency', '_parent_purchase.party',
            '_parent_purchase.purchase_date'],
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
        on_change=['product', 'quantity', 'unit', '_parent_purchase.currency',
            '_parent_purchase.party'],
        depends=['product', 'type', 'product_uom_category'])
    unit_digits = fields.Function(fields.Integer('Unit Digits',
            on_change_with=['unit']), 'on_change_with_unit_digits')
    product = fields.Many2One('product.product', 'Product',
        domain=[('purchasable', '=', True)],
        states={
            'invisible': Eval('type') != 'line',
            'readonly': ~Eval('_parent_purchase'),
            }, on_change=['product', 'unit', 'quantity', 'description',
            '_parent_purchase.party', '_parent_purchase.currency',
            '_parent_purchase.purchase_date'],
        context={
            'locations': If(Bool(Eval('_parent_purchase', {}).get(
                        'warehouse')),
                [Eval('_parent_purchase', {}).get('warehouse', None)],
                []),
            'stock_date_end': Eval('_parent_purchase', {}).get(
                'purchase_date'),
            'purchasable': True,
            'stock_skip_warehouse': True,
            }, depends=['type'])
    product_uom_category = fields.Function(
        fields.Many2One('product.uom.category', 'Product Uom Category',
            on_change_with=['product']),
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
                }, on_change_with=['type', 'quantity', 'unit_price', 'unit',
                '_parent_purchase.currency'],
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
            on_change_with=['product', '_parent_purchase.purchase_date',
                '_parent_purchase.party']),
        'on_change_with_delivery_date')

    @classmethod
    def __setup__(cls):
        super(PurchaseLine, cls).__setup__()
        cls._order.insert(0, ('sequence', 'ASC'))
        cls._error_messages.update({
                'supplier_location_required': ('Purchase "%(purchase)s" misses '
                    'the supplier location for line "%(line)s".'),
                'missing_account_expense': ('Product "%(product)s" of purchase '
                    '%(purchase)s misses an expense account.'),
                'missing_account_expense_property': ('Purchase "%(purchase)s" '
                    'misses an "account expense" default property.'),
                })

    @classmethod
    def __register__(cls, module_name):
        super(PurchaseLine, cls).__register__(module_name)
        cursor = Transaction().cursor
        table = TableHandler(cursor, cls, module_name)

        # Migration from 1.0 comment change into note
        if table.column_exist('comment'):
            cursor.execute('UPDATE "' + cls._table + '" '
                'SET note = comment')
            table.drop_column('comment', exception=True)

        # Migration from 2.4: drop required on sequence
        table.not_null_action('sequence', action='remove')

    @staticmethod
    def default_type():
        return 'line'

    def get_move_done(self, name):
        Uom = Pool().get('product.uom')
        done = True
        if not self.product:
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
                self.quantity or 0)[self.product.id]
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

    def on_change_with_product_uom_category(self, name=None):
        if self.product:
            return self.product.default_uom_category.id

    def on_change_quantity(self):
        Product = Pool().get('product.product')

        if not self.product:
            return {}
        res = {}

        with Transaction().set_context(self._get_context_purchase_price()):
            res['unit_price'] = Product.get_purchase_price([self.product],
                self.quantity or 0)[self.product.id]
            if res['unit_price']:
                res['unit_price'] = res['unit_price'].quantize(
                    Decimal(1) / 10 ** self.__class__.unit_price.digits[1])
        return res

    def on_change_unit(self):
        return self.on_change_quantity()

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
            return self.purchase.currency.round(
                Decimal(str(self.quantity)) * self.unit_price)
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

    def on_change_with_delivery_date(self, name=None):
        if (self.product
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

        with Transaction().set_user(0, set_context=True):
            invoice_line = InvoiceLine()
        invoice_line.type = self.type
        invoice_line.description = self.description
        invoice_line.note = self.note
        if self.type != 'line':
            if (self.purchase.invoice_method == 'order'
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

        if (self.purchase.invoice_method == 'order'
                or not self.product
                or self.product.type == 'service'):
            quantity = abs(self.quantity)
        else:
            quantity = 0.0
            for move in self.moves:
                if move.state == 'done':
                    quantity += Uom.compute_qty(move.uom, move.quantity,
                        self.unit)

        skip_ids = set(l.id for i in self.purchase.invoices_recreated
            for l in i.lines)
        for old_invoice_line in self.invoice_lines:
            if old_invoice_line.type != 'line':
                continue
            if old_invoice_line.id not in skip_ids:
                quantity -= Uom.compute_qty(old_invoice_line.unit,
                        old_invoice_line.quantity, self.unit)
        invoice_line.quantity = quantity

        if invoice_line.quantity <= 0.0:
            return []
        invoice_line.unit = self.unit
        invoice_line.product = self.product
        invoice_line.unit_price = self.unit_price
        invoice_line.taxes = self.taxes
        if self.product:
            invoice_line.account = self.product.account_expense_used
            if not invoice_line.account:
                self.raise_user_error('missing_account_expense', {
                        'product': invoice_line.product.rec_name,
                        'purchase': invoice_line.purchase.rec_name,
                        })
        else:
            for model in ('product.template', 'product.category'):
                invoice_line.account = Property.get('account_expense', model)
                if invoice_line.account:
                    break
            if not invoice_line.account:
                self.raise_user_error('missing_account_expense_property',
                    (invoice_line.purchase.rec_name,))
        invoice_line.origin = self
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
        if quantity <= 0.0:
            return
        if not self.purchase.party.supplier_location:
            self.raise_user_error('supplier_location_required', {
                    'purchase': self.purchase.rec_name,
                    'line': self.rec_name,
                    })
        with Transaction().set_user(0, set_context=True):
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


class Template:
    __name__ = "product.template"
    purchasable = fields.Boolean('Purchasable', states={
            'readonly': ~Eval('active', True),
            }, depends=['active'])
    product_suppliers = fields.One2Many('purchase.product_supplier',
        'product', 'Suppliers', states={
            'readonly': ~Eval('active', True),
            'invisible': (~Eval('purchasable', False)
                | ~Eval('context', {}).get('company', 0)),
            }, depends=['active', 'purchasable'])
    purchase_uom = fields.Many2One('product.uom', 'Purchase UOM', states={
            'readonly': ~Eval('active'),
            'invisible': ~Eval('purchasable'),
            'required': Eval('purchasable', False),
            },
        domain=[('category', '=', Eval('default_uom_category'))],
        on_change_with=['default_uom', 'purchase_uom', 'purchasable'],
        depends=['active', 'purchasable', 'default_uom_category'])

    @classmethod
    def __setup__(cls):
        super(Template, cls).__setup__()
        cls._error_messages.update({
                'change_purchase_uom': ('Purchase prices are based '
                    'on the purchase uom, are you sure to change it?'),
                })
        required = ~Eval('account_category') & Eval('purchasable', False)
        if not cls.account_expense.states.get('required'):
            cls.account_expense.states['required'] = required
        else:
            cls.account_expense.states['required'] = (
                cls.account_expense.states['required'] | required)
        if 'account_category' not in cls.account_expense.depends:
            cls.account_expense.depends.append('account_category')
        if 'purchasable' not in cls.account_expense.depends:
            cls.account_expense.depends.append('purchasable')

    @staticmethod
    def default_purchasable():
        return Transaction().context.get('purchasable') or False

    def on_change_with_purchase_uom(self):
        if self.default_uom:
            if self.purchase_uom:
                if self.default_uom.category == self.purchase_uom.category:
                    return self.purchase_uom.id
                else:
                    return self.default_uom.id
            else:
                return self.default_uom.id

    @classmethod
    def write(cls, templates, vals):
        if vals.get("purchase_uom"):
            for template in templates:
                if not template.purchase_uom:
                    continue
                if template.purchase_uom.id == vals["purchase_uom"]:
                    continue
                for product in template.products:
                    if not product.product_suppliers:
                        continue
                    cls.raise_user_warning(
                            '%s@product_template' % template.id,
                            'change_purchase_uom')
        super(Template, cls).write(templates, vals)


class Product:
    __name__ = 'product.product'

    @classmethod
    def get_purchase_price(cls, products, quantity=0):
        '''
        Return purchase price for product ids.
        The context that can have as keys:
            uom: the unit of measure
            supplier: the supplier party id
            currency: the currency id for the returned price
        '''
        pool = Pool()
        Uom = pool.get('product.uom')
        User = pool.get('res.user')
        Currency = pool.get('currency.currency')
        Date = pool.get('ir.date')

        today = Date.today()
        res = {}

        uom = None
        if Transaction().context.get('uom'):
            uom = Uom(Transaction().context['uom'])

        currency = None
        if Transaction().context.get('currency'):
            currency = Currency(Transaction().context['currency'])

        user = User(Transaction().user)

        for product in products:
            res[product.id] = product.cost_price
            default_uom = product.default_uom
            default_currency = (user.company.currency if user.company
                else None)
            if not uom:
                uom = default_uom
            if (Transaction().context.get('supplier')
                    and product.product_suppliers):
                supplier_id = Transaction().context['supplier']
                for product_supplier in product.product_suppliers:
                    if product_supplier.party.id == supplier_id:
                        for price in product_supplier.prices:
                            if Uom.compute_qty(product.purchase_uom,
                                    price.quantity, uom) <= quantity:
                                res[product.id] = price.unit_price
                                default_uom = product.purchase_uom
                                default_currency = product_supplier.currency
                        break
            res[product.id] = Uom.compute_price(default_uom, res[product.id],
                uom)
            if currency and default_currency:
                date = Transaction().context.get('purchase_date') or today
                with Transaction().set_context(date=date):
                    res[product.id] = Currency.compute(default_currency,
                        res[product.id], currency, round=False)
        return res


class ProductSupplier(ModelSQL, ModelView):
    'Product Supplier'
    __name__ = 'purchase.product_supplier'
    product = fields.Many2One('product.template', 'Product', required=True,
            ondelete='CASCADE', select=True)
    party = fields.Many2One('party.party', 'Supplier', required=True,
            ondelete='CASCADE', select=True, on_change=['party'])
    name = fields.Char('Name', size=None, translate=True, select=True)
    code = fields.Char('Code', size=None, select=True)
    sequence = fields.Integer('Sequence',
        order_field='(%(table)s.sequence IS NULL) %(order)s, '
        '%(table)s.sequence %(order)s')
    prices = fields.One2Many('purchase.product_supplier.price',
            'product_supplier', 'Prices')
    company = fields.Many2One('company.company', 'Company', required=True,
        ondelete='CASCADE', select=True,
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', 0)),
            ])
    delivery_time = fields.Integer('Delivery Time', help="In number of days")
    currency = fields.Many2One('currency.currency', 'Currency', required=True,
        ondelete='RESTRICT')

    @classmethod
    def __setup__(cls):
        super(ProductSupplier, cls).__setup__()
        cls._order.insert(0, ('sequence', 'ASC'))

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor
        table = TableHandler(cursor, cls, module_name)

        # Migration from 2.2 new field currency
        created_currency = table.column_exist('currency')

        super(ProductSupplier, cls).__register__(module_name)

        # Migration from 2.2 fill currency
        if not created_currency:
            Company = Pool().get('company.company')
            limit = cursor.IN_MAX
            cursor.execute('SELECT count(id) FROM "' + cls._table + '"')
            product_supplier_count, = cursor.fetchone()
            for offset in range(0, product_supplier_count, limit):
                cursor.execute(cursor.limit_clause(
                        'SELECT p.id, c.currency '
                        'FROM "' + cls._table + '" AS p '
                        'INNER JOIN "' + Company._table + '" AS c '
                            'ON p.company = c.id '
                        'ORDER BY p.id',
                        limit, offset))
                for product_supplier_id, currency_id in cursor.fetchall():
                    cursor.execute('UPDATE "' + cls._table + '" '
                        'SET currency = %s '
                        'WHERE id = %s', (currency_id, product_supplier_id))

        # Migration from 2.4: drop required on sequence
        table.not_null_action('sequence', action='remove')

        # Migration from 2.6: drop required on delivery_time
        table.not_null_action('delivery_time', action='remove')

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_currency():
        Company = Pool().get('company.company')
        if Transaction().context.get('company'):
            company = Company(Transaction().context['company'])
            return company.currency.id

    def on_change_party(self):
        cursor = Transaction().cursor
        changes = {
            'currency': self.default_currency(),
            }
        if self.party:
            cursor.execute('SELECT currency FROM "' + self._table + '" '
                'WHERE party = %s '
                'GROUP BY currency '
                'ORDER BY COUNT(1) DESC', (self.party.id,))
            row = cursor.fetchone()
            if row:
                changes['currency'], = row
        return changes

    def compute_supply_date(self, date=None):
        '''
        Compute the supply date for the Product Supplier at the given date
        '''
        Date = Pool().get('ir.date')

        if not date:
            date = Date.today()
        if self.delivery_time is None:
            return datetime.date.max
        return date + datetime.timedelta(self.delivery_time)

    def compute_purchase_date(self, date):
        '''
        Compute the purchase date for the Product Supplier at the given date
        '''
        Date = Pool().get('ir.date')

        if self.delivery_time is None:
            return Date.today()
        return date - datetime.timedelta(self.delivery_time)


class ProductSupplierPrice(ModelSQL, ModelView):
    'Product Supplier Price'
    __name__ = 'purchase.product_supplier.price'
    product_supplier = fields.Many2One('purchase.product_supplier',
            'Supplier', required=True, ondelete='CASCADE')
    quantity = fields.Float('Quantity', required=True, help='Minimal quantity')
    unit_price = fields.Numeric('Unit Price', required=True, digits=(16, 4))

    @classmethod
    def __setup__(cls):
        super(ProductSupplierPrice, cls).__setup__()
        cls._order.insert(0, ('quantity', 'ASC'))

    @staticmethod
    def default_quantity():
        return 0.0


class ShipmentIn:
    __name__ = 'stock.shipment.in'

    @classmethod
    def __setup__(cls):
        super(ShipmentIn, cls).__setup__()
        add_remove = [
            ('supplier', '=', Eval('supplier')),
            ]
        if not cls.incoming_moves.add_remove:
            cls.incoming_moves.add_remove = add_remove
        else:
            cls.incoming_moves.add_remove = [
                add_remove,
                cls.incoming_moves.add_remove,
                ]
        if 'supplier' not in cls.incoming_moves.depends:
            cls.incoming_moves.depends.append('supplier')

        cls._error_messages.update({
                'reset_move': ('You cannot reset to draft move "%s" because '
                    'it was generated by a purchase.'),
                })

    @classmethod
    def write(cls, shipments, vals):
        pool = Pool()
        Purchase = pool.get('purchase.purchase')
        PurchaseLine = pool.get('purchase.line')

        super(ShipmentIn, cls).write(shipments, vals)

        if 'state' in vals and vals['state'] in ('received', 'cancel'):
            purchases = []
            move_ids = []
            for shipment in shipments:
                move_ids.extend([x.id for x in shipment.incoming_moves])

            purchase_lines = PurchaseLine.search([
                    ('moves', 'in', move_ids),
                    ])
            if purchase_lines:
                for purchase_line in purchase_lines:
                    if purchase_line.purchase not in purchases:
                        purchases.append(purchase_line.purchase)

            with Transaction().set_user(0, set_context=True):
                purchases = Purchase.browse([p.id for p in purchases])
                Purchase.process(purchases)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, shipments):
        PurchaseLine = Pool().get('purchase.line')
        for shipment in shipments:
            for move in shipment.incoming_moves:
                if (move.state == 'cancel'
                        and isinstance(move.origin, PurchaseLine)):
                    cls.raise_user_error('reset_move', (move.rec_name,))

        return super(ShipmentIn, cls).draft(shipments)


class ShipmentInReturn:
    __name__ = 'stock.shipment.in.return'

    @classmethod
    def __setup__(cls):
        super(ShipmentInReturn, cls).__setup__()
        cls._error_messages.update({
                'reset_move': ('You cannot reset to draft a move generated '
                    'by a purchase.'),
                })

    @classmethod
    def write(cls, shipments, vals):
        pool = Pool()
        Purchase = pool.get('purchase.purchase')
        PurchaseLine = pool.get('purchase.line')

        super(ShipmentInReturn, cls).write(shipments, vals)

        if 'state' in vals and vals['state'] == 'done':
            move_ids = []
            for shipment in shipments:
                move_ids.extend([x.id for x in shipment.moves])

            purchase_lines = PurchaseLine.search([
                    ('moves', 'in', move_ids),
                    ])
            purchases = set()
            if purchase_lines:
                for purchase_line in purchase_lines:
                    purchases.add(purchase_line.purchase)

            with Transaction().set_user(0, set_context=True):
                purchases = Purchase.browse([p.id for p in purchases])
                Purchase.process(purchases)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, shipments):
        PurchaseLine = Pool().get('purchase.line')
        for shipment in shipments:
            for move in shipment.moves:
                if (move.state == 'cancel'
                        and isinstance(move.origin, PurchaseLine)):
                    cls.raise_user_error('reset_move')

        return super(ShipmentInReturn, cls).draft(shipments)


class Move(ModelSQL, ModelView):
    __name__ = 'stock.move'
    purchase = fields.Function(fields.Many2One('purchase.purchase', 'Purchase',
            states={
                'invisible': ~Eval('purchase_visible', False),
                },
            depends=['purchase_visible']), 'get_purchase',
        searcher='search_purchase')
    purchase_quantity = fields.Function(fields.Float('Purchase Quantity',
            digits=(16, Eval('unit_digits', 2)),
            states={
                'invisible': ~Eval('purchase_visible', False),
                },
            depends=['purchase_visible', 'unit_digits']),
        'get_purchase_fields')
    purchase_unit = fields.Function(fields.Many2One('product.uom',
            'Purchase Unit', states={
                'invisible': ~Eval('purchase_visible', False),
                }, depends=['purchase_visible']), 'get_purchase_fields')
    purchase_unit_digits = fields.Function(fields.Integer(
        'Purchase Unit Digits'), 'get_purchase_fields')
    purchase_unit_price = fields.Function(fields.Numeric('Purchase Unit Price',
            digits=(16, 4), states={
                'invisible': ~Eval('purchase_visible', False),
                }, depends=['purchase_visible']), 'get_purchase_fields')
    purchase_currency = fields.Function(fields.Many2One('currency.currency',
            'Purchase Currency', states={
                'invisible': ~Eval('purchase_visible', False),
                }, depends=['purchase_visible']), 'get_purchase_fields')
    purchase_visible = fields.Function(fields.Boolean('Purchase Visible',
        on_change_with=['from_location']), 'on_change_with_purchase_visible')
    supplier = fields.Function(fields.Many2One('party.party', 'Supplier'),
        'get_supplier', searcher='search_supplier')
    purchase_exception_state = fields.Function(fields.Selection([
        ('', ''),
        ('ignored', 'Ignored'),
        ('recreated', 'Recreated'),
        ], 'Exception State'), 'get_purchase_exception_state')

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor

        super(Move, cls).__register__(module_name)

        table = TableHandler(cursor, cls, module_name)

        # Migration from 2.6: remove purchase_line
        if table.column_exist('purchase_line'):
            cursor.execute('UPDATE "' + cls._table + '" '
                'SET origin = \'purchase.line,\' || purchase_line '
                'WHERE purchase_line IS NOT NULL')
            table.drop_column('purchase_line')

    @classmethod
    def _get_origin(cls):
        models = super(Move, cls)._get_origin()
        models.append('purchase.line')
        return models

    def get_purchase(self, name):
        PurchaseLine = Pool().get('purchase.line')
        if isinstance(self.origin, PurchaseLine):
            return self.origin.purchase.id

    @classmethod
    def search_purchase(cls, name, clause):
        return [('origin.' + name,) + tuple(clause[1:]) + ('purchase.line',)]

    def get_purchase_exception_state(self, name):
        PurchaseLine = Pool().get('purchase.line')
        if not isinstance(self.origin, PurchaseLine):
            return ''
        if self in self.origin.moves_recreated:
            return 'recreated'
        if self in self.origin.moves_ignored:
            return 'ignored'

    def get_purchase_fields(self, name):
        PurchaseLine = Pool().get('purchase.line')
        if isinstance(self.origin, PurchaseLine):
            if name[9:] == 'currency':
                return self.origin.purchase.currency.id
            elif name[9:] in ('quantity', 'unit_digits', 'unit_price'):
                return getattr(self.origin, name[9:])
            else:
                return getattr(self.origin, name[9:]).id
        else:
            if name[9:] == 'quantity':
                return 0.0
            elif name[9:] == 'unit_digits':
                return 2

    def on_change_with_purchase_visible(self, name=None):
        if self.from_location:
            if self.from_location.type == 'supplier':
                return True
        return False

    def get_supplier(self, name):
        PurchaseLine = Pool().get('purchase.line')
        if isinstance(self.origin, PurchaseLine):
            return self.origin.purchase.party.id

    @classmethod
    def search_supplier(cls, name, clause):
        return [('origin.purchase.party',) + tuple(clause[1:]) +
            ('purchase.line',)]

    @classmethod
    def write(cls, moves, vals):
        pool = Pool()
        Purchase = pool.get('purchase.purchase')
        PurchaseLine = pool.get('purchase.line')

        super(Move, cls).write(moves, vals)
        if 'state' in vals and vals['state'] in ('cancel',):
            purchases = set()
            purchase_lines = PurchaseLine.search([
                    ('moves', 'in', [m.id for m in moves]),
                    ])
            if purchase_lines:
                for purchase_line in purchase_lines:
                    purchases.add(purchase_line.purchase)
            if purchases:
                with Transaction().set_user(0, set_context=True):
                    purchases = Purchase.browse([p.id for p in purchases])
                    Purchase.process(purchases)

    @classmethod
    def delete(cls, moves):
        pool = Pool()
        Purchase = pool.get('purchase.purchase')
        PurchaseLine = pool.get('purchase.line')

        purchases = set()
        purchase_lines = PurchaseLine.search([
                ('moves', 'in', [m.id for m in moves]),
                ])

        super(Move, cls).delete(moves)

        if purchase_lines:
            for purchase_line in purchase_lines:
                purchases.add(purchase_line.purchase)
            if purchases:
                with Transaction().set_user(0, set_context=True):
                    purchases = Purchase.browse([p.id for p in purchases])
                    Purchase.process(purchases)


class OpenSupplier(Wizard):
    'Open Suppliers'
    __name__ = 'purchase.open_supplier'
    start_state = 'open_'
    open_ = StateAction('party.act_party_form')

    def do_open_(self, action):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        Wizard = pool.get('ir.action.wizard')
        cursor = Transaction().cursor

        cursor.execute("SELECT DISTINCT(party) FROM purchase_purchase")
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
        # Migration from 1.2: packing renamed into shipment
        cursor.execute("UPDATE ir_model "
            "SET model = REPLACE(model, 'packing', 'shipment') "
            "WHERE model like '%%packing%%' AND module = %s",
            (module_name,))
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
            'to_recreate': moves,
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
            'to_recreate': invoices,
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
