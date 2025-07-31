# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import functools
from decimal import Decimal
from itertools import groupby

from sql import Null
from sql.functions import CharLength

from trytond.i18n import gettext
from trytond.model import Index, ModelSQL, ModelView, Workflow, fields
from trytond.modules.currency.fields import Monetary
from trytond.modules.product import price_digits, round_price
from trytond.modules.product.exceptions import UOMValidationError
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Date, Eval, Id, If
from trytond.transaction import Transaction
from trytond.wizard import Button, StateAction, StateView, Wizard

from .exceptions import (
    BlanketAgreementClosingWarning, BlanketAgreementQuantityWarning)


def blanket_agreement_quantity_warning():
    def decorator(func):
        @functools.wraps(func)
        def wrapper(cls, purchases, *args, **kwargs):
            pool = Pool()
            Warning = pool.get('res.user.warning')
            Lang = pool.get('ir.lang')
            for purchase in purchases:
                for line in purchase.lines:
                    agreement_line = line.blanket_agreement_line
                    if not agreement_line:
                        continue
                    remaining_quantity = (
                        agreement_line.remainig_quantity_for_purchase(line))
                    if (remaining_quantity is not None
                            and line.quantity > remaining_quantity):
                        warning_key = Warning.format(
                            'blanket_agreement_quantity_greater_remaining',
                            [line])
                        if Warning.check(warning_key):
                            lang = Lang.get()
                            raise BlanketAgreementQuantityWarning(
                                warning_key,
                                gettext('purchase_blanket_agreement'
                                    '.msg_quantity_greater_remaining',
                                    line=line.rec_name,
                                    remaining=lang.format_number_symbol(
                                        remaining_quantity, line.unit),
                                    agreement=agreement_line.rec_name))
            return func(cls, purchases, *args, **kwargs)
        return wrapper
    return decorator


class Configuration(metaclass=PoolMeta):
    __name__ = 'purchase.configuration'

    blanket_agreement_sequence = fields.MultiValue(fields.Many2One(
            'ir.sequence', "Blanket Agreement Sequence",
            required=True,
            domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('sequence_type', '=',
                    Id('purchase_blanket_agreement',
                    'sequence_type_blanket_agreement')),
                ]))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'blanket_agreement_sequence':
            return pool.get('purchase.configuration.sequence')
        return super().multivalue_model(field)

    @classmethod
    def default_blanket_agreement_sequence(cls, **pattern):
        return cls.multivalue_model(
            'blanket_agreement_sequence'
            ).default_blanket_agreement_sequence()


