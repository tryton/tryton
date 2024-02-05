# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.i18n import gettext
from trytond.model import Index, ModelSQL, ModelView, Workflow, fields
from trytond.modules.product import price_digits
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval, If
from trytond.transaction import Transaction

from .exceptions import AmendmentValidateError


class Purchase(metaclass=PoolMeta):
    __name__ = 'purchase.purchase'

    amendments = fields.One2Many(
        'purchase.amendment', 'purchase', "Amendments",
        states={
            'invisible': ((Eval('state') != 'processing')
                | ~Eval('amendments')),
            'readonly': Eval('state') != 'processing',
            })

    @classmethod
    def copy(cls, purchases, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('amendments')
        return super().copy(purchases, default=default)


class Amendment(Workflow, ModelSQL, ModelView):
    "Purchase Amendment"
    __name__ = 'purchase.amendment'

    purchase = fields.Many2One(
        'purchase.purchase', "Purchase", required=True,
        domain=[
            ('state', 'in', ['processing', 'done']),
            ],
        states={
            'readonly': (Eval('state') != 'draft') | Eval('lines', [0]),
            })
    date = fields.Date(
        "Date", required=True,
        states={
            'readonly': Eval('state') != 'draft',
            })
    description = fields.Char(
        "Description",
        states={
            'readonly': Eval('state') != 'draft',
            })
    state = fields.Selection([
            ('draft', "Draft"),
            ('validated', "Validated"),
            ], "State", readonly=True, required=True, sort=False)
    lines = fields.One2Many(
        'purchase.amendment.line', 'amendment', "Lines",
        states={
            'readonly': (
                (Eval('state') != 'draft')
                | ~Eval('purchase')),
            })

    @classmethod
    def __setup__(cls):
        super(Amendment, cls).__setup__()
        t = cls.__table__()
        cls._sql_indexes.add(
            Index(
                t,
                (t.state, Index.Equality()),
                where=t.state == 'draft'))
        cls._order = [
            ('date', 'DESC'),
            ('id', 'DESC'),
            ]
        cls._transitions |= {
            ('draft', 'validated'),
            }
        cls._buttons.update({
                'validate_amendment': {
                    'invisible': Eval('state') != 'draft',
                    'depends': ['state'],
                    },
                })

    @classmethod
    def default_date(cls):
        return Pool().get('ir.date').today()

    @classmethod
    def default_state(cls):
        return 'draft'

    @classmethod
    @ModelView.button
    @Workflow.transition('validated')
    def validate_amendment(cls, amendments):
        pool = Pool()
        Purchase = pool.get('purchase.purchase')
        transaction = Transaction()
        context = transaction.context
        purchases = set()
        for amendment in amendments:
            purchase = amendment.purchase
            if purchase in purchases:
                raise AmendmentValidateError(
                    gettext('purchase_amendment.msg_one_purchase_at_time',
                        purchase=purchase.rec_name))
            purchases.add(purchase)
            purchase.revision += 1
            for line in amendment.lines:
                line.apply(purchase)
            # Force saved lines
            purchase.lines = purchase.lines
            # Force recompute cache
            purchase.untaxed_amount_cache = None
            purchase.tax_amount_cache = None
            purchase.total_amount_cache = None

        Purchase.save(purchases)
        Purchase.store_cache(purchases)
        cls._clear_purchase(purchases)
        with transaction.set_context(
                queue_batch=context.get('queue_batch', True)):
            Purchase.__queue__.process(purchases)

    @classmethod
    def _clear_purchase(cls, purchases):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        InvoiceLine = pool.get('account.invoice.line')
        Move = pool.get('stock.move')

        invoices = set()
        invoice_lines = set()
        moves = set()
        for purchase in purchases:
            for invoice in purchase.invoices:
                if invoice.state == 'draft':
                    invoices.add(invoice)

            for line in purchase.lines:
                for invoice_line in line.invoice_lines:
                    if invoice_line.invoice_state == 'draft':
                        invoice_lines.add(invoice_line)
                moves.update(cls._stock_moves(line))

        InvoiceLine.delete(invoice_lines)
        Move.delete(moves)

        Invoice.update_taxes([i for i in invoices if i.lines])
        Invoice.delete([i for i in invoices if not i.lines])

    @classmethod
    def _stock_moves(cls, line):
        for move in line.moves:
            if move.state in {'staging', 'draft'}:
                yield move


class AmendmentLine(ModelSQL, ModelView):
    "Purchase Amendment Line"
    __name__ = 'purchase.amendment.line'

    amendment = fields.Many2One(
        'purchase.amendment', "Amendment", required=True, ondelete='CASCADE')
    state = fields.Function(fields.Selection(
            'get_states', "State"), 'on_change_with_state')
    action = fields.Selection([
            ('taxes', "Recompute Taxes"),
            ('payment_term', "Change Payment Term"),
            ('party', "Change Parties and Addresses"),
            ('warehouse', "Change Warehouse"),
            ('line', "Change Line"),
            ], "Action", required=True,
        states={
            'readonly': Eval('state') != 'draft',
            })

    purchase = fields.Function(fields.Many2One(
            'purchase.purchase', "Purchase"), 'on_change_with_purchase')
    line = fields.Many2One(
        'purchase.line', "Line",
        domain=[
            ('type', '=', 'line'),
            ('purchase', '=', Eval('purchase', -1)),
            ],
        states={
            'readonly': Eval('state') != 'draft',
            'invisible': Eval('action') != 'line',
            'required': Eval('action') == 'line',
            })

    payment_term = fields.Many2One(
        'account.invoice.payment_term', "Payment Term", ondelete='RESTRICT',
        states={
            'invisible': Eval('action') != 'payment_term',
            })

    party = fields.Many2One(
        'party.party', "Party",
        states={
            'readonly': Eval('state') != 'draft',
            'invisible': Eval('action') != 'party',
            'required': Eval('action') == 'party',
            })
    invoice_party = fields.Many2One(
        'party.party', "Invoice Party",
        states={
            'readonly': Eval('state') != 'draft',
            'invisible': Eval('action') != 'party',
            },
        search_context={
            'related_party': Eval('party'),
            })
    invoice_address = fields.Many2One(
        'party.address', "Invoice Address",
        domain=[
            ('party', '=', If(Eval('invoice_party'),
                    Eval('invoice_party'), Eval('party'))),
            ],
        states={
            'readonly': Eval('state') != 'draft',
            'invisible': Eval('action') != 'party',
            'required': Eval('action') == 'party',
            })

    warehouse = fields.Many2One(
        'stock.location', "Warehouse",
        domain=[
            ('type', '=', 'warehouse'),
            ],
        states={
            'readonly': Eval('state') != 'draft',
            'invisible': Eval('action') != 'warehouse',
            'required': Eval('action') == 'warehouse',
            })

    product = fields.Many2One(
        'product.product', "Product",
        domain=[
            If((Eval('state') == 'draft')
                & ~(Eval('quantity', 0) < 0),
                ('purchasable', '=', True),
                ()),
            If(Eval('product_uom_category'),
                ('default_uom_category', '=', Eval('product_uom_category')),
                ()),
            ],
        states={
            'readonly': Eval('state') != 'draft',
            'invisible': Eval('action') != 'line',
            })
    product_supplier = fields.Many2One(
        'purchase.product_supplier', "Supplier's Product",
        domain=[
            If(Eval('product'),
                ['OR',
                    [
                        ('template.products', '=', Eval('product')),
                        ('product', '=', None),
                        ],
                    ('product', '=', Eval('product')),
                    ],
                []),
            ('party', '=', Eval('party', -1)),
            ],
        states={
            'readonly': Eval('state') != 'draft',
            'invisible': Eval('action') != 'line',
            })
    quantity = fields.Float(
        "Quantity", digits='unit',
        states={
            'readonly': Eval('state') != 'draft',
            'invisible': Eval('action') != 'line',
            'required': Eval('action') == 'line',
            })
    unit = fields.Many2One(
        'product.uom', "Unit", ondelete='RESTRICT',
        domain=[
            ('category', '=', Eval('product_uom_category')),
            ],
        states={
            'readonly': Eval('state') != 'draft',
            'invisible': Eval('action') != 'line',
            'required': Bool(Eval('product')),
            })
    unit_price = fields.Numeric(
        "Unit Price", digits=price_digits,
        states={
            'readonly': Eval('state') != 'draft',
            'invisible': Eval('action') != 'line',
            'required': Eval('action') == 'line',
            })
    description = fields.Text(
        "Description",
        states={
            'readonly': Eval('state') != 'draft',
            'invisible': Eval('action') != 'line',
            })

    product_uom_category = fields.Function(
        fields.Many2One('product.uom.category', "Product UoM Category"),
        'on_change_with_product_uom_category')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('amendment')

    @fields.depends(
        'amendment',
        '_parent_amendment.purchase',
        '_parent_amendment._parent_purchase.payment_term',
        '_parent_amendment._parent_purchase.party',
        '_parent_amendment._parent_purchase.invoice_party',
        '_parent_amendment._parent_purchase.invoice_address',
        '_parent_amendment._parent_purchase.warehouse')
    def on_change_amendment(self):
        if self.amendment and self.amendment.purchase:
            self.payment_term = self.amendment.purchase.payment_term

            self.party = self.amendment.purchase.party
            self.invoice_party = self.amendment.purchase.invoice_party
            self.invoice_address = self.amendment.purchase.invoice_address

            self.warehouse = self.amendment.purchase.warehouse

    @fields.depends(methods=['on_change_amendment'])
    def on_change_state(self):
        self.on_change_amendment()

    @classmethod
    def get_states(cls):
        pool = Pool()
        Amendment = pool.get('purchase.amendment')
        return Amendment.fields_get(['state'])['state']['selection']

    @fields.depends(
        'amendment',
        '_parent_amendment.state')
    def on_change_with_state(self, name=None):
        if self.amendment:
            return self.amendment.state

    @fields.depends(methods=['on_change_line', 'on_change_amendment'])
    def on_change_action(self):
        self.line = None
        self.on_change_line()
        self.on_change_amendment()

    @fields.depends(
        'amendment',
        '_parent_amendment.purchase')
    def on_change_with_purchase(self, name=None):
        return self.amendment.purchase if self.amendment else None

    @fields.depends('line')
    def on_change_line(self):
        if self.line:
            self.product = self.line.product
            self.product_supplier = self.line.product_supplier
            self.quantity = self.line.quantity
            self.unit = self.line.unit
            self.unit_price = self.line.unit_price
            self.description = self.line.description
        else:
            self.product = self.product_supplier = self.description = None
            self.quantity = self.unit = self.unit_price = None

    @fields.depends('party', 'invoice_party')
    def on_change_party(self):
        if not self.invoice_party:
            self.invoice_address = None
        if self.party:
            if not self.invoice_address:
                self.invoice_address = self.party.address_get(type='invoice')

    @fields.depends('party', 'invoice_party')
    def on_change_invoice_party(self):
        if self.invoice_party:
            self.invoice_address = self.invoice_party.address_get(
                type='invoice')
        elif self.party:
            self.invoice_address = self.party.address_get(type='invoice')

    @fields.depends('line')
    def on_change_with_product_uom_category(self, name=None):
        if self.line:
            if self.line.product_uom_category:
                return self.line.product_uom_category
            elif self.line.unit:
                return self.line.unit.category

    def apply(self, purchase):
        assert self.purchase == purchase
        purchase_line = None
        if self.line:
            for line in purchase.lines:
                if self.line == line:
                    purchase_line = line
                    break
        getattr(self, '_apply_%s' % self.action)(purchase, purchase_line)

    def _apply_taxes(self, purchase, purchase_line):
        for line in purchase.lines:
            if line.product:
                line.taxes = line.compute_taxes(purchase.party)

    def _apply_payment_term(self, purchase, purchase_line):
        purchase.payment_term = self.payment_term

    def _apply_party(self, purchase, purchase_line):
        purchase.party = self.party
        purchase.invoice_party = self.invoice_party
        purchase.invoice_address = self.invoice_address

    def _apply_warehouse(self, purchase, purchase_line):
        purchase.warehouse = self.warehouse

    def _apply_line(self, purchase, purchase_line):
        purchase_line.product = self.product
        purchase_line.product_supplier = self.product_supplier
        purchase_line.quantity = self.quantity
        purchase_line.unit = self.unit
        purchase_line.unit_price = self.unit_price
        purchase_line.description = self.description
