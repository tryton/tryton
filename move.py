#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal
import datetime
import time
from itertools import groupby
from operator import itemgetter

from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard, StateTransition, StateView, StateAction, \
    Button
from trytond.report import Report
from trytond.backend import TableHandler, FIELDS
from trytond.pyson import Eval, PYSONEncoder
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta
from trytond.rpc import RPC
from trytond.tools import reduce_ids

__all__ = ['Move', 'Reconciliation', 'Line', 'Move2', 'OpenJournalAsk',
    'OpenJournal', 'OpenAccount', 'ReconcileLinesWriteOff', 'ReconcileLines',
    'UnreconcileLinesStart', 'UnreconcileLines', 'OpenReconcileLinesStart',
    'OpenReconcileLines', 'FiscalYearLine', 'FiscalYear2',
    'PrintGeneralJournalStart', 'PrintGeneralJournal', 'GeneralJournal']
__metaclass__ = PoolMeta

_MOVE_STATES = {
    'readonly': Eval('state') == 'posted',
    }
_MOVE_DEPENDS = ['state']
_LINE_STATES = {
    'readonly': Eval('state') == 'valid',
    }
_LINE_DEPENDS = ['state']


class Move(ModelSQL, ModelView):
    'Account Move'
    __name__ = 'account.move'
    _rec_name = 'number'
    number = fields.Char('Number', required=True, readonly=True)
    post_number = fields.Char('Post Number', readonly=True,
        help='Also known as Folio Number')
    period = fields.Many2One('account.period', 'Period', required=True,
            states=_MOVE_STATES, depends=_MOVE_DEPENDS, select=True)
    journal = fields.Many2One('account.journal', 'Journal', required=True,
            states=_MOVE_STATES, depends=_MOVE_DEPENDS)
    date = fields.Date('Effective Date', required=True, states=_MOVE_STATES,
        depends=_MOVE_DEPENDS, on_change_with=['period', 'journal', 'date'])
    post_date = fields.Date('Post Date', readonly=True)
    description = fields.Char('Description', states=_MOVE_STATES,
        depends=_MOVE_DEPENDS)
    origin = fields.Reference('Origin', selection='get_origin',
        states=_MOVE_STATES, depends=_MOVE_DEPENDS)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ], 'State', required=True, readonly=True, select=True)
    lines = fields.One2Many('account.move.line', 'move', 'Lines',
            states=_MOVE_STATES, depends=_MOVE_DEPENDS,
            context={
                'journal': Eval('journal'),
                'period': Eval('period'),
                'date': Eval('date'),
            })

    @classmethod
    def __setup__(cls):
        super(Move, cls).__setup__()
        cls._check_modify_exclude = ['state']
        cls._order.insert(0, ('date', 'DESC'))
        cls._order.insert(1, ('number', 'DESC'))
        cls._error_messages.update({
                'post_empty_move': ('You can not post move "%s" because it is '
                    'empty.'),
                'post_unbalanced_move': ('You can not post move "%s" because '
                    'it is an unbalanced.'),
                'draft_posted_move_journal': ('You can not set posted move '
                    '"%(move)s" to draft in journal "%(journal)s".'),
                'modify_posted_move': ('You can not modify move "%s" because '
                    'it is already posted.'),
                'period_centralized_journal': ('Move "%(move)s" cannot be '
                    'created because there is already a move in journal '
                    '"%(journal)s" and you cannot create more than one move '
                    'per period in a centralized journal.'),
                'company_in_move': ('You can not create lines on accounts'
                    'of different companies in move "%s".'),
                'date_outside_period': ('You can not create move "%(move)s" '
                    'because it\'s date is outside its period.'),
                'draft_closed_period': ('You can not set to draft move '
                    '"%(move)s" because period "%(period)s" is closed.'),
                })
        cls._buttons.update({
                'post': {
                    'invisible': Eval('state') == 'posted',
                    },
                'draft': {
                    'invisible': Eval('state') == 'draft',
                    },
                })

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor
        table = TableHandler(cursor, cls, module_name)

        # Migration from 2.4:
        #   - name renamed into number
        #   - reference renamed into post_number
        if table.column_exist('name'):
            table.column_rename('name', 'number')
        if table.column_exist('reference'):
            table.column_rename('reference', 'post_number')

        super(Move, cls).__register__(module_name)

        table = TableHandler(cursor, cls, module_name)
        table.index_action(['journal', 'period'], 'add')

        # Add index on create_date
        table.index_action('create_date', action='add')

    @staticmethod
    def default_period():
        Period = Pool().get('account.period')
        return Period.find(Transaction().context.get('company'),
            exception=False)

    @staticmethod
    def default_state():
        return 'draft'

    @classmethod
    def default_date(cls):
        pool = Pool()
        Period = pool.get('account.period')
        Date = pool.get('ir.date')
        period_id = cls.default_period()
        if period_id:
            period = Period(period_id)
            return period.start_date
        return Date.today()

    def on_change_with_date(self):
        Line = Pool().get('account.move.line')
        date = self.date
        lines = Line.search([
                ('journal', '=', self.journal),
                ('period', '=', self.period),
                ], order=[('id', 'DESC')], limit=1)
        if lines:
            date = lines[0].date
        elif self.period:
            date = self.period.start_date
        return date

    @classmethod
    def _get_origin(cls):
        'Return list of Model names for origin Reference'
        return []

    @classmethod
    def get_origin(cls):
        Model = Pool().get('ir.model')
        models = cls._get_origin()
        models = Model.search([
                ('model', 'in', models),
                ])
        return [('', '')] + [(m.model, m.name) for m in models]

    @classmethod
    def validate(cls, moves):
        super(Move, cls).validate(moves)
        for move in moves:
            move.check_centralisation()
            move.check_company()
            move.check_date()

    def check_centralisation(self):
        if self.journal.centralised:
            moves = self.search([
                    ('period', '=', self.period.id),
                    ('journal', '=', self.journal.id),
                    ('state', '!=', 'posted'),
                    ], limit=2)
            if len(moves) > 1:
                self.raise_user_error('period_centralized_journal', {
                        'move': self.rec_name,
                        'journal': self.journal.rec_name,
                        })

    def check_company(self):
        company_id = -1
        for line in self.lines:
            if company_id < 0:
                company_id = line.account.company.id
            if line.account.company.id != company_id:
                self.raise_user_error('company_in_move', (self.rec_name,))

    def check_date(self):
        if (self.date < self.period.start_date
                or self.date > self.period.end_date):
            self.raise_user_error('date_outside_period', (self.rec_name,))

    @classmethod
    def check_modify(cls, moves):
        'Check posted moves for modifications.'
        for move in moves:
            if move.state == 'posted':
                cls.raise_user_error('modify_posted_move', (move.rec_name,))

    @classmethod
    def search_rec_name(cls, name, clause):
        moves = cls.search(['OR',
                ('post_number',) + tuple(clause[1:]),
                (cls._rec_name,) + tuple(clause[1:]),
                ])
        return [('id', 'in', [m.id for m in moves])]

    @classmethod
    def write(cls, moves, vals):
        keys = vals.keys()
        for key in cls._check_modify_exclude:
            if key in keys:
                keys.remove(key)
        if len(keys):
            cls.check_modify(moves)
        super(Move, cls).write(moves, vals)
        cls.validate_move(moves)

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        Sequence = pool.get('ir.sequence')
        Journal = pool.get('account.journal')

        vlist = [x.copy() for x in vlist]
        for vals in vlist:
            if not vals.get('number'):
                journal_id = (vals.get('journal')
                        or Transaction().context.get('journal'))
                if journal_id:
                    journal = Journal(journal_id)
                    vals['number'] = Sequence.get_id(journal.sequence.id)

        moves = super(Move, cls).create(vlist)
        for move in moves:
            if move.journal.centralised:
                line, = MoveLine.create([{
                            'account': move.journal.credit_account.id,
                            'move': move.id,
                            }])
                cls.write([move], {
                        'centralised_line': line.id,
                        })
        cls.validate_move(moves)
        return moves

    @classmethod
    def delete(cls, moves):
        MoveLine = Pool().get('account.move.line')
        cls.check_modify(moves)
        MoveLine.delete([l for m in moves for l in m.lines])
        super(Move, cls).delete(moves)

    @classmethod
    def copy(cls, moves, default=None):
        Line = Pool().get('account.move.line')

        if default is None:
            default = {}
        default = default.copy()
        default['number'] = None
        default['post_number'] = None
        default['state'] = cls.default_state()
        default['post_date'] = None
        default['lines'] = None

        new_moves = []
        for move in moves:
            new_move, = super(Move, cls).copy([move], default=default)
            Line.copy(move.lines, default={
                    'move': new_move.id,
                    })
            new_moves.append(new_move)
        return new_moves

    @classmethod
    def validate_move(cls, moves):
        '''
        Validate balanced move and centralise it if in centralised journal
        '''
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        User = pool.get('res.user')

        cursor = Transaction().cursor

        if (Transaction().user == 0
                and Transaction().context.get('user')):
            user = Transaction().context.get('user')
        else:
            user = Transaction().user
        company = User(user).company
        amounts = {}
        move2draft_lines = {}
        for i in range(0, len(moves), cursor.IN_MAX):
            sub_moves = moves[i:i + cursor.IN_MAX]
            sub_move_ids = [m.id for m in sub_moves]
            red_sql, red_ids = reduce_ids('move', sub_move_ids)

            cursor.execute('SELECT move, SUM(debit - credit) '
                'FROM "' + MoveLine._table + '" '
                'WHERE ' + red_sql + ' '
                'GROUP BY move', red_ids)
            amounts.update(dict(cursor.fetchall()))

            cursor.execute('SELECT move, id '
                'FROM "' + MoveLine._table + '" '
                'WHERE ' + red_sql + ' AND state = %s '
                'ORDER BY move', red_ids + ['draft'])
            move2draft_lines.update(dict((k, (j[1] for j in g))
                    for k, g in groupby(cursor.fetchall(), itemgetter(0))))

        valid_moves = []
        draft_moves = []
        for move in moves:
            if move.id not in amounts:
                continue
            amount = amounts[move.id]
            # SQLite uses float for SUM
            if not isinstance(amount, Decimal):
                amount = Decimal(amount)
            draft_lines = MoveLine.browse(
                list(move2draft_lines.get(move.id, [])))
            if not company.currency.is_zero(amount):
                if not move.journal.centralised:
                    draft_moves.append(move.id)
                else:
                    if not move.centralised_line:
                        centralised_amount = - amount
                    else:
                        centralised_amount = move.centralised_line.debit \
                            - move.centralised_line.credit \
                            - amount
                    if centralised_amount >= Decimal('0.0'):
                        debit = centralised_amount
                        credit = Decimal('0.0')
                        account_id = move.journal.debit_account.id
                    else:
                        debit = Decimal('0.0')
                        credit = - centralised_amount
                        account_id = move.journal.credit_account.id
                    if not move.centralised_line:
                        centralised_line, = MoveLine.create([{
                                    'debit': debit,
                                    'credit': credit,
                                    'account': account_id,
                                    'move': move.id,
                                    }])
                        cls.write([move], {
                            'centralised_line': centralised_line.id,
                            })
                    else:
                        MoveLine.write([move.centralised_line], {
                                'debit': debit,
                                'credit': credit,
                                'account': account_id,
                                })
                continue
            if not draft_lines:
                continue
            valid_moves.append(move.id)
        for move_ids, state in (
                (valid_moves, 'valid'),
                (draft_moves, 'draft'),
                ):
            if move_ids:
                for i in range(0, len(move_ids), cursor.IN_MAX):
                    sub_ids = move_ids[i:i + cursor.IN_MAX]
                    red_sql, red_ids = reduce_ids('move', sub_ids)
                    # Use SQL to prevent double validate loop
                    cursor.execute('UPDATE "' + MoveLine._table + '" '
                        'SET state = %s '
                        'WHERE ' + red_sql, [state] + red_ids)

    @classmethod
    @ModelView.button
    def post(cls, moves):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Date = pool.get('ir.date')

        for move in moves:
            amount = Decimal('0.0')
            if not move.lines:
                cls.raise_user_error('post_empty_move', (move.rec_name,))
            company = None
            for line in move.lines:
                amount += line.debit - line.credit
                if not company:
                    company = line.account.company
            if not company.currency.is_zero(amount):
                cls.raise_user_error('post_unbalanced_move', (move.rec_name,))
        for move in moves:
            values = {
                'state': 'posted',
                }
            if not move.post_number:
                values['post_date'] = Date.today()
                values['post_number'] = Sequence.get_id(
                    move.period.post_move_sequence_used.id)
            cls.write([move], values)

    @classmethod
    @ModelView.button
    def draft(cls, moves):
        for move in moves:
            if not move.journal.update_posted:
                cls.raise_user_error('draft_posted_move_journal', {
                        'move': move.rec_name,
                        'journal': move.journal.rec_name,
                        })
            if move.period.state == 'close':
                cls.raise_user_error('draft_closed_period', {
                        'move': move.rec_name,
                        'period': move.period.rec_name,
                        })
        cls.write(moves, {
            'state': 'draft',
            })