class ConfigurationSequence(metaclass=PoolMeta):
    __name__ = 'purchase.configuration.sequence'
    blanket_agreement_sequence = fields.Many2One(
        'ir.sequence', "Blanket Agreement Sequence", required=True,
        domain=[
            ('company', 'in', [Eval('company', -1), None]),
            ('sequence_type', '=',
                Id('purchase_blanket_agreement',
                'sequence_type_blanket_agreement')),
            ])

    @classmethod
    def default_blanket_agreement_sequence(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        try:
            return ModelData.get_id(
                'purchase_blanket_agreement', 'sequence_blanket_agreement')
        except KeyError:
            return None


class BlanketAgreement(Workflow, ModelSQL, ModelView):
    __name__ = 'purchase.blanket_agreement'
    _rec_name = 'number'

    company = fields.Many2One(
        'company.company', "Company", required=True,
        states={
            'readonly': (
                (Eval('state') != 'draft')
                | Eval('lines', [0])
                | Eval('supplier', True)),
            })
    number = fields.Char("Number", readonly=True)
    reference = fields.Char("Reference")
    description = fields.Char(
        "Description",
        states={
            'readonly': Eval('state') != 'draft',
            })
    supplier = fields.Many2One(
        'party.party', "Supplier", required=True,
        states={
            'readonly': (
                (Eval('state') != 'draft')
                | (Eval('lines', [0]) & Eval('supplier'))),
            },
        context={
            'company': Eval('company', -1),
            },
        depends=['company'])
    from_date = fields.Date(
        "From Date",
        domain=[
            If(Eval('to_date') & Eval('from_date'),
                ('from_date', '<=', Eval('to_date')),
                ()),
            ],
        states={
            'readonly': Eval('state') != 'draft',
            'required': ~Eval('state').in_(['draft', 'cancelled']),
            })
    to_date = fields.Date(
        "To Date",
        domain=[
            If(Eval('from_date') & Eval('to_date'),
                ('to_date', '>=', Eval('from_date')),
                ()),
            ],
        states={
            'readonly': ~Eval('state').in_(['draft', 'running']),
            'required': Eval('state') == 'closed',
            })
    currency = fields.Many2One(
        'currency.currency', "Currency", required=True,
        states={
            'readonly': (
                (Eval('state') != 'draft')
                | (Eval('lines', [0]) & Eval('currency', 0))),
            })
    lines = fields.One2Many(
        'purchase.blanket_agreement.line', 'blanket_agreement', "Lines",
        states={
            'readonly': (
                (Eval('state') != 'draft')
                | ~Eval('supplier'))
            })

    amount = fields.Function(Monetary(
            "Amount", currency='currency', digits='currency'),
        'on_change_with_amount')

    state = fields.Selection([
        ('draft', "Draft"),
        ('running', "Running"),
        ('closed', "Closed"),
        ('cancelled', "Cancelled"),
        ], "State", readonly=True, required=True)

    @classmethod
    def __setup__(cls):
        cls.number.search_unaccented = False
        cls.reference.search_unaccented = False
        super().__setup__()
        t = cls.__table__()
        cls._sql_indexes.update({
                Index(t, (t.reference, Index.Similarity())),
                Index(
                    t, (t.state, Index.Equality(cardinality='low')),
                    where=t.state.in_(['draft', 'running'])),
                })
        cls._order = [
            ('from_date', 'DESC NULLS FIRST'),
            ('id', 'DESC'),
            ]
        cls._transitions |= set((
                ('draft', 'running'),
                ('draft', 'cancelled'),
                ('running', 'draft'),
                ('running', 'closed'),
                ('closed', 'running'),
                ('cancelled', 'draft'),
                ))
        cls._buttons.update({
                'cancel': {
                    'invisible': Eval('state') != 'draft',
                    'depends': ['state'],
                    },
                'draft': {
                    'invisible': ~Eval('state').in_(['cancelled', 'running']),
                    'icon': 'tryton-undo',
                    'depends': ['state'],
                    },
                'run': {
                    'invisible': (
                        (Eval('state') != 'draft')
                        & ~(Id('purchase', 'group_purchase_admin').in_(
                                Eval('context', {}).get('groups', []))
                            & (Eval('state') == 'closed'))),
                    'readonly': (~Eval('lines')
                        | (Eval('from_date', Date()) > Date())),
                    'icon': If(Eval('state') == 'closed',
                        'tryton-back',
                        'tryton-forward'),
                    'depends': ['state'],
                    },
                'create_purchase': {
                    'invisible': Eval('state') != 'running',
                    'depends': ['state'],
                    },
                'close': {
                    'invisible': Eval('state') != 'running',
                    'depends': ['state'],
                    },
                })

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def order_number(cls, tables):
        table, _ = tables[None]
        return [
            ~((table.state == 'cancelled') & (table.state == Null)),
            CharLength(table.number), table.number]

    @classmethod
    def default_currency(cls, **pattern):
        pool = Pool()
        Company = pool.get('company.company')
        company = pattern.get('company')
        if not company:
            company = cls.default_company()
        if company is not None and company >= 0:
            return Company(company).currency.id

    @fields.depends('company', 'supplier', 'lines')
    def on_change_supplier(self):
        if not self.lines:
            self.currency = self.default_currency(
                company=self.company.id if self.company else None)
            if self.supplier and self.supplier.supplier_currency:
                self.currency = self.supplier.supplier_currency

    @fields.depends('lines', 'currency')
    def on_change_with_amount(self, name=None):
        amount = sum(
            (line.amount or Decimal(0) for line in self.lines),
            Decimal(0))
        if self.currency:
            amount = self.currency.round(amount)
        return amount

    @classmethod
    def default_state(cls):
        return 'draft'

    @property
    def full_number(self):
        return self.number

    def get_rec_name(self, name):
        items = []
        if self.full_number:
            items.append(self.full_number)
        if self.reference:
            items.append('[%s]' % self.reference)
        if not items:
            items.append('(%s)' % self.id)
        return ' '.join(items)

    @classmethod
    def search_rec_name(cls, name, clause):
        _, operator, value = clause
        if operator.startswith('!') or operator.startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'

        return [bool_op,
            ('number', operator, value),
            ('reference', operator, value),
            ]

    @classmethod
    def copy(cls, agreements, default=None):
        default = default.copy() if default is not None else {}
        default.setdefault('number', None)
        default.setdefault('reference')
        default.setdefault('from_date', None)
        default.setdefault('to_date', None)
        return super().copy(agreements, default=default)

    @classmethod
    def set_number(cls, agreements):
        '''
        Fill the number field with the blanket agreement sequence
        '''
        pool = Pool()
        Config = pool.get('purchase.configuration')

        config = Config(1)
        for company, c_agreements in groupby(
                agreements, key=lambda a: a.company):
            c_agreements = [a for a in c_agreements if not a.number]
            if c_agreements:
                sequence = config.get_multivalue(
                    'blanket_agreement_sequence', company=company.id)
                for agreement, number in zip(
                        c_agreements, sequence.get_many(len(c_agreements))):
                    agreement.number = number
        cls.save(agreements)

    @classmethod
    def set_date(cls, agreements, field):
        pool = Pool()
        Date = pool.get('ir.date')
        for company, agreements in groupby(
                agreements, key=lambda p: p.company):
            with Transaction().set_context(company=company.id):
                today = Date.today()
            cls.write([a for a in agreements if not getattr(a, field)], {
                    field: today,
                    })

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('/tree', 'visual',
                If(Eval('state').in_(['cancelled', 'closed']),
                    'muted',
                    If(Eval('to_date', Date()) < Date(),
                        'warning',
                        ''))),
            ]

    def get_purchase(self, lines=None):
        pool = Pool()
        Purchase = pool.get('purchase.purchase')
        purchase = Purchase(
            company=self.company,
            party=self.supplier,
            )
        purchase.on_change_party()
        purchase.currency = self.currency
        if lines:
            purchase_lines = []
            for line in lines:
                assert line.blanket_agreement == self
                purchase_line = line.get_purchase_line(purchase)
                purchase_lines.append(purchase_line)
            purchase.lines = purchase_lines
        return purchase

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, agreements):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, agreements):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('running')
    def run(cls, agreements):
        cls.set_number(agreements)
        cls.set_date(agreements, 'from_date')

    @classmethod
    @ModelView.button_action(
        'purchase_blanket_agreement'
        '.purchase_blanked_agreement_create_purchase_wizard')
    def create_purchase(cls, agreements):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('closed')
    def close(cls, agreements):
        pool = Pool()
        Warning = pool.get('res.user.warning')
        Date = pool.get('ir.date')
        today = Date.today()
        cls.set_date(agreements, 'to_date')
        for agreement in agreements:
            if agreement.to_date > today:
                if any(l.remaining_quantity > 0 for l in agreement.lines):
                    warning_key = Warning.format(
                            'closed_remaining_quantity', [agreement])
                    if Warning.check(warning_key):
                        raise BlanketAgreementClosingWarning(
                            warning_key,
                            gettext('purchase_blanket_agreement'
                                '.msg_agreement_closed_remaining_quantity',
                                agreement=agreement.rec_name))


