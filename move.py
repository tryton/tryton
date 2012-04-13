#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal
import datetime
import time
try:
    import hashlib
except ImportError:
    hashlib = None
    import md5
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard
from trytond.report import Report
from trytond.backend import TableHandler, FIELDS
from trytond.pyson import Eval, PYSONEncoder
from trytond.transaction import Transaction
from trytond.pool import Pool

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
    _name = 'account.move'
    _description = __doc__

    name = fields.Char('Name', size=None, required=True)
    reference = fields.Char('Reference', size=None, readonly=True,
            help='Also known as Folio Number')
    period = fields.Many2One('account.period', 'Period', required=True,
            states=_MOVE_STATES, depends=_MOVE_DEPENDS, select=1)
    journal = fields.Many2One('account.journal', 'Journal', required=True,
            states=_MOVE_STATES, depends=_MOVE_DEPENDS)
    date = fields.Date('Effective Date', required=True, states=_MOVE_STATES,
            depends=_MOVE_DEPENDS, on_change_with=['period', 'journal', 'date'])
    post_date = fields.Date('Post Date', readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ], 'State', required=True, readonly=True, select=1)
    lines = fields.One2Many('account.move.line', 'move', 'Lines',
            states=_MOVE_STATES, depends=_MOVE_DEPENDS,
            context={
                'journal': Eval('journal'),
                'period': Eval('period'),
                'date': Eval('date'),
            })

    def __init__(self):
        super(Move, self).__init__()
        self._constraints += [
            ('check_centralisation', 'period_centralized_journal'),
            ('check_company', 'company_in_move'),
            ('check_date', 'date_outside_period'),
        ]
        self._rpc.update({
            'button_post': True,
            'button_draft': True,
        })
        self._order.insert(0, ('date', 'DESC'))
        self._order.insert(1, ('reference', 'DESC'))
        self._error_messages.update({
            'del_posted_move': 'You can not delete posted moves!',
            'post_empty_move': 'You can not post an empty move!',
            'post_unbalanced_move': 'You can not post an unbalanced move!',
            'modify_posted_move': 'You can not modify a posted move ' \
                    'in this journal!',
            'period_centralized_journal': 'You can not create more than ' \
                    'one move per period\n' \
                    'in a centralized journal!',
            'company_in_move': 'You can not create lines on accounts\n' \
                    'of different companies in the same move!',
            'date_outside_period': 'You can not create move ' \
                    'with a date outside the period!',
            })

    def init(self, module_name):
        super(Move, self).init(module_name)

        cursor = Transaction().cursor
        table = TableHandler(cursor, self, module_name)
        table.index_action(['journal', 'period'], 'add')

        # Add index on create_date
        table.index_action('create_date', action='add')

    def default_period(self):
        period_obj = Pool().get('account.period')
        return period_obj.find(Transaction().context.get('company') or False,
                exception=False)

    def default_state(self):
        return 'draft'

    def default_date(self):
        period_obj = Pool().get('account.period')
        date_obj = Pool().get('ir.date')
        period_id = self.default_period()
        if period_id:
            period = period_obj.browse(period_id)
            return period.start_date
        return date_obj.today()

    def on_change_with_date(self, vals):
        line_obj = Pool().get('account.move.line')
        period_obj = Pool().get('account.period')
        res = vals['date']
        line_ids = line_obj.search([
            ('journal', '=', vals.get('journal', False)),
            ('period', '=', vals.get('period', False)),
            ], order=[('id', 'DESC')], limit=1)
        if line_ids:
            line = line_obj.browse(line_ids[0])
            res = line.date
        elif vals.get('period'):
            period = period_obj.browse(vals['period'])
            res = period.start_date
        return res

    def check_centralisation(self, ids):
        for move in self.browse(ids):
            if move.journal.centralised:
                move_ids = self.search([
                    ('period', '=', move.period.id),
                    ('journal', '=', move.journal.id),
                    ('state', '!=', 'posted'),
                    ], limit=2)
                if len(move_ids) > 1:
                    return False
        return True

    def check_company(self, ids):
        for move in self.browse(ids):
            company_id = -1
            for line in move.lines:
                if company_id < 0:
                    company_id = line.account.company.id
                if line.account.company.id != company_id:
                    return False
        return True

    def check_date(self, ids):
        for move in self.browse(ids):
            if move.date < move.period.start_date:
                return False
            if move.date > move.period.end_date:
                return False
        return True

    def search_rec_name(self, name, clause):
        ids = self.search(['OR',
            ('reference',) + clause[1:],
            (self._rec_name,) + clause[1:],
            ])
        return [('id', 'in', ids)]

    def write(self, ids, vals):
        res = super(Move, self).write(ids, vals)
        self.validate(ids)
        return res

    def create(self, vals):
        pool = Pool()
        move_line_obj = pool.get('account.move.line')
        sequence_obj = pool.get('ir.sequence')
        journal_obj = pool.get('account.journal')

        if not vals.get('name'):
            journal_id = (vals.get('journal')
                    or Transaction().context.get('journal'))
            if journal_id:
                vals = vals.copy()
                journal = journal_obj.browse(journal_id)
                vals['name'] = sequence_obj.get_id(journal.sequence.id)

        res = super(Move, self).create(vals)
        move = self.browse(res)
        if move.journal.centralised:
            line_id = move_line_obj.create({
                'account': move.journal.credit_account.id,
                'move': move.id,
                'name': 'Centralised Counterpart',
                })
            self.write(move.id, {
                'centralised_line': line_id,
                })
        if 'lines' in vals:
            self.validate([res])
        return res

    def delete(self, ids):
        if isinstance(ids, (int, long)):
            ids = [ids]
        move_line_obj = Pool().get('account.move.line')
        for move in self.browse(ids):
            if move.state == 'posted':
                self.raise_user_error('del_posted_move')
            if move.lines:
                move_line_ids = [x.id for x in move.lines]
                move_line_obj.delete(move_line_ids)
        return super(Move, self).delete(ids)

    def copy(self, ids, default=None):
        line_obj = Pool().get('account.move.line')

        int_id = False
        if isinstance(ids, (int, long)):
            int_id = True
            ids = [ids]

        if default is None:
            default = {}
        default = default.copy()
        default['reference'] = False
        default['state'] = self.default_state()
        default['post_date'] = False
        default['lines'] = False

        new_ids = []
        for move in self.browse(ids):
            new_id = super(Move, self).copy(move.id, default=default)
            line_obj.copy([x.id for x in move.lines], default={
                'move': new_id,
                })
            new_ids.append(new_id)

        if int_id:
            return new_ids[0]
        return new_ids

    def validate(self, ids):
        '''
        Validate balanced move and centralise it if in centralised journal
        '''
        currency_obj = Pool().get('currency.currency')
        move_line_obj = Pool().get('account.move.line')
        if isinstance(ids, (int, long)):
            ids = [ids]
        for move in self.browse(ids):
            if not move.lines:
                continue
            amount = Decimal('0.0')
            company = None
            draft_lines = []
            for line in move.lines:
                amount += line.debit - line.credit
                if not company:
                    company = line.account.company
                if line.state == 'draft':
                    draft_lines.append(line)
            if not currency_obj.is_zero(company.currency, amount):
                if not move.journal.centralised:
                    move_line_obj.write(
                            [x.id for x in move.lines if x.state != 'draft'], {
                                'state': 'draft',
                                })
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
                        centralised_line_id = move_line_obj.create({
                            'debit': debit,
                            'credit': credit,
                            'account': account_id,
                            'move': move.id,
                            'name': 'Centralised Counterpart',
                            })
                        self.write(move.id, {
                            'centralised_line': centralised_line_id,
                            })
                    else:
                        move_line_obj.write( move.centralised_line.id, {
                            'debit': debit,
                            'credit': credit,
                            'account': account_id,
                            })
                continue
            if not draft_lines:
                continue
            move_line_obj.write( [x.id for x in draft_lines], {
                'state': 'valid',
                })
        return

    def post(self, ids):
        pool = Pool()
        currency_obj = pool.get('currency.currency')
        sequence_obj = pool.get('ir.sequence')
        date_obj = pool.get('ir.date')

        if isinstance(ids, (int, long)):
            ids = [ids]

        moves = self.browse(ids)
        for move in moves:
            amount = Decimal('0.0')
            if not move.lines:
                self.raise_user_error('post_empty_move')
            company = None
            for line in move.lines:
                amount += line.debit - line.credit
                if not company:
                    company = line.account.company
            if not currency_obj.is_zero(company.currency, amount):
                self.raise_user_error('post_unbalanced_move')
        for move in moves:
            reference = sequence_obj.get_id(move.period.post_move_sequence.id)
            self.write(move.id, {
                'reference': reference,
                'state': 'posted',
                'post_date': date_obj.today(),
                })
        return

    def draft(self, ids):
        for move in self.browse(ids):
            if not move.journal.update_posted:
                self.raise_user_error('modify_posted_move')
        return self.write(ids, {
            'state': 'draft',
            })

    def button_post(self, ids):
        return self.post(ids)

    def button_draft(self, ids):
        return self.draft(ids)

