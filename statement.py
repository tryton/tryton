#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal
from trytond.model import Workflow, ModelView, ModelSQL, fields
from trytond.pyson import Eval, If, Bool
from trytond.transaction import Transaction
from trytond.backend import TableHandler
from trytond.pool import Pool

_STATES = {'readonly': Eval('state') != 'draft'}
_DEPENDS = ['state']


class Statement(Workflow, ModelSQL, ModelView):
    'Account Statement'
    _name = 'account.statement'
    _description = __doc__

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
        on_change_with=['journal']), 'get_currency_digits')
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
        'get_balance')
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

    def __init__(self):
        super(Statement, self).__init__()
        self._order[0] = ('id', 'DESC')
        self._error_messages.update({
                'wrong_end_balance': 'End Balance must be %s!',
                'delete_cancel': 'Statement "%s" must be cancelled before ' \
                    'deletion!',
                })
        self._transitions |= set((
                ('draft', 'validated'),
                ('validated', 'posted'),
                ('validated', 'cancel'),
                ('cancel', 'draft'),
                ))
        self._buttons.update({
                'draft': {
                    'invisible': Eval('state') != 'cancel',
                    },
                'validate': {
                    'invisible': Eval('state') != 'draft',
                    },
                'post': {
                    'invisible': Eval('state') != 'validated',
                    },
                'cancel': {
                    'invisible': Eval('state') != 'validated',
                    },
                })

    def init(self, module_name):
        cursor = Transaction().cursor

        # Migration from 1.8: new field company
        table = TableHandler(cursor, self, module_name)
        company_exist = table.column_exist('company')

        super(Statement, self).init(module_name)

        # Migration from 1.8: fill new field company
        if not company_exist:
            offset = 0
            limit = cursor.IN_MAX
            statement_ids = True
            while statement_ids:
                statement_ids = self.search([], offset=offset, limit=limit)
                offset += limit
                for statement in self.browse(statement_ids):
                    self.write(statement.id, {
                        'company': statement.journal.company.id,
                    })
            table = TableHandler(cursor, self, module_name)
            table.not_null_action('company', action='add')

    def default_company(self):
        return Transaction().context.get('company')

    def default_state(self):
        return 'draft'

    def default_date(self):
        date_obj = Pool().get('ir.date')
        return date_obj.today()

    def default_currency_digits(self):
        company_obj = Pool().get('company.company')
        if Transaction().context.get('company'):
            company = company_obj.browse(Transaction().context['company'])
            return company.currency.digits
        return 2

    def on_change_journal(self, value):
        res = {}
        if not value.get('journal'):
            return res

        statement_ids = self.search([
            ('journal', '=', value['journal']),
            ], order=[
                ('date', 'DESC'),
            ], limit=1)
        if not statement_ids:
            return res

        statement = self.browse(statement_ids[0])
        res['start_balance'] = statement.end_balance
        return res

    def on_change_with_currency_digits(self, vals):
        journal_obj = Pool().get('account.statement.journal')
        if vals.get('journal'):
            journal = journal_obj.browse(vals['journal'])
            return journal.currency.digits
        return 2

    def get_currency_digits(self, ids, name):
        res = {}
        for statement in self.browse(ids):
            res[statement.id] = statement.journal.currency.digits
        return res

    def get_rec_name(self, ids, name):
        lang_obj = Pool().get('ir.lang')

        if not ids:
            return {}

        lang_id, = lang_obj.search([
                ('code', '=', Transaction().language),
                ])
        lang = lang_obj.browse(lang_id)

        res = {}
        for statement in self.browse(ids):
            res[statement.id] = statement.journal.name + ' ' + \
                    lang.currency(lang, statement.start_balance,
                        statement.journal.currency, symbol=False,
                        grouping=True) + \
                    lang.currency(lang, statement.end_balance,
                        statement.journal.currency, symbol=False,
                        grouping=True)
        return res

    def search_rec_name(self, name, clause):
        ids = self.search(['OR',
            ('start_balance',) + clause[1:],
            ('end_balance',) + clause[1:],
            ])
        if ids:
            return [('id', 'in', ids)]
        return [('journal',) + clause[1:]]

    def get_move_lines(self, ids, name):
        '''
        Return the move lines that have been generated by the statements.
        '''
        res = {}
        for statement in self.browse(ids):
            res[statement.id] = []
            for line in statement.lines:
                if not line.move:
                    continue
                for move_line in line.move.lines:
                    res[statement.id].append(move_line.id)
        return res

    def get_end_balance(self, ids, name):
        statements = self.browse(ids)
        res = {}
        for statement in statements:
            res[statement.id] = statement.start_balance
            for line in statement.lines:
                res[statement.id] += line.amount
        return res

    def get_balance(self, ids, name):
        return dict((s.id, s.end_balance - s.start_balance)
            for s in self.browse(ids))

    def on_change_with_balance(self, values):
        if not set(('end_balance', 'start_balance')) <= set(values):
            return Decimal(0)
        else:
            return Decimal(values.get('end_balance') or 0
                - values.get('start_balance') or 0)

    def on_change_lines(self, values):
        pool = Pool()
        invoice_obj = pool.get('account.invoice')
        journal_obj = pool.get('account.statement.journal')
        currency_obj = pool.get('currency.currency')
        res = {
            'lines': {},
        }
        if values.get('journal') and values.get('lines'):
            journal = journal_obj.browse(values['journal'])
            invoice_ids = set()
            for line in values['lines']:
                if line['invoice']:
                    invoice_ids.add(line['invoice'])
            invoice_id2amount_to_pay = {}
            for invoice in invoice_obj.browse(list(invoice_ids)):
                with Transaction().set_context(date=invoice.currency_date):
                    invoice_id2amount_to_pay[invoice.id] = (
                        currency_obj.compute(invoice.currency.id,
                            invoice.amount_to_pay, journal.currency.id))

            for line in values['lines']:
                if line['invoice'] and line['id']:
                    amount_to_pay = invoice_id2amount_to_pay[line['invoice']]
                    if abs(line['amount']) > amount_to_pay:
                        res['lines'].setdefault('update', [])
                        if currency_obj.is_zero(journal.currency,
                                amount_to_pay):
                            res['lines']['update'].append({
                                'id': line['id'],
                                'invoice': None,
                                })
                        else:
                            res['lines']['update'].append({
                                'id': line['id'],
                                'amount': amount_to_pay,
                                })
                            res['lines'].setdefault('add', [])
                            vals = line.copy()
                            del vals['id']
                            vals['amount'] = (abs(line['amount'])
                                - amount_to_pay)
                            if line['amount'] < 0:
                                vals['amount'] = - vals['amount']
                            vals['invoice'] = None
                            res['lines']['add'].append(vals)
                    invoice_id2amount_to_pay[line['invoice']] = \
                            amount_to_pay - abs(line['amount'])
        return res

    def delete(self, ids):
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Cancel before delete
        self.cancel(ids)
        for statement in self.browse(ids):
            if statement.state != 'cancel':
                self.raise_user_error('delete_cancel', statement.rec_name)
        return super(Statement, self).delete(ids)

    @ModelView.button
    @Workflow.transition('draft')
    def draft(self, ids):
        pass

    @ModelView.button
    @Workflow.transition('validated')
    def validate(self, ids):
        statement_line_obj = Pool().get('account.statement.line')
        lang_obj = Pool().get('ir.lang')

        for statement in self.browse(ids):
            computed_end_balance = statement.start_balance
            for line in statement.lines:
                computed_end_balance += line.amount
            if computed_end_balance != statement.end_balance:
                lang_id, = lang_obj.search([
                        ('code', '=', Transaction().language),
                        ])
                lang = lang_obj.browse(lang_id)

                amount = lang_obj.format(lang,
                        '%.' + str(statement.journal.currency.digits) + 'f',
                        computed_end_balance, True)
                self.raise_user_error('wrong_end_balance',
                    error_args=(amount,))
            for line in statement.lines:
                statement_line_obj.create_move(line)

    @ModelView.button
    @Workflow.transition('posted')
    def post(self, ids):
        statement_line_obj = Pool().get('account.statement.line')

        statements = self.browse(ids)
        lines = [l for s in statements for l in s.lines]
        statement_line_obj.post_move(lines)

    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(self, ids):
        statement_line_obj = Pool().get('account.statement.line')

        statements = self.browse(ids)
        lines = [l for s in statements for l in s.lines]
        statement_line_obj.delete_move(lines)