class BlanketAgreementLine(ModelSQL, ModelView):
    __name__ = 'purchase.blanket_agreement.line'

    _states = {
            'readonly': Eval('blanket_agreement_state') != 'draft'
            }

    blanket_agreement = fields.Many2One(
        'purchase.blanket_agreement', "Blanket Agreement",
        ondelete='CASCADE', required=True,
        states={
            'readonly': (
                _states['readonly'] & Bool(Eval('blanket_agreement'))),
            })
    product = fields.Many2One(
        'product.product', "Product", ondelete='RESTRICT', required=True,
        domain=[
            If(Eval('blanket_agreement_state') == 'draft',
                ('purchasable', '=', True),
                ()),
            ],
        states=_states,
        context={
            'company': Eval('company', None),
            },
        search_context={
            'currency': Eval('_parent_blanket_agreement', {}).get('currency'),
            'supplier': Eval('_parent_blanket_agreement', {}).get('supplier'),
            'quantity': Eval('quantity'),
            'uom': Eval('unit'),
            },
        depends=['company', 'unit', 'quantity'])
    product_supplier = fields.Many2One(
        'purchase.product_supplier', "Supplier's Product", ondelete='RESTRICT',
        domain=[
            If(Bool(Eval('product')),
                ['OR',
                    [
                        ('template.products', '=', Eval('product')),
                        ('product', '=', None),
                        ],
                    ('product', '=', Eval('product')),
                    ],
                []),
            ('party', '=',
                Eval('_parent_blanket_agreement', {}).get('supplier', -1)),
            ],
        states=_states)
    product_uom_category = fields.Function(
        fields.Many2One(
            'product.uom.category', "Product UoM Category",
            help="The category of Unit of Measure for the product."),
        'on_change_with_product_uom_category')
    quantity = fields.Float("Quantity", digits='unit', states=_states)
    unit = fields.Many2One(
        'product.uom', "Unit", ondelete='RESTRICT', required=True,
        states=_states)
    unit_price = Monetary(
        "Unit Price", digits=price_digits, currency='currency', required=True,
        states=_states)
    amount = fields.Function(
        Monetary("Amount", digits='currency', currency='currency'),
        'on_change_with_amount')
    processed_quantity = fields.Function(
        fields.Float("Processed quantity", digits='unit'),
        'get_processed_quantity')
    remaining_quantity = fields.Function(
        fields.Float(
            "Remaining quantity", digits='unit',
            states={
                'invisible': ~Eval('quantity'),
                }),
        'on_change_with_remaining_quantity')
    purchase_lines = fields.One2Many(
        'purchase.line', 'blanket_agreement_line', "Purchase Lines",
        readonly=True)

    blanket_agreement_state = fields.Function(
        fields.Selection(
            'get_purchase_blanket_agreement_states',
            "Blanket Agreement State"),
        'on_change_with_blanket_agreement_state')
    company = fields.Function(
        fields.Many2One('company.company', "Company"),
        'on_change_with_company')
    currency = fields.Function(
        fields.Many2One('currency.currency', "Currency"),
        'on_change_with_currency')

    del _states

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('blanket_agreement')
        unit_categories = cls._unit_categories()
        cls.unit.domain = [
            If(Bool(Eval('product_uom_category')),
                ('category', 'in', [Eval(c) for c in unit_categories]),
                ('category', '!=', -1)),
            ]

    @fields.depends(
        'blanket_agreement', 'company', '_parent_blanket_agreement.supplier')
    def _get_product_supplier_pattern(self):
        return {
            'party': (
                self.blanket_agreement.supplier.id
                if self.blanket_agreement and self.blanket_agreement.supplier
                else -1),
            'company': (self.company.id if self.company else -1),
            }

    @fields.depends(
        'product', 'unit', 'blanket_agreement',
        '_parent_blanket_agreement.supplier', 'product_supplier',
        methods=['on_change_with_amount'])
    def on_change_product(self):
        if not self.product:
            return

        category = self.product.purchase_uom.category
        if not self.unit or self.unit.category != category:
            self.unit = self.product.purchase_uom

        product_suppliers = list(self.product.product_suppliers_used(
                **self._get_product_supplier_pattern()))
        if len(product_suppliers) == 1:
            self.product_supplier, = product_suppliers
        elif (self.product_supplier
                and self.product_supplier not in product_suppliers):
            self.product_supplier = None

    @fields.depends('product', 'product_supplier',
        methods=['on_change_product'])
    def on_change_product_supplier(self):
        if self.product_supplier:
            if self.product_supplier.product:
                self.product = self.product_supplier.product
            elif not self.product:
                if len(self.product_supplier.template.products) == 1:
                    self.product, = self.product_supplier.template.products
        self.on_change_product()

    @classmethod
    def _unit_categories(cls):
        return ['product_uom_category']

    @fields.depends('product')
    def on_change_with_product_uom_category(self, name=None):
        return self.product.default_uom_category if self.product else None

    @fields.depends(
        'quantity', 'unit_price', 'blanket_agreement',
        '_parent_blanket_agreement.currency')
    def on_change_with_amount(self, name=None):
        amount = (
            Decimal(str(self.quantity or 0))
            * (self.unit_price or Decimal(0)))

        if self.blanket_agreement and self.blanket_agreement.currency:
            return self.blanket_agreement.currency.round(amount)
        return amount

    @fields.depends('blanket_agreement', '_parent_blanket_agreement.currency')
    def on_change_with_currency(self, name=None):
        if self.blanket_agreement:
            return self.blanket_agreement.currency

    def get_processed_quantity(self, name=None):
        processed_quantity = 0.
        for line in self.purchase_lines:
            if line.purchase.state in {'confirmed', 'processing', 'done'}:
                processed_quantity += line.quantity_for_blanket_agreement(
                    self, round=False)
        return self.unit.round(processed_quantity)

    @fields.depends('quantity', 'processed_quantity')
    def on_change_with_remaining_quantity(self, name=None):
        if self.quantity is not None:
            return max(self.quantity - (self.processed_quantity or 0.), 0.)

    @classmethod
    def get_purchase_blanket_agreement_states(cls):
        pool = Pool()
        Agreement = pool.get('purchase.blanket_agreement')
        return Agreement.fields_get(['state'])['state']['selection']

    @fields.depends('blanket_agreement', '_parent_blanket_agreement.state')
    def on_change_with_blanket_agreement_state(self, name=None):
        if self.blanket_agreement:
            return self.blanket_agreement.state

    @fields.depends('blanket_agreement', '_parent_blanket_agreement.company')
    def on_change_with_company(self, name=None):
        if self.blanket_agreement:
            return self.blanket_agreement.company

    def get_purchase_line(self, purchase):
        pool = Pool()
        PurchaseLine = pool.get('purchase.line')
        purchase_line = PurchaseLine(
            purchase=purchase,
            product=self.product,
            product_supplier=self.product_supplier,
            blanket_agreement_line=self,
            )
        purchase_line.on_change_product()
        self._set_purchase_line_quantity(purchase_line)
        return purchase_line

    def _set_purchase_line_quantity(self, purchase_line):
        if self.unit.category == self.product.purchase_uom.category:
            purchase_line.quantity = self.remaining_quantity or 0
            purchase_line.unit = self.unit
            purchase_line.unit_price = self.unit_price
            purchase_line.on_change_quantity()

    def get_rec_name(self, name):
        pool = Pool()
        Lang = pool.get('ir.lang')
        lang = Lang.get()
        name = f'{self.product.rec_name}s @ {self.blanket_agreement.rec_name}'
        if self.quantity is not None:
            name = '%s %s' % (lang.format_number_symbol(
                    self.quantity, self.unit, digits=self.unit.digits), name)
        return name

    @classmethod
    def validate_fields(cls, records, field_names):
        super().validate_fields(records, field_names)
        cls.check_unit(records, field_names)

    @classmethod
    def check_unit(cls, lines, field_names=None):
        if field_names and not (field_names & {'unit'}):
            return
        for line in lines:
            for purchase_line in line.purchase_lines:
                if not line.is_same_uom_category(purchase_line):
                    raise UOMValidationError(
                        gettext('purchase_blanket_agreement'
                            '.msg_agreement_line_incompatible_unit',
                            line=line.rec_name))

    def is_same_uom_category(self, purchase_line):
        return self.unit.category == purchase_line.product_uom_category

    def remainig_quantity_for_purchase(self, line, round=True):
        pool = Pool()
        Uom = pool.get('product.uom')
        if (self.remaining_quantity is not None
                and self.unit.category == line.unit.category):
            return Uom.compute_qty(
                self.unit, self.remaining_quantity, line.unit,
                round=round)

    @classmethod
    def copy(cls, lines, default=None):
        default = default.copy() if default is not None else {}
        default.setdefault('purchase_lines', None)
        return super().copy(lines, default=default)


