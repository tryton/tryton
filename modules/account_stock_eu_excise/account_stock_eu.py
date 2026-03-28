# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime as dt
from collections import defaultdict
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from simpleeval import simple_eval
from sql import Literal, Null, Union, With
from sql.aggregate import Sum
from sql.conditionals import Case
from sql.operators import Exists

from trytond.i18n import gettext
from trytond.model import (
    DeactivableMixin, MatchMixin, ModelSQL, ModelView, fields)
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval, Id, If
from trytond.tools import cursor_dict, decistmt
from trytond.tools.decimal_ import DecimalNull
from trytond.transaction import Transaction

from .exceptions import FormulaError


class ExciseTax(DeactivableMixin, ModelSQL, ModelView):
    __name__ = 'account.stock.eu.excise.tax'
    _rec_name = 'code'

    code = fields.Char("Code", required=True)
    description = fields.Char("Description", translate=True)
    country = fields.Many2One('country.country', "Country", required=True)

    quantity = fields.Selection([
            ('measurement_volume', "Volume Measurements"),
            ('measurement_weight', "Weight Measurements"),
            ], "Quantity", required=True,
        help="Define which quantity to use for excise declaration.")
    uom = fields.Many2One('product.uom', "UoM", required=True,
        domain=[
            If(Eval('quantity') == 'measurement_volume',
                ('category', '=', Id('product', 'uom_cat_volume')),
                ()),
            If(Eval('quantity') == 'measurement_weight',
                ('category', '=', Id('product', 'uom_cat_weight')),
                ()),
            ],
        help="The Unit of Measure for excise declaration.")
    currency = fields.Many2One(
        'currency.currency', "Currency",
        states={
            'required': Bool(Eval('tax_rates', [])),
            })
    tax_rates = fields.One2Many(
        'account.stock.eu.excise.tax.rate', 'excise_tax', "Tax Rates",
        states={
            'readonly': ~Eval('currency'),
            })

    @fields.depends('quantity', 'uom')
    def on_change_quantity(self):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        if self.uom:
            if self.quantity == 'measurement_volume':
                volume_id = ModelData.get_id('product', 'uom_cat_volume')
                if self.uom.category.id != volume_id:
                    self.uom = None
            elif self.quantity == 'measurement_weight':
                weight_id = ModelData.get_id('product', 'uom_cat_weight')
                if self.uom.category.id != weight_id:
                    self.uom = None

    def convert_quantity(self, product, quantity):
        pool = Pool()
        UoM = pool.get('product.uom')

        if self.quantity == 'measurement_volume':
            if product.default_uom.category == self.uom.category:
                return UoM.compute_qty(
                    product.default_uom, quantity, self.uom)
            elif product.volume is not None:
                quantity = quantity * product.volume
                return UoM.compute_qty(
                    product.volume_uom, quantity, self.uom)
        elif self.quantity == 'measurement_weight':
            if product.default_uom.category == self.uom.category:
                return UoM.compute_qty(
                    product.default_uom, quantity, self.uom)
            elif product.weight is not None:
                quantity = quantity * product.weight
                return UoM.compute_qty(product.weight_uom, quantity, self.uom)

    def get_tax_rate(self, pattern):
        for tax_rate in self.tax_rates:
            if tax_rate.match(pattern):
                return tax_rate