Statement()


class Line(ModelSQL, ModelView):
    'Account Statement Line'
    _name = 'account.statement.line'
    _description = __doc__

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
            If(Bool(Eval('party')),
                If(Eval('amount', 0) > 0,
                    ('kind', '=', 'receivable'),
                    ('kind', '=', 'payable')),
                ('kind', 'in', ['payable', 'receivable', 'revenue', 'expense',
                        'other'])),
            ],
        depends=['party', 'amount'])
    description = fields.Char('Description')
    move = fields.Many2One('account.move', 'Account Move', readonly=True)
    invoice = fields.Many2One('account.invoice', 'Invoice',
        domain=[
            ('party', '=', Eval('party')),
            ('account', '=', Eval('account')),
            ('state', '=', If(Eval('_parent_statement', {}).get('state')
                    == 'draft', 'open', '')),
            ],
        states={
            'readonly': ~Eval('amount'),
            },
        depends=['party', 'account', 'amount'])

    def __init__(self):
        super(Line, self).__init__()
        self._error_messages.update({
            'debit_credit_account_statement_journal': 'Please provide debit '
                'and credit account on statement journal.',
            'same_debit_credit_account': 'Credit or debit account on '
                'journal is the same than the statement line account!',
            'amount_greater_invoice_amount_to_pay': 'Amount (%s) greater than '
                'the amount to pay of invoice!',
            })
        self._sql_constraints += [
            ('check_statement_line_amount', 'CHECK(amount != 0)',
                'Amount should be a positive or negative value!'),
            ]

    def default_amount(self):
        return Decimal(0)

    def on_change_party(self, value):
        party_obj = Pool().get('party.party')
        invoice_obj = Pool().get('account.invoice')
        res = {}

        if value.get('party'):
            party = party_obj.browse(value['party'])
            if value.get('amount'):
                if value['amount'] > Decimal("0.0"):
                    account = party.account_receivable
                else:
                    account = party.account_payable
                res['account'] = account.id
                res['account.rec_name'] = account.rec_name

        if value.get('invoice'):
            if value.get('party'):
                invoice = invoice_obj.browse(value['invoice'])
                if invoice.party != value['party']:
                    res['invoice'] = None
            else:
                res['invoice'] = None
        return res

    def on_change_amount(self, value):
        pool = Pool()
        party_obj = pool.get('party.party')
        invoice_obj = pool.get('account.invoice')
        journal_obj = pool.get('account.statement.journal')
        currency_obj = pool.get('currency.currency')
        res = {}

        if value.get('party'):
            party = party_obj.browse(value['party'])
            if value.get('account') and value['account'] not in (
                party.account_receivable.id, party.account_payable.id):
                # The user has entered a non-default value, we keep it.
                pass
            elif value.get('amount'):
                if value['amount'] > Decimal("0.0"):
                    account = party.account_receivable
                else:
                    account = party.account_payable
                res['account'] = account.id
                res['account.rec_name'] = account.rec_name
        if value.get('invoice'):
            if value.get('amount') and value.get('_parent_statement.journal'):
                invoice = invoice_obj.browse(value['invoice'])
                journal = journal_obj.browse(
                    value['_parent_statement.journal'])
                with Transaction().set_context(date=invoice.currency_date):
                    amount_to_pay = currency_obj.compute(invoice.currency.id,
                        invoice.amount_to_pay, journal.currency.id)
                if abs(value['amount']) > amount_to_pay:
                    res['invoice'] = None
            else:
                res['invoice'] = None
        return res

    def on_change_account(self, value):
        invoice_obj = Pool().get('account.invoice')
        res = {}

        if value.get('invoice'):
            if value.get('account'):
                invoice = invoice_obj.browse(value['invoice'])
                if invoice.account.id != value['account']:
                    res['invoice'] = None
            else:
                res['invoice'] = None
        return res

    def create_move(self, line):
        '''
        Create move for the statement line and return move id if created.
        '''
        pool = Pool()
        move_obj = pool.get('account.move')
        period_obj = pool.get('account.period')
        invoice_obj = pool.get('account.invoice')
        currency_obj = pool.get('currency.currency')
        move_line_obj = pool.get('account.move.line')
        lang_obj = pool.get('ir.lang')

        if line.move:
            return

        period_id = period_obj.find(line.statement.company.id,
                date=line.date)

        move_lines = self._get_move_lines(line)
        move_id = move_obj.create({
                'name': unicode(line.date),
                'period': period_id,
                'journal': line.statement.journal.journal.id,
                'date': line.date,
                'lines': [('create', x) for x in move_lines],
             })

        self.write(line.id, {
            'move': move_id,
            })

        if line.invoice:
            with Transaction().set_context(date=line.invoice.currency_date):
                amount_to_pay = currency_obj.compute(line.invoice.currency.id,
                        line.invoice.amount_to_pay,
                        line.statement.journal.currency.id)
            if amount_to_pay < abs(line.amount):
                lang_id, = lang_obj.search([
                        ('code', '=', Transaction().language),
                        ])
                lang = lang_obj.browse(lang_id)

                amount = lang_obj.format(lang,
                    '%.' + str(line.statement.journal.currency.digits) + 'f',
                    line.amount, True)
                self.raise_user_error('amount_greater_invoice_amount_to_pay',
                        error_args=(amount,))

            with Transaction().set_context(date=line.invoice.currency_date):
                amount = currency_obj.compute(
                        line.statement.journal.currency.id, line.amount,
                        line.statement.company.currency.id)

            reconcile_lines = invoice_obj.get_reconcile_lines_for_amount(
                    line.invoice, abs(amount))

            move = move_obj.browse(move_id)
            line_id = None
            for move_line in move.lines:
                if move_line.account.id == line.invoice.account.id:
                    line_id = move_line.id
                    invoice_obj.write(line.invoice.id, {
                        'payment_lines': [('add', line_id)],
                        })
                    break
            if reconcile_lines[1] == Decimal('0.0'):
                line_ids = reconcile_lines[0] + [line_id]
                move_line_obj.reconcile(line_ids)
        return move_id

    def post_move(self, lines):
        move_obj = Pool().get('account.move')
        move_obj.post([l.move.id for l in lines if l.move])

    def delete_move(self, lines):
        move_obj = Pool().get('account.move')
        move_obj.delete([l.move.id for l in lines if l.move])

    def _get_move_lines(self, statement_line):
        '''
        Return the values of the move lines for the statement line

        :param statement_line: a BrowseRecord of the statement line
        :return: a list of dictionary of move line values
        '''
        currency_obj = Pool().get('currency.currency')
        zero = Decimal("0.0")
        amount = currency_obj.compute(
            statement_line.statement.journal.currency, statement_line.amount,
            statement_line.statement.company.currency)
        if statement_line.statement.journal.currency.id != \
                statement_line.statement.company.currency.id:
            second_currency = statement_line.statement.journal.currency.id
            amount_second_currency = abs(statement_line.amount)
        else:
            amount_second_currency = None
            second_currency = None

        party_id = statement_line.party.id if statement_line.party else None
        vals = []
        vals.append({
            'name': unicode(statement_line.date),
            'debit': amount < zero and -amount or zero,
            'credit': amount >= zero and amount or zero,
            'account': statement_line.account.id,
            'party': party_id,
            'second_currency': second_currency,
            'amount_second_currency': amount_second_currency,
            })

        journal = statement_line.statement.journal.journal
        if statement_line.amount >= zero:
            account = journal.credit_account
        else:
            account = journal.debit_account
        if not account:
            self.raise_user_error('debit_credit_account_statement_journal')
        if statement_line.account.id == account.id:
            self.raise_user_error('same_debit_credit_account')
        vals.append({
            'name': unicode(statement_line.date),
            'debit': amount >= zero and amount or zero,
            'credit': amount < zero and -amount or zero,
            'account': account.id,
            'party': party_id,
            'second_currency': second_currency,
            'amount_second_currency': amount_second_currency,
            })
        return vals

Line()