class Purchase(metaclass=PoolMeta):
    __name__ = 'purchase.purchase'

    blanket_agreements = fields.Function(fields.Many2Many(
            'purchase.blanket_agreement', None, None, "Blanket Agreements"),
        'get_blanket_agreements', searcher='search_blanket_agreements')

    def get_blanket_agreements(self, name):
        return list({
                l.blanket_agreement_line.blanket_agreement.id
                for l in self.lines
                if l.blanket_agreement_line})

    @classmethod
    def search_blanket_agreements(cls, name, clause):
        return [
            ('lines.blanket_agreement_line.blanket_agreement'
                + clause[0][len(name):], *clause[1:])]

    @classmethod
    @ModelView.button
    @Workflow.transition('quotation')
    @blanket_agreement_quantity_warning()
    def quote(cls, purchases):
        super().quote(purchases)

    @classmethod
    @ModelView.button
    @Workflow.transition('confirmed')
    @blanket_agreement_quantity_warning()
    def confirm(cls, purchases):
        super().confirm(purchases)


class Line(metaclass=PoolMeta):
    __name__ = 'purchase.line'

    blanket_agreement_line = fields.Many2One(
        'purchase.blanket_agreement.line', "Blanket Agreement Line",
        ondelete='RESTRICT',
        states={
            'invisible': ~Eval('product'),
            'readonly': Eval('purchase_state') != 'draft',
            })

    @classmethod
    def __setup__(cls):
        super().__setup__()
        purchase_date = Eval('_parent_purchase', {}).get(
            'purchase_date', Date())
        purchase_date = If(purchase_date, purchase_date, Date())
        cls.blanket_agreement_line.domain = [
            If(Eval('purchase_state').in_(['draft', 'quotation']),
                [
                    ('blanket_agreement.state', '=', 'running'),
                    ['OR',
                        ('blanket_agreement.from_date', '<=', purchase_date),
                        ('blanket_agreement.from_date', '=', None),
                        ],
                    ['OR',
                        ('blanket_agreement.to_date', '>=', purchase_date),
                        ('blanket_agreement.to_date', '=', None),
                        ],
                    cls._domain_blanket_agreemnt_line_product(),
                    ],
                []),
            ('blanket_agreement.supplier', '=',
                Eval('_parent_purchase', {}).get('party', -1)),
            ]

    @classmethod
    def _domain_blanket_agreemnt_line_product(cls):
        return [
            ('product', '=', Eval('product', -1)),
            If(Eval('product_supplier'),
                ['OR',
                    ('product_supplier', '=', Eval('product_supplier')),
                    ('product_supplier', '=', None),
                    ],
                []),
            ]

    @fields.depends(
        'blanket_agreement_line', '_parent_blanket_agreement_line.unit',
        '_parent_blanket_agreement_line.unit_price', 'unit')
    def compute_unit_price(self):
        pool = Pool()
        Uom = pool.get('product.uom')
        unit_price = super().compute_unit_price()
        line = self.blanket_agreement_line
        if (line
                and self.unit
                and line.unit
                and self.unit.category == line.unit.category):
            unit_price = Uom.compute_price(
                line.unit, line.unit_price, self.unit)
            unit_price = round_price(unit_price)
        return unit_price

    @fields.depends(
        'quantity', 'unit', 'product_supplier',
        'blanket_agreement_line',
        '_parent_blanket_agreement_line.product_supplier',
        '_parent_blanket_agreement_line.unit',
        '_parent_blanket_agreement_line.remaining_quantity',
        methods=['compute_unit_price', 'on_change_quantity'])
    def on_change_blanket_agreement_line(self):
        pool = Pool()
        Uom = pool.get('product.uom')
        if self.blanket_agreement_line:
            line = self.blanket_agreement_line
            if not self.product_supplier:
                self.product_supplier = line.product_supplier
            self.unit_price = self.compute_unit_price()
            if (self.unit and line.unit
                    and self.unit.category == line.unit.category):
                if line.remaining_quantity is not None:
                    remaining_quantity = Uom.compute_qty(
                        line.unit, line.remaining_quantity, self.unit)
                    if (self.quantity is None
                            or remaining_quantity < self.quantity):
                        self.quantity = remaining_quantity
                        self.on_change_quantity()

    @fields.depends(methods=['is_valid_product_for_blanket_agreement'])
    def on_change_product(self):
        super().on_change_product()
        if not self.is_valid_product_for_blanket_agreement():
            self.blanket_agreement_line = None

    @fields.depends(
        'blanket_agreement_line', 'product', 'product_supplier',
        '_parent_blanket_agreement_line.product',
        '_parent_blanket_agreement_line.product_supplier')
    def is_valid_product_for_blanket_agreement(self):
        if self.blanket_agreement_line:
            return (self.product == self.blanket_agreement_line.product
                and (
                    (self.product_supplier
                        == self.blanket_agreement_line.product_supplier)
                    or not self.product_supplier))

    def quantity_for_blanket_agreement(self, line, round=True):
        pool = Pool()
        Uom = pool.get('product.uom')
        if self.unit.category == line.unit.category:
            quantity = (
                self.actual_quantity if self.actual_quantity is not None
                else self.quantity)
            return Uom.compute_qty(self.unit, quantity, line.unit, round=round)
        return 0