class ExciseTaxRate(MatchMixin, ModelSQL, ModelView):
    __name__ = 'account.stock.eu.excise.tax.rate'

    excise_tax = fields.Many2One(
        'account.stock.eu.excise.tax', "Excise Tax", required=True)
    start_date = fields.Date(
        "Start Date",
        domain=['OR',
            ('start_date', '<=', If(Eval('end_date'),
                    Eval('end_date', dt.date.max), dt.date.max)),
            ('start_date', '=', None),
            ])
    end_date = fields.Date('End Date',
        domain=['OR',
            ('end_date', '>=', If(Eval('start_date'),
                    Eval('start_date', dt.date.min), dt.date.min)),
            ('end_date', '=', None),
            ])
    formula = fields.Char(
        "Formula", required=True,
        help=("A python expression that will be evaluated with:\n"
            "-quantity: the quantity of product"))

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('excise_tax')
        cls._order.insert(0, ('start_date', 'ASC'))
        cls._order.insert(1, ('end_date', 'ASC'))

    @classmethod
    def order_start_date(cls, tables):
        table, _ = tables[None]
        return [table.start_date == Null, table.start_date]

    @classmethod
    def order_end_date(cls, tables):
        table, _ = tables[None]
        return [table.end_date == Null, table.end_date]

    @classmethod
    def validate_fields(cls, rates, field_names=None):
        super().validate_fields(rates, field_names=field_names)
        cls.check_formula(rates, field_names=field_names)

    @classmethod
    def check_formula(cls, rates, field_names):
        if field_names and not (field_names & {'excise_tax', 'formula'}):
            return
        for rate in rates:
            rate.compute(None, 0)

    def match(self, pattern):
        if 'date' in pattern:
            pattern = pattern.copy()
            if date := pattern.pop('date'):
                start = self.start_date or dt.date.min
                end = self.end_date or dt.date.max
                if not (start <= date <= end):
                    return False
        return super().match(pattern)

    def _compute_context(self, product, quantity):
        if product:
            quantity = self.excise_tax.convert_quantity(product, quantity)
        quantity = Decimal(str(quantity))
        return {
            'names': {
                'quantity': (
                    quantity if quantity is not None else DecimalNull()),
                },
            }

    def compute(self, product, quantity, unit=None):
        pool = Pool()
        UoM = pool.get('product.uom')
        if unit:
            quantity = UoM.compute_qty(
                unit, quantity, product.default_uom, round=False)
        context = self._compute_context(product, quantity)
        context.setdefault('functions', {})['Decimal'] = Decimal
        try:
            value = simple_eval(decistmt(self.formula), **context)
            if isinstance(value, DecimalNull):
                value = None
            if value is not None:
                if not isinstance(value, Decimal):
                    raise ValueError(f"{value!r} is not a Decimal")
                value = self.excise_tax.currency.round(value)
            return value
        except Exception as exception:
            raise FormulaError(gettext(
                    'account_stock_eu_excise.msg_invalid_formula',
                    formula=self.formula,
                    tax_rate=self.rec_name,
                    exception=exception)) from exception


class ExciseDeclarationContext(ModelView):
    __name__ = 'account.stock.eu.excise.declaration.context'

    company = fields.Many2One('company.company', "Company", required=True)
    warehouse = fields.Many2One(
        'stock.location', "Warehouse", required=True,
        domain=[
            ('type', '=', 'warehouse'),
            ('eu_excise_numbers', 'where', [
                    ('company', '=', Eval('company', -1)),
                    ]),
            ])
    from_date = fields.Date(
        "From Date", required=True,
        domain=[
            ('from_date', '<=', Eval('to_date', None)),
            ])
    to_date = fields.Date(
        "To Date", required=True,
        domain=[
            ('to_date', '>=', Eval('from_date', None)),
            ])

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_warehouse(cls):
        pool = Pool()
        Location = pool.get('stock.location')
        context = Transaction().context
        if 'warehouse' in context:
            return context.get('warehouse')
        company_id = context.get('company')
        warehouses = Location.search([
                ('type', '=', 'warehouse'),
                ('eu_excise_numbers', 'where', [
                        ('company', '=', company_id),
                        ]),
                ], limit=2)
        if len(warehouses) == 1:
            warehouse, = warehouses
            return warehouse.id

    @classmethod
    def default_from_date(cls):
        pool = Pool()
        Date = pool.get('ir.date')
        context = Transaction().context
        today = Date.today()
        return context.get(
            'from_date', today + relativedelta(months=-1, day=1))

    @classmethod
    def default_to_date(cls):
        pool = Pool()
        Date = pool.get('ir.date')
        context = Transaction().context
        today = Date.today()
        return context.get(
            'to_date', today + relativedelta(months=-1, day=31))


