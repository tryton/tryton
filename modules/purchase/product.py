# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from collections import defaultdict

from sql import Literal
from sql.aggregate import Count, Max

from trytond.i18n import gettext
from trytond.model import (
    Index, MatchMixin, ModelSQL, ModelView, fields, sequence_ordered)
from trytond.modules.currency.fields import Monetary
from trytond.modules.product import (
    ProductDeactivatableMixin, price_digits, round_price)
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval, If, TimeDelta
from trytond.tools import (
    grouped_slice, is_full_text, lstrip_wildcard, reduce_ids)
from trytond.transaction import Transaction

from .exceptions import PurchaseUOMWarning


class Template(metaclass=PoolMeta):
    __name__ = "product.template"
    purchasable = fields.Boolean("Purchasable")
    product_suppliers = fields.One2Many(
        'purchase.product_supplier', 'template', "Suppliers",
        states={
            'invisible': (~Eval('purchasable', False)
                | ~Eval('context', {}).get('company')),
            })
    purchase_uom = fields.Many2One(
        'product.uom', "Purchase UoM",
        states={
            'invisible': ~Eval('purchasable'),
            'required': Eval('purchasable', False),
            },
        domain=[('category', '=', Eval('default_uom_category'))],
        help="The default Unit of Measure for purchases.")

    @fields.depends('default_uom', 'purchase_uom', 'purchasable')
    def on_change_default_uom(self):
        try:
            super(Template, self).on_change_default_uom()
        except AttributeError:
            pass
        if self.default_uom:
            if self.purchase_uom:
                if self.default_uom.category != self.purchase_uom.category:
                    self.purchase_uom = self.default_uom
            else:
                self.purchase_uom = self.default_uom

    @classmethod
    def view_attributes(cls):
        return super(Template, cls).view_attributes() + [
            ('//page[@id="suppliers"]', 'states', {
                    'invisible': ~Eval('purchasable'),
                    })]

    def product_suppliers_used(self, **pattern):
        for product_supplier in self.product_suppliers:
            if product_supplier.match(pattern):
                yield product_supplier

    @classmethod
    def write(cls, *args):
        pool = Pool()
        Warning = pool.get('res.user.warning')
        actions = iter(args)
        for templates, values in zip(actions, actions):
            if not values.get("purchase_uom"):
                continue
            for template in templates:
                if not template.purchase_uom:
                    continue
                if template.purchase_uom.id == values["purchase_uom"]:
                    continue
                for product in template.products:
                    if not product.product_suppliers:
                        continue
                    name = '%s@product_template' % template.id
                    if Warning.check(name):
                        raise PurchaseUOMWarning(
                            name, gettext('purchase.msg_change_purchase_uom'))
        super(Template, cls).write(*args)

    @classmethod
    def copy(cls, templates, default=None):
        pool = Pool()
        ProductSupplier = pool.get('purchase.product_supplier')
        if default is None:
            default = {}
        else:
            default = default.copy()

        copy_suppliers = 'product_suppliers' not in default
        default.setdefault('product_suppliers', None)
        new_templates = super().copy(templates, default)
        if copy_suppliers:
            old2new = {}
            to_copy = []
            for template, new_template in zip(templates, new_templates):
                to_copy.extend(
                    ps for ps in template.product_suppliers if not ps.product)
                old2new[template.id] = new_template.id
            if to_copy:
                ProductSupplier.copy(to_copy, {
                        'template': lambda d: old2new[d['template']],
                        })
        return new_templates


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'

    product_suppliers = fields.One2Many(
        'purchase.product_supplier', 'product', "Suppliers",
        domain=[
            ('template', '=', Eval('template')),
            ],
        states={
            'invisible': (~Eval('purchasable', False)
                | ~Eval('context', {}).get('company')),
            })
    purchase_price_uom = fields.Function(fields.Numeric(
            "Purchase Price", digits=price_digits), 'get_purchase_price_uom')
    last_purchase_price_uom = fields.Function(fields.Numeric(
            "Last Purchase Price", digits=price_digits),
        'get_last_purchase_price_uom')

    @classmethod
    def get_purchase_price_uom(cls, products, name):
        quantity = Transaction().context.get('quantity') or 0
        return cls.get_purchase_price(products, quantity=quantity)

    @classmethod
    def get_last_purchase_price_uom(cls, products, name=None):
        pool = Pool()
        Company = pool.get('company.company')
        Currency = pool.get('currency.currency')
        Date = pool.get('ir.date')
        Line = pool.get('purchase.line')
        Purchase = pool.get('purchase.purchase')
        UoM = pool.get('product.uom')

        transaction = Transaction()
        context = transaction.context
        cursor = transaction.connection.cursor()
        purchase = Purchase.__table__()
        line = Line.__table__()

        line_ids = []
        where = purchase.state.in_(['confirmed', 'processing', 'done'])
        supplier = context.get('supplier')
        if supplier:
            where &= purchase.party == supplier
        for sub_products in grouped_slice(products):
            query = (line
                .join(purchase, condition=line.purchase == purchase.id)
                .select(
                    Max(line.id),
                    where=where & reduce_ids(
                        line.product, map(int, sub_products)),
                    group_by=[line.product]))
            cursor.execute(*query)
            line_ids.extend(i for i, in cursor)
        lines = Line.browse(line_ids)

        uom = None
        if context.get('uom'):
            uom = UoM(context['uom'])

        currency = None
        if context.get('currency'):
            currency = Currency(context['currency'])
        elif context.get('company'):
            currency = Company(context['company']).currency
        date = context.get('purchase_date') or Date.today()

        prices = defaultdict(lambda: None)
        for line in lines:
            default_uom = line.product.default_uom
            if not uom or default_uom.category != uom.category:
                product_uom = default_uom
            else:
                product_uom = uom
            unit_price = UoM.compute_price(
                line.unit, line.unit_price, product_uom)
            if currency and line.purchase.currency != currency:
                with Transaction().set_context(date=date):
                    unit_price = Currency.compute(
                        line.purchase.currency, unit_price, currency,
                        round=False)
            prices[line.product.id] = round_price(unit_price)
        return prices

    def product_suppliers_used(self, **pattern):
        for product_supplier in self.product_suppliers:
            if product_supplier.match(pattern):
                yield product_supplier
        pattern['product'] = None
        yield from self.template.product_suppliers_used(**pattern)

    def _get_purchase_unit_price(self, quantity=0):
        return

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
        Company = pool.get('company.company')
        Currency = pool.get('currency.currency')
        Date = pool.get('ir.date')
        ProductSupplier = pool.get('purchase.product_supplier')
        ProductSupplierPrice = pool.get('purchase.product_supplier.price')

        context = Transaction().context
        prices = {}

        assert len(products) == len(set(products)), "Duplicate products"

        uom = None
        if context.get('uom'):
            uom = Uom(context['uom'])

        currency = None
        if context.get('currency'):
            currency = Currency(context['currency'])
        elif context.get('company'):
            currency = Company(context['company']).currency
        date = context.get('purchase_date') or Date.today()

        last_purchase_prices = cls.get_last_purchase_price_uom(products)

        for product in products:
            unit_price = product._get_purchase_unit_price(quantity=quantity)
            default_uom = product.default_uom
            default_currency = currency
            if not uom or default_uom.category != uom.category:
                product_uom = default_uom
            else:
                product_uom = uom
            pattern = ProductSupplier.get_pattern()
            product_suppliers = product.product_suppliers_used(**pattern)
            try:
                product_supplier = next(product_suppliers)
            except StopIteration:
                pass
            else:
                pattern = ProductSupplierPrice.get_pattern()
                for price in product_supplier.prices:
                    if price.match(quantity, product_uom, pattern):
                        unit_price = price.unit_price
                        default_uom = product_supplier.unit
                        default_currency = product_supplier.currency
                if unit_price is not None:
                    unit_price = Uom.compute_price(
                        default_uom, unit_price, product_uom)
                    if currency and default_currency:
                        with Transaction().set_context(date=date):
                            unit_price = Currency.compute(
                                default_currency, unit_price, currency,
                                round=False)
            if unit_price is None:
                unit_price = last_purchase_prices[product.id]
            else:
                unit_price = round_price(unit_price)
            prices[product.id] = unit_price
        return prices

    @classmethod
    def copy(cls, products, default=None):
        pool = Pool()
        ProductSupplier = pool.get('purchase.product_supplier')
        if default is None:
            default = {}
        else:
            default = default.copy()

        copy_suppliers = 'product_suppliers' not in default
        if 'template' in default:
            default.setdefault('product_suppliers', None)
        new_products = super().copy(products, default)
        if 'template' in default and copy_suppliers:
            template2new = {}
            product2new = {}
            to_copy = []
            for product, new_product in zip(products, new_products):
                if product.product_suppliers:
                    to_copy.extend(product.product_suppliers)
                    template2new[product.template.id] = new_product.template.id
                    product2new[product.id] = new_product.id
            if to_copy:
                ProductSupplier.copy(to_copy, {
                        'product': lambda d: product2new[d['product']],
                        'template': lambda d: template2new[d['template']],
                        })
        return new_products


