"Statement"

from trytond.osv import fields, OSV, ExceptORM
from trytond.netsvc import LocalService

_STATES = {'readonly': 'state != "draft"'}

class Statement(OSV):
    'Bank Statement'
    _name = 'statement.statement'
    _description = __doc__

    journal = fields.Many2One(
        'statement.journal', 'Journal', required=True, states=_STATES,
        on_change=['journal'], select=True)
    date = fields.Date('date', required=True, states=_STATES, select=True)
    start_balance = fields.Numeric('Start Balance', digits=(16, 2),)
    end_balance = fields.Function(
        'get_end_balance', string='End Balance', type='numeric',)
    company = fields.Many2One(
        'company.company', 'Company', required=True, select=True)
    currency = fields.Many2One('currency.currency', 'Currency', required=True)
    lines = fields.One2Many(
        'statement.statement.line', 'statement', 'Transactions',
        states=_STATES,)
    move = fields.Many2One(
        'account.move', 'Move', readonly=True,)
    state = fields.Selection(
        [('draft', 'Draft'), ('waiting','Waiting'), ('done', 'Done'),],'State',
        readonly=True, select=True)

    def __init__(self):
        super(Statement, self).__init__()
        self._constraints += [
            ('check_unique_waiting_statement',
             'Error: You can only have one waiting statement '\
                 'for the same journal.',
             ['journal']),
            ]

    def check_unique_waiting_statement(self, cursor, user, ids, parent=None):
        cursor.execute('SELECT max(nb_waiting) AS max_nb_waiting '\
                       'FROM (SELECT count(\'\') AS nb_waiting '\
                           'FROM statement_statement WHERE state = \'waiting\' '\
                           'GROUP BY company, journal) AS sub_query')
        if cursor.rowcount and cursor.fetchone()[0] > 1:
            return False
        return True

    def default_state(self, cursor, user, context=None):
        return 'draft'

    def on_change_journal(self, cursor, user, ids, value, context=None):
        if not value.get('journal'):
            return {}
        journal_obj = self.pool.get('statement.journal')
        currency_obj = self.pool.get('currency.currency')
        company_obj = self.pool.get('company.company')
        journal= journal_obj.browse(cursor, user, value['journal'],
                                    context=context)
        return {'currency': currency_obj.name_get(
                    cursor, user, journal.currency.id, context=context)[0],
                'company': company_obj.name_get(
                    cursor, user, journal.company.id, context=context)[0],
                'start_balance': journal.balance}

    def get_end_balance(self, cursor, user, ids, name, arg, context=None):
        statements = self.browse(cursor, user, ids, context=context)
        res = {}
        for statement in statements:
            res[statement.id] = statement.start_balance
            for line in statement.lines:
                res[statement.id] += line.amount
        return res

    def set_state_waiting(self, cursor, user, statement_id, context=None):
        move_obj = self.pool.get('account.move')
        move_line_obj = self.pool.get('account.move.line')
        period_obj = self.pool.get('account.period')
        statement = self.browse(cursor, user, statement_id, context=context)

        period = period_obj.find(cursor, user, date=statement.date,
                                 context=context)
        move_id = move_obj.create(
            cursor, user,
            {'name': statement.date, #XXX
             'period': period,
             'journal': statement.journal.journal.id,
             'date': statement.date,
             },
            context=context)

        for line in statement.lines:
            move_line_obj.create(
                cursor, user,
                {'name': '?',
                 'debit': line.amount>=0 and line.amount,
                 'credit': line.amount<0 and -line.amount,
                 'account': line.account.id,
                 'move': move_id,
                 'party': line.party and line.party.id,
                 },             # second currency?
                context=context)

            journal = line.statement.journal.journal
            if line.amount < 0:
                account = journal.credit_account
            else:
                account = journal.debit_account
            if not account:
                raise ExceptORM('Error:', 'Please provide debit and '\
                                    'credit account on bank journal.')

            move_line_obj.create(
                cursor, user,
                {'name': '?',
                 'debit': line.amount < 0 and -line.amount or 0.0,
                 'credit': line.amount >= 0 and line.amount or 0.0,
                 'account': account.id,
                 'move': move_id,
                 'party': line.party and line.party.id,
                 },             # second currency?
                context=context)

        self.write(cursor, user, statement_id,
                   {'state':'waiting',
                    'start_balance': statement.journal.balance,
                    'move': move_id,},
                   context=context)

    def set_state_done(self, cursor, user, statement_id, context=None):
        move_obj = self.pool.get('account.move')
        statement = self.browse(cursor, user, statement_id, context=context)
        move_obj.write(
            cursor, user, statement.move.id, {'state': 'posted'},
            context=context)
        self.write(
            cursor, user, statement_id, {'state':'done'}, context=context)

Statement()

class Line(OSV):
    'Bank Statement Line'
    _name = 'statement.statement.line'
    _description = __doc__

    statement = fields.Many2One(
        'statement.statement','Statement', required=True)
    date = fields.Date('Date', required=True)
    amount = fields.Numeric(
        'Amount', digits=(16,2), required=True, on_change=['amount','party'])
    party = fields.Many2One(
        'relationship.party', 'Party', on_change=['amount','party'])
    account = fields.Many2One(
        'account.account', 'Account', required=True,)
    description = fields.Char('Description', size=None)

    def on_change_party(self, cursor, user, ids, value, context=None):
        if not (value.get('party') and value.get('amount')):
            return {}
        party_obj = self.pool.get('relationship.party')
        account_obj = self.pool.get('account.account')
        party = party_obj.browse(cursor, user, value['party'], context=context)
        if value['amount'] > 0:
            account = party.account_receivable
        else:
            account = party.account_payable
        return {'account': account_obj.name_get(
                cursor, user, account.id, context=context)[0]}

    def on_change_amount(self, cursor, user, ids, value, context=None):
        return self.on_change_party(cursor, user, ids, value, context=context)
Line()