Move()


class Reconciliation(ModelSQL, ModelView):
    'Account Move Reconciliation Lines'
    _name = 'account.move.reconciliation'
    _description = __doc__

    name = fields.Char('Name', size=None, required=True)
    lines = fields.One2Many('account.move.line', 'reconciliation',
            'Lines')

    def __init__(self):
        super(Reconciliation, self).__init__()
        self._constraints += [
            ('check_lines', 'invalid_reconciliation'),
        ]
        self._error_messages.update({
            'modify': 'You can not modify a reconciliation!',
            'invalid_reconciliation': 'You can not create reconciliation ' \
                    'where lines are not balanced, nor valid, ' \
                    'nor in the same account, nor in account to reconcile, ' \
                    'nor from the same party!',
            })

    def create(self, vals):
        move_line_obj = Pool().get('account.move.line')
        sequence_obj = Pool().get('ir.sequence')

        if 'name' not in vals:
            vals = vals.copy()
            vals['name'] = sequence_obj.get('account.move.reconciliation')

        res = super(Reconciliation, self).create(vals)
        reconciliation = self.browse(res)

        move_line_obj.workflow_trigger_trigger(
                [x.id for x in reconciliation.lines])
        return res

    def write(self, ids, vals):
        self.raise_user_error('modify')

    def check_lines(self, ids):
        currency_obj = Pool().get('currency.currency')
        for reconciliation in self.browse(ids):
            amount = Decimal('0.0')
            account = None
            party = None
            for line in reconciliation.lines:
                if line.state != 'valid':
                    return False
                amount += line.debit - line.credit
                if not account:
                    account = line.account
                elif account.id != line.account.id:
                    return False
                if not account.reconcile:
                    return False
                if not party:
                    party = line.party
                elif line.party and party.id != line.party.id:
                    return False
            if not currency_obj.is_zero(account.company.currency, amount):
                return False
        return True

Reconciliation()


