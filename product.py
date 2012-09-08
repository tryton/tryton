#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import copy
from decimal import Decimal
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.pyson import Eval, Get
from trytond.transaction import Transaction
from trytond.pool import Pool


class Category(ModelSQL, ModelView):
    _name = 'product.category'

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
    account_stock_lost_found_used = fields.Function(fields.Many2One(
        'account.account', 'Account Stock Lost and Found'), 'get_account')

Category()


class Template(ModelSQL, ModelView):
    _name = 'product.template'

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
    account_stock_lost_found_used = fields.Function(fields.Many2One(
        'account.account', 'Account Stock Lost and Found'), 'get_account')

    def __init__(self):
        super(Template, self).__init__()
        self.cost_price = copy.copy(self.cost_price)
        self.cost_price.states = copy.copy(self.cost_price.states)
        self.cost_price.states['readonly'] = (
            self.cost_price.states.get('readonly', False)
            | ((Eval('type', 'goods') == 'goods') & (Eval('id', -1) >= 0)))
        self.cost_price.depends = copy.copy(self.cost_price.depends)
        if 'type' not in self.cost_price.depends:
            self.cost_price.depends.append('type')
        self._reset_columns()

Template()


class UpdateCostPriceAsk(ModelView):
    'Update Cost Price Ask'
    _name = 'product.update_cost_price.ask'
    product = fields.Many2One('product.product', 'Product', readonly=True)
    cost_price = fields.Numeric('Cost Price', required=True, digits=(16, 4))

UpdateCostPriceAsk()


class UpdateCostPriceShowMove(ModelView):
    'Update Cost Price Show Move'
    _name = 'product.update_cost_price.show_move'
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
        depends=['company', 'stock_account'], required=True)
    description = fields.Char('Description', required=True)

UpdateCostPriceShowMove()


class UpdateCostPrice(Wizard):
    'Update Cost Price'
    _name = 'product.update_cost_price'
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

    def __init__(self):
        super(UpdateCostPrice, self).__init__()
        self._error_messages.update({
                'same_account': 'The stock account and the counterpart can '
                    'not be the same account',
                })

    def default_ask_price(self, session, fields):
        if 'product' in fields:
            return {
                'product': Transaction().context['active_id'],
                }

    def get_quantity(self):
        pool = Pool()
        date_obj = pool.get('ir.date')
        product_obj = pool.get('product.product')
        stock_obj = pool.get('stock.location')

        locations = stock_obj.search([('type', '=', 'storage')])
        stock_date_end = date_obj.today()
        with Transaction().set_context(locations=locations,
                stock_date_end=stock_date_end):
            product = product_obj.browse(Transaction().context['active_id'])
            if hasattr(product_obj, 'cost_price'):
                return product.quantity
            else:
                return product.template.quantity

    def transition_should_show_move(self, session):
        if self.get_quantity() != 0:
            return 'show_move'
        return 'update_price'

    def default_show_move(self, session, fields):
        pool = Pool()
        currency_obj = pool.get('currency.currency')
        user_obj = pool.get('res.user')
        accountconf_obj = pool.get('account.configuration')
        product_obj = pool.get('product.product')

        product = product_obj.browse(Transaction().context['active_id'])
        price_diff = (session.ask_price.cost_price
                - product.cost_price)
        user = user_obj.browse(Transaction().user)
        amount = currency_obj.round(user.company.currency,
            Decimal(str(self.get_quantity())) * price_diff)
        stock_account = product.account_stock_used.id
        config = accountconf_obj.browse(1)
        stock_journal = config.stock_journal.id
        counterpart = (config.cost_price_counterpart_account.id if
            config.cost_price_counterpart_account else None)
        return {
            'journal': stock_journal,
            'amount': amount,
            'price_difference': price_diff,
            'stock_account': stock_account,
            'counterpart': counterpart,
            'currency_digits': user.company.currency.digits,
            }

    def get_move_lines(self, session):
        amount = session.show_move.amount
        return [{
                'name': session.ask_price.product.name,
                'debit': amount if amount > 0 else 0,
                'credit': -amount if amount < 0 else 0,
                'account': session.show_move.stock_account.id,
                },
            {
                'name': session.ask_price.product.name,
                'debit': -amount if amount < 0 else 0,
                'credit': amount if amount > 0 else 0,
                'account': session.show_move.counterpart.id,
                },
            ]

    def get_move(self, session):
        pool = Pool()
        date_obj = pool.get('ir.date')
        period_obj = pool.get('account.period')
        user_obj = pool.get('res.user')

        user = user_obj.browse(Transaction().user)
        period_id = period_obj.find(user.company.id)
        return {
            'name': session.show_move.description,
            'period': period_id,
            'journal': session.show_move.journal.id,
            'date': date_obj.today(),
            'lines': [('create', l)
                for l in self.get_move_lines(session)],
            }

    def transition_create_move(self, session):
        move_obj = Pool().get('account.move')

        if session.show_move.counterpart == session.show_move.stock_account:
            self.raise_user_error('same_account')
        move_data = self.get_move(session)
        with Transaction().set_user(0, set_context=True):
            move_id = move_obj.create(move_data)
            move_obj.post([move_id])
        return 'update_price'

    def transition_update_price(self, session):
        product_obj = Pool().get('product.product')
        product_obj.write(session.ask_price.product.id, {
                'cost_price': session.ask_price.cost_price,
                })
        return 'end'

UpdateCostPrice()
