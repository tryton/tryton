# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
from decimal import Decimal

from sql import Literal, Union
from sql.aggregate import Sum
from sql.conditionals import Coalesce
from sql.operators import Equal

from trytond.i18n import gettext
from trytond.model import (
    DeactivableMixin, Exclude, ModelSQL, ModelView, Workflow, fields)
from trytond.model.exceptions import AccessError
from trytond.modules.account.tax import TaxableMixin
from trytond.modules.currency.fields import Monetary
from trytond.modules.product import price_digits, round_price
from trytond.pool import Pool
from trytond.pyson import Bool, Eval, Id, If
from trytond.tools import grouped_slice, reduce_ids
from trytond.transaction import Transaction
from trytond.wizard import Button, StateTransition, StateView, Wizard

from .exceptions import SaleValidationError, SessionValidationError


class POS(ModelSQL, ModelView):
    "Point of Sale"
    __name__ = 'sale.point'
    name = fields.Char("Name", required=True, select=True)
    company = fields.Many2One('company.company', "Company", required=True)
    tax_included = fields.Boolean(
        "Tax Included",
        help="Check if unit Price includes tax.")
    sequence = fields.Many2One(
        'ir.sequence.strict', "Sequence", required=True,
        domain=[
            ('company', '=', Eval('company', -1)),
            ('sequence_type', '=', Id('sale_point', 'sequence_type_sale')),
            ])

    address = fields.Many2One('party.address', "Address")

    storage_location = fields.Many2One(
        'stock.location', "Storage Location", required=True,
        domain=[('type', '=', 'storage')],
        help="The location from where goods are taken when sold.")
    return_location = fields.Many2One(
        'stock.location', "Return Location",
        domain=[('type', '=', 'storage')],
        help="The location where goods are put when returned.\n"
        "If empty the storage location is used.")
    customer_location = fields.Many2One(
        'stock.location', "To Location", required=True,
        domain=[('type', '=', 'customer')],
        help="The location where goods are put when sold.")

    journal = fields.Many2One(
        'account.journal', "Journal", required=True,
        domain=[
            ('type', '=', 'revenue'),
            ])

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_tax_included(cls):
        return True

    @classmethod
    def write(cls, *args):
        pool = Pool()
        Sale = pool.get('sale.point.sale')
        transaction = Transaction()
        if (transaction.user != 0
                and transaction.context.get('_check_access')):
            actions = iter(args)
            for points, values in zip(actions, actions):
                if 'tax_included' in values:
                    for sub_points in grouped_slice(points):
                        if Sale.search([
                                    ('points', 'in',
                                        list(map(int, sub_points))),
                                    ],
                                limit=1, order=[]):
                            raise AccessError(gettext(
                                    'sale_point.msg_point_change_tax_included')
                                )
        super().write(*args)