class Line(ModelSQL, ModelView):
    'Account Move Line'
    _name = 'account.move.line'
    _description = __doc__

    name = fields.Char('Name', size=None, required=True)
    debit = fields.Numeric('Debit', digits=(16, Eval('currency_digits', 2)),
            on_change=['account', 'debit', 'credit', 'tax_lines',
                'journal', 'move'], depends=['currency_digits', 'credit',
                    'tax_lines', 'journal'])
    credit = fields.Numeric('Credit', digits=(16, Eval('currency_digits', 2)),
            on_change=['account', 'debit', 'credit', 'tax_lines',
                'journal', 'move'], depends=['currency_digits', 'debit',
                    'tax_lines', 'journal'])
    account = fields.Many2One('account.account', 'Account', required=True,
            domain=[('kind', '!=', 'view')],
            select=1,
            on_change=['account', 'debit', 'credit', 'tax_lines',
                'journal', 'move'])
    move = fields.Many2One('account.move', 'Move', select=1, required=True,
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
    reference = fields.Char('Reference', size=None)
    amount_second_currency = fields.Numeric('Amount Second Currency',
            digits=(16, Eval('second_currency_digits', 2)),
            help='The amount expressed in a second currency',
            depends=['second_currency_digits'])
    second_currency = fields.Many2One('currency.currency', 'Second Currency',
            help='The second currency')
    party = fields.Many2One('party.party', 'Party',
            on_change=['move', 'party', 'account', 'debit', 'credit',
                'journal'], select=1, depends=['debit', 'credit', 'account',
                    'journal'])
    maturity_date = fields.Date('Maturity Date',
            help='This field is used for payable and receivable lines. \n' \
                    'You can put the limit date for the payment.')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('valid', 'Valid'),
        ], 'State', readonly=True, required=True, select=1)
    active = fields.Boolean('Active', select=2)
    reconciliation = fields.Many2One('account.move.reconciliation',
            'Reconciliation', readonly=True, ondelete='SET NULL', select=2)
    tax_lines = fields.One2Many('account.tax.line', 'move_line', 'Tax Lines')
    move_state = fields.Function(fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ], 'Move State'), 'get_move_field', searcher='search_move_field')
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
            'get_currency_digits')
    second_currency_digits = fields.Function(fields.Integer(
        'Second Currency Digits'), 'get_currency_digits')

    def __init__(self):
        super(Line, self).__init__()
        self._sql_constraints += [
            ('credit_debit',
                'CHECK(credit * debit = 0.0)',
                'Wrong credit/debit values!'),
        ]
        self._constraints += [
            ('check_account', 'move_view_inactive_account'),
        ]
        self._rpc.update({
            'on_write': False,
        })
        self._order[0] = ('id', 'DESC')
        self._error_messages.update({
            'add_modify_closed_journal_period': 'You can not ' \
                    'add/modify lines in a closed journal period!',
            'modify_posted_move': 'You can not modify lines of a posted move!',
            'modify_reconciled': 'You can not modify reconciled lines!',
            'no_journal': 'No journal defined!',
            'move_view_inactive_account': 'You can not create move lines\n' \
                    'on view/inactive accounts!',
            'already_reconciled': 'Line "%s" (%d) already reconciled!',
            })

    def init(self, module_name):
        super(Line, self).init(module_name)

        cursor = Transaction().cursor
        table = TableHandler(cursor, self, module_name)
        # Index for General Ledger
        table.index_action(['move', 'account'], 'add')

        # Migration from 1.2
        table.not_null_action('blocked', action='remove')

    def default_date(self):
        '''
        Return the date of the last line for journal, period
        or the starting date of the period
        or today
        '''
        period_obj = Pool().get('account.period')
        date_obj = Pool().get('ir.date')

        res = date_obj.today()
        line_ids = self.search([
            ('journal', '=', Transaction().context.get('journal', False)),
            ('period', '=', Transaction().context.get('period', False)),
            ], order=[('id', 'DESC')], limit=1)
        if line_ids:
            line = self.browse(line_ids[0])
            res = line.date
        elif Transaction().context.get('period'):
            period = period_obj.browse(Transaction().context['period'])
            res = period.start_date
        if Transaction().context.get('date'):
            res = Transaction().context['date']
        return res

    def default_state(self):
        return 'draft'

    def default_active(self):
        return True

    def default_currency_digits(self):
        return 2

    def default_get(self, fields, with_rec_name=True):
        pool = Pool()
        move_obj = pool.get('account.move')
        tax_obj = pool.get('account.tax')
        account_obj = pool.get('account.account')
        tax_code_obj = pool.get('account.tax.code')
        currency_obj = pool.get('currency.currency')
        values = super(Line, self).default_get(fields,
                with_rec_name=with_rec_name)

        if 'move' not in fields:
            #Not manual entry
            if 'date' in values:
                values = values.copy()
                del values['date']
            return values

        if (Transaction().context.get('journal')
                and Transaction().context.get('period')):
            line_ids = self.search([
                ('move.journal', '=', Transaction().context['journal']),
                ('move.period', '=', Transaction().context['period']),
                ('create_uid', '=', Transaction().user),
                ('state', '=', 'draft'),
                ], order=[('id', 'DESC')], limit=1)
            if not line_ids:
                return values
            line = self.browse(line_ids[0])
            values['move'] = line.move.id

        if 'move' not in values:
            return values

        move = move_obj.browse(values['move'])
        total = Decimal('0.0')
        taxes = {}
        no_code_taxes = []
        for line in move.lines:
            total += line.debit - line.credit
            if line.party and 'party' in fields:
                values.setdefault('party', line.party.id)
            if 'reference' in fields:
                values.setdefault('reference', line.reference)
            if 'name' in fields:
                values.setdefault('name', line.name)
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
                        taxes.setdefault((account_id, code_id, tax.id), False)
                for tax_line in line.tax_lines:
                    taxes[(line.account.id, tax_line.code.id,
                            tax_line.tax.id)] = True
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
            if total >= Decimal('0.0'):
                values.setdefault('account', move.journal.credit_account \
                        and move.journal.credit_account.id or False)
            else:
                values.setdefault('account', move.journal.debit_account \
                        and move.journal.debit_account.id or False)

        if ('debit' in fields) or ('credit' in fields):
            values.setdefault('debit',  total < 0 and - total or False)
            values.setdefault('credit', total > 0 and total or False)

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
                    for tax_line in tax_obj.compute(
                            [x.id for x in line.account.taxes],
                            line.debit or line.credit, 1):
                        if (tax_line['tax'][key + '_account'].id \
                                or line.account.id) == account_id \
                                and tax_line['tax'][key + '_tax_code'].id \
                                    == code_id \
                                and tax_line['tax'].id == tax_id:
                            if line.debit:
                                line_amount += tax_line['amount']
                            else:
                                line_amount -= tax_line['amount']
                            tax_amount += tax_line['amount'] * \
                                    tax_line['tax'][key + '_tax_sign']
                    line_amount = currency_obj.round(
                            line.account.company.currency, line_amount)
                    tax_amount = currency_obj.round(
                            line.account.company.currency, tax_amount)
                    if ('debit' in fields):
                        values['debit'] = line_amount > Decimal('0.0') \
                                and line_amount or Decimal('0.0')
                    if ('credit' in fields):
                        values['credit'] = line_amount < Decimal('0.0') \
                                and - line_amount or Decimal('0.0')
                    if 'account' in fields:
                        values['account'] = account_id
                        values['account.rec_name'] = account_obj.browse(
                                account_id).rec_name
                    if 'tax_lines' in fields and code_id:
                        values['tax_lines'] = [
                            {
                                'amount': tax_amount,
                                'currency_digits': line.currency_digits,
                                'code': code_id,
                                'code.rec_name': tax_code_obj.browse(
                                    code_id).rec_name,
                                'tax': tax_id,
                                'tax.rec_name': tax_obj.browse(tax_id).rec_name
                            },
                        ]
        return values

    def get_currency_digits(self, ids, names):
        res = {}
        for line in self.browse(ids):
            for name in names:
                res.setdefault(name, {})
                res[name].setdefault(line.id, 2)
                if name == 'currency_digits':
                    res[name][line.id] = line.account.currency_digits
                elif name == 'second_currency_digits':
                    if line.account.second_currency:
                        res[name][line.id] = line.account.second_currency.digits
        return res

    def on_change_debit(self, vals):
        res = {}
        journal_obj = Pool().get('account.journal')
        if vals.get('journal') or Transaction().context.get('journal'):
            journal = journal_obj.browse(vals.get('journal')
                    or Transaction().context.get('journal'))
            if journal.type in ('expense', 'revenue'):
                res['tax_lines'] = self._compute_tax_lines(vals, journal.type)
                if not res['tax_lines']:
                    del res['tax_lines']
        if vals.get('debit'):
            res['credit'] = Decimal('0.0')
        return res

    def on_change_credit(self, vals):
        res = {}
        journal_obj = Pool().get('account.journal')
        if vals.get('journal') or Transaction().context.get('journal'):
            journal = journal_obj.browse(vals.get('journal')
                    or Transaction().context.get('journal'))
            if journal.type in ('expense', 'revenue'):
                res['tax_lines'] = self._compute_tax_lines(
                        vals, journal.type)
                if not res['tax_lines']:
                    del res['tax_lines']
        if vals.get('credit'):
            res['debit'] = Decimal('0.0')
        return res

    def on_change_account(self, vals):
        account_obj = Pool().get('account.account')
        journal_obj = Pool().get('account.journal')

        res = {}
        if Transaction().context.get('journal'):
            journal = journal_obj.browse(Transaction().context['journal'])
            if journal.type in ('expense', 'revenue'):
                res['tax_lines'] = self._compute_tax_lines(vals, journal.type)
                if not res['tax_lines']:
                    del res['tax_lines']

        if vals.get('account'):
            account = account_obj.browse(vals['account'])
            res['currency_digits'] = account.currency_digits
            if account.second_currency:
                res['second_currency_digits'] = account.second_currency.digits
        return res

    def _compute_tax_lines(self, vals, journal_type):
        res = {}
        pool = Pool()
        account_obj = pool.get('account.account')
        tax_code_obj = pool.get('account.tax.code')
        tax_obj = pool.get('account.tax')
        move_obj = pool.get('account.move')
        tax_line_obj = pool.get('account.tax.line')

        if vals.get('move'):
            #Only for first line
            return res
        if vals.get('tax_lines'):
            res['remove'] = [x['id'] for x in vals['tax_lines']]
        if vals.get('account'):
            account = account_obj.browse(vals['account'])
            debit = vals.get('debit', Decimal('0.0'))
            credit = vals.get('credit', Decimal('0.0'))
            for tax in account.taxes:
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
                for tax_line in tax_obj.compute(
                        [x.id for x in account.taxes],
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
                    value = tax_line_obj.default_get(
                        tax_line_obj._columns.keys())
                    value.update({
                            'amount': base_amounts[code_id, tax_id],
                            'currency_digits': account.currency_digits,
                            'code': code_id,
                            'code.rec_name': tax_code_obj.browse(
                                code_id).rec_name,
                            'tax': tax_id,
                            'tax.rec_name': tax_obj.browse(tax_id).rec_name,
                            })
                    res.setdefault('add', []).append(value)
        return res

    def on_change_party(self, vals):
        pool = Pool()
        party_obj = pool.get('party.party')
        journal_obj = pool.get('account.journal')
        account_obj = pool.get('account.account')
        currency_obj = pool.get('currency.currency')
        cursor = Transaction().cursor
        res = {}
        if (not vals.get('party')) or vals.get('account'):
            return res
        party = party_obj.browse(vals.get('party'))

        if not party.account_receivable \
                or not party.account_payable:
            return res

        if party and (not vals.get('debit')) and (not vals.get('credit')):
            type_name = FIELDS[self.debit._type].sql_type(self.debit)[0]
            query = 'SELECT ' \
                        'CAST(COALESCE(SUM(' \
                            '(COALESCE(debit, 0) - COALESCE(credit, 0))' \
                        '), 0) AS ' + type_name + ') ' \
                    'FROM account_move_line ' \
                    'WHERE reconciliation IS NULL ' \
                        'AND party = %s ' \
                        'AND account = %s'
            cursor.execute(query, (party.id, party.account_receivable.id))
            amount = cursor.fetchone()[0]
            # SQLite uses float for SUM
            if not isinstance(amount, Decimal):
                amount = Decimal(str(amount))
            if not currency_obj.is_zero( party.account_receivable.currency,
                    amount):
                if amount > Decimal('0.0'):
                    res['credit'] = currency_obj.round(
                            party.account_receivable.currency, amount)
                    res['debit'] = Decimal('0.0')
                else:
                    res['credit'] = Decimal('0.0')
                    res['debit'] = - currency_obj.round(
                            party.account_receivable.currency, amount)
                res['account'] = party.account_receivable.id
                res['account.rec_name'] = party.account_receivable.rec_name
            else:
                cursor.execute(query, (party.id, party.account_payable.id))
                amount = cursor.fetchone()[0]
                if not currency_obj.is_zero( party.account_payable.currency,
                        amount):
                    if amount > Decimal('0.0'):
                        res['credit'] = currency_obj.round(
                                party.account_payable.currency, amount)
                        res['debit'] = Decimal('0.0')
                    else:
                        res['credit'] = Decimal('0.0')
                        res['debit'] = - currency_obj.round(
                                party.account_payable.currency, amount)
                    res['account'] = party.account_payable.id
                    res['account.rec_name'] = party.account_payable.rec_name

        if party and vals.get('debit'):
            if vals['debit'] > Decimal('0.0'):
                if 'account' not in res:
                    res['account'] = party.account_receivable.id
                    res['account.rec_name'] = party.account_receivable.rec_name
            else:
                if 'account' not in res:
                    res['account'] = party.account_payable.id
                    res['account.rec_name'] = party.account_payable.id

        if party and vals.get('credit'):
            if vals['credit'] > Decimal('0.0'):
                if 'account' not in res:
                    res['account'] = party.account_payable.id
                    res['account.rec_name'] = party.account_payable.rec_name
            else:
                if 'account' not in res:
                    res['account'] = party.account_receivable.id
                    res['account.rec_name'] = party.account_receivable.rec_name

        journal_id = (vals.get('journal')
                or Transaction().context.get('journal'))
        if journal_id and party:
            journal = journal_obj.browse(journal_id)
            if journal.type == 'revenue':
                if 'account' not in res:
                    res['account'] = party.account_receivable.id
                    res['account.rec_name'] = party.account_receivable.rec_name
            elif journal.type == 'expense':
                if 'account' not in res:
                    res['account'] = party.account_payable.id
                    res['account.rec_name'] = party.account_payable.rec_name
        return res

    def get_move_field(self, ids, name):
        if name == 'move_state':
            name = 'state'
        if name not in ('period', 'journal', 'date', 'state'):
            raise Exception('Invalid name')
        res = {}
        for line in self.browse(ids):
            if name in ('date', 'state'):
                res[line.id] = line.move[name]
            else:
                res[line.id] = line.move[name].id
        return res

    def set_move_field(self, ids, name, value):
        if name == 'move_state':
            name = 'state'
        if name not in ('period', 'journal', 'date', 'state'):
            raise Exception('Invalid name')
        if not value:
            return
        move_obj = Pool().get('account.move')
        lines = self.browse(ids)
        move_obj.write([line.move.id for line in lines], {
            name: value,
            })

    def search_move_field(self, name, clause):
        if name == 'move_state':
            name = 'state'
        return [('move.' + name,) + tuple(clause[1:])]

    def query_get(self, obj='l'):
        '''
        Return SQL clause and fiscal years for account move line
        depending of the context.

        :param obj: the SQL alias of account_move_line in the query
        :return: a tuple with the SQL clause and the fiscalyear ids
        '''
        fiscalyear_obj = Pool().get('account.fiscalyear')

        if Transaction().context.get('date'):
            time.strptime(str(Transaction().context['date']), '%Y-%m-%d')
            fiscalyear_ids = fiscalyear_obj.search([
                ('start_date', '<=', Transaction().context['date']),
                ('end_date', '>=', Transaction().context['date']),
                ], limit=1)

            fiscalyear_id = fiscalyear_ids and fiscalyear_ids[0] or 0

            if Transaction().context.get('posted'):
                return (obj + '.active ' \
                        'AND ' + obj + '.state != \'draft\' ' \
                        'AND ' + obj + '.move IN (' \
                            'SELECT m.id FROM account_move AS m, ' \
                                'account_period AS p ' \
                                'WHERE m.period = p.id ' \
                                    'AND p.fiscalyear = ' + \
                                        str(fiscalyear_id) + ' ' \
                                    'AND m.date <= date(\'' + \
                                        str(Transaction().context['date']) + \
                                        '\') ' \
                                    'AND m.state = \'posted\' ' \
                            ')', fiscalyear_ids)
            else:
                return (obj + '.active ' \
                        'AND ' + obj + '.state != \'draft\' ' \
                        'AND ' + obj + '.move IN (' \
                            'SELECT m.id FROM account_move AS m, ' \
                                'account_period AS p ' \
                                'WHERE m.period = p.id ' \
                                    'AND p.fiscalyear = ' + \
                                        str(fiscalyear_id) + ' ' \
                                    'AND m.date <= date(\'' + \
                                        str(Transaction().context['date']) + \
                                        '\')' \
                            ')', fiscalyear_ids)

        if not Transaction().context.get('fiscalyear'):
            fiscalyear_ids = fiscalyear_obj.search([
                ('state', '=', 'open'),
                ])
            fiscalyear_clause = (','.join(map(str, fiscalyear_ids))) or '0'
        else:
            fiscalyear_ids = [int(Transaction().context.get('fiscalyear'))]
            fiscalyear_clause = '%s' % int(
                    Transaction().context.get('fiscalyear'))

        if Transaction().context.get('periods'):
            ids = ','.join(
                    str(int(x)) for x in Transaction().context['periods'])
            if Transaction().context.get('posted'):
                return (obj + '.active ' \
                        'AND ' + obj + '.state != \'draft\' ' \
                        'AND ' + obj + '.move IN (' \
                            'SELECT id FROM account_move ' \
                                'WHERE period IN (' + ids + ') ' \
                                    'AND state = \'posted\' ' \
                            ')', [])
            else:
                return (obj + '.active ' \
                        'AND ' + obj + '.state != \'draft\' ' \
                        'AND ' + obj + '.move IN (' \
                            'SELECT id FROM account_move ' \
                                'WHERE period IN (' + ids + ')' \
                            ')', [])
        else:
            if Transaction().context.get('posted'):
                return (obj + '.active ' \
                        'AND ' + obj + '.state != \'draft\' ' \
                        'AND ' + obj + '.move IN (' \
                            'SELECT id FROM account_move ' \
                                'WHERE period IN (' \
                                    'SELECT id FROM account_period ' \
                                    'WHERE fiscalyear IN (' + fiscalyear_clause + ')' \
                                    ') ' \
                                    'AND state = \'posted\' ' \
                            ')', fiscalyear_ids)
            else:
                return (obj + '.active ' \
                        'AND ' + obj + '.state != \'draft\' ' \
                        'AND ' + obj + '.move IN (' \
                            'SELECT id FROM account_move ' \
                                'WHERE period IN (' \
                                    'SELECT id FROM account_period ' \
                                    'WHERE fiscalyear IN (' + fiscalyear_clause + ')' \
                                ')' \
                            ')', fiscalyear_ids)

    def on_write(self, ids):
        lines = self.browse(ids)
        res = []
        for line in lines:
            res.extend([x.id for x in line.move.lines])
        return list({}.fromkeys(res))

    def check_account(self, ids):
        for line in self.browse(ids):
            if line.account.kind in ('view',):
                return False
            if not line.account.active:
                return False
        return True

    def check_journal_period_modify(self, period_id, journal_id):
        '''
        Check if the lines can be modified or created for the journal - period
        and if there is no journal - period, create it
        '''
        pool = Pool()
        journal_period_obj = pool.get('account.journal.period')
        journal_obj = pool.get('account.journal')
        period_obj = pool.get('account.period')
        journal_period_ids = journal_period_obj.search([
            ('journal', '=', journal_id),
            ('period', '=', period_id),
            ], limit=1)
        if journal_period_ids:
            journal_period = journal_period_obj.browse(journal_period_ids[0])
            if journal_period.state == 'close':
                self.raise_user_error('add_modify_closed_journal_period')
        else:
            journal = journal_obj.browse(journal_id)
            period = period_obj.browse(period_id)
            journal_period_obj.create({
                'name': journal.name + ' - ' + period.name,
                'journal': journal.id,
                'period': period.id,
                })
        return

    def check_modify(self, ids):
        '''
        Check if the lines can be modified
        '''
        journal_period_done = []
        for line in self.browse(ids):
            if line.move.state == 'posted':
                self.raise_user_error('modify_posted_move')
            if line.reconciliation:
                self.raise_user_error('modify_reconciled')
            journal_period = (line.journal.id, line.period.id)
            if journal_period not in journal_period_done:
                self.check_journal_period_modify(line.period.id,
                        line.journal.id)
                journal_period_done.append(journal_period)
        return

    def delete(self, ids):
        move_obj = Pool().get('account.move')
        if isinstance(ids, (int, long)):
            ids = [ids]
        self.check_modify(ids)
        lines = self.browse(ids)
        move_ids = [x.move.id for x in lines]
        res = super(Line, self).delete(ids)
        move_obj.validate(move_ids)
        return res

    def write(self, ids, vals):
        move_obj = Pool().get('account.move')

        if isinstance(ids, (int, long)):
            ids = [ids]

        if len(vals) > 1 or 'reconciliation' not in vals:
            self.check_modify(ids)
        lines = self.browse(ids)
        move_ids = [x.move.id for x in lines]
        res = super(Line, self).write(ids, vals)

        Transaction().timestamp = {}

        lines = self.browse(ids)
        for line in lines:
            if line.move.id not in move_ids:
                move_ids.append(line.move.id)
        move_obj.validate(move_ids)
        return res

    def create(self, vals):
        journal_obj = Pool().get('account.journal')
        move_obj = Pool().get('account.move')
        vals = vals.copy()
        if not vals.get('move'):
            journal_id = (vals.get('journal')
                    or Transaction().context.get('journal'))
            if not journal_id:
                self.raise_user_error('no_journal')
            journal = journal_obj.browse(journal_id)
            if journal.centralised:
                move_ids = move_obj.search([
                    ('period', '=', vals.get('period')
                        or Transaction().context.get('period')),
                    ('journal', '=', journal_id),
                    ('state', '!=', 'posted'),
                    ], limit=1)
                if move_ids:
                    vals['move'] = move_ids[0]
            if not vals.get('move'):
                vals['move'] = move_obj.create({
                    'period': (vals.get('period')
                        or Transaction().context.get('period')),
                    'journal': journal_id,
                    'date': vals.get('date', False),
                    })
        res = super(Line, self).create(vals)
        line = self.browse(res)
        self.check_journal_period_modify(line.period.id, line.journal.id)
        move_obj.validate([vals['move']])
        return res

    def copy(self, ids, default=None):
        if default is None:
            default = {}
        if 'move' not in default:
            default['move'] = False
        if 'reconciliation' not in default:
            default['reconciliation'] = False
        return super(Line, self).copy(ids, default=default)

    def view_header_get(self, value, view_type='form'):
        journal_period_obj = Pool().get('account.journal.period')
        if (not Transaction().context.get('journal')
                or not Transaction().context.get('period')):
            return value
        journal_period_ids = journal_period_obj.search([
            ('journal', '=', Transaction().context['journal']),
            ('period', '=', Transaction().context['period']),
            ], limit=1)
        if not journal_period_ids:
            return value
        journal_period = journal_period_obj.browse(journal_period_ids[0])
        return value + ': ' + journal_period.rec_name

    def fields_view_get(self, view_id=None, view_type='form', hexmd5=None):
        journal_obj = Pool().get('account.journal')
        result = super(Line, self).fields_view_get(view_id=view_id,
            view_type=view_type, hexmd5=hexmd5)
        if view_type == 'tree' and 'journal' in Transaction().context:
            title = self.view_header_get('', view_type=view_type)
            journal = journal_obj.browse(Transaction().context['journal'])

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
                xml += '<field name="%s" %s/>\n' % (column.field.name, ' '.join(attrs))
                for depend in getattr(self, column.field.name).depends:
                    fields.add(depend)
            fields.add('state')
            xml += '</tree>'
            result['arch'] = xml
            result['fields'] = self.fields_get(fields_names=list(fields))
            del result['md5']
            if hashlib:
                result['md5'] = hashlib.md5(str(result)).hexdigest()
            else:
                result['md5'] = md5.new(str(result)).hexdigest()
            if hexmd5 == result['md5']:
                return True
        return result

    def reconcile(self, ids, journal_id=False, date=False, account_id=False):
        pool = Pool()
        move_obj = pool.get('account.move')
        currency_obj = pool.get('currency.currency')
        reconciliation_obj = pool.get('account.move.reconciliation')
        period_obj = pool.get('account.period')
        date_obj = pool.get('ir.date')
        translation_obj = pool.get('ir.translation')

        for line in self.browse(ids):
            if line.reconciliation:
                self.raise_user_error('already_reconciled',
                        error_args=(line.name, line.id,))

        ids = ids[:]
        if journal_id and account_id:
            if not date:
                date = date_obj.today()
            account = None
            amount = Decimal('0.0')
            for line in self.browse(ids):
                amount += line.debit - line.credit
                if not account:
                    account = line.account
            amount = currency_obj.round(account.currency, amount)
            period_id = period_obj.find(account.company.id, date=date)
            lang_code = 'en_US'
            if account.company.lang:
                lang_code = account.company.lang.code
            writeoff = translation_obj._get_source(
                    'account.move.reconcile_lines.writeoff', 'view', lang_code,
                    'Write-Off') or 'Write-Off'
            move_id = move_obj.create({
                'journal': journal_id,
                'period': period_id,
                'date': date,
                'lines': [
                    ('create', {
                        'name': writeoff,
                        'account': account.id,
                        'debit': amount < Decimal('0.0') and - amount \
                                or Decimal('0.0'),
                        'credit': amount > Decimal('0.0') and amount \
                                or Decimal('0.0'),
                    }),
                    ('create', {
                        'name': writeoff,
                        'account': account_id,
                        'debit': amount > Decimal('0.0') and amount \
                                or Decimal('0.0'),
                        'credit': amount < Decimal('0.0') and - amount \
                                or Decimal('0.0'),
                    }),
                ],
                })
            ids += self.search([
                ('move', '=', move_id),
                ('account', '=', account.id),
                ('debit', '=', amount < Decimal('0.0') and - amount \
                        or Decimal('0.0')),
                ('credit', '=', amount > Decimal('0.0') and amount \
                        or Decimal('0.0')),
                ], limit=1)
        return reconciliation_obj.create({
            'lines': [('add', x) for x in ids],
            })

Line()


class Move2(ModelSQL, ModelView):
    _name = 'account.move'
    centralised_line = fields.Many2One('account.move.line', 'Centralised Line',
            readonly=True)

Move2()


class OpenJournalAsk(ModelView):
    'Open Journal Ask'
    _name = 'account.move.open_journal.ask'
    _description = __doc__
    journal = fields.Many2One('account.journal', 'Journal', required=True)
    period = fields.Many2One('account.period', 'Period', required=True,
        domain=[
            ('state', '!=', 'close'),
            ('fiscalyear.company.id', '=',
                Eval('context', {}).get('company', 0)),
            ])

    def default_period(self):
        period_obj = Pool().get('account.period')
        return period_obj.find(Transaction().context.get('company') or False,
                exception=False)

OpenJournalAsk()


class OpenJournal(Wizard):
    'Open Journal'
    _name = 'account.move.open_journal'
    states = {
        'init': {
            'result': {
                'type': 'choice',
                'next_state': '_next',
            },
        },
        'ask': {
            'result': {
                'type': 'form',
                'object': 'account.move.open_journal.ask',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('open', 'Open', 'tryton-ok', True),
                ],
            },
        },
        'open': {
            'result': {
                'type': 'action',
                'action': '_action_open_journal',
                'state': 'end',
            },
        },
    }

    def _next(self, data):
        if data.get('model', '') == 'account.journal.period' \
                and data.get('id'):
            return 'open'
        return 'ask'

    def _get_journal_period(self, data):
        journal_period_obj = Pool().get('account.journal.period')
        if data.get('model', '') == 'account.journal.period' \
                and data.get('id'):
            journal_period = journal_period_obj.browse(data['id'])
            return {
                'journal': journal_period.journal.id,
                'period': journal_period.period.id,
            }
        return {}

    def _action_open_journal(self, data):
        pool = Pool()
        journal_period_obj = pool.get('account.journal.period')
        journal_obj = pool.get('account.journal')
        period_obj = pool.get('account.period')
        model_data_obj = pool.get('ir.model.data')
        act_window_obj = pool.get('ir.action.act_window')
        if data.get('model', '') == 'account.journal.period' \
                and data.get('id'):
            journal_period = journal_period_obj.browse(data['id'])
            journal_id = journal_period.journal.id
            period_id = journal_period.period.id
        else:
            journal_id = data['form']['journal']
            period_id = data['form']['period']
        if not journal_period_obj.search([
            ('journal', '=', journal_id),
            ('period', '=', period_id),
            ]):
            journal = journal_obj.browse(journal_id)
            period = period_obj.browse(period_id)
            journal_period_obj.create({
                'name': journal.name + ' - ' + period.name,
                'journal': journal.id,
                'period': period.id,
                })

        act_window_id = model_data_obj.get_id('account', 'act_move_line_form')
        res = act_window_obj.read(act_window_id)
        # Remove name to use the one from view_header_get
        del res['name']
        res['pyson_domain'] = PYSONEncoder().encode([
            ('journal', '=', journal_id),
            ('period', '=', period_id),
            ])
        res['pyson_context'] = PYSONEncoder().encode({
            'journal': journal_id,
            'period': period_id,
            })
        return res