class Reconciliation(ModelSQL, ModelView):
    'Account Move Reconciliation Lines'
    __name__ = 'account.move.reconciliation'
    name = fields.Char('Name', size=None, required=True)
    lines = fields.One2Many('account.move.line', 'reconciliation',
            'Lines')

    @classmethod
    def __setup__(cls):
        super(Reconciliation, cls).__setup__()
        cls._error_messages.update({
                'modify': 'You can not modify a reconciliation.',
                'reconciliation_line_not_valid': ('You can not reconcile line '
                    '"%s" because it is not in valid state.'),
                'reconciliation_different_accounts': ('You can not reconcile '
                    'line "%(line)s" because it\'s account "%(account1)s" is '
                    'different from "%(account2)s".'),
                'reconciliation_account_no_reconcile': ('You can not reconcile '
                    'line "%(line)s" because it\'s account "%(account)s" is '
                    'configured as not reconcilable.'),
                'reconciliation_different_parties': ('You can not reconcile '
                    'line "%(line)s" because it\'s party "%(party1)s" is '
                    'different from %(party2)s".'),
                'reconciliation_unbalanced': ('You can not create a '
                    'reconciliation where debit "%(debit)s" and credit '
                    '"%(credit)s" differ.'),
                })

    @classmethod
    def create(cls, vlist):
        Sequence = Pool().get('ir.sequence')

        vlist = [x.copy() for x in vlist]
        for vals in vlist:
            if 'name' not in vals:
                vals['name'] = Sequence.get('account.move.reconciliation')

        return super(Reconciliation, cls).create(vlist)

    @classmethod
    def write(cls, moves, vals):
        cls.raise_user_error('modify')

    @classmethod
    def validate(cls, reconciliations):
        super(Reconciliation, cls).validate(reconciliations)
        cls.check_lines(reconciliations)

    @classmethod
    def check_lines(cls, reconciliations):
        Lang = Pool().get('ir.lang')
        for reconciliation in reconciliations:
            debit = Decimal('0.0')
            credit = Decimal('0.0')
            account = None
            party = None
            for line in reconciliation.lines:
                if line.state != 'valid':
                    cls.raise_user_error('reconciliation_line_not_valid',
                        (line.rec_name,))
                debit += line.debit
                credit += line.credit
                if not account:
                    account = line.account
                elif account.id != line.account.id:
                    cls.raise_user_error('reconciliation_different_accounts', {
                            'line': line.rec_name,
                            'account1': line.account.rec_name,
                            'account2': account.rec_name,
                            })
                if not account.reconcile:
                    cls.raise_user_error('reconciliation_account_no_reconcile',
                        {
                            'line': line.rec_name,
                            'account': line.account.rec_name,
                            })
                if not party:
                    party = line.party
                elif line.party and party.id != line.party.id:
                    cls.raise_user_error('reconciliation_different_parties', {
                            'line': line.rec_name,
                            'party1': line.party.rec_name,
                            'party2': party.rec_name,
                            })
            if not account.company.currency.is_zero(debit - credit):
                language = Transaction().language
                languages = Lang.search([('code', '=', language)])
                if not languages:
                    languages = Lang.search([('code', '=', 'en_US')])
                language = languages[0]
                debit = Lang.currency(
                    language, debit, account.company.currency)
                credit = Lang.currency(
                    language, credit, account.company.currency)
                cls.raise_user_error('reconciliation_unbalanced', {
                        'debit': debit,
                        'credit': credit,
                        })