class ProductSupplier(
        sequence_ordered(), ProductDeactivatableMixin, MatchMixin,
        ModelSQL, ModelView):
    'Product Supplier'
    __name__ = 'purchase.product_supplier'
    template = fields.Many2One(
        'product.template', "Product",
        required=True, ondelete='CASCADE',
        domain=[
            If(Bool(Eval('product')),
                ('products', '=', Eval('product')),
                ()),
            ],
        states={
            'readonly': Eval('id', -1) >= 0,
            },
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    product = fields.Many2One(
        'product.product', "Variant",
        domain=[
            If(Bool(Eval('template')),
                ('template', '=', Eval('template')),
                ()),
            ],
        states={
            'readonly': Eval('id', -1) >= 0,
            },
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    party = fields.Many2One(
        'party.party', 'Supplier', required=True, ondelete='CASCADE',
        states={
            'readonly': Eval('id', -1) >= 0,
            },
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    name = fields.Char("Name", translate=True)
    code = fields.Char("Code")
    prices = fields.One2Many(
        'purchase.product_supplier.price', 'product_supplier', "Prices",
        help="Add price for different criteria.\n"
        "The last matching line is used.")
    company = fields.Many2One(
        'company.company', "Company",
        required=True, ondelete='CASCADE')
    lead_time = fields.TimeDelta(
        "Lead Time",
        domain=['OR',
            ('lead_time', '=', None),
            ('lead_time', '>=', TimeDelta()),
            ],
        help="The time from confirming the purchase order to receiving the "
        "products.\n"
        "If empty the lead time of the supplier is used.")
    currency = fields.Many2One('currency.currency', 'Currency', required=True,
        ondelete='RESTRICT')
    unit = fields.Function(
        fields.Many2One('product.uom', "Unit"), 'on_change_with_unit')

    @classmethod
    def __setup__(cls):
        cls.code.search_unaccented = False
        super().__setup__()
        t = cls.__table__()
        cls._sql_indexes.update({
                Index(t, (t.code, Index.Similarity())),
                })

    @classmethod
    def __register__(cls, module_name):
        table = cls.__table_handler__(module_name)

        # Migration from 5.0: add product/template
        if (table.column_exist('product')
                and not table.column_exist('template')):
            table.column_rename('product', 'template')

        super(ProductSupplier, cls).__register__(module_name)

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_currency():
        Company = Pool().get('company.company')
        if Transaction().context.get('company'):
            company = Company(Transaction().context['company'])
            return company.currency.id

    @fields.depends(
        'product', '_parent_product.template')
    def on_change_product(self):
        if self.product:
            self.template = self.product.template

    @fields.depends('party')
    def on_change_party(self):
        cursor = Transaction().connection.cursor()
        self.currency = self.default_currency()
        if self.party:
            table = self.__table__()
            cursor.execute(*table.select(table.currency,
                    where=table.party == self.party.id,
                    group_by=table.currency,
                    order_by=Count(Literal(1)).desc))
            row = cursor.fetchone()
            if row:
                self.currency, = row

    def get_rec_name(self, name):
        if not self.name and not self.code:
            if self.product:
                name = self.product.rec_name
            else:
                name = self.template.rec_name
        else:
            if self.name:
                name = self.name
            elif self.product:
                name = self.product.name
            else:
                name = self.template.name
            if self.code:
                name = '[' + self.code + ']' + name
        return name

    @classmethod
    def search_rec_name(cls, name, clause):
        _, operator, operand, *extra = clause
        if operator.startswith('!') or operator.startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        code_value = operand
        if operator.endswith('like') and is_full_text(operand):
            code_value = lstrip_wildcard(operand)
        domain = [bool_op,
            ('template', operator, operand, *extra),
            ('product', operator, operand, *extra),
            ('party', operator, operand, *extra),
            ('code', operator, code_value, *extra),
            ('name', operator, operand, *extra),
            ]
        return domain

    @fields.depends(
        'product', '_parent_product.purchase_uom',
        'template', '_parent_template.purchase_uom')
    def on_change_with_unit(self, name=None):
        if self.product:
            return self.product.purchase_uom
        elif self.template:
            return self.template.purchase_uom

    @property
    def lead_time_used(self):
        # Use getattr because it can be called with an unsaved instance
        lead_time = getattr(self, 'lead_time', None)
        party = getattr(self, 'party', None)
        if lead_time is None and party:
            company = getattr(self, 'company', None)
            lead_time = party.get_multivalue(
                'supplier_lead_time', company=company.id if company else None)
        return lead_time

    def compute_supply_date(self, date=None):
        '''
        Compute the supply date for the Product Supplier at the given date
        '''
        Date = Pool().get('ir.date')

        if not date:
            with Transaction().set_context(company=self.company.id):
                date = Date.today()
        if self.lead_time_used is None:
            return datetime.date.max
        return date + self.lead_time_used

    def compute_purchase_date(self, date):
        '''
        Compute the purchase date for the Product Supplier at the given date
        '''
        Date = Pool().get('ir.date')

        if self.lead_time_used is None or date is None:
            with Transaction().set_context(company=self.company.id):
                return Date.today()
        return date - self.lead_time_used

    @staticmethod
    def get_pattern():
        context = Transaction().context
        pattern = {'party': context.get('supplier')}
        if 'product_supplier' in context:
            pattern['id'] = context['product_supplier']
        return pattern


class ProductSupplierPrice(
        sequence_ordered(), ModelSQL, ModelView, MatchMixin):
    'Product Supplier Price'
    __name__ = 'purchase.product_supplier.price'
    product_supplier = fields.Many2One('purchase.product_supplier',
            'Supplier', required=True, ondelete='CASCADE')
    quantity = fields.Float(
        "Quantity",
        required=True,
        domain=[('quantity', '>=', 0)],
        help='Minimal quantity.')
    unit_price = Monetary(
        "Unit Price", currency='currency', required=True, digits=price_digits)

    unit = fields.Function(fields.Many2One(
            'product.uom', "Unit",
            help="The unit in which the quantity is specified."),
        'on_change_with_unit')
    currency = fields.Function(
        fields.Many2One('currency.currency', 'Currency'),
        'on_change_with_currency')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('product_supplier')

    @staticmethod
    def default_quantity():
        return 0.0

    @fields.depends('product_supplier', '_parent_product_supplier.unit')
    def on_change_with_unit(self, name=None):
        return self.product_supplier.unit if self.product_supplier else None

    @fields.depends('product_supplier', '_parent_product_supplier.currency')
    def on_change_with_currency(self, name=None):
        if self.product_supplier:
            return self.product_supplier.currency

    @staticmethod
    def get_pattern():
        return {}

    def match(self, quantity, unit, pattern):
        pool = Pool()
        Uom = pool.get('product.uom')
        test_quantity = Uom.compute_qty(
            self.product_supplier.unit, self.quantity, unit)
        if test_quantity > abs(quantity):
            return False
        return super(ProductSupplierPrice, self).match(pattern)