OpenJournal()


class OpenAccount(Wizard):
    'Open Account'
    _name = 'account.move.open_account'
    states = {
        'init': {
            'result': {
                'type': 'action',
                'action': '_action_open_account',
                'state': 'end',
            },
        },
    }

    def _action_open_account(self, data):
        pool = Pool()
        model_data_obj = pool.get('ir.model.data')
        act_window_obj = pool.get('ir.action.act_window')
        fiscalyear_obj = pool.get('account.fiscalyear')

        if not Transaction().context.get('fiscalyear'):
            fiscalyear_ids = fiscalyear_obj.search([
                ('state', '=', 'open'),
                ])
        else:
            fiscalyear_ids = [Transaction().context['fiscalyear']]

        period_ids = []
        for fiscalyear in fiscalyear_obj.browse(fiscalyear_ids):
            for period in fiscalyear.periods:
                period_ids.append(period.id)

        act_window_id = model_data_obj.get_id('account', 'act_move_line_form')
        res = act_window_obj.read(act_window_id)
        res['pyson_domain'] = [
            ('period', 'in', period_ids),
            ('account', '=', data['id']),
            ]
        if Transaction().context.get('posted'):
            res['pyson_domain'].append(('move.state', '=', 'posted'))
        res['pyson_domain'] = PYSONEncoder().encode(res['pyson_domain'])
        res['pyson_context'] = PYSONEncoder().encode({
            'fiscalyear': Transaction().context.get('fiscalyear'),
        })
        return res