class Line(ModelSQL, ModelView):
    'Account Move Line'
    __name__ = 'account.move.line'
    debit = fields.Numeric('Debit', digits=(16, Eval('currency_digits', 2)),
        required=True,
        on_change=['account', 'debit', 'credit', 'tax_lines', 'journal',
            'move'],
        depends=['currency_digits', 'credit', 'tax_lines', 'journal'])
    credit = fields.Numeric('Credit', digits=(16, Eval('currency_digits', 2)),
        required=True,
        on_change=['account', 'debit', 'credit', 'tax_lines', 'journal',
            'move'],
        depends=['currency_digits', 'debit', 'tax_lines', 'journal'])
    account = fields.Many2One('account.account', 'Account', required=True,
            domain=[('kind', '!=', 'view')],
            select=True,
            on_change=['account', 'debit', 'credit', 'tax_lines',
                'journal', 'move'])
    move = fields.Many2One('account.move', 'Move', select=True, required=True,
        states={
            'required': False,
            'readonly': Eval('state') == 'valid',
            },
        depends=['state'])
    journal = fields.Function(fields.Many2One('account.journal', 'Journal'),
            'get_move_field', setter='set_move_field',
            searcher='search_move_field')
    period = fields.Function(fields.Many2One('account.period', 'Period'),
            'get_move_field', setter='set_move_field',
            searcher='search_move_field')
    date = fields.Function(fields.Date('Effective Date', required=True),
            'get_move_field', setter='set_move_field',
            searcher='search_move_field')
    origin = fields.Function(fields.Reference('Origin',
            selection='get_origin'),
        'get_move_field', searcher='search_move_field')
    description = fields.Char('Description')
    amount_second_currency = fields.Numeric('Amount Second Currency',
            digits=(16, Eval('second_currency_digits', 2)),
            help='The amount expressed in a second currency',
            depends=['second_currency_digits'])
    second_currency = fields.Many2One('currency.currency', 'Second Currency',
            help='The second currency')
    party = fields.Many2One('party.party', 'Party',
            on_change=['move', 'party', 'account', 'debit', 'credit',
                'journal'], select=True, depends=['debit', 'credit', 'account',
                    'journal'])
    maturity_date = fields.Date('Maturity Date',
        help='This field is used for payable and receivable lines. \n'
        'You can put the limit date for the payment.')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('valid', 'Valid'),
        ], 'State', readonly=True, required=True, select=True)
    reconciliation = fields.Many2One('account.move.reconciliation',
            'Reconciliation', readonly=True, ondelete='SET NULL', select=True)
    tax_lines = fields.One2Many('account.tax.line', 'move_line', 'Tax Lines')
    move_state = fields.Function(fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ], 'Move State'), 'get_move_field', searcher='search_move_field')
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
            'get_currency_digits')
    second_currency_digits = fields.Function(fields.Integer(
        'Second Currency Digits'), 'get_currency_digits')

    @classmethod
    def __setup__(cls):
        super(Line, cls).__setup__()
        cls._sql_constraints += [
            ('credit_debit',
                'CHECK(credit * debit = 0.0)',
                'Wrong credit/debit values.'),
            ]
        cls.__rpc__.update({
                'on_write': RPC(instantiate=0),
                'get_origin': RPC(),
                })
        cls._order[0] = ('id', 'DESC')
        cls._error_messages.update({
                'add_modify_closed_journal_period': ('You can not '
                    'add/modify lines in closed journal period "%s".'),
                'modify_posted_move': ('You can not modify lines of move "%s" '
                    'because it is already posted.'),
                'modify_reconciled': ('You can not modify line "%s" because it '
                    'is reconciled.'),
                'no_journal': ('Move line cannot be created because there is '
                    'no journal defined.'),
                'move_view_account': ('You can not create a move line with '
                    'account "%s" because it is a view account.'),
                'move_inactive_account': ('You can not create a move line with '
                    'account "%s" because it is inactive.'),
                'already_reconciled': 'Line "%s" (%d) already reconciled.',
                })

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor
        table = TableHandler(cursor, cls, module_name)

        # Migration from 2.4: reference renamed into description
        if table.column_exist('reference'):
            table.column_rename('reference', 'description')

        super(Line, cls).__register__(module_name)

        table = TableHandler(cursor, cls, module_name)
        # Index for General Ledger
        table.index_action(['move', 'account'], 'add')

        # Migration from 1.2
        table.not_null_action('blocked', action='remove')

        # Migration from 2.4: remove name
        table.not_null_action('name', action='remove')

    @classmethod
    def default_date(cls):
        '''
        Return the date of the last line for journal, period
        or the starting date of the period
        or today
        '''
        pool = Pool()
        Period = pool.get('account.period')
        Date = pool.get('ir.date')

        date = Date.today()
        lines = cls.search([
                ('journal', '=', Transaction().context.get('journal')),
                ('period', '=', Transaction().context.get('period')),
                ], order=[('id', 'DESC')], limit=1)
        if lines:
            date = lines[0].date
        elif Transaction().context.get('period'):
            period = Period(Transaction().context['period'])
            date = period.start_date
        if Transaction().context.get('date'):
            date = Transaction().context['date']
        return date

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_currency_digits():
        return 2

    @staticmethod
    def default_debit():
        return Decimal(0)

    @staticmethod
    def default_credit():
        return Decimal(0)

    @classmethod
    def default_get(cls, fields, with_rec_name=True):
        pool = Pool()
        Move = pool.get('account.move')
        Tax = pool.get('account.tax')
        Account = pool.get('account.account')
        TaxCode = pool.get('account.tax.code')
        values = super(Line, cls).default_get(fields,
                with_rec_name=with_rec_name)

        if 'move' not in fields:
            #Not manual entry
            if 'date' in values:
                values = values.copy()
                del values['date']
            return values

        if (Transaction().context.get('journal')
                and Transaction().context.get('period')):
            lines = cls.search([
                ('move.journal', '=', Transaction().context['journal']),
                ('move.period', '=', Transaction().context['period']),
                ('create_uid', '=', Transaction().user),
                ('state', '=', 'draft'),
                ], order=[('id', 'DESC')], limit=1)
            if not lines:
                return values
            move = lines[0].move
            values['move'] = move.id
            values['move.rec_name'] = move.rec_name

        if 'move' not in values:
            return values

        move = Move(values['move'])
        total = Decimal('0.0')
        taxes = {}
        no_code_taxes = []
        for line in move.lines:
            total += line.debit - line.credit
            if line.party and 'party' in fields and 'party' not in values:
                values['party'] = line.party.id
                values['party.rec_name'] = line.party.rec_name
            if move.journal.type in ('expense', 'revenue'):
                line_code_taxes = [x.code.id for x in line.tax_lines]
                for tax in line.account.taxes:
                    if move.journal.type == 'revenue':
                        if line.debit:
                            base_id = tax.credit_note_base_code.id
                            code_id = tax.credit_note_tax_code.id
                            account_id = tax.credit_note_account.id
                        else:
                            base_id = tax.invoice_base_code.id
                            code_id = tax.invoice_tax_code.id
                            account_id = tax.invoice_account.id
                    else:
                        if line.debit:
                            base_id = tax.invoice_base_code.id
                            code_id = tax.invoice_tax_code.id
                            account_id = tax.invoice_account.id
                        else:
                            base_id = tax.credit_note_base_code.id
                            code_id = tax.credit_note_tax_code.id
                            account_id = tax.credit_note_account.id
                    if base_id in line_code_taxes or not base_id:
                        taxes.setdefault((account_id, code_id, tax.id), None)
                for tax_line in line.tax_lines:
                    taxes[
                        (line.account.id, tax_line.code.id, tax_line.tax.id)
                        ] = True
                if not line.tax_lines:
                    no_code_taxes.append(line.account.id)
        for no_code_account_id in no_code_taxes:
            for (account_id, code_id, tax_id), test in \
                    taxes.iteritems():
                if (not test
                        and not code_id
                        and no_code_account_id == account_id):
                    taxes[(account_id, code_id, tax_id)] = True

        if 'account' in fields:
            account = None
            if total >= Decimal('0.0'):
                if move.journal.credit_account:
                    account = move.journal.credit_account
            else:
                if move.journal.debit_account:
                    account = move.journal.debit_account
            if account:
                    values['account'] = account.id
                    values['account.rec_name'] = account.rec_name
            else:
                values['account'] = None

        if ('debit' in fields) or ('credit' in fields):
            values['debit'] = total < 0 and - total or Decimal(0)
            values['credit'] = total > 0 and total or Decimal(0)

        if move.journal.type in ('expense', 'revenue'):
            for account_id, code_id, tax_id in taxes:
                if taxes[(account_id, code_id, tax_id)]:
                    continue
                for line in move.lines:
                    if move.journal.type == 'revenue':
                        if line.debit:
                            key = 'credit_note'
                        else:
                            key = 'invoice'
                    else:
                        if line.debit:
                            key = 'invoice'
                        else:
                            key = 'credit_note'
                    line_amount = Decimal('0.0')
                    tax_amount = Decimal('0.0')
                    for tax_line in Tax.compute(line.account.taxes,
                            line.debit or line.credit, 1):
                        if ((tax_line['tax'][key + '_account'].id
                                or line.account.id) == account_id
                                and (tax_line['tax'][key + '_tax_code'].id
                                    == code_id)
                                and tax_line['tax'].id == tax_id):
                            if line.debit:
                                line_amount += tax_line['amount']
                            else:
                                line_amount -= tax_line['amount']
                            tax_amount += tax_line['amount'] * \
                                tax_line['tax'][key + '_tax_sign']
                    line_amount = line.account.company.currency.round(
                        line_amount)
                    tax_amount = line.account.company.currency.round(
                        tax_amount)
                    if ('debit' in fields):
                        values['debit'] = line_amount > Decimal('0.0') \
                            and line_amount or Decimal('0.0')
                    if ('credit' in fields):
                        values['credit'] = line_amount < Decimal('0.0') \
                            and - line_amount or Decimal('0.0')
                    if 'account' in fields:
                        values['account'] = account_id
                        values['account.rec_name'] = Account(
                            account_id).rec_name
                    if 'tax_lines' in fields and code_id:
                        values['tax_lines'] = [
                            {
                                'amount': tax_amount,
                                'currency_digits': line.currency_digits,
                                'code': code_id,
                                'code.rec_name': TaxCode(code_id).rec_name,
                                'tax': tax_id,
                                'tax.rec_name': Tax(tax_id).rec_name,
                            },
                        ]
        return values

    @classmethod
    def get_currency_digits(cls, lines, names):
        digits = {}
        for line in lines:
            for name in names:
                digits.setdefault(name, {})
                digits[name].setdefault(line.id, 2)
                if name == 'currency_digits':
                    digits[name][line.id] = line.account.currency_digits
                elif name == 'second_currency_digits':
                    second_currency = line.account.second_currency
                    if second_currency:
                        digits[name][line.id] = second_currency.digits
        return digits

    @classmethod
    def get_origin(cls):
        Move = Pool().get('account.move')
        return Move.get_origin()

    def on_change_debit(self):
        changes = {}
        Journal = Pool().get('account.journal')
        if self.journal or Transaction().context.get('journal'):
            journal = self.journal or Journal(Transaction().context['journal'])
            if journal.type in ('expense', 'revenue'):
                changes['tax_lines'] = self._compute_tax_lines(journal.type)
                if not changes['tax_lines']:
                    del changes['tax_lines']
        if self.debit:
            changes['credit'] = Decimal('0.0')
        return changes

    def on_change_credit(self):
        changes = {}
        Journal = Pool().get('account.journal')
        if self.journal or Transaction().context.get('journal'):
            journal = self.journal or Journal(Transaction().context['journal'])
            if journal.type in ('expense', 'revenue'):
                changes['tax_lines'] = self._compute_tax_lines(journal.type)
                if not changes['tax_lines']:
                    del changes['tax_lines']
        if self.credit:
            changes['debit'] = Decimal('0.0')
        return changes

    def on_change_account(self):
        Journal = Pool().get('account.journal')

        changes = {}
        if Transaction().context.get('journal'):
            journal = Journal(Transaction().context['journal'])
            if journal.type in ('expense', 'revenue'):
                changes['tax_lines'] = self._compute_tax_lines(journal.type)
                if not changes['tax_lines']:
                    del changes['tax_lines']

        if self.account:
            changes['currency_digits'] = self.account.currency_digits
            if self.account.second_currency:
                changes['second_currency_digits'] = \
                    self.account.second_currency.digits
        return changes

    def _compute_tax_lines(self, journal_type):
        res = {}
        pool = Pool()
        TaxCode = pool.get('account.tax.code')
        Tax = pool.get('account.tax')
        TaxLine = pool.get('account.tax.line')

        if self.move:
            #Only for first line
            return res
        if self.tax_lines:
            res['remove'] = [x['id'] for x in self.tax_lines]
        if self.account:
            debit = self.debit or Decimal('0.0')
            credit = self.credit or Decimal('0.0')
            for tax in self.account.taxes:
                if journal_type == 'revenue':
                    if debit:
                        key = 'credit_note'
                    else:
                        key = 'invoice'
                else:
                    if debit:
                        key = 'invoice'
                    else:
                        key = 'credit_note'
                base_amounts = {}
                for tax_line in Tax.compute(self.account.taxes,
                        debit or credit, 1):
                    code_id = tax_line['tax'][key + '_base_code'].id
                    if not code_id:
                        continue
                    tax_id = tax_line['tax'].id
                    base_amounts.setdefault((code_id, tax_id), Decimal('0.0'))
                    base_amounts[code_id, tax_id] += tax_line['base'] * \
                        tax_line['tax'][key + '_tax_sign']
                for code_id, tax_id in base_amounts:
                    if not base_amounts[code_id, tax_id]:
                        continue
                    value = TaxLine.default_get(TaxLine._fields.keys())
                    value.update({
                            'amount': base_amounts[code_id, tax_id],
                            'currency_digits': self.account.currency_digits,
                            'code': code_id,
                            'code.rec_name': TaxCode(code_id).rec_name,
                            'tax': tax_id,
                            'tax.rec_name': Tax(tax_id).rec_name,
                            })
                    res.setdefault('add', []).append(value)
        return res

    def on_change_party(self):
        Journal = Pool().get('account.journal')
        cursor = Transaction().cursor
        res = {}
        if (not self.party) or self.account:
            return res

        if not self.party.account_receivable \
                or not self.party.account_payable:
            return res

        if self.party and (not self.debit) and (not self.credit):
            type_name = FIELDS[self.__class__.debit._type].sql_type(
                self.__class__.debit)[0]
            query = ('SELECT '
                'CAST(COALESCE(SUM('
                        '(COALESCE(debit, 0) - COALESCE(credit, 0))'
                    '), 0) AS ' + type_name + ') '
                'FROM account_move_line '
                'WHERE reconciliation IS NULL '
                    'AND party = %s '
                    'AND account = %s')
            cursor.execute(query,
                (self.party.id, self.party.account_receivable.id))
            amount = cursor.fetchone()[0]
            # SQLite uses float for SUM
            if not isinstance(amount, Decimal):
                amount = Decimal(str(amount))
            if not self.party.account_receivable.currency.is_zero(amount):
                if amount > Decimal('0.0'):
                    res['credit'] = \
                        self.party.account_receivable.currency.round(amount)
                    res['debit'] = Decimal('0.0')
                else:
                    res['credit'] = Decimal('0.0')
                    res['debit'] = \
                        - self.party.account_receivable.currency.round(amount)
                res['account'] = self.party.account_receivable.id
                res['account.rec_name'] = \
                    self.party.account_receivable.rec_name
            else:
                cursor.execute(query,
                    (self.party.id, self.party.account_payable.id))
                amount = cursor.fetchone()[0]
                if not self.party.account_payable.currency.is_zero(amount):
                    if amount > Decimal('0.0'):
                        res['credit'] = \
                            self.party.account_payable.currency.round(amount)
                        res['debit'] = Decimal('0.0')
                    else:
                        res['credit'] = Decimal('0.0')
                        res['debit'] = \
                            - self.party.account_payable.currency.round(amount)
                    res['account'] = self.party.account_payable.id
                    res['account.rec_name'] = \
                        self.party.account_payable.rec_name

        if self.party and self.debit:
            if self.debit > Decimal('0.0'):
                if 'account' not in res:
                    res['account'] = self.party.account_receivable.id
                    res['account.rec_name'] = \
                        self.party.account_receivable.rec_name
            else:
                if 'account' not in res:
                    res['account'] = self.party.account_payable.id
                    res['account.rec_name'] = \
                        self.party.account_payable.rec_name

        if self.party and self.credit:
            if self.credit > Decimal('0.0'):
                if 'account' not in res:
                    res['account'] = self.party.account_payable.id
                    res['account.rec_name'] = \
                        self.party.account_payable.rec_name
            else:
                if 'account' not in res:
                    res['account'] = self.party.account_receivable.id
                    res['account.rec_name'] = \
                        self.party.account_receivable.rec_name

        journal = None
        if self.journal:
            journal = self.journal
        elif Transaction().context.get('journal'):
            journal = Journal(Transaction().context.get('journal'))
        if journal and self.party:
            if journal.type == 'revenue':
                if 'account' not in res:
                    res['account'] = self.party.account_receivable.id
                    res['account.rec_name'] = \
                        self.party.account_receivable.rec_name
            elif journal.type == 'expense':
                if 'account' not in res:
                    res['account'] = self.party.account_payable.id
                    res['account.rec_name'] = \
                        self.party.account_payable.rec_name
        return res

    def get_move_field(self, name):
        if name == 'move_state':
            name = 'state'
        if name in ('date', 'state'):
            return getattr(self.move, name)
        elif name == 'origin':
            origin = getattr(self.move, name)
            if origin:
                return str(origin)
            return None
        else:
            return getattr(self.move, name).id

    @classmethod
    def set_move_field(cls, lines, name, value):
        if name == 'move_state':
            name = 'state'
        if not value:
            return
        Move = Pool().get('account.move')
        Move.write([line.move for line in lines], {
                name: value,
                })

    @classmethod
    def search_move_field(cls, name, clause):
        if name == 'move_state':
            name = 'state'
        return [('move.' + name,) + tuple(clause[1:])]

    @classmethod
    def query_get(cls, obj='l'):
        '''
        Return SQL clause and fiscal years for account move line
        depending of the context.
        obj is the SQL alias of account_move_line in the query
        '''
        FiscalYear = Pool().get('account.fiscalyear')

        if Transaction().context.get('date'):
            time.strptime(str(Transaction().context['date']), '%Y-%m-%d')
            fiscalyears = FiscalYear.search([
                    ('start_date', '<=', Transaction().context['date']),
                    ('end_date', '>=', Transaction().context['date']),
                    ], limit=1)

            fiscalyear_id = fiscalyears and fiscalyears[0].id or 0

            if Transaction().context.get('posted'):
                return (obj + '.state != \'draft\' '
                        'AND ' + obj + '.move IN ('
                            'SELECT m.id FROM account_move AS m, '
                                'account_period AS p '
                                'WHERE m.period = p.id '
                                    'AND p.fiscalyear = ' +
                                        str(fiscalyear_id) + ' '
                                    'AND m.date <= date(\'' +
                                        str(Transaction().context['date']) +
                                        '\') '
                                    'AND m.state = \'posted\' '
                            ')', [f.id for f in fiscalyears])
            else:
                return (obj + '.state != \'draft\' '
                        'AND ' + obj + '.move IN ('
                            'SELECT m.id FROM account_move AS m, '
                                'account_period AS p '
                                'WHERE m.period = p.id '
                                    'AND p.fiscalyear = ' +
                                        str(fiscalyear_id) + ' '
                                    'AND m.date <= date(\'' +
                                        str(Transaction().context['date']) +
                                        '\')'
                            ')', [f.id for f in fiscalyears])

        if Transaction().context.get('periods'):
            if Transaction().context.get('fiscalyear'):
                fiscalyear_ids = [int(Transaction().context['fiscalyear'])]
            else:
                fiscalyear_ids = []
            ids = ','.join(
                    str(int(x)) for x in Transaction().context['periods'])
            if Transaction().context.get('posted'):
                return (obj + '.state != \'draft\' '
                    'AND ' + obj + '.move IN ('
                        'SELECT id FROM account_move '
                        'WHERE period IN (' + ids + ') '
                            'AND state = \'posted\' '
                        ')', fiscalyear_ids)
            else:
                return (obj + '.state != \'draft\' '
                    'AND ' + obj + '.move IN ('
                        'SELECT id FROM account_move '
                        'WHERE period IN (' + ids + ')'
                        ')', fiscalyear_ids)
        else:
            if not Transaction().context.get('fiscalyear'):
                fiscalyears = FiscalYear.search([
                    ('state', '=', 'open'),
                    ])
                fiscalyear_ids = [f.id for f in fiscalyears]
                fiscalyear_clause = (','.join(
                        str(f.id) for f in fiscalyears)) or '0'
            else:
                fiscalyear_ids = [int(Transaction().context.get('fiscalyear'))]
                fiscalyear_clause = '%s' % int(
                        Transaction().context.get('fiscalyear'))

            if Transaction().context.get('posted'):
                return (obj + '.state != \'draft\' '
                    'AND ' + obj + '.move IN ('
                        'SELECT id FROM account_move '
                        'WHERE period IN ('
                            'SELECT id FROM account_period '
                            'WHERE fiscalyear IN (' + fiscalyear_clause + ')'
                            ') '
                            'AND state = \'posted\' '
                        ')', fiscalyear_ids)
            else:
                return (obj + '.state != \'draft\' '
                    'AND ' + obj + '.move IN ('
                        'SELECT id FROM account_move '
                        'WHERE period IN ('
                            'SELECT id FROM account_period '
                            'WHERE fiscalyear IN (' + fiscalyear_clause + ')'
                            ')'
                        ')', fiscalyear_ids)

    @classmethod
    def on_write(cls, lines):
        return list(set(l.id for line in lines for l in line.move.lines))

    @classmethod
    def validate(cls, lines):
        super(Line, cls).validate(lines)
        for line in lines:
            line.check_account()

    def check_account(self):
        if self.account.kind in ('view',):
            self.raise_user_error('move_view_account', (
                    self.account.rec_name,))
        if not self.account.active:
            self.raise_user_error('move_inactive_account', (
                    self.account.rec_name,))

    @classmethod
    def check_journal_period_modify(cls, period, journal):
        '''
        Check if the lines can be modified or created for the journal - period
        and if there is no journal - period, create it
        '''
        JournalPeriod = Pool().get('account.journal.period')
        journal_periods = JournalPeriod.search([
                ('journal', '=', journal.id),
                ('period', '=', period.id),
                ], limit=1)
        if journal_periods:
            journal_period, = journal_periods
            if journal_period.state == 'close':
                cls.raise_user_error('add_modify_closed_journal_period', (
                        journal_period.rec_name,))
        else:
            JournalPeriod.create([{
                        'name': journal.name + ' - ' + period.name,
                        'journal': journal.id,
                        'period': period.id,
                        }])

    @classmethod
    def check_modify(cls, lines):
        '''
        Check if the lines can be modified
        '''
        journal_period_done = []
        for line in lines:
            if line.move.state == 'posted':
                cls.raise_user_error('modify_posted_move', (
                        line.move.rec_name,))
            if line.reconciliation:
                cls.raise_user_error('modify_reconciled', (
                        line.rec_name,))
            journal_period = (line.journal.id, line.period.id)
            if journal_period not in journal_period_done:
                cls.check_journal_period_modify(line.period,
                        line.journal)
                journal_period_done.append(journal_period)

    @classmethod
    def delete(cls, lines):
        Move = Pool().get('account.move')
        cls.check_modify(lines)
        moves = [x.move for x in lines]
        super(Line, cls).delete(lines)
        Move.validate_move(moves)

    @classmethod
    def write(cls, lines, vals):
        Move = Pool().get('account.move')

        if len(vals) > 1 or 'reconciliation' not in vals:
            cls.check_modify(lines)
        moves = [x.move for x in lines]
        super(Line, cls).write(lines, vals)

        Transaction().timestamp = {}

        Move.validate_move(list(set(l.move for l in lines) | set(moves)))

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Journal = pool.get('account.journal')
        Move = pool.get('account.move')
        vlist = [x.copy() for x in vlist]
        for vals in vlist:
            if not vals.get('move'):
                journal_id = (vals.get('journal')
                        or Transaction().context.get('journal'))
                if not journal_id:
                    cls.raise_user_error('no_journal')
                journal = Journal(journal_id)
                if journal.centralised:
                    moves = Move.search([
                            ('period', '=', vals.get('period')
                                or Transaction().context.get('period')),
                            ('journal', '=', journal_id),
                            ('state', '!=', 'posted'),
                            ], limit=1)
                    if moves:
                        vals['move'] = moves[0].id
                if not vals.get('move'):
                    vals['move'] = Move.create([{
                                'period': (vals.get('period')
                                    or Transaction().context.get('period')),
                                'journal': journal_id,
                                'date': vals.get('date'),
                                }])[0].id
            else:
                # prevent computation of default date
                vals.setdefault('date', None)
        lines = super(Line, cls).create(vlist)
        period_and_journals = set((line.period, line.journal)
            for line in lines)
        for period, journal in period_and_journals:
            cls.check_journal_period_modify(period, journal)
        Move.validate_move(list(set(line.move for line in lines)))
        return lines

    @classmethod
    def copy(cls, lines, default=None):
        if default is None:
            default = {}
        if 'move' not in default:
            default['move'] = None
        if 'reconciliation' not in default:
            default['reconciliation'] = None
        return super(Line, cls).copy(lines, default=default)

    @classmethod
    def view_header_get(cls, value, view_type='form'):
        JournalPeriod = Pool().get('account.journal.period')
        if (not Transaction().context.get('journal')
                or not Transaction().context.get('period')):
            return value
        journal_periods = JournalPeriod.search([
                ('journal', '=', Transaction().context['journal']),
                ('period', '=', Transaction().context['period']),
                ], limit=1)
        if not journal_periods:
            return value
        journal_period, = journal_periods
        return value + ': ' + journal_period.rec_name

    @classmethod
    def fields_view_get(cls, view_id=None, view_type='form'):
        Journal = Pool().get('account.journal')
        result = super(Line, cls).fields_view_get(view_id=view_id,
            view_type=view_type)
        if view_type == 'tree' and 'journal' in Transaction().context:
            title = cls.view_header_get('', view_type=view_type)
            journal = Journal(Transaction().context['journal'])

            if not journal.view:
                return result

            xml = '<?xml version="1.0"?>\n' \
                '<tree string="%s" editable="top" on_write="on_write" ' \
                'colors="red:state==\'draft\'">\n' % title
            fields = set()
            for column in journal.view.columns:
                fields.add(column.field.name)
                attrs = []
                if column.field.name == 'debit':
                    attrs.append('sum="Debit"')
                elif column.field.name == 'credit':
                    attrs.append('sum="Credit"')
                if column.readonly:
                    attrs.append('readonly="1"')
                if column.required:
                    attrs.append('required="1"')
                else:
                    attrs.append('required="0"')
                xml += ('<field name="%s" %s/>\n'
                    % (column.field.name, ' '.join(attrs)))
                for depend in getattr(cls, column.field.name).depends:
                    fields.add(depend)
            fields.add('state')
            xml += '</tree>'
            result['arch'] = xml
            result['fields'] = cls.fields_get(fields_names=list(fields))
        return result

    @classmethod
    def reconcile(cls, lines, journal=None, date=None, account=None):
        pool = Pool()
        Move = pool.get('account.move')
        Reconciliation = pool.get('account.move.reconciliation')
        Period = pool.get('account.period')
        Date = pool.get('ir.date')

        for line in lines:
            if line.reconciliation:
                cls.raise_user_error('already_reconciled',
                        error_args=(line.move.number, line.id,))

        lines = lines[:]
        if journal and account:
            if not date:
                date = Date.today()
            reconcile_account = None
            amount = Decimal('0.0')
            for line in lines:
                amount += line.debit - line.credit
                if not reconcile_account:
                    reconcile_account = line.account
            amount = reconcile_account.currency.round(amount)
            period_id = Period.find(reconcile_account.company.id, date=date)
            move, = Move.create([{
                        'journal': journal.id,
                        'period': period_id,
                        'date': date,
                        'lines': [
                            ('create', [{
                                        'account': reconcile_account.id,
                                        'debit': (amount < Decimal('0.0')
                                            and - amount or Decimal('0.0')),
                                        'credit': (amount > Decimal('0.0')
                                            and amount or Decimal('0.0')),
                                        }, {
                                        'account': account.id,
                                        'debit': (amount > Decimal('0.0')
                                            and amount or Decimal('0.0')),
                                        'credit': (amount < Decimal('0.0')
                                            and - amount or Decimal('0.0')),
                                        }]),
                            ],
                        }])
            lines += cls.search([
                    ('move', '=', move.id),
                    ('account', '=', reconcile_account.id),
                    ('debit', '=', amount < Decimal('0.0') and - amount
                        or Decimal('0.0')),
                    ('credit', '=', amount > Decimal('0.0') and amount
                        or Decimal('0.0')),
                    ], limit=1)
        return Reconciliation.create([{
                    'lines': [('add', [x.id for x in lines])],
                    }])[0]