class ExciseDeclaration(ModelSQL, ModelView):
    __name__ = 'account.stock.eu.excise.declaration'

    company = fields.Many2One('company.company', "Company")
    eu_excise_tax = fields.Many2One(
        'account.stock.eu.excise.tax', "Excise Tax")
    unit = fields.Many2One('product.uom', "Unit")
    products = fields.One2Many(
        'account.stock.eu.excise.declaration.product', 'eu_excise_tax',
        "Products",
        context={
            'company': Eval('company', -1),
            },
        depends=['company'])
    start_quantity = fields.Function(
        fields.Float("Start Quantity", digits='unit'),
        '_sum_products')
    input_production = fields.Function(
        fields.Float("Input Production", digits='unit'),
        '_sum_products')
    input_duty_suspension = fields.Function(
        fields.Float("Input Duty Suspension", digits='unit'),
        '_sum_products')
    input_replacement = fields.Function(
        fields.Float("Input Replacement", digits='unit'),
        '_sum_products')
    input_other = fields.Function(
        fields.Float("Input Other", digits='unit'),
        '_sum_products')
    input_total = fields.Function(
        fields.Float("Input Total", digits='unit'),
        '_sum_products')
    output_with_duty = fields.Function(
        fields.Float("Output with Duty", digits='unit'),
        '_sum_products')
    output_production = fields.Function(
        fields.Float("Output Production", digits='unit'),
        '_sum_products')
    output_duty_suspension = fields.Function(
        fields.Float("Output Duty Suspension", digits='unit'),
        '_sum_products')
    output_duty_free = fields.Function(
        fields.Float("Output Duty Free", digits='unit'),
        '_sum_products')
    output_other = fields.Function(
        fields.Float("Output Other", digits='unit'),
        '_sum_products')
    output_total = fields.Function(
        fields.Float("Output Total", digits='unit'),
        '_sum_products')
    end_quantity = fields.Function(
        fields.Float("End Quantity", digits='unit'),
        '_sum_products')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('eu_excise_tax', 'ASC'))

    @classmethod
    def table_query(cls):
        pool = Pool()
        ExciseTax = pool.get('account.stock.eu.excise.tax')
        Product_ExciseTax = pool.get('product-account.stock.eu.excise.tax')
        Location = pool.get('stock.location')

        excise_tax = ExciseTax.__table__()
        product_excise_tax = Product_ExciseTax.__table__()

        context = Transaction().context
        country = None
        if warehouse := context.get('warehouse'):
            warehouse = Location(warehouse)
            if warehouse.address and warehouse.address.country:
                country = warehouse.address.country.id

        return excise_tax.select(
            excise_tax.id.as_('id'),
            *cls._columns(excise_tax),
            where=Exists(product_excise_tax.select(
                    product_excise_tax.id,
                    where=product_excise_tax.excise_tax == excise_tax.id))
            & (excise_tax.country == country))

    @classmethod
    def _columns(cls, excise_tax):
        context = Transaction().context
        return [
            Literal(context.get('company')).as_('company'),
            excise_tax.id.as_('eu_excise_tax'),
            excise_tax.uom.as_('unit'),
            ]

    def _sum_products(self, names):
        total = defaultdict(float)
        for product in self.products:
            assert self.unit == product.unit
            for name in names:
                total[name] += getattr(product, name) or 0
        return total

    def get_rec_name(self, name):
        return self.eu_excise_tax.rec_name