OpenAccount()


class ReconcileLinesWriteOff(ModelView):
    'Reconcile Lines Write-Off'
    _name = 'account.move.reconcile_lines.writeoff'
    _description = __doc__
    journal = fields.Many2One('account.journal', 'Journal', required=True)
    date = fields.Date('Date', required=True)
    account = fields.Many2One('account.account', 'Account', required=True,
            domain=[('kind', '!=', 'view')])

    def default_date(self):
        date_obj = Pool().get('ir.date')
        return date_obj.today()

ReconcileLinesWriteOff()


class ReconcileLines(Wizard):
    'Reconcile Lines'
    _name = 'account.move.reconcile_lines'
    states = {
        'init': {
            'result': {
                'type': 'choice',
                'next_state': '_check_writeoff',
            },
        },
        'writeoff': {
            'result': {
                'type': 'form',
                'object': 'account.move.reconcile_lines.writeoff',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('reconcile', 'Reconcile', 'tryton-ok', True),
                ],
            },
        },
        'reconcile': {
            'actions': ['_reconcile'],
            'result': {
                'type': 'state',
                'state': 'end',
            },
        },
    }

    def _check_writeoff(self, data):
        line_obj = Pool().get('account.move.line')
        currency_obj = Pool().get('currency.currency')

        company = None
        amount = Decimal('0.0')
        for line in line_obj.browse(data['ids']):
            amount += line.debit - line.credit
            if not company:
                company = line.account.company
        if not company:
            return 'end'
        if currency_obj.is_zero(company.currency, amount):
            return 'reconcile'
        return 'writeoff'

    def _reconcile(self, data):
        line_obj = Pool().get('account.move.line')

        if data['form']:
            journal_id = data['form'].get('journal')
            date = data['form'].get('date')
            account_id = data['form'].get('account')
        else:
            journal_id = False
            date = False
            account_id = False
        line_obj.reconcile(data['ids'], journal_id, date, account_id)
        return {}

