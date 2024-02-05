# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.i18n import gettext
from trytond.model import Index, ModelSQL, ModelView, Workflow, fields
from trytond.modules.product import price_digits
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval, If
from trytond.transaction import Transaction

from .exceptions import AmendmentValidateError


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    amendments = fields.One2Many(
        'sale.amendment', 'sale', "Amendments",
        states={
            'invisible': ((Eval('state') != 'processing')
                | ~Eval('amendments')),
            'readonly': Eval('state') != 'processing',
            })

    @classmethod
    def copy(cls, sales, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('amendments')
        return super().copy(sales, default=default)


class Amendment(Workflow, ModelSQL, ModelView):
    "Sale Amendment"
    __name__ = 'sale.amendment'

    sale = fields.Many2One(
        'sale.sale', "Sale", required=True,
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
        'sale.amendment.line', 'amendment', "Lines",
        states={
            'readonly': (
                (Eval('state') != 'draft')
                | ~Eval('sale')),
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
        Sale = pool.get('sale.sale')
        transaction = Transaction()
        context = transaction.context
        sales = set()
        for amendment in amendments:
            sale = amendment.sale
            if sale in sales:
                raise AmendmentValidateError(
                    gettext('sale_amendment.msg_one_sale_at_time',
                        sale=sale.rec_name))
            sales.add(sale)
            sale.revision += 1
            for line in amendment.lines:
                line.apply(sale)
            # Force saved lines
            sale.lines = sale.lines
            # Force recompute cache
            sale.untaxed_amount_cache = None
            sale.tax_amount_cache = None
            sale.total_amount_cache = None

        Sale.save(sales)
        Sale.store_cache(sales)
        cls._clear_sale(sales)
        with transaction.set_context(
                queue_batch=context.get('queue_batch', True)):
            Sale.__queue__.process(sales)

    @classmethod
    def _clear_sale(cls, sales):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        InvoiceLine = pool.get('account.invoice.line')
        Shipment = pool.get('stock.shipment.out')
        ShipmentReturn = pool.get('stock.shipment.out.return')
        Move = pool.get('stock.move')

        invoices = set()
        shipments = set()
        shipment_returns = set()
        invoice_lines = set()
        moves = set()
        for sale in sales:
            for invoice in sale.invoices:
                if invoice.state == 'draft':
                    invoices.add(invoice)
            for shipment in sale.shipments:
                if shipment.state in ['draft', 'waiting']:
                    shipments.add(shipment)
            for shipment_return in sale.shipment_returns:
                if shipment_return.state == 'draft':
                    shipment_returns.add(shipment_return)

            for line in sale.lines:
                for invoice_line in line.invoice_lines:
                    if invoice_line.invoice_state == 'draft':
                        invoice_lines.add(invoice_line)
                moves.update(cls._stock_moves(line))

        shipments_waiting = [s for s in shipments if s.state == 'waiting']
        Shipment.draft(shipments)  # Clear inventory moves
        InvoiceLine.delete(invoice_lines)
        Move.delete(moves)

        Invoice.update_taxes([i for i in invoices if i.lines])
        Invoice.delete([i for i in invoices if not i.lines])
        Shipment.wait([s for s in shipments_waiting if s.outgoing_moves])
        Shipment.delete([s for s in shipments if not s.outgoing_moves])
        ShipmentReturn.delete(
            [s for s in shipment_returns if not s.incoming_moves])

    @classmethod
    def _stock_moves(cls, line):
        for move in line.moves:
            if move.state in {'staging', 'draft'}:
                yield move


class AmendmentLine(ModelSQL, ModelView):
    "Sale Amendment Line"
    __name__ = 'sale.amendment.line'

    amendment = fields.Many2One(
        'sale.amendment', "Amendment", required=True, ondelete='CASCADE')
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

    sale = fields.Function(fields.Many2One(
            'sale.sale', "Sale"), 'on_change_with_sale')
    line = fields.Many2One(
        'sale.line', "Line",
        domain=[
            ('type', '=', 'line'),
            ('sale', '=', Eval('sale', -1)),
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
    shipment_party = fields.Many2One(
        'party.party', "Shipment Party",
        states={
            'readonly': Eval('state') != 'draft',
            'invisible': Eval('action') != 'party',
            },
        search_context={
            'related_party': Eval('party'),
            })
    shipment_address = fields.Many2One(
        'party.address', "Shipment Address",
        domain=['OR',
            ('party', '=', If(Eval('shipment_party'),
                    Eval('shipment_party'), Eval('party'))),
            ('warehouses', '=', Eval('warehouse')),
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
                ('salable', '=', True),
                ()),
            If(Eval('product_uom_category'),
                ('default_uom_category', '=', Eval('product_uom_category')),
                ()),
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
            If(Eval('product_uom_category'),
                ('category', '=', Eval('product_uom_category')),
                ()),
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
        '_parent_amendment.sale',
        '_parent_amendment._parent_sale.payment_term',
        '_parent_amendment._parent_sale.party',
        '_parent_amendment._parent_sale.invoice_party',
        '_parent_amendment._parent_sale.invoice_address',
        '_parent_amendment._parent_sale.shipment_party',
        '_parent_amendment._parent_sale.shipment_address',
        '_parent_amendment._parent_sale.warehouse')
    def on_change_amendment(self):
        if self.amendment and self.amendment.sale:
            self.payment_term = self.amendment.sale.payment_term

            self.party = self.amendment.sale.party
            self.invoice_party = self.amendment.sale.invoice_party
            self.invoice_address = self.amendment.sale.invoice_address
            self.shipment_party = self.amendment.sale.shipment_party
            self.shipment_address = self.amendment.sale.shipment_address

            self.warehouse = self.amendment.sale.warehouse

    @fields.depends(methods=['on_change_amendment'])
    def on_change_state(self):
        self.on_change_amendment()

    @classmethod
    def get_states(cls):
        pool = Pool()
        Amendment = pool.get('sale.amendment')
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
        '_parent_amendment.sale')
    def on_change_with_sale(self, name=None):
        return self.amendment.sale if self.amendment else None

    @fields.depends('line')
    def on_change_line(self):
        if self.line:
            self.product = self.line.product
            self.quantity = self.line.quantity
            self.unit = self.line.unit
            self.unit_price = self.line.unit_price
            self.description = self.line.description
        else:
            self.product = self.quantity = self.unit = self.unit_price = None
            self.description = None

    @fields.depends('party', 'invoice_party', 'shipment_party', 'warehouse')
    def on_change_party(self):
        if not self.invoice_party:
            self.invoice_address = None
        if not self.shipment_party:
            self.shipment_address = None
        if self.party:
            if not self.invoice_address:
                self.invoice_address = self.party.address_get(type='invoice')
            if not self.shipment_party:
                with Transaction().set_context(
                        warehouse=(
                            self.warehouse.id if self.warehouse else None)):
                    self.shipment_address = self.party.address_get(
                        type='delivery')

    @fields.depends('party', 'invoice_party')
    def on_change_invoice_party(self):
        if self.invoice_party:
            self.invoice_address = self.invoice_party.address_get(
                type='invoice')
        elif self.party:
            self.invoice_address = self.party.address_get(type='invoice')

    @fields.depends('party', 'shipment_party', 'warehouse')
    def on_change_shipment_party(self):
        with Transaction().set_context(
                warehouse=self.warehouse.id if self.warehouse else None):
            if self.shipment_party:
                self.shipment_address = self.shipment_party.address_get(
                    type='delivery')
            elif self.party:
                self.shipment_address = self.party.address_get(type='delivery')

    @fields.depends('line')
    def on_change_with_product_uom_category(self, name=None):
        if self.line:
            if self.line.product_uom_category:
                return self.line.product_uom_category
            elif self.line.unit:
                return self.line.unit.category

    def apply(self, sale):
        assert self.sale == sale
        sale_line = None
        if self.line:
            for line in sale.lines:
                if self.line == line:
                    sale_line = line
                    break
        getattr(self, '_apply_%s' % self.action)(sale, sale_line)

    def _apply_taxes(self, sale, sale_line):
        for line in sale.lines:
            if line.product:
                line.taxes = line.compute_taxes(sale.party)

    def _apply_payment_term(self, sale, sale_line):
        sale.payment_term = self.payment_term

    def _apply_party(self, sale, sale_line):
        sale.party = self.party
        sale.invoice_party = self.invoice_party
        sale.invoice_address = self.invoice_address
        sale.shipment_party = self.shipment_party
        sale.shipment_address = self.shipment_address

    def _apply_warehouse(self, sale, sale_line):
        sale.warehouse = self.warehouse

    def _apply_line(self, sale, sale_line):
        sale_line.product = self.product
        sale_line.quantity = self.quantity
        sale_line.unit = self.unit
        sale_line.unit_price = self.unit_price
        sale_line.description = self.description