class Move2:
    __name__ = 'account.move'
    centralised_line = fields.Many2One('account.move.line', 'Centralised Line',
            readonly=True)


class OpenJournalAsk(ModelView):
    'Open Journal Ask'
    __name__ = 'account.move.open_journal.ask'
    journal = fields.Many2One('account.journal', 'Journal', required=True)
    period = fields.Many2One('account.period', 'Period', required=True,
        domain=[
            ('state', '!=', 'close'),
            ('fiscalyear.company.id', '=',
                Eval('context', {}).get('company', 0)),
            ])

    @staticmethod
    def default_period():
        Period = Pool().get('account.period')
        return Period.find(Transaction().context.get('company'),
                exception=False)


class OpenJournal(Wizard):
    'Open Journal'
    __name__ = 'account.move.open_journal'
    start = StateTransition()
    ask = StateView('account.move.open_journal.ask',
        'account.open_journal_ask_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Open', 'open_', 'tryton-ok', default=True),
            ])
    open_ = StateAction('account.act_move_line_form')

    def transition_start(self):
        if (Transaction().context.get('active_model', '')
                == 'account.journal.period'
                and Transaction().context.get('active_id')):
            return 'open_'
        return 'ask'

    def default_ask(self, fields):
        JournalPeriod = Pool().get('account.journal.period')
        if (Transaction().context.get('active_model', '') ==
                'account.journal.period'
                and Transaction().context.get('active_id')):
            journal_period = JournalPeriod(Transaction().context['active_id'])
            return {
                'journal': journal_period.journal.id,
                'period': journal_period.period.id,
                }
        return {}

    def do_open_(self, action):
        JournalPeriod = Pool().get('account.journal.period')

        if (Transaction().context.get('active_model', '') ==
                'account.journal.period'
                and Transaction().context.get('active_id')):
            journal_period = JournalPeriod(Transaction().context['active_id'])
            journal = journal_period.journal
            period = journal_period.period
        else:
            journal = self.ask.journal
            period = self.ask.period
        journal_periods = JournalPeriod.search([
                ('journal', '=', journal.id),
                ('period', '=', period.id),
                ], limit=1)
        if not journal_periods:
            journal_period, = JournalPeriod.create([{
                        'name': journal.name + ' - ' + period.name,
                        'journal': journal.id,
                        'period': period.id,
                        }])
        else:
            journal_period, = journal_periods

        action['name'] += ' - %s' % journal_period.rec_name
        action['pyson_domain'] = PYSONEncoder().encode([
            ('journal', '=', journal.id),
            ('period', '=', period.id),
            ])
        action['pyson_context'] = PYSONEncoder().encode({
            'journal': journal.id,
            'period': period.id,
            })
        return action, {}

    def transition_open_(self):
        return 'end'


