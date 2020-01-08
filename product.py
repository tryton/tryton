# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond import backend
from trytond.model import ModelView, fields
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta

from trytond.modules.account_product.product import (
    account_used, template_property)
from trytond.modules.product import price_digits

__all__ = ['Category', 'CategoryAccount', 'Template',
    'Product', 'ModifyCostPriceAsk',
    'ModifyCostPriceShowMove', 'ModifyCostPrice']
account_names = [
    'account_stock', 'account_stock_in', 'account_stock_out']


class Category(metaclass=PoolMeta):
    __name__ = 'product.category'
    account_stock = fields.MultiValue(fields.Many2One(
            'account.account', "Account Stock",
            domain=[
                ('closed', '!=', True),
                ('type.stock', '=', True),
                ('id', 'not in', [
                        Eval('account_stock_in', -1),
                        Eval('account_stock_out', -1)]),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('account_parent')
                    | ~Eval('accounting', False)),
                },
            depends=['account_parent', 'accounting',
                'account_stock_in', 'account_stock_out']))
    account_stock_in = fields.MultiValue(fields.Many2One(
            'account.account', "Account Stock IN",
            domain=[
                ('closed', '!=', True),
                ('type.stock', '=', True),
                ('id', '!=', Eval('account_stock', -1)),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('account_parent')
                    | ~Eval('accounting', False)),
                },
            depends=['account_parent', 'accounting', 'account_stock']))
    account_stock_out = fields.MultiValue(fields.Many2One(
            'account.account', "Account Stock OUT",
            domain=[
                ('closed', '!=', True),
                ('type.stock', '=', True),
                ('id', '!=', Eval('account_stock', -1)),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('account_parent')
                    | ~Eval('accounting', False)),
                },
            depends=['account_parent', 'accounting', 'account_stock']))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field in account_names:
            return pool.get('product.category.account')
        return super(Category, cls).multivalue_model(field)

    @property
    @account_used('account_stock')
    def account_stock_used(self):
        pass

    @property
    @account_used('account_stock_in')
    def account_stock_in_used(self):
        pass

    @property
    @account_used('account_stock_out')
    def account_stock_out_used(self):
        pass


class CategoryAccount(metaclass=PoolMeta):
    __name__ = 'product.category.account'
    account_stock = fields.Many2One(
        'account.account', "Account Stock",
        domain=[
            ('closed', '!=', True),
            ('type.stock', '=', True),
            ('type.statement', '=', 'balance'),
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])
    account_stock_in = fields.Many2One(
        'account.account', "Account Stock IN",
        domain=[
            ('closed', '!=', True),
            ('type.stock', '=', True),
            ('type.statement', '=', 'income'),
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])
    account_stock_out = fields.Many2One(
        'account.account', "Account Stock OUT",
        domain=[
            ('closed', '!=', True),
            ('type.stock', '=', True),
            ('type.statement', '=', 'income'),
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])

    @classmethod
    def __register__(cls, module_name):
        exist = backend.TableHandler.table_exist(cls._table)
        if exist:
            table = cls.__table_handler__(module_name)
            exist &= all(table.column_exist(c) for c in account_names)

            # Migration from 5.4: rename account_stock_{supplier,customer}
            for old, new in [
                    ('account_stock_supplier', 'account_stock_in'),
                    ('account_stock_customer', 'account_stock_out')]:
                if table.column_exist(old):
                    table.column_rename(old, new)

        super(CategoryAccount, cls).__register__(module_name)

        if not exist:
            # Re-migration
            cls._migrate_property([], [], [])

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.extend(account_names)
        value_names.extend(account_names)
        super(CategoryAccount, cls)._migrate_property(
            field_names, value_names, fields)


class Template(metaclass=PoolMeta):
    __name__ = 'product.template'

    @classmethod
    def __setup__(cls):
        super(Template, cls).__setup__()
        cls._modify_no_move.append(
            ('cost_price',
                'account_stock_continental.msg_product_change_cost_price'))

    @property
    @account_used('account_stock', 'account_category')
    def account_stock_used(self):
        pass

    @property
    @account_used('account_stock_in', 'account_category')
    def account_stock_in_used(self):
        pass

    @property
    @account_used('account_stock_out', 'account_category')
    def account_stock_out_used(self):
        pass


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'
    account_stock_used = template_property('account_stock_used')
    account_stock_in_used = template_property('account_stock_in_used')
    account_stock_out_used = template_property('account_stock_out_used')