ReconcileLines()


class UnreconcileLinesInit(ModelView):
    'Unreconcile Lines Init'
    _name = 'account.move.unreconcile_lines.init'
    _description = __doc__

UnreconcileLinesInit()


class UnreconcileLines(Wizard):
    'Unreconcile Lines'
    _name = 'account.move.unreconcile_lines'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'account.move.unreconcile_lines.init',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('unreconcile', 'Unreconcile', 'tryton-ok', True),
                ],
            },
        },
        'unreconcile': {
            'actions': ['_unreconcile'],
            'result': {
                'type': 'state',
                'state': 'end',
            },
        },
    }

    def _unreconcile(self, data):
        line_obj = Pool().get('account.move.line')
        reconciliation_obj = Pool().get('account.move.reconciliation')

        lines = line_obj.browse(data['ids'])
        reconciliation_ids = [x.reconciliation.id for x in lines \
                if x.reconciliation]
        if reconciliation_ids:
            reconciliation_obj.delete(reconciliation_ids)
        return {}

UnreconcileLines()


class OpenReconcileLinesInit(ModelView):
    'Open Reconcile Lines Init'
    _name = 'account.move.open_reconcile_lines.init'
    _description = __doc__
    account = fields.Many2One('account.account', 'Account', required=True,
            domain=[('kind', '!=', 'view'), ('reconcile', '=', True)])

