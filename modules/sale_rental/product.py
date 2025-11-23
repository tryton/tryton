# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime as dt
from decimal import Decimal
from itertools import chain

from trytond.i18n import gettext
from trytond.model import (
    MatchMixin, ModelSQL, ModelView, fields, sequence_ordered)
from trytond.modules.account_product.exceptions import TaxError
from trytond.modules.account_product.product import (
    account_used, template_property)
from trytond.modules.currency.fields import Monetary
from trytond.modules.product import price_digits, round_price
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Id, If, TimeDelta
from trytond.transaction import Transaction


class Category(metaclass=PoolMeta):
    __name__ = 'product.category'

    account_rental = fields.MultiValue(fields.Many2One(
            'account.account', "Account Rental",
            domain=[
                ('closed', '!=', True),
                ('type.revenue', '=', True),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ],
            states={
                'invisible': (
                    ~Eval('context', {}).get('company', -1)
                    | Eval('account_parent', True)
                    | ~Eval('accounting', False)),
                }))
    customer_rental_taxes = fields.Many2Many(
        'product.category-customer_rental-account.tax',
        'category', 'tax', "Customer Rental Taxes",
        order=[('tax.sequence', 'ASC'), ('tax.id', 'ASC')],
        domain=[
            ('parent', '=', None),
            ['OR',
                ('group', '=', None),
                ('group.kind', 'in', ['sale', 'both']),
                ],
            ],
        states={
            'invisible': (
                ~Eval('context', {}).get('company')
                | Eval('taxes_parent', False)
                | ~Eval('accounting', False)),
            },
        help="The taxes to apply when renting goods or services "
        "of this category.")
    customer_rental_taxes_used = fields.Function(
        fields.Many2Many(
            'account.tax', None, None, "Customer Rental Taxes Used"),
        'get_taxes')

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'account_rental':
            return pool.get('product.category.account')
        return super().multivalue_model(field)

    @property
    @account_used('account_rental')
    def account_rental_used(self):
        pass


class CategoryAccount(metaclass=PoolMeta):
    __name__ = 'product.category.account'

    account_rental = fields.Many2One(
        'account.account', "Account Rental",
        domain=[
            ('closed', '!=', True),
            ('type.revenue', '=', True),
            ('company', '=', Eval('company', -1)),
            ])