class ExciseDeclarationProduct(ModelSQL, ModelView):
    __name__ = 'account.stock.eu.excise.declaration.product'

    company = fields.Many2One('company.company', "Company")
    product = fields.Many2One(
        'product.product', "Product",
        context={
            'company': Eval('company', -1),
            },
        depends=['company'])
    eu_excise_code = fields.Many2One('product.eu.excise_code', "Excise Code")
    eu_excise_tax = fields.Many2One(
        'account.stock.eu.excise.tax', "Excise Tax")
    unit = fields.Many2One('product.uom', "Unit")
    start_quantity = fields.Function(
        fields.Float("Start Quantity", digits='unit'),
        'get_quantity')
    input_production = fields.Function(
        fields.Float("Input Production", digits='unit'),
        'get_input')
    input_duty_suspension = fields.Function(
        fields.Float("Input Duty Suspension", digits='unit'),
        'get_input')
    input_replacement = fields.Function(
        fields.Float("Input Replacement", digits='unit'),
        'get_input')
    input_other = fields.Function(
        fields.Float("Input Other", digits='unit'),
        'get_input')
    input_total = fields.Function(
        fields.Float("Input Total", digits='unit'),
        'get_input')
    output_with_duty = fields.Function(
        fields.Float("Output with Duty", digits='unit'),
        'get_output')
    output_production = fields.Function(
        fields.Float("Output Production", digits='unit'),
        'get_output')
    output_duty_suspension = fields.Function(
        fields.Float("Output Duty Suspension", digits='unit'),
        'get_output')
    output_duty_free = fields.Function(
        fields.Float("Output Duty Free", digits='unit'),
        'get_output')
    output_other = fields.Function(
        fields.Float("Output Other", digits='unit'),
        'get_output')
    output_total = fields.Function(
        fields.Float("Output Total", digits='unit'),
        'get_output')
    end_quantity = fields.Function(
        fields.Float("End Quantity", digits='unit'),
        'get_quantity')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('product', 'ASC'))

    @classmethod
    def table_query(cls):
        from_item, tables = cls._joins()
        return from_item.select(
            *cls._columns(tables),
            where=cls._where(tables))

    @classmethod
    def _joins(cls):
        pool = Pool()
        Product = pool.get('product.product')
        ProductTemplate = pool.get('product.template')
        Location = pool.get('stock.location')
        Product_ExciseTax = pool.get('product-account.stock.eu.excise.tax')
        ExciseTax = pool.get('account.stock.eu.excise.tax')

        context = Transaction().context
        country = None
        if warehouse := context.get('warehouse'):
            warehouse = Location(warehouse)
            if warehouse.address and warehouse.address.country:
                country = warehouse.address.country.id

        tables = {}
        tables['product'] = product = Product.__table__()
        tables['template'] = template = ProductTemplate.__table__()
        product_excise_tax = Product_ExciseTax.__table__()
        tables['product_excise_tax'] = product_excise_tax
        tables['excise_tax'] = excise_tax = ExciseTax.__table__()
        return (
            product
            .join(template,
                condition=product.template == template.id)
            .join(product_excise_tax,
                condition=(template.id == product_excise_tax.template)
                & (product_excise_tax.country == country))
            .join(excise_tax,
                condition=product_excise_tax.excise_tax == excise_tax.id),
            tables)

    @classmethod
    def _columns(cls, tables):
        context = Transaction().context
        product = tables['product']
        template = tables['template']
        excise_tax = tables['excise_tax']
        return [
            product.id.as_('id'),
            Literal(context.get('company')).as_('company'),
            product.id.as_('product'),
            template.eu_excise_code.as_('eu_excise_code'),
            excise_tax.id.as_('eu_excise_tax'),
            excise_tax.uom.as_('unit'),
            ]

    @classmethod
    def _where(cls, tables):
        pool = Pool()
        Company = pool.get('company.company')
        Location = pool.get('stock.location')

        context = Transaction().context
        product = tables['product']
        template = tables['template']

        is_excise_product = Literal(False)
        if warehouse := context.get('warehouse'):
            warehouse = Location(warehouse)
            if company := context.get('company'):
                company = Company(company)
                if excise_number := warehouse.get_eu_excise_number(company):
                    is_excise_product = (
                        excise_number.is_excise_product_sql(
                            product, template))

        return (template.eu_excise_code != Null) & is_excise_product

    @classmethod
    def get_quantity(cls, declarations, name):
        pool = Pool()
        Product = pool.get('product.product')
        transaction = Transaction()
        context = transaction.context
        quantities = defaultdict(type(None))
        if name == 'start_quantity':
            stock_date_end = context.get('from_date')
            if not stock_date_end:
                stock_date_end = dt.date.min
            else:
                try:
                    stock_date_end -= dt.timedelta(days=1)
                except OverflowError:
                    pass
        elif name == 'end_quantity':
            stock_date_end = context.get('to_date')
            if not stock_date_end:
                stock_date_end = dt.date.max
        else:
            return quantities
        with transaction.set_context(
                stock_date_end=stock_date_end,
                locations=[context.get('warehouse', -1)]):
            products = Product.browse(declarations)
        for declaration, product in zip(declarations, products):
            if excise_tax := declaration.eu_excise_tax:
                name = excise_tax.quantity
                quantities[declaration.id] = excise_tax.convert_quantity(
                    product, product.quantity)
        return quantities

    @classmethod
    def get_input(cls, declarations, names):
        pool = Pool()
        Location = pool.get('stock.location')
        Move = pool.get('stock.move')
        transaction = Transaction()
        context = transaction.context
        cursor = transaction.connection.cursor()

        move = Move.__table__()
        location = Location.__table__()
        quantities = defaultdict(lambda: defaultdict(float))
        id2declaration = {d.id: d for d in declarations}

        warehouse = With('id', query=Location.search([
                    ('parent', 'child_of', [context.get('warehouse', -1)]),
                    ], order=[], query=True))

        where = move.state == 'done'
        where &= move.company == context.get('company', -1)
        where &= move.effective_date >= context.get('from_date')
        where &= move.effective_date <= context.get('to_date')
        where &= (~move.from_location.in_(
                warehouse.select(warehouse.id))
            & move.to_location.in_(
                warehouse.select(warehouse.id)))

        quantity = move.internal_quantity
        columns = cls._input_columns(quantity, move, location)
        others = columns[0].expression  # total
        for qty in columns[1:]:
            others -= qty.expression
        columns.append(others.as_('input_other'))
        query = (move
            .join(location,
                condition=move.from_location == location.id)
            .select(
                move.product.as_('id'),
                *columns,
                group_by=[move.product],
                with_=warehouse))
        declaration_ids = [s.id for s in declarations]
        query.where = where & fields.SQL_OPERATORS['in'](
            move.product, declaration_ids)
        cursor.execute(*query)
        for values in cursor_dict(cursor):
            declaration = id2declaration[values['id']]
            for name in names:
                if qty := values[name]:
                    quantities[name][values['id']] = (
                        declaration.eu_excise_tax.convert_quantity(
                            declaration.product, qty))
        return quantities

    @classmethod
    def _input_columns(cls, quantity, move, location):
        return [
            Sum(quantity).as_('input_total'),
            Sum(Case(
                    (location.type == 'production', quantity),
                    else_=0)).as_('input_production'),
            Sum(Case(
                    (~location.type.in_(['production', 'lost_found'])
                        & (move.eu_excise_duty != Null),
                        quantity),
                    else_=0)).as_('input_duty_suspension'),
            Sum(Case(
                    (~location.type.in_(['production', 'lost_found'])
                        & (move.eu_excise_duty == Null),
                        quantity),
                    else_=0)).as_('input_replacement'),
            ]

    @classmethod
    def get_output(cls, declarations, names):
        pool = Pool()
        Location = pool.get('stock.location')
        Move = pool.get('stock.move')
        transaction = Transaction()
        context = transaction.context
        cursor = transaction.connection.cursor()

        move = Move.__table__()
        location = Location.__table__()
        quantities = defaultdict(lambda: defaultdict(float))
        id2declaration = {d.id: d for d in declarations}

        warehouse = With('id', query=Location.search([
                    ('parent', 'child_of', [context.get('warehouse', -1)]),
                    ], order=[], query=True))

        where = move.state == 'done'
        where &= move.company == context.get('company', -1)
        where &= move.effective_date >= context.get('from_date')
        where &= move.effective_date <= context.get('to_date')
        where &= (move.from_location.in_(
                warehouse.select(warehouse.id))
            & ~move.to_location.in_(
                warehouse.select(warehouse.id)))

        quantity = move.internal_quantity
        columns = cls._output_columns(quantity, move, location)
        others = columns[0].expression  # total
        for qty in columns[1:]:
            others -= qty.expression
        columns.append(others.as_('output_other'))
        query = (move
            .join(location,
                condition=move.to_location == location.id)
            .select(
                move.product.as_('id'),
                *columns,
                group_by=[move.product],
                with_=warehouse))
        declaration_ids = [s.id for s in declarations]
        query.where = where & fields.SQL_OPERATORS['in'](
            move.product, declaration_ids)
        cursor.execute(*query)
        for values in cursor_dict(cursor):
            declaration = id2declaration[values['id']]
            for name in names:
                if qty := values[name]:
                    quantities[name][values['id']] = (
                        declaration.eu_excise_tax.convert_quantity(
                            declaration.product, qty))
        return quantities

    @classmethod
    def _output_columns(cls, quantity, move, location):
        return [
            Sum(quantity).as_('output_total'),
            Sum(Case(
                    (~location.type.in_(['production', 'lost_found'])
                        & (move.eu_excise_duty == Null),
                        quantity),
                    else_=0)).as_('output_with_duty'),
            Sum(Case(
                    (location.type == 'production', quantity),
                    else_=0)).as_('output_production'),
            Sum(Case(
                    (~location.type.in_(['production', 'lost_found'])
                        & (move.eu_excise_duty == 'suspension'),
                        quantity),
                    else_=0)).as_('output_duty_suspension'),
            Sum(Case(
                    (~location.type.in_(['production', 'lost_found'])
                        & (move.eu_excise_duty == 'free'),
                        quantity),
                    else_=0)).as_('output_duty_free'),
            ]

    def get_rec_name(self, name):
        return self.product.rec_name


