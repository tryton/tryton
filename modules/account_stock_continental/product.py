# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from functools import partial

from trytond.model import ModelView, fields
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta

from trytond.modules.account_product import MissingFunction
from trytond.modules.product import price_digits, TemplateFunction

__all__ = ['Category', 'Template', 'Product', 'UpdateCostPriceAsk',
    'UpdateCostPriceShowMove', 'UpdateCostPrice']


class Category:
    __metaclass__ = PoolMeta
    __name__ = 'product.category'
    account_stock = fields.Property(fields.Many2One('account.account',
            'Account Stock', domain=[
                ('kind', '=', 'stock'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('account_parent')
                    | ~Eval('accounting', False)),
                },
            depends=['account_parent', 'accounting']))
    account_stock_supplier = fields.Property(fields.Many2One('account.account',
            'Account Stock Supplier', domain=[
                ('kind', '=', 'stock'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('account_parent')
                    | ~Eval('accounting', False)),
                },
            depends=['account_parent', 'accounting']))
    account_stock_customer = fields.Property(fields.Many2One('account.account',
            'Account Stock Customer', domain=[
                ('kind', '=', 'stock'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('account_parent')
                    | ~Eval('accounting', False)),
                },
            depends=['account_parent', 'accounting']))
    account_stock_production = fields.Property(
        fields.Many2One('account.account',
            'Account Stock Production', domain=[
                ('kind', '=', 'stock'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('account_parent')
                    | ~Eval('accounting', False)),
                },
            depends=['account_parent', 'accounting']))
    account_stock_lost_found = fields.Property(fields.Many2One(
            'account.account', 'Account Stock Lost and Found', domain=[
                ('kind', '=', 'stock'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('account_parent')
                    | ~Eval('accounting', False)),
                },
            depends=['account_parent', 'accounting']))
    account_stock_used = MissingFunction(fields.Many2One('account.account',
        'Account Stock Used'), 'missing_account', 'get_account')
    account_stock_supplier_used = MissingFunction(fields.Many2One(
            'account.account', 'Account Stock Supplier Used'),
        'missing_account', 'get_account')
    account_stock_customer_used = MissingFunction(fields.Many2One(
            'account.account', 'Account Stock Customer Used'),
        'missing_account', 'get_account')
    account_stock_production_used = MissingFunction(fields.Many2One(
            'account.account', 'Account Stock Production Used'),
        'missing_account', 'get_account')
    account_stock_lost_found_used = MissingFunction(fields.Many2One(
        'account.account', 'Account Stock Lost and Found'),
        'missing_account', 'get_account')