class OpenAccount(Wizard):
    'Open Account'
    __name__ = 'account.move.open_account'
    start_state = 'open_'
    open_ = StateAction('account.act_move_line_form')

    def do_open_(self, action):
        FiscalYear = Pool().get('account.fiscalyear')

        if not Transaction().context.get('fiscalyear'):
            fiscalyears = FiscalYear.search([
                    ('state', '=', 'open'),
                    ])
        else:
            fiscalyears = [FiscalYear(Transaction().context['fiscalyear'])]

        periods = [p for f in fiscalyears for p in f.periods]

        action['pyson_domain'] = [
            ('period', 'in', [p.id for p in periods]),
            ('account', '=', Transaction().context['active_id']),
            ]
        if Transaction().context.get('posted'):
            action['pyson_domain'].append(('move.state', '=', 'posted'))
        if Transaction().context.get('date'):
            action['pyson_domain'].append(('move.date', '<=',
                    Transaction().context['date']))
        action['pyson_domain'] = PYSONEncoder().encode(action['pyson_domain'])
        action['pyson_context'] = PYSONEncoder().encode({
            'fiscalyear': Transaction().context.get('fiscalyear'),
        })
        return action, {}


class ReconcileLinesWriteOff(ModelView):
    'Reconcile Lines Write-Off'
    __name__ = 'account.move.reconcile_lines.writeoff'
    journal = fields.Many2One('account.journal', 'Journal', required=True)
    date = fields.Date('Date', required=True)
    account = fields.Many2One('account.account', 'Account', required=True,
            domain=[('kind', '!=', 'view')])

    @staticmethod
    def default_date():
        Date = Pool().get('ir.date')
        return Date.today()