class POSSale(Workflow, ModelSQL, ModelView, TaxableMixin):
    "POS Sale"
    __name__ = 'sale.point.sale'
    _rec_name = 'number'

    _states = {
        'readonly': Eval('state') != 'open',
        }

    company = fields.Many2One(
        'company.company', "Company", required=True, states=_states)
    employee = fields.Many2One(
        'company.employee', "Employee",
        domain=[
            ('company', '=', Eval('company', -1)),
            ],
        states=_states)
    point = fields.Many2One(
        'sale.point', "Point", required=True, ondelete='RESTRICT',
        states={
            'readonly': ((Eval('id', 0) > 0)
                | Bool(Eval('lines', [0]))
                | _states['readonly']),
            },
        domain=[
            ('company', '=', Eval('company', -1)),
            ])
    number = fields.Char(
        "Number", readonly=True, select=True,
        states={
            'required': Eval('state').in_(['done', 'posted']),
            })
    date = fields.Date("Date", required=True, states=_states)
    lines = fields.One2Many(
        'sale.point.sale.line', 'sale', "Lines",
        states={
            'readonly': (~Eval('point')
                | _states['readonly']),
            })
    payments = fields.One2Many(
        'sale.point.payment', 'sale', "Payments", states=_states)
    total_tax = fields.Function(Monetary(
            "Total Tax", currency='currency', digits='currency'),
        'on_change_with_total_tax')
    total = fields.Function(Monetary(
            "Total", currency='currency', digits='currency'),
        'on_change_with_total')
    amount_paid = fields.Function(Monetary(
            "Paid", currency='currency', digits='currency'),
        'on_change_with_amount_paid')
    amount_to_pay = fields.Function(Monetary(
            "To Pay", currency='currency', digits='currency'),
        'on_change_with_amount_to_pay')
    state = fields.Selection([
            ('open', "Open"),
            ('done', "Done"),
            ('posted', "Posted"),
            ('cancelled', "Cancelled"),
            ], "State", readonly=True, select=True, sort=False)

    move = fields.Many2One(
        'account.move', "Move", readonly=True,
        states={
            'invisible': ~Eval('move'),
            })

    currency = fields.Function(fields.Many2One(
            'currency.currency', "Currency"), 'on_change_with_currency')

    del _states

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._transitions |= {
            ('open', 'done'),
            ('done', 'posted'),
            ('done', 'open'),
            ('open', 'cancelled'),
            ('cancelled', 'open'),
            }
        cls._buttons.update(
            pay={
                'invisible': Eval('state') != 'open',
                'readonly': ~Eval('amount_to_pay'),
                'depends': ['amount_to_pay'],
                },
            cancel={
                'invisible': Eval('state') != 'open',
                'depends': ['state'],
                },
            open={
                'invisible': ~Eval('state').in_(['done', 'cancelled']),
                'depends': ['state'],
                },
            process={
                'invisible': Eval('state') != 'open',
                'readonly': (
                    Bool(Eval('amount_to_pay', 0))
                    | ~Eval('lines', [-1])),
                'depends': ['state', 'amount_to_pay'],
                },
            post={
                'invisible': Eval('state') != 'done',
                'depends': ['state'],
                },
            )

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_employee(cls):
        User = Pool().get('res.user')

        if Transaction().context.get('employee'):
            return Transaction().context['employee']
        else:
            user = User(Transaction().user)
            if user.employee:
                return user.employee.id

    @classmethod
    def default_date(cls):
        return Pool().get('ir.date').today()

    @classmethod
    def default_state(cls):
        return 'open'

    @fields.depends('company')
    def on_change_with_currency(self, name=None):
        if self.company and self.company.currency:
            return self.company.currency.id

    @fields.depends('lines')
    def on_change_with_total_tax(self, name=None):
        return sum(line.tax_amount for line in self.lines)

    @fields.depends('company', 'lines')
    def on_change_with_total(self, name=None):
        return sum(line.gross_amount for line in self.lines)

    @fields.depends('payments')
    def on_change_with_amount_paid(self, name=None):
        return sum(p.amount or Decimal('0') for p in self.payments)

    @fields.depends(methods=[
            'on_change_with_total', 'on_change_with_amount_paid'])
    def on_change_with_amount_to_pay(self, name=None):
        return (self.on_change_with_total()
            - self.on_change_with_amount_paid())

    def get_rec_name(self, name):
        if self.number:
            return self.number
        else:
            return '(%s)' % self.id

    @classmethod
    def copy(cls, sales, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('employee')
        default.setdefault('number')
        default.setdefault('payments')
        return super().copy(sales, default=default)

    @classmethod
    def delete(cls, sales):
        for sale in sales:
            if sale.number:
                raise AccessError(
                    gettext('sale_point.msg_sale_delete_numbered',
                        sale=sale.rec_name))
        super().delete(sales)

    @classmethod
    def validate(cls, sales):
        super().validate(sales)
        for sale in sales:
            if sale.state in {'done', 'posted'}:
                if sale.amount_to_pay:
                    raise SaleValidationError(gettext(
                            'sale_point.msg_sale_amount_to_pay_done_posted',
                            sale=sale.rec_name))
            elif sale.state == 'cancelled':
                if sale.amount_paid:
                    raise SaleValidationError(gettext(
                            'sale_point.msg_sale_amount_paid_cancelled',
                            sale=sale.rec_name))

    @classmethod
    @ModelView.button_action('sale_point.wizard_pay')
    def pay(cls, sales):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, sales):
        pass

    @classmethod
    @ModelView.button
    def open(cls, sales):
        pass

    @classmethod
    @ModelView.button
    def process(cls, sales):
        cls.do([sale for sale in sales if not sale.amount_to_pay])

    @classmethod
    @Workflow.transition('done')
    def do(cls, sales):
        for sale in sales:
            with Transaction().set_context(company=sale.company.id):
                sale.number = sale.point.sequence.get()
        cls.save(sales)

    @classmethod
    @Workflow.transition('posted')
    def post(cls, sales):
        pool = Pool()
        StockMove = pool.get('stock.move')
        AccountMove = pool.get('account.move')

        stock_moves = []
        account_moves = []
        for sale in sales:
            assert not sale.move
            for line in sale.lines:
                move = line.get_stock_move()
                if move:
                    stock_moves.append(move)
            account_move = sale.get_account_move()
            sale.move = account_move
            account_moves.append(account_move)
        if stock_moves:
            StockMove.save(stock_moves)
            StockMove.do(stock_moves)
        if account_moves:
            AccountMove.save(account_moves)
            AccountMove.post(account_moves)
        cls.save(sales)

    def get_account_move(self):
        'Return account move'
        pool = Pool()
        Move = pool.get('account.move')
        Period = pool.get('account.period')

        period_id = Period.find(self.company.id, date=self.date)
        lines = []
        for line in self.lines:
            move_lines = line.get_account_move_lines()
            if move_lines:
                lines.extend(move_lines)

        move_lines = self.get_tax_move_lines()
        if move_lines:
            lines.extend(move_lines)

        for payment in self.payments:
            move_lines = payment.get_account_move_lines()
            if move_lines:
                lines.extend(move_lines)

        move = Move()
        move.journal = self.point.journal
        move.period = period_id
        move.date = self.date
        move.origin = self
        move.company = self.company
        move.lines = lines
        return move

    def get_tax_move_lines(self):
        "Return account move lines for taxes"
        pool = Pool()
        Line = pool.get('account.move.line')
        TaxLine = pool.get('account.tax.line')

        lines = []
        taxes = self._get_taxes()

        # Distribute rounding error from tax computation
        tax_amount = sum(t['amount'] for t in taxes)
        difference = self.total_tax - tax_amount
        if difference:
            remaining = difference
            for tax in taxes:
                if tax['amount']:
                    if tax_amount:
                        ratio = tax['amount'] / tax_amount
                    else:
                        ratio = 1 / len(taxes)
                    value = self.currency.round(difference * ratio)
                    tax['amount'] += value
                    remaining -= value
            # Add remaining rounding error to the first tax
            if remaining:
                for tax in taxes:
                    if tax['amount']:
                        tax['amount'] += remaining
                        break

        for tax in taxes:
            amount = tax['amount']
            if not amount:
                continue
            line = Line()
            line.description = tax['description']
            if amount >= 0:
                line.debit, line.credit = Decimal(0), amount
            else:
                line.debit, line.credit = -amount, 0
            line.account = tax['account']
            if tax['tax']:
                tax_line = TaxLine()
                tax_line.amount = amount
                tax_line.type = 'tax'
                tax_line.tax = tax['tax']
                line.tax_lines = [tax_line]
            lines.append(line)
        return lines

    @property
    def taxable_lines(self):
        return sum((line.taxable_lines for line in self.lines), [])

    @property
    def tax_date(self):
        return self.date


