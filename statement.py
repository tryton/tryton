#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Statement"
from trytond.model import ModelWorkflow, ModelView, ModelSQL, fields
from trytond.pyson import Not, Equal, Eval, Or, Bool, Get, If
from decimal import Decimal

_STATES = {'readonly': Not(Equal(Eval('state'), 'draft'))}


class Statement(ModelWorkflow, ModelSQL, ModelView):
    'Account Statement'
    _name = 'account.statement'
    _description = __doc__

    journal = fields.Many2One('account.statement.journal', 'Journal', required=True,
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

    def default_state(self, cursor, user, context=None):
        return 'draft'

    def default_date(self, cursor, user, context=None):
        date_obj = self.pool.get('ir.date')
        return date_obj.today(cursor, user, context=context)

    def default_currency_digits(self, cursor, user, context=None):
        company_obj = self.pool.get('company.company')
        if context is None:
            context = {}
        if context.get('company'):
            company = company_obj.browse(cursor, user, context['company'],
                    context=context)
            return company.currency.digits
        return 2

    def on_change_journal(self, cursor, user, value, context=None):
        res = {}
        if not value.get('journal'):
            return res

        statement_ids = self.search(cursor, user, [
            ('journal', '=', value['journal']),
            ], order=[
                ('date', 'DESC'),
            ], limit=1, context=context)
        if not statement_ids:
            return res

        statement = self.browse(cursor, user, statement_ids[0], context=context)
        res['start_balance'] = statement.end_balance
        return res

    def on_change_with_currency_digits(self, cursor, user, vals, context=None):
        journal_obj = self.pool.get('account.statement.journal')
        if vals.get('journal'):
            journal = journal_obj.browse(cursor, user, vals['journal'],
                    context=context)
            return journal.currency.digits
        return 2

    def get_currency_digits(self, cursor, user, ids, name, context=None):
        res = {}
        for statement in self.browse(cursor, user, ids, context=context):
            res[statement.id] = statement.journal.currency.digits
        return res

    def get_rec_name(self, cursor, user, ids, name, context=None):
        lang_obj = self.pool.get('ir.lang')

        if context is None:
            context = {}

        if not ids:
            return {}

        for code in [context.get('language', False) or 'en_US', 'en_US']:
            lang_ids = lang_obj.search(cursor, user, [
                ('code', '=', code),
                ], context=context)
            if lang_ids:
                break
        lang = lang_obj.browse(cursor, user, lang_ids[0], context=context)

        res = {}
        for statement in self.browse(cursor, user, ids, context=context):
            res[statement.id] = statement.journal.name + ' ' + \
                    lang.currency(lang, statement.start_balance,
                        statement.journal.currency, symbol=False,
                        grouping=True) + \
                    lang.currency(lang, statement.end_balance,
                        statement.journal.currency, symbol=False,
                        grouping=True)
        return res

    def search_rec_name(self, cursor, user, name, clause, context=None):
        ids = self.search(cursor, user, ['OR',
            ('start_balance',) + clause[1:],
            ('end_balance',) + clause[1:],
            ], context=context)
        if ids:
            return [('id', 'in', ids)]
        return [('journal',) + clause[1:]]

    def get_move_lines(self, cursor, user, ids, name, context=None):
        '''
        Return the move lines that have been generated by the statements.
        '''
        res = {}
        for statement in self.browse(cursor, user, ids, context=context):
            res[statement.id] = []
            for line in statement.lines:
                if not line.move:
                    continue
                for move_line in line.move.lines:
                    res[statement.id].append(move_line.id)
        return res

    def get_end_balance(self, cursor, user, ids, name, context=None):
        statements = self.browse(cursor, user, ids, context=context)
        res = {}
        for statement in statements:
            res[statement.id] = statement.start_balance
            for line in statement.lines:
                res[statement.id] += line.amount
        return res

    def on_change_lines(self, cursor, user, values, context=None):
        invoice_obj = self.pool.get('account.invoice')
        journal_obj = self.pool.get('account.statement.journal')
        currency_obj = self.pool.get('currency.currency')
        res = {
            'lines': {},
        }
        if values.get('journal') and values.get('lines'):
            journal = journal_obj.browse(cursor, user, values['journal'],
                    context=context)
            invoice_ids = set()
            for line in values['lines']:
                if line['invoice']:
                    invoice_ids.add(line['invoice'])
            invoice_id2amount_to_pay = {}
            for invoice in invoice_obj.browse(cursor, user, invoice_ids,
                    context=context):
                invoice_id2amount_to_pay[invoice.id] = currency_obj.compute(
                        cursor, user, invoice.currency, invoice.amount_to_pay,
                        journal.currency, context=context)

            for line in values['lines']:
                if line['invoice'] and line['id']:
                    amount_to_pay = invoice_id2amount_to_pay[line['invoice']]
                    if abs(line['amount']) > amount_to_pay:
                        res['lines'].setdefault('update', [])
                        if currency_obj.is_zero(cursor, user, journal.currency,
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

    def set_state_validated(self, cursor, user, statement_id, context=None):
        statement_line_obj = self.pool.get('account.statement.line')
        lang_obj = self.pool.get('ir.lang')

        if context is None:
            context = {}

        statement = self.browse(cursor, user, statement_id, context=context)

        computed_end_balance = statement.start_balance
        for line in statement.lines:
            computed_end_balance += line.amount
        if computed_end_balance != statement.end_balance:
            for code in [context.get('language', False) or 'en_US', 'en_US']:
                lang_ids = lang_obj.search(cursor, user, [
                    ('code', '=', code),
                    ], context=context)
                if lang_ids:
                    break
            lang = lang_obj.browse(cursor, user, lang_ids[0], context=context)

            amount = lang_obj.format(lang,
                    '%.' + str(statement.journal.currency.digits) + 'f',
                    computed_end_balance, True)
            self.raise_user_error(cursor, 'wrong_end_balance',
                    error_args=(amount,), context=context)
        for line in statement.lines:
            statement_line_obj.create_move(cursor, user, line, context=context)
        self.write(cursor, user, statement_id, {
            'state':'validated',
            }, context=context)

    def set_state_posted(self, cursor, user, statement_id, context=None):
        statement_line_obj = self.pool.get('account.statement.line')

        statement = self.browse(cursor, user, statement_id, context=context)
        statement_line_obj.post_move(cursor, user, statement.lines,
                context=context)
        self.write(cursor, user, statement_id, {
            'state':'posted',
            }, context=context)

    def set_state_cancel(self, cursor, user, statement_id, context=None):
        statement_line_obj = self.pool.get('account.statement.line')

        statement = self.browse(cursor, user, statement_id, context=context)
        statement_line_obj.delete_move(cursor, user, statement.lines,
                context=context)
        self.write(cursor, user, statement_id, {
            'state':'cancel',
            }, context=context)

    def draft_workflow(self, cursor, user, ids, context=None):
        self.workflow_trigger_create(cursor, user, ids, context=context)
        self.write(cursor, user, ids, {
            'state': 'draft',
            }, context=context)
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
            on_change=['account', 'invoice'], domain=[('kind', '!=', 'view')])
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

    def on_change_party(self, cursor, user, value, context=None):
        party_obj = self.pool.get('party.party')
        account_obj = self.pool.get('account.account')
        invoice_obj = self.pool.get('account.invoice')
        res = {}

        if value.get('party'):
            party = party_obj.browse(cursor, user, value['party'],
                    context=context)
            if value.get('amount'):
                if value['amount'] > Decimal("0.0"):
                    account = party.account_receivable
                else:
                    account = party.account_payable
                res['account'] = account.id
                res['account.rec_name'] = account.rec_name

        if value.get('invoice'):
            if value.get('party'):
                invoice = invoice_obj.browse(cursor, user, value['invoice'],
                        context=context)
                if invoice.party != value['party']:
                    res['invoice'] = False
            else:
                res['invoice'] = False
        return res

    def on_change_amount(self, cursor, user, value, context=None):
        party_obj = self.pool.get('party.party')
        account_obj = self.pool.get('account.account')
        invoice_obj = self.pool.get('account.invoice')
        journal_obj = self.pool.get('account.statement.journal')
        currency_obj = self.pool.get('currency.currency')
        res = {}

        if value.get('party'):
            party = party_obj.browse(cursor, user, value['party'], context=context)
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
                invoice = invoice_obj.browse(cursor, user, value['invoice'],
                        context=context)
                journal = journal_obj.browse(cursor, user,
                        value['_parent_statement.journal'], context=context)
                amount_to_pay = currency_obj.compute(cursor, user,
                        invoice.currency, invoice.amount_to_pay,
                        journal.currency, context=context)
                if abs(value['amount']) > amount_to_pay:
                    res['invoice'] = False
            else:
                res['invoice'] = False
        return res

    def on_change_account(self, cursor, user, value, context=None):
        invoice_obj = self.pool.get('account.invoice')
        res = {}

        if value.get('invoice'):
            if value.get('account'):
                invoice = invoice_obj.browse(cursor, user, value['invoice'],
                        context=context)
                if invoice.account.id != value['account']:
                    res['invoice'] = False
            else:
                res['invoice'] = False
        return res

    def create_move(self, cursor, user, line, context=None):
        '''
        Create move for the statement line

        :param cursor: the database cursor
        :param user: the user id
        :param line: a BrowseRecord of the line
        :param context: the contest
        :return: the move id
        '''
        move_obj = self.pool.get('account.move')
        period_obj = self.pool.get('account.period')
        invoice_obj = self.pool.get('account.invoice')
        currency_obj = self.pool.get('currency.currency')
        move_line_obj = self.pool.get('account.move.line')
        lang_obj = self.pool.get('ir.lang')

        if context is None:
            context = {}

        period_id = period_obj.find(cursor, user,
                line.statement.journal.company.id, date=line.date,
                context=context)

        move_lines = self._get_move_lines(cursor, user, line, context=context)
        move_id = move_obj.create(cursor, user, {
                'name': line.date,
                'period': period_id,
                'journal': line.statement.journal.journal.id,
                'date': line.date,
                'lines': [('create', x) for x in move_lines],
             }, context=context)

        self.write(cursor, user, line.id, {
            'move': move_id,
            }, context=context)

        if line.invoice:

            amount_to_pay = currency_obj.compute(cursor, user,
                    line.invoice.currency, line.invoice.amount_to_pay,
                    line.statement.journal.currency, context=context)
            if amount_to_pay < abs(line.amount):
                for code in [context.get('language', False) or 'en_US', 'en_US']:
                    lang_ids = lang_obj.search(cursor, user, [
                        ('code', '=', code),
                        ], context=context)
                    if lang_ids:
                        break
                lang = lang_obj.browse(cursor, user, lang_ids[0], context=context)

                amount = lang_obj.format(lang,
                        '%.' + str(line.statement.journal.currency.digits) + 'f',
                        line.amount, True)
                self.raise_user_error(cursor,
                        'amount_greater_invoice_amount_to_pay',
                        error_args=(amount,), context=context)

            amount = currency_obj.compute(cursor, user,
                    line.statement.journal.currency, line.amount,
                    line.statement.journal.company.currency,
                    context=context)

            reconcile_lines = invoice_obj.get_reconcile_lines_for_amount(cursor,
                    user, line.invoice, abs(amount))

            move = move_obj.browse(cursor, user, move_id, context=context)
            line_id = None
            for move_line in move.lines:
                if move_line.account.id == line.invoice.account.id:
                    line_id = move_line.id
                    invoice_obj.write(cursor, user, line.invoice.id, {
                        'payment_lines': [('add', line_id)],
                        }, context=context)
                    break
            if reconcile_lines[1] == Decimal('0.0'):
                line_ids = reconcile_lines[0] + [line_id]
                move_line_obj.reconcile(cursor, user, line_ids, context=context)
        return move_id

    def post_move(self, cursor, user, lines, context=None):
        move_obj = self.pool.get('account.move')
        move_obj.post(cursor, user, [l.move.id for l in lines if l.move],
                context=context)

    def delete_move(self, cursor, user, lines, context=None):
        move_obj = self.pool.get('account.move')
        move_obj.delete(cursor, user, [l.move.id for l in lines if l.move],
                context=context)

    def _get_move_lines(self, cursor, user, statement_line, context=None):
        '''
        Return the values of the move lines for the statement line

        :param cursor: the database cursor
        :param user: the user id
        :param statement_line: a BrowseRecord of the statement line
        :param context: the context
        :return: a list of dictionary of move line values
        '''
        currency_obj = self.pool.get('currency.currency')
        zero = Decimal("0.0")
        amount = currency_obj.compute(
            cursor, user, statement_line.statement.journal.currency,
            statement_line.amount,
            statement_line.statement.journal.company.currency, context=context)
        if statement_line.statement.journal.currency.id != \
                statement_line.statement.journal.company.currency.id:
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
            self.raise_user_error(cursor,
                    'debit_credit_account_statement_journal',
                    context=context)
        if statement_line.account.id == account.id:
            self.raise_user_error(cursor, 'same_debit_credit_account',
                    context=context)
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