class ReconcileLines(Wizard):
    'Reconcile Lines'
    __name__ = 'account.move.reconcile_lines'
    start = StateTransition()
    writeoff = StateView('account.move.reconcile_lines.writeoff',
        'account.reconcile_lines_writeoff_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Reconcile', 'reconcile', 'tryton-ok', default=True),
            ])
    reconcile = StateTransition()

    def transition_start(self):
        Line = Pool().get('account.move.line')

        company = None
        amount = Decimal('0.0')
        for line in Line.browse(Transaction().context['active_ids']):
            amount += line.debit - line.credit
            if not company:
                company = line.account.company
        if not company:
            return 'end'
        if company.currency.is_zero(amount):
            return 'reconcile'
        return 'writeoff'

    def transition_reconcile(self):
        Line = Pool().get('account.move.line')

        journal = getattr(self.writeoff, 'journal', None)
        date = getattr(self.writeoff, 'date', None)
        account = getattr(self.writeoff, 'account', None)
        Line.reconcile(Line.browse(Transaction().context['active_ids']),
            journal, date, account)
        return 'end'


class UnreconcileLinesStart(ModelView):
    'Unreconcile Lines'
    __name__ = 'account.move.unreconcile_lines.start'


class UnreconcileLines(Wizard):
    'Unreconcile Lines'
    __name__ = 'account.move.unreconcile_lines'
    start_state = 'unreconcile'
    unreconcile = StateTransition()

    def transition_unreconcile(self):
        pool = Pool()
        Line = pool.get('account.move.line')
        Reconciliation = pool.get('account.move.reconciliation')

        lines = Line.browse(Transaction().context['active_ids'])
        reconciliations = [x.reconciliation for x in lines if x.reconciliation]
        if reconciliations:
            Reconciliation.delete(reconciliations)
        return 'end'


