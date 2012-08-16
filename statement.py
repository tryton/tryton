#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from __future__ import with_statement
from decimal import Decimal
from trytond.model import ModelWorkflow, ModelView, ModelSQL, fields
from trytond.pyson import Not, Equal, Eval, Or, Bool, Get, If, In
from trytond.transaction import Transaction
from trytond.backend import TableHandler

_STATES = {'readonly': Not(Equal(Eval('state'), 'draft'))}


class Statement(ModelWorkflow, ModelSQL, ModelView):
    'Account Statement'
    _name = 'account.statement'
    _description = __doc__

    company = fields.Many2One('company.company', 'Company', required=True,
        select=1, states=_STATES, domain=[
            ('id', If(In('company', Eval('context', {})), '=', '!='),
                Get(Eval('context', {}), 'company', 0)),
        ])
    journal = fields.Many2One('account.statement.journal', 'Journal', required=True,
        domain=[
            ('company', '=', Eval('company')),
        ],
        states={
            'readonly': Or(Not(Equal(Eval('state'), 'draft')),
                Bool(Eval('lines'))),
        }, on_change=['journal'], select=1)
    currency_digits = fields.Function(fields.Integer('Currency Digits',
        on_change_with=['journal']), 'get_currency_digits')
    date = fields.Date('Date', required=True, states=_STATES, select=1)
    start_balance = fields.Numeric('Start Balance',
            digits=(16, Eval('currency_digits', 2)),
            states=_STATES, depends=['currency_digits'])
    end_balance = fields.Numeric('End Balance',
            digits=(16, Eval('currency_digits', 2)),
            states=_STATES, depends=['currency_digits'])
    lines = fields.One2Many('account.statement.line', 'statement',
            'Transactions', states={
                'readonly': Or(Not(Equal(Eval('state'), 'draft')),
                    Not(Bool(Eval('journal')))),
            }, on_change=['lines', 'journal'])
    state = fields.Selection([
        ('draft', 'Draft'),
        ('validated', 'Validated'),
        ('cancel', 'Canceled'),
        ('posted', 'Posted'),
        ], 'State', readonly=True, select=1)
    move_lines = fields.Function(fields.One2Many('account.move.line',
        None, 'Move Lines'), 'get_move_lines')

    def __init__(self):
        super(Statement, self).__init__()
        self._rpc.update({
            'draft_workflow': True,
        })
        self._order[0] = ('id', 'DESC')
        self._error_messages.update({
            'wrong_end_balance': 'End Balance must be %s!',
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
        return Transaction().context.get('company') or False

    def default_state(self):
        return 'draft'

    def default_date(self):
        date_obj = self.pool.get('ir.date')
        return date_obj.today()

    def default_currency_digits(self):
        company_obj = self.pool.get('company.company')
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
        journal_obj = self.pool.get('account.statement.journal')
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
        lang_obj = self.pool.get('ir.lang')

        if not ids:
            return {}

        for code in [Transaction().language, 'en_US']:
            lang_ids = lang_obj.search([
                ('code', '=', code),
                ])
            if lang_ids:
                break
        lang = lang_obj.browse(lang_ids[0])

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

    def on_change_lines(self, values):
        invoice_obj = self.pool.get('account.invoice')
        journal_obj = self.pool.get('account.statement.journal')
        currency_obj = self.pool.get('currency.currency')
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
            for invoice in invoice_obj.browse(invoice_ids):
                with Transaction().set_context(date=invoice.currency_date):
                    invoice_id2amount_to_pay[invoice.id] = currency_obj.compute(
                        invoice.currency.id, invoice.amount_to_pay,
                        journal.currency.id)

            for line in values['lines']:
                if line['invoice'] and line['id']:
                    amount_to_pay = invoice_id2amount_to_pay[line['invoice']]
                    if abs(line['amount']) > amount_to_pay:
                        res['lines'].setdefault('update', [])
                        if currency_obj.is_zero(journal.currency,
                                amount_to_pay):
                            res['lines']['update'].append({
                                'id': line['id'],
                                'invoice': False,
                                })
                        else:
                            res['lines']['update'].append({
                                'id': line['id'],
                                'amount': (amount_to_pay
                                        if line['amount'] >= 0
                                        else -amount_to_pay),
                                })
                            res['lines'].setdefault('add', [])
                            vals = line.copy()
                            del vals['id']
                            vals['amount'] = abs(line['amount']) - amount_to_pay
                            if line['amount'] < 0:
                                vals['amount'] = - vals['amount']
                            vals['invoice'] = False
                            res['lines']['add'].append(vals)
                    invoice_id2amount_to_pay[line['invoice']] = \
                            amount_to_pay - abs(line['amount'])
        return res

    def set_state_validated(self, statement_id):
        statement_line_obj = self.pool.get('account.statement.line')
        lang_obj = self.pool.get('ir.lang')

        statement = self.browse(statement_id)

        computed_end_balance = statement.start_balance
        for line in statement.lines:
            computed_end_balance += line.amount
        if computed_end_balance != statement.end_balance:
            for code in [Transaction().language, 'en_US']:
                lang_ids = lang_obj.search([
                    ('code', '=', code),
                    ])
                if lang_ids:
                    break
            lang = lang_obj.browse(lang_ids[0])

            amount = lang_obj.format(lang,
                    '%.' + str(statement.journal.currency.digits) + 'f',
                    computed_end_balance, True)
            self.raise_user_error('wrong_end_balance', error_args=(amount,))
        for line in statement.lines:
            statement_line_obj.create_move(line)
        self.write(statement_id, {
            'state':'validated',
            })

    def set_state_posted(self, statement_id):
        statement_line_obj = self.pool.get('account.statement.line')

        statement = self.browse(statement_id)
        statement_line_obj.post_move(statement.lines)
        self.write(statement_id, {
            'state':'posted',
            })

    def set_state_cancel(self, statement_id):
        statement_line_obj = self.pool.get('account.statement.line')

        statement = self.browse(statement_id)
        statement_line_obj.delete_move(statement.lines)
        self.write(statement_id, {
            'state':'cancel',
            })

    def draft_workflow(self, ids):
        self.workflow_trigger_create(ids)
        self.write(ids, {
            'state': 'draft',
            })
        return True

Statement()


class Line(ModelSQL, ModelView):
    'Account Statement Line'
    _name = 'account.statement.line'
    _description = __doc__

    statement = fields.Many2One('account.statement', 'Statement',
            required=True, ondelete='CASCADE')
    date = fields.Date('Date', required=True)
    amount = fields.Numeric('Amount', required=True,
            digits=(16, Get(Eval('_parent_statement', {}),
                'currency_digits', 2)),
            on_change=['amount', 'party', 'account', 'invoice',
                '_parent_statement.journal'])
    party = fields.Many2One('party.party', 'Party',
            on_change=['amount', 'party', 'invoice'])
    account = fields.Many2One('account.account', 'Account', required=True,
            on_change=['account', 'invoice'], domain=[
                ('kind', '!=', 'view'),
                ('company', '=', Get(Eval('_parent_statement', {}), 'company')),
            ])
    description = fields.Char('Description')
    move = fields.Many2One('account.move', 'Account Move', readonly=True)
    invoice = fields.Many2One('account.invoice', 'Invoice',
            domain=[
                ('party', '=', Eval('party')),
                ('account', '=', Eval('account')),
                ('state', '=', If(Equal(Get(Eval('_parent_statement', {}),
                    'state'), 'draft'), 'open', '')),
            ],
            states={
                'readonly': Not(Bool(Eval('amount'))),
            })

    def __init__(self):
        super(Line, self).__init__()
        self._error_messages.update({
            'debit_credit_account_statement_journal': 'Please provide debit and ' \
                    'credit account on statement journal.',
            'same_debit_credit_account': 'Credit or debit account on ' \
                    'journal is the same than the statement line account!',
            'amount_greater_invoice_amount_to_pay': 'Amount (%s) greater than '\
                    'the amount to pay of invoice!',
            })

    def on_change_party(self, value):
        party_obj = self.pool.get('party.party')
        invoice_obj = self.pool.get('account.invoice')
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
                    res['invoice'] = False
            else:
                res['invoice'] = False
        return res

    def on_change_amount(self, value):
        party_obj = self.pool.get('party.party')
        invoice_obj = self.pool.get('account.invoice')
        journal_obj = self.pool.get('account.statement.journal')
        currency_obj = self.pool.get('currency.currency')
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
                journal = journal_obj.browse(value['_parent_statement.journal'])
                with Transaction().set_context(date=invoice.currency_date):
                    amount_to_pay = currency_obj.compute(invoice.currency.id,
                        invoice.amount_to_pay, journal.currency.id)
                if abs(value['amount']) > amount_to_pay:
                    res['invoice'] = False
            else:
                res['invoice'] = False
        return res

    def on_change_account(self, value):
        invoice_obj = self.pool.get('account.invoice')
        res = {}

        if value.get('invoice'):
            if value.get('account'):
                invoice = invoice_obj.browse(value['invoice'])
                if invoice.account.id != value['account']:
                    res['invoice'] = False
            else:
                res['invoice'] = False
        return res

    def create_move(self, line):
        '''
        Create move for the statement line

        :param line: a BrowseRecord of the line
        :return: the move id
        '''
        move_obj = self.pool.get('account.move')
        period_obj = self.pool.get('account.period')
        invoice_obj = self.pool.get('account.invoice')
        currency_obj = self.pool.get('currency.currency')
        move_line_obj = self.pool.get('account.move.line')
        lang_obj = self.pool.get('ir.lang')

        period_id = period_obj.find(line.statement.company.id,
                date=line.date)

        move_lines = self._get_move_lines(line)
        move_id = move_obj.create({
                'name': line.date,
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
                for code in [Transaction().language, 'en_US']:
                    lang_ids = lang_obj.search([
                        ('code', '=', code),
                        ])
                    if lang_ids:
                        break
                lang = lang_obj.browse(lang_ids[0])

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
        move_obj = self.pool.get('account.move')
        move_obj.post([l.move.id for l in lines if l.move])

    def delete_move(self, lines):
        move_obj = self.pool.get('account.move')
        move_obj.delete([l.move.id for l in lines if l.move])

    def _get_move_lines(self, statement_line):
        '''
        Return the values of the move lines for the statement line

        :param statement_line: a BrowseRecord of the statement line
        :return: a list of dictionary of move line values
        '''
        currency_obj = self.pool.get('currency.currency')
        zero = Decimal("0.0")
        amount = currency_obj.compute(
            statement_line.statement.journal.currency, statement_line.amount,
            statement_line.statement.company.currency)
        if statement_line.statement.journal.currency.id != \
                statement_line.statement.company.currency.id:
            second_currency = statement_line.statement.journal.currency.id
            amount_second_currency = abs(statement_line.amount)
        else:
            amount_second_currency = False
            second_currency = None

        vals = []
        vals.append({
            'name': statement_line.date,
            'debit': amount < zero and -amount or zero,
            'credit': amount >= zero and amount or zero,
            'account': statement_line.account.id,
            'party': statement_line.party and statement_line.party.id,
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
            'name': statement_line.date,
            'debit': amount >= zero and amount or zero,
            'credit': amount < zero and -amount or zero,
            'account': account.id,
            'party': statement_line.party and statement_line.party.id,
            'second_currency': second_currency,
            'amount_second_currency': amount_second_currency,
            })
        return vals

Line()