class ExciseDeclarationProductLine(ModelSQL, ModelView):
    __name__ = 'account.stock.eu.excise.declaration.product.line'

    company = fields.Many2One('company.company', "Company")
    product = fields.Many2One(
        'product.product', "Product",
        context={
            'company': Eval('company', -1),
            },
        depends=['company'])
    eu_excise_code = fields.Function(
        fields.Many2One('product.eu.excise_code', "Excise Code"),
        'on_change_with_eu_excise_code')
    eu_excise_tax = fields.Function(
        fields.Many2One('account.stock.eu.excise.tax', "Excise Tax"),
        'on_change_with_eu_excise_tax')
    unit = fields.Function(
        fields.Many2One('product.uom', "Unit"),
        'on_change_with_unit')
    date = fields.Date("Date")
    move = fields.Many2One('stock.move', "Move")
    location = fields.Many2One('stock.location', "Location")
    origin = fields.Reference("Origin", selection='get_origin')
    document = fields.Function(
        fields.Reference("Document", selection='get_documents'),
        'get_document')
    internal_quantity = fields.Float("Internal Quantity")
    quantity = fields.Function(
        fields.Float("Quantity", digits='unit'), 'get_quantity')
    duty = fields.Selection([
            (None, ""),
            ('suspension', "Suspension"),
            ('free', "Free"),
            ], "Duty")
    direction = fields.Selection([
            ('input', "Input"),
            ('output', "Output"),
            ], "Direction")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('date', 'ASC'))

    @classmethod
    def table_query(cls):
        pool = Pool()
        Move = pool.get('stock.move')
        Location = pool.get('stock.location')
        context = Transaction().context

        move = Move.__table__()

        warehouse = With('id', query=Location.search([
                    ('parent', 'child_of', [context.get('warehouse', -1)]),
                    ], order=[], query=True))

        where = move.state == 'done'
        where &= move.company == context.get('company', -1)
        where &= move.effective_date >= context.get('from_date')
        where &= move.effective_date <= context.get('to_date')
        return Union(move
            .select(
                move.id.as_('id'),
                *cls._columns(move),
                Literal('input').as_('direction'),
                move.from_location.as_('location'),
                where=where
                & (~move.from_location.in_(
                        warehouse.select(warehouse.id))
                    & move.to_location.in_(
                        warehouse.select(warehouse.id))))
            | move
            .select(
                move.id.as_('id'),
                *cls._columns(move, -1),
                Literal('output').as_('direction'),
                move.to_location.as_('location'),
                where=where
                & (move.from_location.in_(
                        warehouse.select(warehouse.id))
                    & ~move.to_location.in_(
                        warehouse.select(warehouse.id)))),
            with_=warehouse)

    @classmethod
    def _columns(cls, move, sign=1):
        return [
            move.company.as_('company'),
            move.product.as_('product'),
            move.effective_date.as_('date'),
            move.id.as_('move'),
            move.origin.as_('origin'),
            (Literal(sign) * move.internal_quantity).as_('internal_quantity'),
            move.eu_excise_duty.as_('duty'),
            ]

    @fields.depends('product')
    def on_change_with_eu_excise_code(self, name=None):
        if self.product:
            return self.product.eu_excise_code

    @fields.depends('product')
    def on_change_with_eu_excise_tax(self, name=None):
        pool = Pool()
        Location = pool.get('stock.location')
        context = Transaction().context
        if self.product:
            country = None
            if warehouse := context.get('warehouse'):
                warehouse = Location(warehouse)
                if warehouse.address and warehouse.address.country:
                    country = warehouse.address.country
            return self.product.get_eu_excise_tax(country)

    @fields.depends('eu_excise_tax')
    def on_change_with_unit(self, name=None):
        if self.eu_excise_tax:
            return self.eu_excise_tax.uom

    @classmethod
    def get_origin(cls):
        pool = Pool()
        Move = pool.get('stock.move')
        return Move.get_origin()

    @classmethod
    def _get_document_models(cls):
        pool = Pool()
        Move = pool.get('stock.move')
        return [m for m, _ in Move.get_shipment() if m] + ['stock.inventory']

    @classmethod
    def get_documents(cls):
        pool = Pool()
        Model = pool.get('ir.model')
        get_name = Model.get_name
        models = cls._get_document_models()
        return [(None, '')] + [(m, get_name(m)) for m in models]

    def get_document(self, name):
        pool = Pool()
        InventoryLine = pool.get('stock.inventory.line')
        if self.move:
            if self.move.shipment:
                return str(self.move.shipment)
            elif isinstance(self.move.origin, InventoryLine):
                return str(self.move.origin.inventory)

    def get_quantity(self, name):
        if self.eu_excise_tax:
            return self.eu_excise_tax.convert_quantity(
                self.product, self.internal_quantity)


class ExciseDeclarationProductLine_Production(metaclass=PoolMeta):
    __name__ = 'account.stock.eu.excise.declaration.product.line'

    @classmethod
    def _get_document_models(cls):
        return super()._get_document_models() + ['production']

    def get_document(self, name):
        document = super().get_document(name)
        if self.move and self.move.production:
            document = str(self.move.production)
        return document