class POSSaleLine(ModelSQL, ModelView, TaxableMixin):
    "POS Sale Line"
    __name__ = 'sale.point.sale.line'

    _states = {
        'readonly': Eval('sale_state') != 'open',
        }

    sale = fields.Many2One(
        'sale.point.sale', "Sale", required=True, ondelete='CASCADE',
        states=_states)
    product = fields.Many2One(
        'product.product', "Product", required=True,
        domain=[
            ('salable', '=', True),
            ],
        context={
            'company': Eval('company'),
            },
        states=_states, depends={'company'})
    quantity = fields.Float(
        "Quantity", digits='unit', required=True, states=_states)
    unit = fields.Function(
        fields.Many2One('product.uom', "Unit"), 'on_change_with_unit')
    unit_list_price = fields.Numeric(
        "Unit List Price", digits=price_digits, required=True,
        states={
            'readonly': True,  # Allow client to sent value
            })
    unit_gross_price = fields.Numeric(
        "Unit Gross Price", digits=price_digits, required=True,
        states={
            'readonly': True,  # Allow client to sent value
            })
    unit_price = fields.Function(fields.Numeric(
            "Unit Price", digits=price_digits,
            depends={'unit_list_price', 'unit_gross_price'}),
        'on_change_with_unit_price')
    amount = fields.Function(Monetary(
            "Amount", currency='currency', digits='currency'),
        'on_change_with_amount')

    moves = fields.One2Many(
        'stock.move', 'origin', 'Moves', readonly=True,
        states={
            'invisible': ~Eval('moves', []),
            })

    sale_state = fields.Function(fields.Selection(
            'get_sale_states', "Sale State"), 'on_change_with_sale_state')
    company = fields.Function(
        fields.Many2One('company.company', "Company"),
        'on_change_with_company', searcher='search_company')
    currency = fields.Function(
        fields.Many2One('currency.currency', "Currency"),
        'on_change_with_currency')

    del _states

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('sale')

    @fields.depends('product')
    def on_change_with_unit(self, name=None):
        # TODO packaging UOM
        if self.product:
            return self.product.sale_uom.id

    @classmethod
    def get_sale_states(cls):
        pool = Pool()
        Sale = pool.get('sale.point.sale')
        return Sale.fields_get(['state'])['state']['selection']

    @fields.depends('sale', '_parent_sale.state')
    def on_change_with_sale_state(self, name=None):
        if self.sale:
            return self.sale.state

    @fields.depends(
        'product', 'sale', '_parent_sale.point', '_parent_sale.date',
        methods=['on_change_with_unit_price', 'on_change_with_amount'])
    def on_change_product(self):
        pool = Pool()
        Tax = pool.get('account.tax')
        if self.product and self.sale and self.sale.point:
            if (self.sale.point.tax_included
                    and self.product.gross_price is not None):
                self.unit_gross_price = self.product.gross_price
                self.unit_list_price = round_price(Tax.reverse_compute(
                        self.unit_gross_price, self.taxes,
                        date=self.sale.date))
            else:
                self.unit_list_price = self.product.list_price
                taxes = Tax.compute(
                    self.taxes, self.unit_list_price, 1,
                    date=self.sale.date)
                tax_amount = sum(t['amount'] for t in taxes)
                self.unit_gross_price = (
                    self.unit_list_price + tax_amount).quantize(
                        Decimal(1)
                        / 10 ** self.__class__.unit_gross_price.digits[1])
        else:
            self.unit_gross_price = None
            self.unit_list_price = None
        self.unit_price = self.on_change_with_unit_price()
        self.amount = self.on_change_with_amount()

    @fields.depends('unit_list_price', 'unit_gross_price',
        'sale', '_parent_sale.point')
    def on_change_with_unit_price(self, name=None):
        if self.sale and self.sale.point:
            if self.sale.point.tax_included:
                return self.unit_gross_price
            else:
                return self.unit_list_price
        else:
            return

    @fields.depends('currency', 'quantity', 'unit_price')
    def on_change_with_amount(self, name=None):
        amount = (Decimal(str(self.quantity or 0))
            * (self.unit_price or Decimal('0')))
        if self.currency:
            return self.currency.round(amount)
        return amount

    @fields.depends('sale', '_parent_sale.company')
    def on_change_with_company(self, name=None):
        if self.sale and self.sale.company:
            return self.sale.company.id

    @classmethod
    def search_company(cls, name, clause):
        return [('sale.company',) + tuple(clause[1:])]

    @fields.depends('sale', '_parent_sale.currency')
    def on_change_with_currency(self, name=None):
        if self.sale and self.sale.currency:
            return self.sale.currency.id

    @property
    def untax_amount(self):
        amount = (Decimal(str(self.quantity or 0))
            * (self.unit_list_price or Decimal('0')))
        if getattr(self, 'currency', None):
            amount = self.currency.round(amount)
        return amount

    @property
    def tax_amount(self):
        amount = self.gross_amount - self.untax_amount
        if getattr(self, 'currency', None):
            amount = self.currency.round(amount)
        return amount

    @property
    def gross_amount(self):
        amount = (Decimal(str(self.quantity or 0))
            * (self.unit_gross_price or Decimal('0')))
        if getattr(self, 'currency', None):
            amount = self.currency.round(amount)
        return amount

    def get_rec_name(self, name):
        return '%s @ %s' % (self.product.rec_name, self.sale.rec_name)

    @classmethod
    def search_rec_name(cls, name, clause):
        return ['OR',
            ('sale.rec_name',) + tuple(clause[1:]),
            ('product.rec_name',) + tuple(clause[1:]),
            ]

    @classmethod
    def copy(cls, lines, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('moves')
        return super().copy(lines, default=default)

    def get_stock_move(self):
        'Return stock move'
        pool = Pool()
        Move = pool.get('stock.move')

        if self.product.type == 'service':
            return

        move = Move()
        move.quantity = abs(self.quantity)
        move.uom = self.unit
        move.product = self.product
        move.from_location = self.from_location
        move.to_location = self.to_location
        move.company = self.company
        move.unit_price = self.unit_list_price
        move.currency = self.currency
        move.effective_date = self.sale.date
        move.origin = self
        return move

    @property
    def from_location(self):
        if self.quantity >= 0:
            return self.sale.point.storage_location
        else:
            return self.sale.point.customer_location

    @property
    def to_location(self):
        if self.quantity >= 0:
            return self.sale.point.customer_location
        else:
            return self.sale.point.return_location

    def get_account_move_lines(self):
        "Return account move lines"
        pool = Pool()
        Line = pool.get('account.move.line')
        TaxLine = pool.get('account.tax.line')

        line = Line()
        if self.quantity >= 0:
            line.debit, line.credit = Decimal(0), self.untax_amount
        else:
            line.debit, line.credit = -self.untax_amount, Decimal(0)
        with Transaction().set_context(company=self.company.id):
            line.account = self.product.account_revenue_used
        line.origin = self

        tax_lines = []
        for tax in self._get_taxes():
            tax_line = TaxLine()
            tax_line.amount = tax['base']
            tax_line.type = 'base'
            tax_line.tax = tax['tax']
            tax_lines.append(tax_line)
        line.tax_lines = tax_lines
        return [line]

    @property
    def taxes(self):
        pool = Pool()
        Product = pool.get('product.product')
        with Transaction().set_context(company=self.company.id):
            return Product(self.product).customer_taxes_used

    @property
    def taxable_lines(self):
        return [
            (self.taxes, self.unit_list_price, self.quantity, self.tax_date)]

    @property
    def tax_type(self):
        if self.quantity >= 0:
            return 'invoice'
        else:
            return 'credit_note'

    @property
    def tax_date(self):
        return self.sale.date


class POSCashSession(Workflow, ModelSQL, ModelView):
    "POS Cash Session"
    __name__ = 'sale.point.cash.session'

    point = fields.Many2One(
        'sale.point', "Point", required=True, ondelete='CASCADE')
    previous_session = fields.Many2One(
        'sale.point.cash.session', "Previous Session",
        readonly=True, ondelete='RESTRICT',
        domain=[
            ('point', '=', Eval('point', -1)),
            ])
    next_session = fields.One2One(
        'sale.point.cash.session.relation', 'previous', 'next', "Next Session",
        readonly=True,
        domain=[
            ('point', '=', Eval('point', -1)),
            ])
    payments = fields.One2Many(
        'sale.point.payment', 'session', "Payments", readonly=True,
        domain=[
            ('sale.point', '=', Eval('point', -1)),
            ])
    transfers = fields.One2Many(
        'sale.point.cash.transfer', 'session', "Transfers",
        domain=[
            ('point', '=', Eval('point', -1)),
            ],
        states={
            'readonly': ~Eval('point'),
            })
    start_amount = fields.Function(
        Monetary("Start Amount", currency='currency', digits='currency'),
        'get_start_amount')
    balance = fields.Function(Monetary(
            "Balance", currency='currency', digits='currency'),
        'get_balance')
    end_amount = Monetary(
        "End Amount", currency='currency', digits='currency', required=True,
        states={
            'required': Eval('state').in_(['closed', 'posted']),
            })
    state = fields.Selection([
            ('open', "Open"),
            ('closed', "Closed"),
            ('posted', "Posted"),
            ], "State", readonly=True, required=True, sort=False)

    currency = fields.Function(fields.Many2One(
            'currency.currency', "Currency"),
        'on_change_with_currency')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints = [
            ('point_cash_session_open_unique',
                Exclude(t, (t.point, Equal),
                    where=t.state == 'open'),
                'sale_point.msg_point_cash_session_open_unique'),
            ('point_cash_session_previous_unique',
                Exclude(t, (Coalesce(t.previous_session, -t.point), Equal)),
                'sale_point.msg_cash_session_previous_unique'),
            ]
        cls._transitions |= {
            ('open', 'closed'),
            ('closed', 'open'),
            ('closed', 'posted'),
            }
        cls._buttons.update(
            open={
                'invisible': Eval('state') != 'closed',
                'depends': ['state'],
                },
            close={
                'pre_validate': [
                    ('end_amount', '!=', None),
                    ],
                'invisible': Eval('state') != 'open',
                'depends': ['state'],
                },
            post={
                'invisible': Eval('state') != 'closed',
                'depends': ['state'],
                },
            )

    @classmethod
    def __register__(cls, module_name):
        super().__register__(module_name)
        table_h = cls.__table_handler__(module_name)
        # Migration from 6.2: add point to previous session uniqueness.
        table_h.drop_constraint('previous_session_unique')

    @classmethod
    def default_state(cls):
        return 'open'

    @fields.depends('point')
    def on_change_point(self):
        if self.point:
            last = self.__class__.search([
                    ('point', '=', self.point.id),
                    ('next_session', '=', None),
                    ], limit=1)
            if last:
                self.previous_session, = last

    def get_start_amount(self, name):
        if self.previous_session:
            return self.previous_session.end_amount
        else:
            return Decimal(0)

    @classmethod
    def get_balance(cls, sessions, name):
        pool = Pool()
        Payment = pool.get('sale.point.payment')
        Transfer = pool.get('sale.point.cash.transfer')
        payment = Payment.__table__()
        transfer = Transfer.__table__()
        cursor = Transaction().connection.cursor()
        balances = defaultdict(Decimal)
        for sub_sessions in grouped_slice(sessions):
            sub_ids = [s.id for s in sub_sessions]
            query = Union(
                payment.select(
                    payment.session.as_('session'),
                    Sum(payment.amount).as_('amount'),
                    where=reduce_ids(payment.session, sub_ids),
                    group_by=[payment.session]),
                transfer.select(
                    transfer.session.as_('session'),
                    Sum(transfer.amount).as_('amount'),
                    where=reduce_ids(transfer.session, sub_ids),
                    group_by=[transfer.session]),
                all_=True)
            query = query.select(
                query.session, Sum(query.amount),
                group_by=[query.session])
            cursor.execute(*query)
            for session_id, balance in cursor:
                if not isinstance(balance, Decimal):
                    balance = Decimal(str(balance))
                balances[session_id] = balance
        for session in sessions:
            balances[session.id] = session.currency.round(balances[session.id])
        return balances

    @classmethod
    def default_end_amount(cls):
        return Decimal(0)

    @fields.depends('point')
    def on_change_with_currency(self, name=None):
        if self.point:
            return self.point.company.currency.id

    @classmethod
    @Workflow.transition('open')
    def open(cls, sessions):
        pass

    @classmethod
    @Workflow.transition('closed')
    def close(cls, sessions):
        pool = Pool()
        Lang = pool.get('ir.lang')
        for session in sessions:
            if session.end_amount - session.start_amount != session.balance:
                lang = Lang.get()
                raise SessionValidationError(gettext(
                        'sale_point.msg_cash_session_wrong_end_amount',
                        session=session.rec_name,
                        end_amount=lang.currency(
                            session.end_amount, session.currency),
                        amount=lang.currency(
                            session.start_amount + session.balance,
                            session.currency)))

    @classmethod
    def delete(cls, sessions):
        cls.open(sessions)
        for session in sessions:
            if session.state != 'open':
                raise AccessError(
                    gettext('sale_point.msg_cash_session_delete_open',
                        session=session.rec_name))
        super().delete(sessions)

    @classmethod
    @Workflow.transition('posted')
    def post(cls, sessions):
        pool = Pool()
        Transfer = pool.get('sale.point.cash.transfer')
        Transfer.post(sum((s.transfers for s in sessions), ()))

    @classmethod
    def get_current(cls, point):
        sessions = cls.search([
                ('point', '=', point.id),
                ('state', '=', 'open'),
                ], limit=1)
        if sessions:
            session, = sessions
        else:
            cls.lock()
            last = cls.search([
                    ('point', '=', point.id),
                    ('next_session', '=', None),
                    ], limit=1)
            if last:
                last, = last
            else:
                last = None
            session = cls(point=point, previous_session=last)
            session.save()
        return session


class POSCashSessionRelation(ModelSQL):
    "POS Session Relation"
    __name__ = 'sale.point.cash.session.relation'

    previous = fields.Many2One('sale.point.cash.session', "Previous")
    next = fields.Many2One('sale.point.cash.session', "Next")

    @classmethod
    def table_query(cls):
        pool = Pool()
        Session = pool.get('sale.point.cash.session')
        session = Session.__table__()
        return session.select(
            session.id.as_('id'),
            session.create_date.as_('create_date'),
            session.create_uid.as_('create_uid'),
            session.write_date.as_('write_date'),
            session.write_uid.as_('write_uid'),
            session.previous_session.as_('previous'),
            session.id.as_('next'))


class POSPayment(ModelSQL, ModelView):
    "POS Payment"
    __name__ = 'sale.point.payment'

    _states = {
        'readonly': Eval('sale_state') != 'open',
        }

    sale = fields.Many2One(
        'sale.point.sale', "Sale", required=True, ondelete='CASCADE',
        states=_states)
    method = fields.Many2One(
        'sale.point.payment.method', "Method", required=True,
        domain=[
            ('company', '=', Eval('company')),
            If(Eval('amount', 0) < 0,
                ('cash', '=', True),
                ()),
            ],
        states=_states)
    amount = Monetary(
        "Amount", currency='currency', digits='currency', states=_states)
    session = fields.Many2One(
        'sale.point.cash.session', "Session",
        ondelete='RESTRICT', readonly=True,
        domain=[
            ('point', '=', Eval('point', -1)),
            ],
        states={
            'invisible': ~Eval('cash'),
            'required': Eval('cash', False),
            })

    currency = fields.Function(fields.Many2One(
            'currency.currency', "Currency"), 'on_change_with_currency')
    company = fields.Function(
        fields.Many2One('company.company', "Company"),
        'on_change_with_company', searcher='search_company')
    sale_state = fields.Function(fields.Selection(
            'get_sale_states', "Sale State"), 'on_change_with_sale_state')
    point = fields.Function(fields.Many2One(
            'sale.point', "Point"), 'on_change_with_point')
    cash = fields.Function(fields.Boolean("Cash"), 'on_change_with_cash')

    del _states

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('sale')

    @fields.depends('sale', '_parent_sale.amount_to_pay')
    def on_change_sale(self):
        if self.sale:
            self.amount = self.sale.amount_to_pay

    @fields.depends('company')
    def on_change_with_currency(self, name=None):
        if self.company and self.company.currency:
            return self.company.currency.id

    @fields.depends('sale', '_parent_sale.company')
    def on_change_with_company(self, name=None):
        if self.sale and self.sale.company:
            return self.sale.company.id

    @classmethod
    def search_company(cls, name, clause):
        return [('sale.company',) + tuple(clause[1:])]

    @classmethod
    def get_sale_states(cls):
        pool = Pool()
        Sale = pool.get('sale.point.sale')
        return Sale.fields_get(['state'])['state']['selection']

    @fields.depends('sale', '_parent_sale.state')
    def on_change_with_sale_state(self, name=None):
        if self.sale:
            return self.sale.state

    @fields.depends('sale', '_parent_sale.point')
    def on_change_with_point(self, name=None):
        if self.sale and self.sale.point:
            return self.sale.point.id

    @fields.depends('method')
    def on_change_with_cash(self, name=None):
        if self.method:
            return self.method.cash

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Method = pool.get('sale.point.payment.method')
        Sale = pool.get('sale.point.sale')
        Session = pool.get('sale.point.cash.session')
        vlist = [v.copy() for v in vlist]
        for values in vlist:
            if values.get('method') and values.get('sale'):
                method = Method(values['method'])
                if method.cash:
                    sale = Sale(values['sale'])
                    values['session'] = Session.get_current(sale.point)
        return super().create(vlist)

    @classmethod
    def delete(cls, payments):
        for payment in payments:
            if payment.sale.state != 'open':
                raise AccessError(
                    gettext('sale_point.msg_payment_delete_sale_open',
                        payment=payment.rec_name,
                        sale=payment.sale.rec_name))
            if payment.session and payment.session.state != 'open':
                raise AccessError(
                    gettext('sale_point.msg_payment_delete_session_open',
                        payment=payment.rec_name,
                        session=payment.session.rec_name))
        super().delete(payments)

    def get_account_move_lines(self):
        "Return account move lines"
        pool = Pool()
        Line = pool.get('account.move.line')

        line = Line()
        if self.sale.total >= 0:
            line.debit, line.credit = self.amount, Decimal(0)
        else:
            line.debit, line.credit = Decimal(0), -self.amount
        line.account = self.method.account
        line.origin = self
        return [line]


class POSPaymentMethod(DeactivableMixin, ModelSQL, ModelView):
    "POS Payment Method"
    __name__ = 'sale.point.payment.method'
    company = fields.Many2One('company.company', "Company", required=True)
    name = fields.Char("Name", required=True, translate=True)
    account = fields.Many2One(
        'account.account', "Account", required=True,
        domain=[
            ('type', '!=', None),
            ('closed', '!=', True),
            ('company', '=', Eval('company')),
            ])
    cash = fields.Boolean("Cash")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints = [
            ('cash_company_unique',
                Exclude(t, (t.company, Equal),
                    where=(t.active == Literal(True))
                    & (t.cash == Literal(True))),
                'sale_point.msg_payment_method_cash_unique'),
            ]
        cls._order.insert(0, ('name', 'ASC'))

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')


class POSPay(Wizard):
    "POS Pay"
    __name__ = 'sale.point.sale.pay'
    start_state = 'payment'
    payment = StateView(
        'sale.point.payment',
        'sale_point.payment_view_form_wizard', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("OK", 'pay', 'tryton-ok', default=True),
            ])
    pay = StateTransition()

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__rpc__['create'].fresh_session = True

    def default_payment(self, fields):
        pool = Pool()
        PaymentMethod = pool.get('sale.point.payment.method')
        default = {
            'sale': self.record.id,
            'amount': self.record.amount_to_pay,
            }
        if default['amount'] < 0:
            methods = PaymentMethod.search([
                    ('company', '=', self.record.company.id),
                    ('cash', '=', True),
                    ])
            if methods:
                method, = methods
                default['method'] = method.id
        return default

    def transition_pay(self):
        self.payment.sale = self.record
        self.payment.save()
        if self.record.amount_to_pay:
            return 'payment'
        else:
            self.model.process([self.record])
            return 'end'