OpenReconcileLinesInit()


class OpenReconcileLines(Wizard):
    'Open Reconcile Lines'
    _name = 'account.move.open_reconcile_lines'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'account.move.open_reconcile_lines.init',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('open', 'Open', 'tryton-ok', True),
                ],
            },
        },
        'open': {
            'result': {
                'type': 'action',
                'action': '_action_open_reconcile_lines',
                'state': 'end',
            },
        },
    }

    def _action_open_reconcile_lines(self, data):
        model_data_obj = Pool().get('ir.model.data')
        act_window_obj = Pool().get('ir.action.act_window')
        act_window_id = model_data_obj.get_id('account', 'act_move_line_form')
        res = act_window_obj.read(act_window_id)
        res['pyson_domain'] = PYSONEncoder().encode([
            ('account', '=', data['form']['account']),
            ('reconciliation', '=', False),
            ])
        return res

OpenReconcileLines()


class FiscalYearLine(ModelSQL):
    'Fiscal Year - Move Line'
    _name = 'account.fiscalyear-account.move.line'
    _table = 'account_fiscalyear_line_rel'
    _description = __doc__
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
            ondelete='CASCADE', select=1)
    line = fields.Many2One('account.move.line', 'Line', ondelete='RESTRICT',
            select=1, required=True)