class BlanketAgreementCreatePurchase(Wizard):
    __name__ = 'purchase.blanket_agreement.create_purchase'
    start = StateView(
        'purchase.blanket_agreement.create_purchase.start',
        'purchase_blanket_agreement.'
        'purchase_blanked_agreement_create_purchase_start_form_view', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Create", 'create_purchase', 'tryton-ok', default=True),
            ])
    create_purchase = StateAction('purchase.act_purchase_form')

    def default_start(self, fields):
        line_ids = [
            line.id for line in self.record.lines
            if line.remaining_quantity > 0]
        return {
            'blanket_agreement': self.record.id,
            'lines': line_ids,
            }

    def do_create_purchase(self, action):
        if self.start.lines:
            purchase = self.record.get_purchase(self.start.lines)
            purchase.save()
            action['domains'] = []
            action['views'].reverse()
            return action, {'res_id': [purchase.id]}


class BlanketAgreementCreatePurchaseStart(ModelView):
    __name__ = 'purchase.blanket_agreement.create_purchase.start'

    blanket_agreement = fields.Many2One(
        'purchase.blanket_agreement', "Blanket Agreement")
    lines = fields.Many2Many(
        'purchase.blanket_agreement.line', None, None, "Lines",
        domain=[('blanket_agreement', '=', Eval('blanket_agreement', -1))])
