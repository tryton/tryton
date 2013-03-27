#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal
from trytond.model import ModelView, fields
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.pyson import Eval, Get
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta

__all__ = ['Category', 'Template', 'UpdateCostPriceAsk',
    'UpdateCostPriceShowMove', 'UpdateCostPrice']
__metaclass__ = PoolMeta


class Category:
    __name__ = 'product.category'
    account_stock = fields.Property(fields.Many2One('account.account',
            'Account Stock', domain=[
                ('kind', '=', 'stock'),
                ('company', '=', Eval('context', {}).get('company', 0)),
                ],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('account_parent')),
                },
            depends=['account_parent']))
    account_stock_supplier = fields.Property(fields.Many2One('account.account',
            'Account Stock Supplier', domain=[
                ('kind', '=', 'stock'),
                ('company', '=', Eval('context', {}).get('company', 0)),
                ],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('account_parent')),
                },
            depends=['account_parent']))
    account_stock_customer = fields.Property(fields.Many2One('account.account',
            'Account Stock Customer', domain=[
                ('kind', '=', 'stock'),
                ('company', '=', Eval('context', {}).get('company', 0)),
                ],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('account_parent')),
                },
            depends=['account_parent']))
    account_stock_production = fields.Property(
        fields.Many2One('account.account',
            'Account Stock Production', domain=[
                ('kind', '=', 'stock'),
                ('company', '=', Eval('context', {}).get('company', 0)),
                ],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('account_parent')),
                },
            depends=['account_parent']))
    account_stock_lost_found = fields.Property(fields.Many2One(
            'account.account', 'Account Stock Lost and Found', domain=[
                ('kind', '=', 'stock'),
                ('company', '=', Eval('context', {}).get('company', 0)),
                ],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('account_parent')),
                },
            depends=['account_parent']))
    account_stock_used = fields.Function(fields.Many2One('account.account',
        'Account Stock Used'), 'get_account')
    account_stock_supplier_used = fields.Function(fields.Many2One(
        'account.account', 'Account Stock Supplier Used'), 'get_account')
    account_stock_customer_used = fields.Function(fields.Many2One(
        'account.account', 'Account Stock Customer Used'), 'get_account')
    account_stock_production_used = fields.Function(fields.Many2One(
        'account.account', 'Account Stock Production Used'), 'get_account')
    account_stock_lost_found_used = fields.Function(fields.Many2One(
        'account.account', 'Account Stock Lost and Found'), 'get_account')


class Template:
    __name__ = 'product.template'
    account_stock = fields.Property(fields.Many2One('account.account',
            'Account Stock',
            domain=[
                ('kind', '=', 'stock'),
                ('company', '=', Eval('context', {}).get('company', 0)),
                ],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('account_category')
                    | (Eval('type') != 'goods')),
                'required': ((Eval('type') == 'goods')
                    & Eval('context', {}).get('company')
                    & ~Eval('account_category')),
                }, help='This account will be used instead of the one defined '
            'on the category.',
            depends=['account_category', 'type']))
    account_stock_supplier = fields.Property(fields.Many2One('account.account',
            'Account Stock Supplier',
            domain=[
                ('kind', '=', 'stock'),
                ('company', '=', Eval('context', {}).get('company', 0)),
                ],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('account_category')
                    | (Eval('type') != 'goods')),
                'required': ((Eval('type') == 'goods')
                    & Eval('context', {}).get('company')
                    & ~Eval('account_category')),
                }, help='This account will be used instead of the one defined '
            'on the category.',
            depends=['account_category', 'type']))
    account_stock_customer = fields.Property(fields.Many2One('account.account',
            'Account Stock Customer',
            domain=[
                ('kind', '=', 'stock'),
                ('company', '=', Eval('context', {}).get('company', 0)),
                ],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('account_category')
                    | (Eval('type') != 'goods')),
                'required': ((Eval('type') == 'goods')
                    & Eval('context', {}).get('company')
                    & ~Eval('account_category')),
                }, help='This account will be used instead of the one defined '
            'on the category.',
            depends=['account_category', 'type']))
    account_stock_production = fields.Property(
        fields.Many2One('account.account',
            'Account Stock Production',
            domain=[
                ('kind', '=', 'stock'),
                ('company', '=', Eval('context', {}).get('company', 0)),
                ],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('account_category')
                    | (Eval('type') != 'goods')),
                'required': ((Eval('type') == 'goods')
                    & Eval('context', {}).get('company')
                    & ~Eval('account_category')),
                }, help='This account will be used instead of the one defined '
            'on the category.',
            depends=['account_category', 'type']))
    account_stock_lost_found = fields.Property(fields.Many2One(
            'account.account', 'Account Stock Lost and Found',
            domain=[
                ('kind', '=', 'stock'),
                ('company', '=', Eval('context', {}).get('company', 0)),
                ],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('account_category')
                    | (Eval('type') != 'goods')),
                'required': ((Eval('type') == 'goods')
                    & Eval('context', {}).get('company')
                    & ~Eval('account_category')),
                }, help='This account will be used instead of the one defined '
            'on the category.',
            depends=['account_category', 'type']))
    account_stock_used = fields.Function(fields.Many2One('account.account',
        'Account Stock Used'), 'get_account')
    account_stock_supplier_used = fields.Function(fields.Many2One(
        'account.account', 'Account Stock Supplier Used'), 'get_account')
    account_stock_customer_used = fields.Function(fields.Many2One(
        'account.account', 'Account Stock Customer Used'), 'get_account')
    account_stock_production_used = fields.Function(fields.Many2One(
        'account.account', 'Account Stock Production Used'), 'get_account')
    account_stock_lost_found_used = fields.Function(fields.Many2One(
        'account.account', 'Account Stock Lost and Found'), 'get_account')

    @classmethod
    def __setup__(cls):
        super(Template, cls).__setup__()
        cls.cost_price.states['readonly'] = (
            cls.cost_price.states.get('readonly', False)
            | ((Eval('type', 'goods') == 'goods') & (Eval('id', -1) >= 0)))
        if 'type' not in cls.cost_price.depends:
            cls.cost_price.depends.append('type')


