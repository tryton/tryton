#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal
from trytond.model import Workflow, ModelView, ModelSQL, fields
from trytond.pyson import Eval, If
from trytond.transaction import Transaction
from trytond.backend import TableHandler
from trytond.pool import Pool

__all__ = ['Statement', 'Line']

_STATES = {'readonly': Eval('state') != 'draft'}
_DEPENDS = ['state']


class Statement(Workflow, ModelSQL, ModelView):
    'Account Statement'
    __name__ = 'account.statement'
    company = fields.Many2One('company.company', 'Company', required=True,
        select=True, states=_STATES, domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', 0)),
            ],
        depends=_DEPENDS)
    journal = fields.Many2One('account.statement.journal', 'Journal',
        required=True,
        domain=[
            ('company', '=', Eval('context', {}).get('company', 0)),
            ],
        states={
            'readonly': (Eval('state') != 'draft') | Eval('lines'),
            },
        on_change=['journal', 'state', 'lines'], select=True,
        depends=['state', 'lines'])
    currency_digits = fields.Function(fields.Integer('Currency Digits',
            on_change_with=['journal']), 'on_change_with_currency_digits')
    date = fields.Date('Date', required=True, states=_STATES, depends=_DEPENDS,
        select=True)
    start_balance = fields.Numeric('Start Balance', required=True,
        digits=(16, Eval('currency_digits', 2)),
        states=_STATES, depends=['state', 'currency_digits'])
    end_balance = fields.Numeric('End Balance', required=True,
        digits=(16, Eval('currency_digits', 2)),
        states=_STATES, depends=['state', 'currency_digits'])
    balance = fields.Function(
        fields.Numeric('Balance',
            digits=(16, Eval('currency_digits', 2)),
            on_change_with=['start_balance', 'end_balance'],
            depends=['currency_digits']),
        'on_change_with_balance')
    lines = fields.One2Many('account.statement.line', 'statement',
        'Transactions', states={
            'readonly': (Eval('state') != 'draft') | ~Eval('journal'),
            }, on_change=['lines', 'journal'],
        depends=['state', 'journal'])
    state = fields.Selection([
        ('draft', 'Draft'),
        ('validated', 'Validated'),
        ('cancel', 'Canceled'),
        ('posted', 'Posted'),
        ], 'State', readonly=True, select=True)
    move_lines = fields.Function(fields.One2Many('account.move.line',
        None, 'Move Lines'), 'get_move_lines')

    @classmethod
    def __setup__(cls):
        super(Statement, cls).__setup__()
        cls._order[0] = ('id', 'DESC')
        cls._error_messages.update({
                'wrong_end_balance': 'End Balance must be "%s".',
                'delete_cancel': ('Statement "%s" must be cancelled before '
                    'deletion.'),
                })
        cls._transitions |= set((
                ('draft', 'validated'),
                ('validated', 'posted'),
                ('validated', 'cancel'),
                ('cancel', 'draft'),
                ))
        cls._buttons.update({
                'draft': {
                    'invisible': Eval('state') != 'cancel',
                    },
                'validate_statement': {
                    'invisible': Eval('state') != 'draft',
                    },
                'post': {
                    'invisible': Eval('state') != 'validated',
                    },
                'cancel': {
                    'invisible': Eval('state') != 'validated',
                    },
                })

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor

        # Migration from 1.8: new field company
        table = TableHandler(cursor, cls, module_name)
        company_exist = table.column_exist('company')

        super(Statement, cls).__register__(module_name)

        # Migration from 1.8: fill new field company
        if not company_exist:
            offset = 0
            limit = cursor.IN_MAX
            statements = True
            while statements:
                statements = cls.search([], offset=offset, limit=limit)
                offset += limit
                for statement in statements:
                    cls.write([statement], {
                            'company': statement.journal.company.id,
                            })
            table = TableHandler(cursor, cls, module_name)
            table.not_null_action('company', action='add')

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_date():
        Date = Pool().get('ir.date')
        return Date.today()

    @staticmethod
    def default_currency_digits():
        Company = Pool().get('company.company')
        if Transaction().context.get('company'):
            company = Company(Transaction().context['company'])
            return company.currency.digits
        return 2

    def on_change_journal(self):
        res = {}
        if not self.journal:
            return res

        statements = self.search([
                ('journal', '=', self.journal.id),
                ], order=[
                ('date', 'DESC'),
                ], limit=1)
        if not statements:
            return res

        statement, = statements
        res['start_balance'] = statement.end_balance
        return res

    def on_change_with_currency_digits(self, name=None):
        if self.journal:
            return self.journal.currency.digits
        return 2

    @classmethod
    def get_rec_name(cls, statements, name):
        Lang = Pool().get('ir.lang')

        lang, = Lang.search([
                ('code', '=', Transaction().language),
                ])

        res = {}
        for statement in statements:
            res[statement.id] = (statement.journal.name + ' '
                + Lang.currency(lang, statement.start_balance,
                    statement.journal.currency, symbol=False, grouping=True)
                + ' - '
                + Lang.currency(lang, statement.end_balance,
                    statement.journal.currency, symbol=False, grouping=True))
        return res

    @classmethod
    def search_rec_name(cls, name, clause):
        statements = cls.search(['OR',
                ('start_balance',) + tuple(clause[1:]),
                ('end_balance',) + tuple(clause[1:]),
                ])
        if statements:
            return [('id', 'in', [s.id for s in statements])]
        return [('journal',) + tuple(clause[1:])]

    def get_move_lines(self, name):
        '''
        Return the move lines that have been generated by the statement.
        '''
        move_lines = []
        for line in self.lines:
            if not line.move:
                continue
            for move_line in line.move.lines:
                move_lines.append(move_line.id)
        return move_lines

    def get_end_balance(self, name):
        end_balance = self.start_balance
        for line in self.lines:
            end_balance += line.amount
        return end_balance

    def on_change_with_balance(self, name=None):
        return ((getattr(self, 'end_balance', 0) or 0)
            - (getattr(self, 'start_balance', 0) or 0))

    def on_change_lines(self):
        pool = Pool()
        Currency = pool.get('currency.currency')
        Line = pool.get('account.statement.line')
        res = {
            'lines': {},
            }
        if self.journal and self.lines:
            invoices = set()
            for line in self.lines:
                if line.invoice:
                    invoices.add(line.invoice)
            invoice_id2amount_to_pay = {}
            for invoice in invoices:
                with Transaction().set_context(date=invoice.currency_date):
                    invoice_id2amount_to_pay[invoice.id] = (
                        Currency.compute(invoice.currency,
                            invoice.amount_to_pay, self.journal.currency))

            for line in self.lines or []:
                if line.invoice and line.id:
                    amount_to_pay = invoice_id2amount_to_pay[line.invoice.id]
                    if abs(line.amount) > amount_to_pay:
                        res['lines'].setdefault('update', [])
                        if self.journal.currency.is_zero(amount_to_pay):
                            res['lines']['update'].append({
                                'id': line.id,
                                'invoice': None,
                                })
                        else:
                            res['lines']['update'].append({
                                'id': line.id,
                                'amount': (amount_to_pay
                                        if line.amount >= 0
                                        else -amount_to_pay),
                                })
                            res['lines'].setdefault('add', [])
                            vals = {}
                            for field_name, field in Line._fields.iteritems():
                                try:
                                    value = getattr(line, field_name)
                                except AttributeError:
                                    continue
                                if (value and field._type in ('many2one',
                                            'one2one')):
                                    vals[field_name] = value.id
                                    vals[field_name + '.rec_name'] = \
                                        value.rec_name
                                else:
                                    vals[field_name] = value
                            del vals['id']
                            vals['amount'] = (abs(line.amount)
                                - amount_to_pay)
                            if line.amount < 0:
                                vals['amount'] = - vals['amount']
                            vals['invoice'] = None
                            del vals['invoice.rec_name']
                            res['lines']['add'].append(vals)
                    invoice_id2amount_to_pay[line.invoice.id] = \
                        amount_to_pay - abs(line.amount)
        return res

    @classmethod
    def delete(cls, statements):
        # Cancel before delete
        cls.cancel(statements)
        for statement in statements:
            if statement.state != 'cancel':
                cls.raise_user_error('delete_cancel', (statement.rec_name,))
        super(Statement, cls).delete(statements)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, statements):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('validated')
    def validate_statement(cls, statements):
        Lang = Pool().get('ir.lang')

        for statement in statements:
            computed_end_balance = statement.start_balance
            for line in statement.lines:
                computed_end_balance += line.amount
            if computed_end_balance != statement.end_balance:
                lang, = Lang.search([
                        ('code', '=', Transaction().language),
                        ])

                amount = Lang.format(lang,
                        '%.' + str(statement.journal.currency.digits) + 'f',
                        computed_end_balance, True)
                cls.raise_user_error('wrong_end_balance',
                    error_args=(amount,))
            for line in statement.lines:
                line.create_move()

    @classmethod
    @ModelView.button
    @Workflow.transition('posted')
    def post(cls, statements):
        StatementLine = Pool().get('account.statement.line')

        lines = [l for s in statements for l in s.lines]
        StatementLine.post_move(lines)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, statements):
        StatementLine = Pool().get('account.statement.line')

        lines = [l for s in statements for l in s.lines]
        StatementLine.delete_move(lines)


