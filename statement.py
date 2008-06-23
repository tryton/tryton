#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
"Statement"

from trytond.osv import fields, OSV, ExceptORM
from trytond.netsvc import LocalService
from decimal import Decimal

_STATES = {'readonly': 'state != "draft"'}


class Statement(OSV):
    'Bank Statement'
    _name = 'statement.statement'
    _description = __doc__

    journal = fields.Many2One(
        'statement.journal', 'Journal', required=True, states=_STATES,
        on_change=['journal'], select=1)
    date = fields.Date('Date', required=True, states=_STATES, select=1)
    start_balance = fields.Numeric(
        'Start Balance', digits=(16, 2), states=_STATES)
    end_balance = fields.Numeric(
        'End Balance', digits=(16, 2), states=_STATES)
    lines = fields.One2Many(
        'statement.statement.line', 'statement', 'Transactions',
        states=_STATES)
    state = fields.Selection(
        [('draft', 'Draft'),
         ('validated', 'Validated'),
         ('cancel', 'Cancel'),
         ('posted', 'Posted'),],
        'State', readonly=True, select=1)

    def __init__(self):
        super(Statement, self).__init__()
        self._rpc_allowed += [
            'draft_workflow',
        ]
        self._order[0] = ('id', 'DESC')

    def default_state(self, cursor, user, context=None):
        return 'draft'

    def on_change_journal(self, cursor, user, ids, value, context=None):
        if not value.get('journal'):
            return {}
        statement_ids = self.search(
            cursor, user, [('journal', '=', value['journal'])],
            order=[('date','DESC')], limit=1, context=context)
        if not statement_ids:
            return {}
        statement = self.browse(cursor, user, statement_ids[0], context=context)
        return {'start_balance': statement.end_balance}

    def get_end_balance(self, cursor, user, ids, name, arg, context=None):
        statements = self.browse(cursor, user, ids, context=context)
        res = {}
        for statement in statements:
            res[statement.id] = statement.start_balance
            for line in statement.lines:
                res[statement.id] += line.amount
        return res

    def set_state_validated(self, cursor, user, statement_id, context=None):
        statement_line_obj = self.pool.get('statement.statement.line')
        statement = self.browse(cursor, user, statement_id, context=context)

        computed_end_balance = statement.start_balance
        for line in statement.lines:
            computed_end_balance += line.amount
        if computed_end_balance != statement.end_balance:
            raise ExceptORM('Error:', 'Wrong End balance:\n'\
                                ' * Expected: %s\n'\
                                ' * Computed: %s'%\
                                (statement.end_balance, computed_end_balance))
        for line in statement.lines:
            statement_line_obj.create_move(cursor, user, line, context=context)
        self.write(cursor, user, statement_id,
                   {'state':'validated',},
                   context=context)

    def set_state_posted(self, cursor, user, statement_id, context=None):
        statement_line_obj = self.pool.get('statement.statement.line')
        statement = self.browse(cursor, user, statement_id, context=context)
        statement_line_obj.post_move(
            cursor, user, statement.lines, context=context)
        self.write(
            cursor, user, statement_id, {'state':'posted'}, context=context)

    def set_state_cancel(self, cursor, user, statement_id, context=None):
        statement_line_obj = self.pool.get('statement.statement.line')
        statement = self.browse(cursor, user, statement_id, context=context)
        statement_line_obj.unlink_move(
            cursor, user, statement.lines, context=context)
        self.write(cursor, user, statement_id,
                   {'state':'cancel',},
                   context=context)

    def draft_workflow(self, cursor, user, ids, context=None):
        workflow_service = LocalService('workflow')
        for statement in self.browse(cursor, user, ids, context=context):
            workflow_service.trg_create(user, self._name, statement.id, cursor)
            self.write(
                cursor, user, statement.id,
                {'state': 'draft',})
        return True

Statement()


class Line(OSV):
    'Bank Statement Line'
    _name = 'statement.statement.line'
    _description = __doc__

    statement = fields.Many2One(
        'statement.statement', 'Statement', required=True,  ondelete='CASCADE')
    date = fields.Date('Date', required=True)
    amount = fields.Numeric(
        'Amount', digits=(16,2), required=True,
        on_change=['amount', 'party', 'account'])
    party = fields.Many2One(
        'relationship.party', 'Party', on_change=['amount', 'party'])
    account = fields.Many2One(
        'account.account', 'Account', required=True)
    description = fields.Char('Description', size=None)
    move = fields.Many2One(
        'account.move', 'Account Move', readonly=True)

    def on_change_party(self, cursor, user, ids, value, context=None):
        if not (value.get('party') and value.get('amount')):
            return {}
        party_obj = self.pool.get('relationship.party')
        account_obj = self.pool.get('account.account')
        party = party_obj.browse(cursor, user, value['party'], context=context)
        if value['amount'] > Decimal("0.0"):
            account = party.account_receivable
        else:
            account = party.account_payable
        return {'account': account_obj.name_get(
                cursor, user, account.id, context=context)[0]}

    def on_change_amount(self, cursor, user, ids, value, context=None):
        if not (value.get('party') and value.get('amount')):
            return {}
        party_obj = self.pool.get('relationship.party')
        account_obj = self.pool.get('account.account')
        party = party_obj.browse(cursor, user, value['party'], context=context)
        if value.get('account') and value['account'] not in (
            party.account_receivable.id, party.account_payable.id):
            # The user has entered a non-default value, we keep it.
            return {}
        if value['amount'] > Decimal("0.0"):
            account = party.account_receivable
        else:
            account = party.account_payable
        return {'account': account_obj.name_get(
                cursor, user, account.id, context=context)[0]}

    def create_move(self, cursor, user, line, context=None):
        move_obj = self.pool.get('account.move')
        period_obj = self.pool.get('account.period')
        period = period_obj.find(cursor, user, date=line.date,
                                 context=context)

        move_lines = self.get_move_lines(
            cursor, user, line, context=context)
        move_id = move_obj.create(
            cursor, user,
            {'name': line.date,
             'period': period,
             'journal': line.statement.journal.journal.id,
             'date': line.date,
             'lines': [('create', x) for x in move_lines],
             },
            context=context)
        self.write(
            cursor, user, line.id, {'move': move_id}, context=context)

    def post_move(self, cursor, user, lines, context=None):
        move_obj = self.pool.get('account.move')
        move_obj.post(cursor, user, [l.move.id for l in lines], context=context)

    def unlink_move(self, cursor, user, lines, context=None):
        move_obj = self.pool.get('account.move')
        move_obj.unlink(
            cursor, user, [l.move.id for l in lines], context=context)
    def get_move_lines(self, cursor, user, statement_line, context=None):
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
        vals.append(
            {'name': statement_line.date,
             'debit': amount >= zero and amount or zero,
             'credit': amount < zero and -amount or zero,
             'account': statement_line.account.id,
             'party': statement_line.party and statement_line.party.id,
             'second_currency': second_currency,
             'amount_second_currency': amount_second_currency,
             })

        journal = statement_line.statement.journal.journal
        if statement_line.amount < zero:
            account = journal.credit_account
        else:
            account = journal.debit_account
        if not account:
            raise ExceptORM('Error:', 'Please provide debit and '\
                                'credit account on bank journal.')
        vals.append(
            {'name': statement_line.date,
             'debit': amount < zero and -amount or zero,
             'credit': amount >= zero and amount or zero,
             'account': account.id,
             'party': statement_line.party and statement_line.party.id,
             'second_currency': second_currency,
             'amount_second_currency': amount_second_currency,
             })
        return vals

Line()