class POSCashTransfer(Workflow, ModelSQL, ModelView):
    "POS Cash Transfer"
    __name__ = 'sale.point.cash.transfer'

    _states = {
        'readonly': Eval('state') == 'done',
        }

    point = fields.Many2One(
        'sale.point', "Point", required=True, states=_states)
    session = fields.Many2One(
        'sale.point.cash.session', "Session", required=True,
        domain=[
            ('point', '=', Eval('point', -1)),
            If(Eval('state') == 'draft',
                ('state', '=', 'open'),
                ()),
            ],
        states={
            'required': Eval('id', -1) >= 0,
            'readonly': _states['readonly'],
            'invisible': ~Eval('point'),
            })
    type = fields.Many2One(
        'sale.point.cash.transfer.type', "Type", required=True,
        domain=[
            ('company', '=', Eval('company', -1)),
            ])
    amount = Monetary(
        "Amount", currency='currency', digits='currency', states=_states)
    date = fields.Date("Date", required=True)
    state = fields.Selection([
            ('draft', "Draft"),
            ('posted', "Posted"),
            ], "State", readonly=True, required=True, sort=False)

    move = fields.Many2One(
        'account.move', "Move", readonly=True,
        states={
            'invisible': ~Eval('move'),
            })

    company = fields.Function(fields.Many2One(
            'company.company', "Company"),
        'on_change_with_company')
    currency = fields.Function(fields.Many2One(
            'currency.currency', "Currency"),
        'on_change_with_currency')

    del _states

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._transitions |= {
            ('draft', 'posted'),
            }
        cls._buttons.update(
            post={
                'invisible': Eval('state') != 'draft',
                'depends': ['state'],
                },
            )

    @classmethod
    def default_state(cls):
        return 'draft'

    @classmethod
    def default_date(cls):
        return Pool().get('ir.date').today()

    @fields.depends('point')
    def on_change_with_company(self, name=None):
        if self.point:
            return self.point.company.id

    @fields.depends('point')
    def on_change_with_currency(self, name=None):
        if self.point:
            return self.point.company.currency.id

    @classmethod
    def delete(cls, transfers):
        for transfer in transfers:
            if transfer.state == 'posted':
                raise AccessError(
                    gettext('sale_point.msg_transfer_delete_posted',
                        transfer=transfer.rec_name))
            if transfer.session.state != 'open':
                raise AccessError(
                    gettext('sale_point.msg_transfer_delete_session_open',
                        transfer=transfer.rec_name,
                        session=transfer.session.rec_name))
        super().delete(transfers)

    @classmethod
    @ModelView.button
    @Workflow.transition('posted')
    def post(cls, transfers):
        pool = Pool()
        Move = pool.get('account.move')
        PaymentMethod = pool.get('sale.point.payment.method')

        methods = PaymentMethod.search([('cash', '=', True)])
        company2account = {m.company: m.account for m in methods}

        moves = []
        for transfer in transfers:
            assert not transfer.move
            move = transfer.get_move(
                account=company2account.get(transfer.company))
            transfer.move = move
            moves.append(move)
        Move.save(moves)
        cls.save(transfers)

    def get_move(self, account):
        pool = Pool()
        Line = pool.get('account.move.line')
        Move = pool.get('account.move')
        Period = pool.get('account.period')

        period_id = Period.find(self.company.id, date=self.date)
        line = Line()
        if self.amount >= 0:
            line.debit, line.credit = self.amount, Decimal(0)
        else:
            line.debit, line.credit = Decimal(0), -self.amount
        line.account = account
        counterpart = Line()
        counterpart.debit, counterpart.credit = line.credit, line.debit
        counterpart.account = self.type.account

        move = Move()
        move.journal = self.type.journal
        move.period = period_id
        move.date = self.date
        move.origin = self
        move.company = self.company
        move.lines = [line, counterpart]
        return move

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Point = pool.get('sale.point')
        Session = pool.get('sale.point.cash.session')
        vlist = [v.copy() for v in vlist]
        for values in vlist:
            if values.get('point') and not values.get('session'):
                point = Point(values['point'])
                values['session'] = Session.get_current(point)
        return super().create(vlist)


class POSCashTransferType(ModelSQL, ModelView):
    "POS Cash Transfer Type"
    __name__ = 'sale.point.cash.transfer.type'

    company = fields.Many2One('company.company', "Company", required=True)
    name = fields.Char("Name", required=True, translate=True)
    journal = fields.Many2One(
        'account.journal', "Journal", required=True,
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    account = fields.Many2One(
        'account.account', "Account", required=True,
        domain=[
            ('type', '!=', None),
            ('closed', '!=', True),
            ('company', '=', Eval('company', -1)),
            ])

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

# TODO: wizard to create an invoice from sale