class CategoryCustomerRentalTax(ModelSQL):
    "Category - Customer Rental Tax"
    __name__ = 'product.category-customer_rental-account.tax'
    category = fields.Many2One(
        'product.category', "Category", ondelete='CASCADE', required=True)
    tax = fields.Many2One(
        'account.tax', "Tax", ondelete='RESTRICT', required=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('tax')


class Template(metaclass=PoolMeta):
    __name__ = 'product.template'

    rentable = fields.Boolean(
        "Rentable",
        states={
            'invisible': ~Eval('type').in_(['assets', 'service']),
            })
    rental_unit = fields.Many2One(
        'product.uom', "Rental Unit",
        domain=[
            ('category', '=', Id('product', 'uom_cat_time')),
            ],
        states={
            'invisible': ~Eval('rentable', False),
            'required': Eval('rentable', False),
            })
    rental_per_day = fields.Boolean(
        "Rental per Day",
        states={
            'invisible': ~Eval('rentable', False),
            })
    rental_prices = fields.One2Many(
        'product.rental.price', 'template', "Rental Prices",
        states={
            'invisible': ~Eval('rentable', False),
            })

    @classmethod
    def default_rental_per_day(cls):
        return False

    @property
    @fields.depends('account_category', methods=['get_account'])
    @account_used('account_rental', 'account_category')
    def account_rental_used(self):
        pass

    @property
    @fields.depends(methods=['get_taxes', 'account_rental_used'])
    def customer_rental_taxes_used(self):
        taxes = self.get_taxes('customer_rental_taxes_used')
        if taxes is None:
            account = self.account_rental_used
            if account:
                taxes = account.taxes
        if taxes is None:
            # Allow empty values on on_change
            if Transaction().readonly:
                taxes = []
            else:
                raise TaxError(
                    gettext('account_product.msg_missing_taxes',
                        name=self.rec_name))
        return taxes

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('//page[@id="rental"]', 'states', {
                    'invisible': ~Eval('rentable', False),
                    })]

    @classmethod
    def copy(cls, templates, default=None):
        pool = Pool()
        RentalPrice = pool.get('product.rental.price')
        default = default.copy() if default is not None else {}

        copy_rental_prices = 'rental_prices' not in default
        default.setdefault('rental_prices', None)
        new_templates = super().copy(templates, default=default)
        if copy_rental_prices:
            old2new = {}
            to_copy = []
            for template, new_template in zip(templates, new_templates):
                to_copy.extend(
                    rp for rp in template.rental_prices if not rp.product)
                old2new[template.id] = new_template.id
            if to_copy:
                RentalPrice.copy(to_copy, {
                        'template': lambda d: old2new[d['template']],
                        })
        return new_templates


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'

    rental_prices = fields.One2Many(
        'product.rental.price', 'product', "Rental Prices",
        domain=[
            ('template', '=', Eval('template', -1)),
            ],
        states={
            'invisible': ~Eval('rentable', False),
            })
    rental_price_uom = fields.Function(
        Monetary("Rental Price", digits=price_digits),
        'get_rental_price_uom')
    account_rental_used = template_property('account_rental_used')
    customer_rental_taxes_used = template_property(
        'customer_rental_taxes_used')

    @classmethod
    def get_rental_price_uom(cls, products, name):
        context = Transaction().context
        quantity = context.get('quantity') or 0
        duration = context.get('duration') or dt.timedelta()
        return cls.get_rental_price(
            products, quantity=quantity, duration=duration)

    @classmethod
    def get_rental_price(cls, products, quantity=0, duration=None):
        """
        Return the rental price for products, quantity and duration.
        It uses if set in the context:
            uom: the unit of measure or the sale uom of the product
            currency: the currency id for the returned price
        """
        pool = Pool()
        Currency = pool.get('currency.currency')
        Date = pool.get('ir.date')
        UoM = pool.get('product.uom')
        User = pool.get('res.user')

        transaction = Transaction()
        context = transaction.context
        today = Date.today()
        prices = {}

        assert len(products) == len(set(products))

        uom = None
        if context.get('uom'):
            uom = UoM(context['uom'])
        currency = None
        if context.get('currency'):
            currency = Currency(context['currency'])
        user = User(transaction.user)
        date = context.get('rental_date') or today

        for product in products:
            unit_price = product._get_rental_unit_price(
                quantity=quantity, duration=duration, company=user.company.id)
            if unit_price is not None:
                if uom and product.default_uom.category == uom.category:
                    unit_price = UoM.compute_price(
                        product.default_uom, unit_price, uom)
                if currency and user.company:
                    if user.company.currency != currency:
                        with transaction.set_context(date=date):
                            unit_price = Currency.compute(
                                user.company.currency, unit_price,
                                currency, round=False)
                unit_price = round_price(unit_price)
            prices[product.id] = unit_price
        return prices

    def _get_rental_unit_price(self, quantity=0, duration=None, **pattern):
        for price in chain(self.rental_prices, self.template.rental_prices):
            if price.match(quantity, duration, pattern):
                return price.get_unit_price(self.rental_unit)

    @classmethod
    def copy(cls, products, default=None):
        pool = Pool()
        RentalPrice = pool.get('product.rental.price')
        default = default.copy() if default is not None else {}

        copy_rental_prices = 'rental_prices' not in default
        if 'template' in default:
            default.setdefault('rental_prices', None)
        new_products = super().copy(products, default=default)
        if 'template' in default and copy_rental_prices:
            template2new = {}
            product2new = {}
            to_copy = []
            for product, new_product in zip(products, new_products):
                if product.rental_prices:
                    to_copy.extend(product.rental_prices)
                    template2new[product.template.id] = new_product.template.id
                    product2new[product.id] = new_product.id
            if to_copy:
                RentalPrice.copy(to_copy, {
                        'product': lambda d: product2new[d['product']],
                        'template': lambda d: template2new[d['template']],
                        })
        return new_products


class RentalPrice(sequence_ordered(), ModelSQL, ModelView, MatchMixin):
    __name__ = 'product.rental.price'

    template = fields.Many2One(
        'product.template', "Product", required=True, ondelete='CASCADE',
        domain=[
            If(Eval('product'),
                ('products', '=', Eval('product', -1)),
                ()),
            ],
        context={
            'company': Eval('company', -1),
            },
        depends=['company'])
    product = fields.Many2One(
        'product.product', "Variant",
        domain=[
            If(Eval('template'),
                ('template', '=', Eval('template', -1)),
                ()),
            ],
        context={
            'company': Eval('company', -1),
            },
        depends=['company'])
    company = fields.Many2One(
        'company.company', "Company", required=True, ondelete='CASCADE')
    duration = fields.TimeDelta(
        "Duration", required=True,
        domain=[
            ('duration', '>', TimeDelta()),
            ],
        help="The minimal duration to apply the price.")
    price = Monetary(
        "Price", currency='currency', digits=price_digits, required=True)

    currency = fields.Function(
        fields.Many2One('currency.currency', "Currency"),
        'on_change_with_currency')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('template')
        cls._order.insert(0, ('company', 'ASC'))

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @fields.depends('product', '_parent_product.template')
    def on_change_product(self):
        if self.product:
            self.template = self.product.template

    @fields.depends('company')
    def on_change_with_currency(self, name=None):
        if self.company:
            return self.company.currency.id

    def match(self, quantity, duration, pattern, match_none=False):
        if self.duration > duration:
            return False
        return super().match(pattern, match_none=match_none)

    def get_unit_price(self, unit):
        pool = Pool()
        UoM = pool.get('product.uom')
        Data = pool.get('ir.model.data')
        hour = UoM(Data.get_id('product', 'uom_hour'))
        unit_price = (
            self.price / Decimal(self.duration.total_seconds() / 60 / 60))
        return UoM.compute_price(hour, unit_price, unit)