class ModifyCostPriceAsk(ModelView):
    'Modify Cost Price Ask'
    __name__ = 'product.modify_cost_price.ask'
    template = fields.Many2One('product.template', 'Product', readonly=True,
        states={
            'invisible': ~Eval('template'),
            })
    product = fields.Many2One('product.product', 'Variant', readonly=True,
        states={
            'invisible': ~Eval('product'),
            })
    cost_price = fields.Numeric('Cost Price', required=True,
        digits=price_digits)


class ModifyCostPriceShowMove(ModelView):
    'Modify Cost Price Show Move'
    __name__ = 'product.modify_cost_price.show_move'
    price_difference = fields.Numeric('Price Difference', readonly=True,
        digits=price_digits)
    amount = fields.Numeric('Amount', readonly=True,
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'])
    currency_digits = fields.Integer('Currency Digits', readonly=True)
    description = fields.Char('Description')


class ModifyCostPrice(Wizard):
    'Modify Cost Price'
    __name__ = 'product.modify_cost_price'
    start_state = 'ask_price'
    ask_price = StateView('product.modify_cost_price.ask',
        'account_stock_continental.modify_cost_price_ask_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('OK', 'should_show_move', 'tryton-forward', default=True),
            ])
    should_show_move = StateTransition()
    show_move = StateView('product.modify_cost_price.show_move',
        'account_stock_continental.modify_cost_price_show_move_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('OK', 'create_move', 'tryton-ok', default=True),
            ])
    create_move = StateTransition()
    modify_price = StateTransition()

    @classmethod
    def get_product(cls):
        'Return the product instance'
        pool = Pool()
        Product = pool.get('product.product')
        context = Transaction().context
        return Product(context['active_id'])

    def default_ask_price(self, fields):
        default = {}
        product = self.get_product()
        default['product'] = product.id
        default['cost_price'] = getattr(
            product, 'recompute_cost_price_%s' % product.cost_price_method)()
        return default

    @classmethod
    def get_quantity(cls):
        pool = Pool()
        Date = pool.get('ir.date')
        Stock = pool.get('stock.location')

        locations = Stock.search([('type', '=', 'storage')])
        stock_date_end = Date.today()
        with Transaction().set_context(locations=[l.id for l in locations],
                stock_date_end=stock_date_end):
            product = cls.get_product()
            return product.quantity

    @property
    def company(self):
        pool = Pool()
        User = pool.get('res.user')
        user = User(Transaction().user)
        return user.company

    @property
    def difference_price(self):
        product = self.get_product()
        return self.ask_price.cost_price - product.cost_price

    def get_amount(self):
        return self.company.currency.round(
            Decimal(str(self.get_quantity())) * self.difference_price)

    def transition_should_show_move(self):
        if self.get_quantity() != 0:
            return 'show_move'
        return 'modify_price'

    def default_show_move(self, fields):
        return {
            'amount': self.get_amount(),
            'price_difference': self.difference_price,
            'currency_digits': self.company.currency.digits,
            }

    def get_move_lines(self):
        pool = Pool()
        Line = pool.get('account.move.line')
        product = self.get_product()
        amount = self.get_amount()
        if amount > 0:
            account = product.account_stock_in_used
        else:
            account = product.account_stock_out_used
        return [Line(
                debit=amount if amount > 0 else 0,
                credit=-amount if amount < 0 else 0,
                account=product.account_stock_used,
                ),
            Line(
                debit=-amount if amount < 0 else 0,
                credit=amount if amount > 0 else 0,
                account=account,
                ),
            ]

    def get_move(self):
        pool = Pool()
        Date = pool.get('ir.date')
        Period = pool.get('account.period')
        User = pool.get('res.user')
        Move = pool.get('account.move')
        AccountConfiguration = pool.get('account.configuration')

        config = AccountConfiguration(1)
        user = User(Transaction().user)
        period_id = Period.find(user.company.id)
        return Move(
            description=self.show_move.description,
            period=period_id,
            journal=config.stock_journal,
            date=Date.today(),
            origin=self.get_product(),
            lines=self.get_move_lines(),
            )

    def transition_create_move(self):
        Move = Pool().get('account.move')
        move = self.get_move()
        move.save()
        Move.post([move])
        return 'modify_price'

    def transition_modify_price(self):
        pool = Pool()
        Product = pool.get('product.product')
        with Transaction().set_context(_check_access=False):
            Product.write([self.get_product()], {
                    'cost_price': self.ask_price.cost_price,
                    })
        return 'end'