class Line(ModelSQL, ModelView):
    'Account Statement Line'
    __name__ = 'account.statement.line'
    statement = fields.Many2One('account.statement', 'Statement',
            required=True, ondelete='CASCADE')
    date = fields.Date('Date', required=True)
    amount = fields.Numeric('Amount', required=True,
        digits=(16, Eval('_parent_statement', {}).get('currency_digits', 2)),
        on_change=['amount', 'party', 'account', 'invoice',
            '_parent_statement.journal'])
    party = fields.Many2One('party.party', 'Party',
            on_change=['amount', 'party', 'invoice'])
    account = fields.Many2One('account.account', 'Account', required=True,
        on_change=['account', 'invoice'], domain=[
            ('company', '=', Eval('_parent_statement', {}).get('company', 0)),
            ('kind', '!=', 'view'),
            ])
    description = fields.Char('Description')
    move = fields.Many2One('account.move', 'Account Move', readonly=True)
    invoice = fields.Many2One('account.invoice', 'Invoice',
        domain=[
            ('party', '=', Eval('party')),
            ('account', '=', Eval('account')),
            If(Eval('_parent_statement', {}).get('state') == 'draft',
                ('state', '=', 'posted'),
                ('state', '!=', '')),
            ],
        states={
            'readonly': (~Eval('amount') | ~Eval('party') | ~Eval('account')),
            },
        depends=['party', 'account', 'amount'])

    @classmethod
    def __setup__(cls):
        super(Line, cls).__setup__()
        cls._error_messages.update({
                'debit_credit_account_statement_journal': ('Please provide '
                    'debit and credit account on statement journal "%s".'),
                'same_debit_credit_account': ('Account "%(account)s" in '
                    'statement line "%(line)s" is the same as the one '
                    'configured as credit or debit on journal "%(journal)s".'),
                'amount_greater_invoice_amount_to_pay': ('Amount "%s" is '
                    'greater than the amount to pay of invoice.'),
                })
        cls._sql_constraints += [
            ('check_statement_line_amount', 'CHECK(amount != 0)',
                'Amount should be a positive or negative value.'),
            ]

    @staticmethod
    def default_amount():
        return Decimal(0)

    def on_change_party(self):
        res = {}

        if self.party:
            if self.amount:
                if self.amount > Decimal("0.0"):
                    account = self.party.account_receivable
                else:
                    account = self.party.account_payable
                res['account'] = account.id
                res['account.rec_name'] = account.rec_name

        if self.invoice:
            if self.party:
                if self.invoice.party != self.party:
                    res['invoice'] = None
            else:
                res['invoice'] = None
        return res

    def on_change_amount(self):
        Currency = Pool().get('currency.currency')
        res = {}

        if self.party:
            if self.account and self.account not in (
                    self.party.account_receivable, self.party.account_payable):
                # The user has entered a non-default value, we keep it.
                pass
            elif self.amount:
                if self.amount > Decimal("0.0"):
                    account = self.party.account_receivable
                else:
                    account = self.party.account_payable
                res['account'] = account.id
                res['account.rec_name'] = account.rec_name
        if self.invoice:
            if self.amount and self.statement and self.statement.journal:
                invoice = self.invoice
                journal = self.statement.journal
                with Transaction().set_context(date=invoice.currency_date):
                    amount_to_pay = Currency.compute(invoice.currency,
                        invoice.amount_to_pay, journal.currency)
                if abs(self.amount) > amount_to_pay:
                    res['invoice'] = None
            else:
                res['invoice'] = None
        return res

    def on_change_account(self):
        res = {}

        if self.invoice:
            if self.account:
                if self.invoice.account != self.account:
                    res['invoice'] = None
            else:
                res['invoice'] = None
        return res

    def get_rec_name(self, name):
        return self.statement.rec_name

    @classmethod
    def copy(cls, lines, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default.setdefault('move', None)
        default.setdefault('invoice', None)
        return super(Line, cls).copy(lines, default=default)

    def create_move(self):
        '''
        Create move for the statement line and return move if created.
        '''
        pool = Pool()
        Move = pool.get('account.move')
        Period = pool.get('account.period')
        Invoice = pool.get('account.invoice')
        Currency = pool.get('currency.currency')
        MoveLine = pool.get('account.move.line')
        Lang = pool.get('ir.lang')

        if self.move:
            return

        period_id = Period.find(self.statement.company.id, date=self.date)

        move_lines = self._get_move_lines()
        move = Move(
            period=period_id,
            journal=self.statement.journal.journal,
            date=self.date,
            origin=self,
            lines=move_lines,
            )
        move.save()

        self.write([self], {
                'move': move.id,
                })

        if self.invoice:
            with Transaction().set_context(date=self.invoice.currency_date):
                amount_to_pay = Currency.compute(self.invoice.currency,
                    self.invoice.amount_to_pay,
                    self.statement.journal.currency)
            if amount_to_pay < abs(self.amount):
                lang, = Lang.search([
                        ('code', '=', Transaction().language),
                        ])

                amount = Lang.format(lang,
                    '%.' + str(self.statement.journal.currency.digits) + 'f',
                    self.amount, True)
                self.raise_user_error('amount_greater_invoice_amount_to_pay',
                        error_args=(amount,))

            with Transaction().set_context(date=self.invoice.currency_date):
                amount = Currency.compute(self.statement.journal.currency,
                    self.amount, self.statement.company.currency)

            reconcile_lines = self.invoice.get_reconcile_lines_for_amount(
                abs(amount))

            for move_line in move.lines:
                if move_line.account == self.invoice.account:
                    Invoice.write([self.invoice], {
                            'payment_lines': [('add', [move_line.id])],
                            })
                    break
            if reconcile_lines[1] == Decimal('0.0'):
                lines = reconcile_lines[0] + [move_line]
                MoveLine.reconcile(lines)
        return move

    @classmethod
    def post_move(cls, lines):
        Move = Pool().get('account.move')
        Move.post([l.move for l in lines if l.move])

    @classmethod
    def delete_move(cls, lines):
        Move = Pool().get('account.move')
        Move.delete([l.move for l in lines if l.move])

    def _get_move_lines(self):
        '''
        Return the move lines for the statement line
        '''
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        Currency = Pool().get('currency.currency')
        zero = Decimal("0.0")
        amount = Currency.compute(self.statement.journal.currency, self.amount,
            self.statement.company.currency)
        if self.statement.journal.currency != self.statement.company.currency:
            second_currency = self.statement.journal.currency.id
            amount_second_currency = abs(self.amount)
        else:
            amount_second_currency = None
            second_currency = None

        move_lines = []
        move_lines.append(MoveLine(
                description=self.description,
                debit=amount < zero and -amount or zero,
                credit=amount >= zero and amount or zero,
                account=self.account,
                party=self.party,
                second_currency=second_currency,
                amount_second_currency=amount_second_currency,
                ))

        journal = self.statement.journal.journal
        if self.amount >= zero:
            account = journal.credit_account
        else:
            account = journal.debit_account
        if not account:
            self.raise_user_error('debit_credit_account_statement_journal',
                (journal.rec_name,))
        if self.account == account:
            self.raise_user_error('same_debit_credit_account', {
                    'account': self.account.rec_name,
                    'line': self.account,
                    'journal': self.journal,
                    })
        move_lines.append(MoveLine(
                description=self.description,
                debit=amount >= zero and amount or zero,
                credit=amount < zero and -amount or zero,
                account=account,
                party=self.party,
                second_currency=second_currency,
                amount_second_currency=amount_second_currency,
                ))
        return move_lines