class Template:
    __metaclass__ = PoolMeta
    __name__ = 'product.template'
    account_stock = fields.Property(fields.Many2One('account.account',
            'Account Stock',
            domain=[
                ('kind', '=', 'stock'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('account_category')
                    | (Eval('type') != 'goods')),
                }, help='This account will be used instead of the one defined '
            'on the category.',
            depends=['account_category', 'type']))
    account_stock_supplier = fields.Property(fields.Many2One('account.account',
            'Account Stock Supplier',
            domain=[
                ('kind', '=', 'stock'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('account_category')
                    | (Eval('type') != 'goods')),
                }, help='This account will be used instead of the one defined '
            'on the category.',
            depends=['account_category', 'type']))
    account_stock_customer = fields.Property(fields.Many2One('account.account',
            'Account Stock Customer',
            domain=[
                ('kind', '=', 'stock'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('account_category')
                    | (Eval('type') != 'goods')),
                }, help='This account will be used instead of the one defined '
            'on the category.',
            depends=['account_category', 'type']))
    account_stock_production = fields.Property(
        fields.Many2One('account.account',
            'Account Stock Production',
            domain=[
                ('kind', '=', 'stock'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('account_category')
                    | (Eval('type') != 'goods')),
                }, help='This account will be used instead of the one defined '
            'on the category.',
            depends=['account_category', 'type']))
    account_stock_lost_found = fields.Property(fields.Many2One(
            'account.account', 'Account Stock Lost and Found',
            domain=[
                ('kind', '=', 'stock'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ],
            states={
                'invisible': (~Eval('context', {}).get('company')
                    | Eval('account_category')
                    | (Eval('type') != 'goods')),
                }, help='This account will be used instead of the one defined '
            'on the category.',
            depends=['account_category', 'type']))
    account_stock_used = MissingFunction(fields.Many2One('account.account',
        'Account Stock Used'), 'missing_account', 'get_account')
    account_stock_supplier_used = MissingFunction(fields.Many2One(
            'account.account', 'Account Stock Supplier Used'),
        'missing_account', 'get_account')
    account_stock_customer_used = MissingFunction(fields.Many2One(
            'account.account', 'Account Stock Customer Used'),
        'missing_account', 'get_account')
    account_stock_production_used = MissingFunction(fields.Many2One(
            'account.account', 'Account Stock Production Used'),
        'missing_account', 'get_account')
    account_stock_lost_found_used = MissingFunction(fields.Many2One(
            'account.account', 'Account Stock Lost and Found'),
        'missing_account', 'get_account')

    @classmethod
    def __setup__(cls):
        super(Template, cls).__setup__()
        cls._modify_no_move.append(('cost_price', 'change_cost_price'))
        cls._error_messages.update({
                'change_cost_price': ('You cannot change the cost price for '
                    'a product which is associated to stock moves.\n'
                    'You must use the "Update Cost Price" wizard.'),
                })


class Product:
    __metaclass__ = PoolMeta
    __name__ = 'product.product'
    # Avoid raise of UserError from MissingFunction
    account_stock_used = fields.Function(
        fields.Many2One('account.account', 'Account Stock Used'),
        'get_template')
    account_stock_supplier_used = fields.Function(
        fields.Many2One('account.account', 'Account Stock Supplier Used'),
        'get_template')
    account_stock_customer_used = fields.Function(
        fields.Many2One('account.account', 'Account Stock Customer Used'),
        'get_template')
    account_stock_production_used = fields.Function(
        fields.Many2One('account.account', 'Account Stock Production Used'),
        'get_template')
    account_stock_lost_found_used = fields.Function(
        fields.Many2One('account.account', 'Account Stock Lost and Found'),
        'get_template')


class UpdateCostPriceAsk(ModelView):
    'Update Cost Price Ask'
    __name__ = 'product.update_cost_price.ask'
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


class UpdateCostPriceShowMove(ModelView):
    'Update Cost Price Show Move'
    __name__ = 'product.update_cost_price.show_move'
    price_difference = fields.Numeric('Price Difference', readonly=True,
        digits=price_digits)
    amount = fields.Numeric('Amount', readonly=True,
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'])
    currency_digits = fields.Integer('Currency Digits', readonly=True)
    journal = fields.Many2One('account.journal', 'Journal', required=True)
    stock_account = fields.Many2One('account.account', 'Stock Account',
        readonly=True)
    counterpart = fields.Many2One('account.account', 'Counterpart',
        domain=[
            ('company', 'in',
                [Eval('context', {}).get('company', -1), None]),
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
            Button('OK', 'should_show_move', 'tryton-go-next', default=True),
            ])
    should_show_move = StateTransition()
    show_move = StateView('product.update_cost_price.show_move',
        'account_stock_continental.update_cost_price_show_move_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('OK', 'create_move', 'tryton-ok', default=True),
            ])
    create_move = StateTransition()
    update_price = StateTransition()

    @classmethod
    def __setup__(cls):
        super(UpdateCostPrice, cls).__setup__()
        cls._error_messages.update({
                'same_account': ('The stock account and the counterpart can '
                    'not be the same account'),
                })

    def default_ask_price(self, fields):
        pool = Pool()
        Product = pool.get('product.product')
        Template = pool.get('product.template')

        context = Transaction().context
        default = {}
        if ('product' in fields
                and context['active_model'] == 'product.product'):
            product = Product(context['active_id'])
            template = product.template
            default['product'] = product.id
        elif ('template' in fields
                and context['active_model'] == 'product.template'):
            template = Template(context['active_id'])
            product = template.products[0]
            default['template'] = template.id
        else:
            return default
        default['cost_price'] = getattr(product, 'recompute_cost_price_%s' %
            product.cost_price_method)()
        return default

    @staticmethod
    def get_product():
        'Return the product or template instance'
        pool = Pool()
        Product = pool.get('product.product')
        ProductTemplate = pool.get('product.template')
        context = Transaction().context
        if context['active_model'] == 'product.product':
            return Product(context['active_id'])
        else:
            return ProductTemplate(context['active_id'])

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
            if hasattr(product.__class__, 'cost_price'):
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

        product = self.get_product()
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
        Line = Pool().get('account.move.line')
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
        return Move(
            description=self.show_move.description,
            period=period_id,
            journal=self.show_move.journal,
            date=Date.today(),
            origin=self.get_product(),
            lines=self.get_move_lines(),
            )

    def transition_create_move(self):
        Move = Pool().get('account.move')

        if self.show_move.counterpart == self.show_move.stock_account:
            self.raise_user_error('same_account')
        move = self.get_move()
        move.save()
        Move.post([move])
        return 'update_price'

    def transition_update_price(self):
        pool = Pool()
        Product = pool.get('product.product')
        ProductTemplate = pool.get('product.template')

        if not isinstance(Product.cost_price, TemplateFunction):
            write = partial(Product.write, [self.ask_price.product])
        else:
            if self.ask_price.template:
                template = self.ask_price.template
            else:
                template = self.ask_price.product.template
            write = partial(ProductTemplate.write, [template])

        write({'cost_price': self.ask_price.cost_price})
        return 'end'