class UpdateCostPriceAsk(ModelView):
    'Update Cost Price Ask'
    __name__ = 'product.update_cost_price.ask'
    product = fields.Many2One('product.product', 'Product', readonly=True)
    cost_price = fields.Numeric('Cost Price', required=True, digits=(16, 4))


class UpdateCostPriceShowMove(ModelView):
    'Update Cost Price Show Move'
    __name__ = 'product.update_cost_price.show_move'
    price_difference = fields.Numeric('Price Difference', readonly=True,
        digits=(16, 4))
    amount = fields.Numeric('Amount', readonly=True,
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'])
    currency_digits = fields.Integer('Currency Digits', readonly=True)
    journal = fields.Many2One('account.journal', 'Journal', required=True)
    stock_account = fields.Many2One('account.account', 'Stock Account',
        readonly=True)
    counterpart = fields.Many2One('account.account', 'Counterpart',
        domain=[
            ('company', 'in', [Get(Eval('context', {}), 'company'), False]),
            ('id', '!=', Eval('stock_account')),
            ],
        depends=['stock_account'], required=True)
    description = fields.Char('Description')


class UpdateCostPrice(Wizard):
    'Update Cost Price'
    __name__ = 'product.update_cost_price'
    start_state = 'ask_price'
    ask_price = StateView('product.update_cost_price.ask',
        'account_stock_continental.update_cost_price_ask_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Ok', 'should_show_move', 'tryton-go-next', default=True),
            ])
    should_show_move = StateTransition()
    show_move = StateView('product.update_cost_price.show_move',
        'account_stock_continental.update_cost_price_show_move_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Ok', 'create_move', 'tryton-ok', default=True),
            ])
    create_move = StateTransition()
    update_price = StateTransition()

    @classmethod
    def __setup__(cls):
        super(UpdateCostPrice, cls).__setup__()
        cls._error_messages.update({
                'same_account': 'The stock account and the counterpart can '
                    'not be the same account',
                })

    def default_ask_price(self, fields):
        if 'product' in fields:
            return {
                'product': Transaction().context['active_id'],
                }

    @staticmethod
    def get_quantity():
        pool = Pool()
        Date = pool.get('ir.date')
        Product = pool.get('product.product')
        Stock = pool.get('stock.location')

        locations = Stock.search([('type', '=', 'storage')])
        stock_date_end = Date.today()
        with Transaction().set_context(locations=[l.id for l in locations],
                stock_date_end=stock_date_end):
            product = Product(Transaction().context['active_id'])
            if hasattr(Product, 'cost_price'):
                return product.quantity
            else:
                return product.template.quantity

    def transition_should_show_move(self):
        if self.get_quantity() != 0:
            return 'show_move'
        return 'update_price'

    def default_show_move(self, fields):
        pool = Pool()
        User = pool.get('res.user')
        AccountConfiguration = pool.get('account.configuration')
        Product = pool.get('product.product')

        product = Product(Transaction().context['active_id'])
        price_diff = (self.ask_price.cost_price
                - product.cost_price)
        user = User(Transaction().user)
        amount = user.company.currency.round(
            Decimal(str(self.get_quantity())) * price_diff)
        stock_account_id = product.account_stock_used.id
        config = AccountConfiguration(1)
        stock_journal_id = config.stock_journal.id
        counterpart_id = (config.cost_price_counterpart_account.id if
            config.cost_price_counterpart_account else None)
        return {
            'journal': stock_journal_id,
            'amount': amount,
            'price_difference': price_diff,
            'stock_account': stock_account_id,
            'counterpart': counterpart_id,
            'currency_digits': user.company.currency.digits,
            }

    def get_move_lines(self):
        Line = Pool.get('account.move.line')
        amount = self.show_move.amount
        return [Line(
                debit=amount if amount > 0 else 0,
                credit=-amount if amount < 0 else 0,
                account=self.show_move.stock_account,
                ),
            Line(
                debit=-amount if amount < 0 else 0,
                credit=amount if amount > 0 else 0,
                account=self.show_move.counterpart,
                ),
            ]

    def get_move(self):
        pool = Pool()
        Date = pool.get('ir.date')
        Period = pool.get('account.period')
        User = pool.get('res.user')
        Move = pool.get('account.move')

        user = User(Transaction().user)
        period_id = Period.find(user.company.id)
        with Transaction().set_user(0, set_context=True):
            return Move(
                description=self.show_move.description,
                period=period_id,
                journal=self.show_move.journal,
                date=Date.today(),
                origin=self.ask_price.product,
                lines=self.get_move_lines(),
                )

    def transition_create_move(self):
        Move = Pool().get('account.move')

        if self.show_move.counterpart == self.show_move.stock_account:
            self.raise_user_error('same_account')
        move = self.get_move()
        move.save()
        with Transaction().set_user(0, set_context=True):
            Move.post([move])
        return 'update_price'

    def transition_update_price(self):
        Product = Pool().get('product.product')
        Product.write([self.ask_price.product], {
                'cost_price': self.ask_price.cost_price,
                })
        return 'end'