FiscalYearLine()


class FiscalYear(ModelSQL, ModelView):
    _name = 'account.fiscalyear'
    close_lines = fields.Many2Many('account.fiscalyear-account.move.line',
            'fiscalyear', 'line', 'Close Lines')

FiscalYear()


class PrintGeneralJournalInit(ModelView):
    'Print General Journal Init'
    _name = 'account.move.print_general_journal.init'
    _description = __doc__
    from_date = fields.Date('From Date', required=True)
    to_date = fields.Date('To Date', required=True)
    company = fields.Many2One('company.company', 'Company', required=True)
    posted = fields.Boolean('Posted Move', help='Show only posted move')

    def default_from_date(self):
        date_obj = Pool().get('ir.date')
        return datetime.date(date_obj.today().year, 1, 1)

    def default_to_date(self):
        date_obj = Pool().get('ir.date')
        return date_obj.today()

    def default_company(self):
        return Transaction().context.get('company') or False

    def default_posted(self):
        return False

PrintGeneralJournalInit()


class PrintGeneralJournal(Wizard):
    'Print General Journal'
    _name = 'account.move.print_general_journal'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'account.move.print_general_journal.init',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('print', 'Print', 'tryton-print', True),
                ],
            },
        },
        'print': {
            'result': {
                'type': 'print',
                'report': 'account.move.general_journal',
                'state': 'end',
            },
        },
    }

PrintGeneralJournal()


class GeneralJournal(Report):
    _name = 'account.move.general_journal'

    def _get_objects(self, ids, model, datas):
        move_obj = Pool().get('account.move')

        clause = [
            ('date', '>=', datas['form']['from_date']),
            ('date', '<=', datas['form']['to_date']),
            ]
        if datas['form']['posted']:
            clause.append(('state', '=', 'posted'))
        move_ids = move_obj.search(clause,
                order=[('date', 'ASC'), ('reference', 'ASC'), ('id', 'ASC')])
        return move_obj.browse(move_ids)

    def parse(self, report, objects, datas, localcontext):
        company_obj = Pool().get('company.company')

        company = company_obj.browse(datas['form']['company'])

        localcontext['company'] = company
        localcontext['digits'] = company.currency.digits
        localcontext['from_date'] = datas['form']['from_date']
        localcontext['to_date'] = datas['form']['to_date']

        return super(GeneralJournal, self).parse(report, objects, datas,
                localcontext)

GeneralJournal()
