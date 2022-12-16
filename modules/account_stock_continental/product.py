# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond import backend
from trytond.model import fields
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta

from trytond.modules.account_product.product import (
    account_used, template_property)

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

    @classmethod
    def update_cost_price(cls, costs):
        pool = Pool()
        Date = pool.get('ir.date')
        Stock = pool.get('stock.location')
        Company = pool.get('company.company')
        Move = pool.get('account.move')

        context = Transaction().context
        locations = Stock.search([('type', '=', 'storage')])
        stock_date_end = Date.today()
        company = Company(context['company'])
        moves = []
        with Transaction().set_context(locations=[l.id for l in locations],
                stock_date_end=stock_date_end):
            for cost, products in costs.items():
                products = cls.browse(products)
                for product in products:
                    difference = cost - product.cost_price
                    quantity = product.quantity
                    amount = company.currency.round(
                        Decimal(str(quantity)) * difference)
                    if amount:
                        moves.append(product._update_cost_price_move(
                                amount, company))
        Move.save(moves)
        Move.post(moves)
        super().update_cost_price(costs)

    def _update_cost_price_move(self, amount, company):
        pool = Pool()
        AccountConfiguration = pool.get('account.configuration')
        Date = pool.get('ir.date')
        Period = pool.get('account.period')
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')

        config = AccountConfiguration(1)
        if amount > 0:
            account = self.account_stock_in_used
        else:
            account = self.account_stock_out_used
        return Move(
            period=Period.find(company.id),
            journal=config.stock_journal,
            date=Date.today(),
            origin=self,
            lines=[Line(
                    debit=amount if amount > 0 else 0,
                    credit=-amount if amount < 0 else 0,
                    account=self.account_stock_used,
                    ),
                Line(
                    debit=-amount if amount < 0 else 0,
                    credit=amount if amount > 0 else 0,
                    account=account,
                    ),
                ],
            )