class OpenReconcileLinesStart(ModelView):
    'Open Reconcile Lines'
    __name__ = 'account.move.open_reconcile_lines.start'
    account = fields.Many2One('account.account', 'Account', required=True,
            domain=[('kind', '!=', 'view'), ('reconcile', '=', True)])


class OpenReconcileLines(Wizard):
    'Open Reconcile Lines'
    __name__ = 'account.move.open_reconcile_lines'
    start = StateView('account.move.open_reconcile_lines.start',
        'account.open_reconcile_lines_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Open', 'open_', 'tryton-ok', default=True),
            ])
    open_ = StateAction('account.act_move_line_form')

    def do_open_(self, action):
        action['pyson_domain'] = PYSONEncoder().encode([
            ('account', '=', self.start.account.id),
            ('reconciliation', '=', None),
            ])
        return action, {}


class FiscalYearLine(ModelSQL):
    'Fiscal Year - Move Line'
    __name__ = 'account.fiscalyear-account.move.line'
    _table = 'account_fiscalyear_line_rel'
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
            ondelete='CASCADE', select=True)
    line = fields.Many2One('account.move.line', 'Line', ondelete='RESTRICT',
            select=True, required=True)


class FiscalYear2:
    __name__ = 'account.fiscalyear'
    close_lines = fields.Many2Many('account.fiscalyear-account.move.line',
            'fiscalyear', 'line', 'Close Lines')


class PrintGeneralJournalStart(ModelView):
    'Print General Journal'
    __name__ = 'account.move.print_general_journal.start'
    from_date = fields.Date('From Date', required=True)
    to_date = fields.Date('To Date', required=True)
    company = fields.Many2One('company.company', 'Company', required=True)
    posted = fields.Boolean('Posted Move', help='Show only posted move')

    @staticmethod
    def default_from_date():
        Date = Pool().get('ir.date')
        return datetime.date(Date.today().year, 1, 1)

    @staticmethod
    def default_to_date():
        Date = Pool().get('ir.date')
        return Date.today()

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_posted():
        return False


class PrintGeneralJournal(Wizard):
    'Print General Journal'
    __name__ = 'account.move.print_general_journal'
    start = StateView('account.move.print_general_journal.start',
        'account.print_general_journal_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Print', 'print_', 'tryton-print', default=True),
            ])
    print_ = StateAction('account.report_general_journal')

    def do_print_(self, action):
        data = {
            'company': self.start.company.id,
            'from_date': self.start.from_date,
            'to_date': self.start.to_date,
            'posted': self.start.posted,
            }
        return action, data


class GeneralJournal(Report):
    __name__ = 'account.move.general_journal'

    @classmethod
    def _get_records(cls, ids, model, data):
        Move = Pool().get('account.move')

        clause = [
            ('date', '>=', data['from_date']),
            ('date', '<=', data['to_date']),
            ('period.fiscalyear.company', '=', data['company']),
            ]
        if data['posted']:
            clause.append(('state', '=', 'posted'))
        return Move.search(clause,
                order=[('date', 'ASC'), ('id', 'ASC')])

    @classmethod
    def parse(cls, report, moves, data, localcontext):
        Company = Pool().get('company.company')

        company = Company(data['company'])

        localcontext['company'] = company
        localcontext['digits'] = company.currency.digits
        localcontext['from_date'] = data['from_date']
        localcontext['to_date'] = data['to_date']

        return super(GeneralJournal, cls).parse(report, moves, data,
            localcontext)
