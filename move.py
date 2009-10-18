#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
'Move'
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard
from trytond.report import Report
from trytond.backend import TableHandler, FIELDS
from decimal import Decimal
import datetime
import md5
import mx.DateTime

_MOVE_STATES = {
    'readonly': "state == 'posted'",
}
_MOVE_DEPENDS = ['state']
_LINE_STATES = {
    'readonly': "state == 'valid'",
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
            states=_MOVE_STATES, depends=_MOVE_DEPENDS)
    journal = fields.Many2One('account.journal', 'Journal', required=True,
            states=_MOVE_STATES, depends=_MOVE_DEPENDS)
    date = fields.Date('Effective Date', required=True, states=_MOVE_STATES,
            depends=_MOVE_DEPENDS, on_change_with=['period', 'journal', 'date'])
    post_date = fields.Date('Post Date', readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ], 'State', required=True, readonly=True)
    lines = fields.One2Many('account.move.line', 'move', 'Lines',
            states=_MOVE_STATES, depends=_MOVE_DEPENDS,
            context="{'journal': journal, 'period': period, " \
                    "'date': date}")

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

    def init(self, cursor, module_name):
        super(Move, self).init(cursor, module_name)

        table = TableHandler(cursor, self, module_name)
        table.index_action(['journal', 'period'], 'add')

    def default_period(self, cursor, user, context=None):
        period_obj = self.pool.get('account.period')
        if context is None:
            context = {}
        return period_obj.find(cursor, user, context.get('company', False),
                exception=False, context=context)

    def default_state(self, cursor, user, context=None):
        return 'draft'

    def default_date(self, cursor, user, context=None):
        period_obj = self.pool.get('account.period')
        date_obj = self.pool.get('ir.date')
        period_id = self.default_period(cursor, user, context=context)
        if period_id:
            period = period_obj.browse(cursor, user, period_id,
                    context=context)
            return period.start_date
        return date_obj.today(cursor, user, context=context)

    def on_change_with_date(self, cursor, user, ids, vals,
            context=None):
        line_obj = self.pool.get('account.move.line')
        period_obj = self.pool.get('account.period')
        res = vals['date']
        line_ids = line_obj.search(cursor, user, [
            ('journal', '=', vals.get('journal', False)),
            ('period', '=', vals.get('period', False)),
            ], order=[('id', 'DESC')], limit=1, context=context)
        if line_ids:
            line = line_obj.browse(cursor, user, line_ids[0], context=context)
            res = line.date
        elif vals.get('period'):
            period = period_obj.browse(cursor, user, vals['period'],
                    context=context)
            res = period.start_date
        return res

    def check_centralisation(self, cursor, user, ids):
        for move in self.browse(cursor, user, ids):
            if move.journal.centralised:
                move_ids = self.search(cursor, user, [
                    ('period', '=', move.period.id),
                    ('journal', '=', move.journal.id),
                    ('state', '!=', 'posted'),
                    ], limit=2)
                if len(move_ids) > 1:
                    return False
        return True

    def check_company(self, cursor, user, ids):
        for move in self.browse(cursor, user, ids):
            company_id = -1
            for line in move.lines:
                if company_id < 0:
                    company_id = line.account.company.id
                if line.account.company.id != company_id:
                    return False
        return True

    def check_date(self, cursor, user, ids):
        for move in self.browse(cursor, user, ids):
            if move.date < move.period.start_date:
                return False
            if move.date > move.period.end_date:
                return False
        return True

    def search_rec_name(self, cursor, user, name, args, context=None):
        args2 = []
        i = 0
        while i < len(args):
            ids = self.search(cursor, user, ['OR',
                ('reference', args[i][1], args[i][2]),
                (self._rec_name, args[i][1], args[i][2]),
                ], context=context)
            args2.append(('id', 'in', ids))
            i += 1
        return args2

    def write(self, cursor, user, ids, vals, context=None):
        res = super(Move, self).write(cursor, user, ids, vals, context=context)
        self.validate(cursor, user, ids, context=context)
        return res

    def create(self, cursor, user, vals, context=None):
        move_line_obj = self.pool.get('account.move.line')
        sequence_obj = self.pool.get('ir.sequence')
        journal_obj = self.pool.get('account.journal')

        if context is None:
            context = {}

        if not vals.get('name'):
            journal_id = vals.get('journal') or context.get('journal')
            if journal_id:
                vals = vals.copy()
                journal = journal_obj.browse(cursor, user, journal_id,
                        context=context)
                vals['name'] = sequence_obj.get_id(cursor, user,
                        journal.sequence.id, context=context)

        res = super(Move, self).create(cursor, user, vals, context=context)
        move = self.browse(cursor, user, res, context=context)
        if move.journal.centralised:
            line_id = move_line_obj.create(cursor, user, {
                'account': move.journal.credit_account.id,
                'move': move.id,
                'name': 'Centralised Counterpart',
                }, context=context)
            self.write(cursor, user, move.id, {
                'centralised_line': line_id,
                }, context=context)
        if 'lines' in vals:
            self.validate(cursor, user, [res], context=context)
        return res

    def delete(self, cursor, user, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        move_line_obj = self.pool.get('account.move.line')
        for move in self.browse(cursor, user, ids, context=context):
            if move.state == 'posted':
                self.raise_user_error(cursor, 'del_posted_move',
                        context=context)
            if move.lines:
                move_line_ids = [x.id for x in move.lines]
                move_line_obj.delete(cursor, user, move_line_ids,
                        context=context)
        return super(Move, self).delete(cursor, user, ids, context=context)

    def copy(self, cursor, user, ids, default=None, context=None):
        line_obj = self.pool.get('account.move.line')

        int_id = False
        if isinstance(ids, (int, long)):
            int_id = True
            ids = [ids]

        if default is None:
            default = {}
        default = default.copy()
        default['reference'] = False
        default['state'] = self.default_state(cursor, user, context=context)
        default['post_date'] = False
        default['lines'] = False

        new_ids = []
        for move in self.browse(cursor, user, ids, context=context):
            new_id = super(Move, self).copy(cursor, user, move.id,
                    default=default, context=context)
            line_obj.copy(cursor, user, [x.id for x in move.lines], default={
                'move': new_id,
                }, context=context)
            new_ids.append(new_id)

        if int_id:
            return new_ids[0]
        return new_ids

    def validate(self, cursor, user, ids, context=None):
        '''
        Validate balanced move and centralise it if in centralised journal
        '''
        currency_obj = self.pool.get('currency.currency')
        move_line_obj = self.pool.get('account.move.line')
        if isinstance(ids, (int, long)):
            ids = [ids]
        for move in self.browse(cursor, user, ids, context=context):
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
            if not currency_obj.is_zero(cursor, user, company.currency, amount):
                if not move.journal.centralised:
                    move_line_obj.write(cursor, user,
                            [x.id for x in move.lines if x.state != 'draft'], {
                                'state': 'draft',
                                }, context=context)
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
                        centralised_line_id = move_line_obj.create(cursor,
                                user, {
                                    'debit': debit,
                                    'credit': credit,
                                    'account': account_id,
                                    'move': move.id,
                                    'name': 'Centralised Counterpart',
                                    }, context=context)
                        self.write(cursor, user, move.id, {
                            'centralised_line': centralised_line_id,
                            }, context=context)
                    else:
                        move_line_obj.write(cursor, user,
                                move.centralised_line.id, {
                                    'debit': debit,
                                    'credit': credit,
                                    'account': account_id,
                                }, context=context)
                continue
            if not draft_lines:
                continue
            move_line_obj.write(cursor, user,
                    [x.id for x in draft_lines], {
                        'state': 'valid',
                        }, context=context)
        return

    def post(self, cursor, user, ids, context=None):
        currency_obj = self.pool.get('currency.currency')
        sequence_obj = self.pool.get('ir.sequence')
        date_obj = self.pool.get('ir.date')

        if isinstance(ids, (int, long)):
            ids = [ids]

        moves = self.browse(cursor, user, ids, context=context)
        for move in moves:
            amount = Decimal('0.0')
            if not move.lines:
                self.raise_user_error(cursor, 'post_empty_move',
                        context=context)
            company = None
            for line in move.lines:
                amount += line.debit - line.credit
                if not company:
                    company = line.account.company
            if not currency_obj.is_zero(cursor, user, company.currency, amount):
                self.raise_user_error(cursor, 'post_unbalanced_move',
                        context=context)
        for move in moves:
            reference = sequence_obj.get_id(cursor, user,
                    move.period.post_move_sequence.id, context=context)
            self.write(cursor, user, move.id, {
                'reference': reference,
                'state': 'posted',
                'post_date': date_obj.today(cursor, user, context=context),
                }, context=context)
        return

    def draft(self, cursor, user, ids, context=None):
        for move in self.browse(cursor, user, ids, context=context):
            if not move.journal.update_posted:
                self.raise_user_error(cursor, 'modify_posted_move',
                        context=context)
        return self.write(cursor, user, ids, {
            'state': 'draft',
            }, context=context)

    def button_post(self, cursor, user, ids, context=None):
        return self.post(cursor, user, ids, context=None)

    def button_draft(self, cursor, user, ids, context=None):
        return self.draft(cursor, user, ids, context=context)

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

    def default_name(self, cursor, user, context=None):
        sequence_obj = self.pool.get('ir.sequence')
        return sequence_obj.get(cursor, user, 'account.move.reconciliation',
                context=context)

    def create(self, cursor, user, vals, context=None):
        move_line_obj = self.pool.get('account.move.line')
        res = super(Reconciliation, self).create(cursor, user, vals, context=context)
        reconciliation = self.browse(cursor, user, res, context=context)

        move_line_obj.workflow_trigger_trigger(cursor, user,
                [x.id for x in reconciliation.lines], context=context)
        return res

    def write(self, cursor, user, ids, vals, context=None):
        self.raise_user_error(cursor, 'modify', context=context)

    def check_lines(self, cursor, user, ids):
        currency_obj = self.pool.get('currency.currency')
        for reconciliation in self.browse(cursor, user, ids):
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
            if not currency_obj.is_zero(cursor, user, account.company.currency,
                    amount):
                return False
        return True

Reconciliation()


class Line(ModelSQL, ModelView):
    'Account Move Line'
    _name = 'account.move.line'
    _description = __doc__

    name = fields.Char('Name', size=None, required=True)
    debit = fields.Numeric('Debit', digits="(16, currency_digits)",
            on_change=['account', 'debit', 'credit', 'tax_lines',
                'journal', 'move'], depends=['currency_digits', 'credit',
                    'tax_lines', 'journal'])
    credit = fields.Numeric('Credit', digits="(16, currency_digits)",
            on_change=['account', 'debit', 'credit', 'tax_lines',
                'journal', 'move'], depends=['currency_digits', 'debit',
                    'tax_lines', 'journal'])
    account = fields.Many2One('account.account', 'Account', required=True,
            domain=[('kind', '!=', 'view')],
            select=1,
            on_change=['account', 'debit', 'credit', 'tax_lines',
                'journal', 'move'])
    move = fields.Many2One('account.move', 'Move', states=_LINE_STATES,
            select=1, required=True)
    journal = fields.Function('get_move_field', fnct_inv='set_move_field',
            type='many2one', relation='account.journal', string='Journal',
            fnct_search='search_move_field')
    period = fields.Function('get_move_field', fnct_inv='set_move_field',
            type='many2one', relation='account.period', string='Period',
            fnct_search='search_move_field')
    date = fields.Function('get_move_field', fnct_inv='set_move_field',
            type='date', string='Effective Date', required=True,
            fnct_search='search_move_field')
    reference = fields.Char('Reference', size=None)
    amount_second_currency = fields.Numeric('Amount Second Currency',
            digits="(16, second_currency_digits)",
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
        ], 'State', readonly=True, required=True)
    active = fields.Boolean('Active', select=2)
    reconciliation = fields.Many2One('account.move.reconciliation',
            'Reconciliation', readonly=True, ondelete='SET NULL', select=2)
    tax_lines = fields.One2Many('account.tax.line', 'move_line', 'Tax Lines')
    move_state = fields.Function('get_move_field', type='selection',
            selection=[
                ('draft', 'Draft'),
                ('posted', 'Posted'),
            ], string='Move State', fnct_search='search_move_field')
    currency_digits = fields.Function('get_currency_digits', type='integer',
            string='Currency Digits')
    second_currency_digits = fields.Function('get_currency_digits',
            type='integer', string='Second Currency Digits')

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

    def init(self, cursor, module_name):
        super(Line, self).init(cursor, module_name)

        table = TableHandler(cursor, self, module_name)

        # Migration from 1.2
        table.not_null_action('blocked', action='remove')

    def default_date(self, cursor, user, context=None):
        '''
        Return the date of the last line for journal, period
        or the starting date of the period
        or today
        '''
        period_obj = self.pool.get('account.period')
        date_obj = self.pool.get('ir.date')

        if context is None:
            context = {}
        res = date_obj.today(cursor, user, context=context)
        line_ids = self.search(cursor, user, [
            ('journal', '=', context.get('journal', False)),
            ('period', '=', context.get('period', False)),
            ], order=[('id', 'DESC')], limit=1, context=context)
        if line_ids:
            line = self.browse(cursor, user, line_ids[0], context=context)
            res = line.date
        elif context.get('period'):
            period = period_obj.browse(cursor, user, context['period'],
                    context=context)
            res = period.start_date
        if context.get('date'):
            res = context['date']
        return res

    def default_state(self, cursor, user, context=None):
        return 'draft'

    def default_active(self, cursor, user, context=None):
        return True

    def default_currency_digits(self, cursor, user, context=None):
        return 2

    def default_get(self, cursor, user, fields, context=None,
            with_rec_name=True):
        if context is None:
            context = {}
        move_obj = self.pool.get('account.move')
        tax_obj = self.pool.get('account.tax')
        account_obj = self.pool.get('account.account')
        tax_code_obj = self.pool.get('account.tax.code')
        currency_obj = self.pool.get('currency.currency')
        values = super(Line, self).default_get(cursor, user, fields,
                context=context, with_rec_name=with_rec_name)

        if 'move' not in fields:
            #Not manual entry
            if 'date' in values:
                values = values.copy()
                del values['date']
            return values

        if context.get('journal') and context.get('period'):
            line_ids = self.search(cursor, user, [
                ('move.journal', '=', context['journal']),
                ('move.period', '=', context['period']),
                ('create_uid', '=', user),
                ('state', '=', 'draft'),
                ], order=[('id', 'DESC')], limit=1, context=context)
            if not line_ids:
                return values
            line = self.browse(cursor, user, line_ids[0], context=context)
            values['move'] = line.move.id

        if 'move' not in values:
            return values

        move = move_obj.browse(cursor, user, values['move'], context=context)
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
                        taxes.setdefault((account_id, code_id), False)
                for tax_line in line.tax_lines:
                    taxes[(line.account.id, tax_line.code.id)] = True
                if not line.tax_lines and line.account.taxes:
                    if line.account.id in no_code_taxes:
                        taxes[(line.account.id, False)] = True
                    else:
                        no_code_taxes.append(line.account.id)
                elif not line.tax_lines:
                    taxes[(line.account.id, False)] = True

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
            for account_id, code_id in taxes:
                if taxes[(account_id, code_id)]:
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
                    for tax_line in tax_obj.compute(cursor, user,
                            [x.id for x in line.account.taxes],
                            line.debit or line.credit, 1, context=context):
                        if (tax_line['tax'][key + '_account'].id \
                                or line.account.id) == account_id \
                            and tax_line['tax'][key + '_tax_code'].id \
                                    == code_id:
                            if line.debit:
                                line_amount += tax_line['amount']
                            else:
                                line_amount -= tax_line['amount']
                            tax_amount += tax_line['amount'] * \
                                    tax_line['tax'][key + '_tax_sign']
                    line_amount = currency_obj.round(cursor, user,
                            line.account.company.currency, line_amount)
                    tax_amount = currency_obj.round(cursor, user,
                            line.account.company.currency, tax_amount)
                    if ('debit' in fields):
                        values['debit'] = line_amount > Decimal('0.0') \
                                and line_amount or Decimal('0.0')
                    if ('credit' in fields):
                        values['credit'] = line_amount < Decimal('0.0') \
                                and - line_amount or Decimal('0.0')
                    if 'account' in fields:
                        values['account'] = account_id
                        values['account.rec_name'] = account_obj.browse(cursor,
                                user, account_id, context=context).rec_name
                    if 'tax_lines' in fields and code_id:
                        values['tax_lines'] = [
                            {
                                'amount': tax_amount,
                                'currency_digits': line.currency_digits,
                                'code': code_id,
                                'code.rec_name': tax_code_obj.browse(cursor,
                                    user, code_id, context=context).rec_name,
                            },
                        ]
        return values

    def get_currency_digits(self, cursor, user, ids, names, arg, context=None):
        res = {}
        for line in self.browse(cursor, user, ids, context=context):
            for name in names:
                res.setdefault(name, {})
                res[name].setdefault(line.id, 2)
                if name == 'currency_digits':
                    res[name][line.id] = line.account.currency_digits
                elif name == 'second_currency_digits':
                    if line.account.second_currency:
                        res[name][line.id] = line.account.second_currency.digits
        return res

    def on_change_debit(self, cursor, user, ids, vals, context=None):
        res = {}
        if context is None:
            context = {}
        journal_obj = self.pool.get('account.journal')
        if vals.get('journal') or context.get('journal'):
            journal = journal_obj.browse(cursor, user,
                    vals.get('journal') or context.get('journal'),
                    context=context)
            if journal.type in ('expense', 'revenue'):
                res['tax_lines'] = self._compute_tax_lines(cursor, user,
                        ids, vals, journal.type, context=context)
                if not res['tax_lines']:
                    del res['tax_lines']
        if vals.get('debit'):
            res['credit'] = Decimal('0.0')
        return res

    def on_change_credit(self, cursor, user, ids, vals, context=None):
        res = {}
        if context is None:
            context = {}
        journal_obj = self.pool.get('account.journal')
        if vals.get('journal') or context.get('journal'):
            journal = journal_obj.browse(cursor, user,
                    vals.get('journal') or context.get('journal'),
                    context=context)
            if journal.type in ('expense', 'revenue'):
                res['tax_lines'] = self._compute_tax_lines(cursor, user,
                        ids, vals, journal.type, context=context)
                if not res['tax_lines']:
                    del res['tax_lines']
        if vals.get('credit'):
            res['debit'] = Decimal('0.0')
        return res

    def on_change_account(self, cursor, user, ids, vals, context=None):
        account_obj = self.pool.get('account.account')
        journal_obj = self.pool.get('account.journal')

        res = {}
        if context is None:
            context = {}

        if context.get('journal'):
            journal = journal_obj.browse(cursor, user,
                    context['journal'], context=context)
            if journal.type in ('expense', 'revenue'):
                res['tax_lines'] = self._compute_tax_lines(cursor, user,
                        ids, vals, journal.type, context=context)
                if not res['tax_lines']:
                    del res['tax_lines']

        if vals.get('account'):
            account = account_obj.browse(cursor, user, vals['account'],
                    context=context)
            res['currency_digits'] = account.currency_digits
            if account.second_currency:
                res['second_currency_digits'] = account.second_currency.digits
        return res

    def _compute_tax_lines(self, cursor, user, ids, vals, journal_type,
            context=None):
        res = {}
        account_obj = self.pool.get('account.account')
        tax_code_obj = self.pool.get('account.tax.code')
        tax_obj = self.pool.get('account.tax')
        move_obj = self.pool.get('account.move')
        if vals.get('move'):
            #Only for first line
            return res
        if vals.get('tax_lines'):
            res['remove'] = [x['id'] for x in vals['tax_lines']]
        if vals.get('account'):
            account = account_obj.browse(cursor, user, vals['account'],
                    context=context)
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
                for tax_line in tax_obj.compute(cursor, user,
                        [x.id for x in account.taxes],
                        debit or credit, 1, context=context):
                    code_id = tax_line['tax'][key + '_base_code'].id
                    base_amounts.setdefault(code_id, Decimal('0.0'))
                    base_amounts[code_id] += tax_line['base'] * \
                            tax_line['tax'][key + '_tax_sign']
                for code_id in base_amounts:
                    if not code_id:
                        continue
                    res.setdefault('add', []).append({
                        'amount': base_amounts[code_id],
                        'currency_digits': account.currency_digits,
                        'code': code_id,
                        'code.rec_name': tax_code_obj.browse(cursor, user,
                            code_id, context=context).rec_name,
                    })
        return res

    def on_change_party(self, cursor, user, ids, vals, context=None):
        party_obj = self.pool.get('party.party')
        journal_obj = self.pool.get('account.journal')
        account_obj = self.pool.get('account.account')
        currency_obj = self.pool.get('currency.currency')
        res = {}
        if (not vals.get('party')) or vals.get('account'):
            return res
        party = party_obj.browse(cursor, user, vals.get('party'),
                context=context)

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
                amout = Decimal(str(amount))
            if not currency_obj.is_zero(cursor, user,
                    party.account_receivable.currency, amount):
                if amount > Decimal('0.0'):
                    res['credit'] = currency_obj.round(cursor, user,
                            party.account_receivable.currency, amount)
                    res['debit'] = Decimal('0.0')
                else:
                    res['credit'] = Decimal('0.0')
                    res['debit'] = - currency_obj.round(cursor, user,
                            party.account_receivable.currency, amount)
                res['account'] = party.account_receivable.id
                res['account.rec_name'] = party.account_receivable.rec_name
            else:
                cursor.execute(query, (party.id, party.account_payable.id))
                amount = cursor.fetchone()[0]
                if not currency_obj.is_zero(cursor, user,
                        party.account_payable.currency, amount):
                    if amount > Decimal('0.0'):
                        res['credit'] = currency_obj.round(cursor, user,
                                party.account_payable.currency, amount)
                        res['debit'] = Decimal('0.0')
                    else:
                        res['credit'] = Decimal('0.0')
                        res['debit'] = - currency_obj.round(cursor, user,
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

        journal_id = vals.get('journal') or context.get('journal')
        if journal_id and party:
            journal = journal_obj.browse(cursor, user, journal_id,
                    context=context)
            if journal.type == 'revenue':
                if 'account' not in res:
                    res['account'] = party.account_receivable.id
                    res['account.rec_name'] = party.account_receivable.rec_name
            elif journal.type == 'expense':
                if 'account' not in res:
                    res['account'] = party.account_payable.id
                    res['account.rec_name'] = party.account_payable.rec_name
        return res

    def get_move_field(self, cursor, user, ids, name, arg, context=None):
        if name == 'move_state':
            name = 'state'
        if name not in ('period', 'journal', 'date', 'state'):
            raise Exception('Invalid name')
        res = {}
        for line in self.browse(cursor, user, ids, context=context):
            if name in ('date', 'state'):
                res[line.id] = line.move[name]
            else:
                res[line.id] = line.move[name].id
        return res

    def set_move_field(self, cursor, user, id, name, value, arg, context=None):
        if name == 'move_state':
            name = 'state'
        if name not in ('period', 'journal', 'date', 'state'):
            raise Exception('Invalid name')
        if not value:
            return
        move_obj = self.pool.get('account.move')
        line = self.browse(cursor, user, id, context=context)
        move_obj.write(cursor, user, line.move.id, {
            name: value,
            }, context=context)

    def search_move_field(self, cursor, user, name, args, context=None):
        args2 = []
        i = 0
        while i < len(args):
            field = args[i][0]
            if args[i][0] == 'move_state':
                field = 'state'
            args2.append(('move.' + field, args[i][1], args[i][2]))
            i += 1
        return args2

    def query_get(self, cursor, user, obj='l', context=None):
        '''
        Return SQL clause and fiscal years for account move line
        depending of the context.

        :param cursor: the database cursor
        :param user: the user id
        :param obj: the SQL alias of account_move_line in the query
        :param context: the context
        :return: a tuple with the SQL clause and the fiscalyear ids
        '''
        fiscalyear_obj = self.pool.get('account.fiscalyear')
        if context is None:
            context = {}

        if context.get('date'):
            mx.DateTime.strptime(str(context['date']), '%Y-%m-%d')
            fiscalyear_ids = fiscalyear_obj.search(cursor, user, [
                ('start_date', '<=', context['date']),
                ('end_date', '>=', context['date']),
                ], limit=1, context=context)
            if not fiscalyear_ids:
                fiscalyear_ids = [0]
            if context.get('posted'):
                return (obj + '.active ' \
                        'AND ' + obj + '.state != \'draft\' ' \
                        'AND ' + obj + '.move IN (' \
                            'SELECT m.id FROM account_move AS m, ' \
                                'account_period AS p ' \
                                'WHERE m.period = p.id ' \
                                    'AND p.fiscalyear = ' + \
                                        str(fiscalyear_ids[0]) + ' ' \
                                    'AND m.date <= date(\'' + \
                                        str(context['date']) + '\') ' \
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
                                        str(fiscalyear_ids[0]) + ' ' \
                                    'AND m.date <= date(\'' + \
                                        str(context['date']) + '\')' \
                            ')', fiscalyear_ids)

        if not context.get('fiscalyear', False):
            fiscalyear_ids = fiscalyear_obj.search(cursor, user, [
                ('state', '=', 'open'),
                ], context=context)
            fiscalyear_clause = (','.join(map(str, fiscalyear_ids))) or '0'
        else:
            fiscalyear_ids = [int(context.get('fiscalyear'))]
            fiscalyear_clause = '%s' % int(context.get('fiscalyear'))

        if context.get('periods', False):
            ids = ','.join(str(int(x)) for x in context['periods'])
            if context.get('posted'):
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
            if context.get('posted'):
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

    def on_write(self, cursor, user, ids, context=None):
        lines = self.browse(cursor, user, ids, context)
        res = []
        for line in lines:
            res.extend([x.id for x in line.move.lines])
        return list({}.fromkeys(res))

    def check_account(self, cursor, user, ids):
        for line in self.browse(cursor, user, ids):
            if line.account.kind in ('view',):
                return False
            if not line.account.active:
                return False
        return True

    def check_journal_period_modify(self, cursor, user, period_id,
            journal_id, context=None):
        '''
        Check if the lines can be modified or created for the journal - period
        and if there is no journal - period, create it
        '''
        journal_period_obj = self.pool.get('account.journal.period')
        journal_obj = self.pool.get('account.journal')
        period_obj = self.pool.get('account.period')
        journal_period_ids = journal_period_obj.search(cursor, user, [
            ('journal', '=', journal_id),
            ('period', '=', period_id),
            ], limit=1, context=context)
        if journal_period_ids:
            journal_period = journal_period_obj.browse(cursor, user,
                    journal_period_ids[0], context=context)
            if journal_period.state == 'close':
                self.raise_user_error(cursor,
                        'add_modify_closed_journal_period', context=context)
        else:
            journal = journal_obj.browse(cursor, user, journal_id,
                    context=context)
            period = period_obj.browse(cursor, user, period_id,
                    context=context)
            journal_period_obj.create(cursor, user, {
                'name': journal.name + ' - ' + period.name,
                'journal': journal.id,
                'period': period.id,
                }, context=context)
        return

    def check_modify(self, cursor, user, ids, context=None):
        '''
        Check if the lines can be modified
        '''
        journal_period_done = []
        for line in self.browse(cursor, user, ids, context=context):
            if line.move.state == 'posted':
                self.raise_user_error(cursor, 'modify_posted_move',
                        context=context)
            if line.reconciliation:
                self.raise_user_error(cursor, 'modify_reconciled',
                        context=context)
            journal_period = (line.journal.id, line.period.id)
            if journal_period not in journal_period_done:
                self.check_journal_period_modify(cursor, user, line.period.id,
                        line.journal.id, context=context)
                journal_period_done.append(journal_period)
        return

    def delete(self, cursor, user, ids, context=None):
        move_obj = self.pool.get('account.move')
        if isinstance(ids, (int, long)):
            ids = [ids]
        self.check_modify(cursor, user, ids, context=context)
        lines = self.browse(cursor, user, ids, context=context)
        move_ids = [x.move.id for x in lines]
        res = super(Line, self).delete(cursor, user, ids, context=context)
        move_obj.validate(cursor, user, move_ids, context=context)
        return res

    def write(self, cursor, user, ids, vals, context=None):
        move_obj = self.pool.get('account.move')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        if len(vals) > 1 or 'reconciliation' not in vals:
            self.check_modify(cursor, user, ids, context=context)
        lines = self.browse(cursor, user, ids, context=context)
        move_ids = [x.move.id for x in lines]
        res = super(Line, self).write(cursor, user, ids, vals, context=context)

        if context.get('_timestamp'):
            context = context.copy()
            del context['_timestamp']

        lines = self.browse(cursor, user, ids, context=context)
        for line in lines:
            if line.move.id not in move_ids:
                move_ids.append(line.move.id)
        move_obj.validate(cursor, user, move_ids, context=context)
        return res

    def create(self, cursor, user, vals, context=None):
        if context is None:
            context = {}
        journal_obj = self.pool.get('account.journal')
        move_obj = self.pool.get('account.move')
        vals = vals.copy()
        if not vals.get('move'):
            journal_id = vals.get('journal') or context.get('journal')
            if not journal_id:
                self.raise_user_error(cursor, 'no_journal',
                        context=context)
            journal = journal_obj.browse(cursor, user, journal_id,
                    context=context)
            if journal.centralised:
                move_ids = move_obj.search(cursor, user, [
                    ('period', '=',
                        vals.get('period') or context.get('period')),
                    ('journal', '=', journal_id),
                    ('state', '!=', 'posted'),
                    ], limit=1, context=context)
                if move_ids:
                    vals['move'] = move_ids[0]
            if not vals.get('move'):
                vals['move'] = move_obj.create(cursor, user, {
                    'period': vals.get('period') or context.get('period'),
                    'journal': journal_id,
                    'date': vals.get('date', False),
                    }, context=context)
        res = super(Line, self).create(cursor, user, vals, context=context)
        line = self.browse(cursor, user, res, context=context)
        self.check_journal_period_modify(cursor, user, line.period.id,
                line.journal.id, context=context)
        move_obj.validate(cursor, user, [vals['move']], context=context)
        return res

    def copy(self, cursor, user, ids, default=None, context=None):
        if default is None:
            default = {}
        if 'move' not in default:
            default['move'] = False
        if 'reconciliation' not in default:
            default['reconciliation'] = False
        return super(Line, self).copy(cursor, user, ids, default=default,
                context=context)

    def view_header_get(self, cursor, user, value, view_type='form',
            context=None):
        journal_period_obj = self.pool.get('account.journal.period')
        if context is None:
            context = {}
        if not context.get('journal') or not context.get('period'):
            return value
        journal_period_ids = journal_period_obj.search(cursor, user, [
            ('journal', '=', context['journal']),
            ('period', '=', context['period']),
            ], context=context, limit=1)
        if not journal_period_ids:
            return value
        journal_period = journal_period_obj.browse(cursor, user,
                journal_period_ids[0], context=context)
        return value + ': ' + journal_period.rec_name

    def fields_view_get(self, cursor, user, view_id=None, view_type='form',
            context=None, toolbar=False, hexmd5=None):
        if context is None:
            context = {}
        journal_obj = self.pool.get('account.journal')
        result = super(Line, self).fields_view_get(cursor, user,
                view_id=view_id, view_type=view_type, context=context,
                toolbar=toolbar, hexmd5=hexmd5)
        if view_type == 'tree' and 'journal' in context:
            title = self.view_header_get(cursor, user, '',
                    view_type=view_type, context=context)
            journal = journal_obj.browse(cursor, user, context['journal'],
                    context=context)

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
            result['fields'] = self.fields_get(cursor, user,
                    fields_names=list(fields), context=context)
            del result['md5']
            result['md5'] = md5.new(str(result)).hexdigest()
            if hexmd5 == result['md5']:
                return True
        return result

    def reconcile(self, cursor, user, ids, journal_id=False, date=False,
            account_id=False, context=None):
        move_obj = self.pool.get('account.move')
        currency_obj = self.pool.get('currency.currency')
        reconciliation_obj = self.pool.get('account.move.reconciliation')
        period_obj = self.pool.get('account.period')
        date_obj = self.pool.get('ir.date')
        translation_obj = self.pool.get('ir.translation')

        for line in self.browse(cursor, user, ids, context=context):
            if line.reconciliation:
                self.raise_user_error(cursor, 'already_reconciled',
                        error_args=(line.name, line.id,), context=context)

        ids = ids[:]
        if journal_id and account_id:
            if not date:
                date = date_obj.today(cursor, user, context=context)
            account = None
            amount = Decimal('0.0')
            for line in self.browse(cursor, user, ids, context=context):
                amount += line.debit - line.credit
                if not account:
                    account = line.account
            amount = currency_obj.round(cursor, user, account.currency, amount)
            period_id = period_obj.find(cursor, user, account.company.id,
                    date=date, context=context)
            lang_code = 'en_US'
            if account.company.lang:
                lang_code = account.company.lang.code
            writeoff = translation_obj._get_source(cursor,
                    'account.move.reconcile_lines.writeoff', 'view',
                    lang_code, 'Write-Off') or 'Write-Off'
            move_id = move_obj.create(cursor, user, {
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
                }, context=context)
            ids += self.search(cursor, user, [
                ('move', '=', move_id),
                ('account', '=', account.id),
                ('debit', '=', amount < Decimal('0.0') and - amount \
                        or Decimal('0.0')),
                ('credit', '=', amount > Decimal('0.0') and amount \
                        or Decimal('0.0')),
                ], limit=1, context=context)
        return reconciliation_obj.create(cursor, user, {
            'lines': [('add', x) for x in ids],
            }, context=context)

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
            domain=[('state', '!=', 'close'),
                "('fiscalyear.company.id', '=', context.get('company', False))"])

    def default_period(self, cursor, user, context=None):
        period_obj = self.pool.get('account.period')
        if context is None:
            context = {}
        return period_obj.find(cursor, user, context.get('company', False),
                exception=False, context=context)

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

    def _next(self, cursor, user, data, context=None):
        if data.get('model', '') == 'account.journal.period' \
                and data.get('id'):
            return 'open'
        return 'ask'

    def _get_journal_period(self, cursor, user, data, context=None):
        journal_period_obj = self.pool.get('account.journal.period')
        if data.get('model', '') == 'account.journal.period' \
                and data.get('id'):
            journal_period = journal_period_obj.browse(cursor, user,
                    data['id'], context=context)
            return {
                'journal': journal_period.journal.id,
                'period': journal_period.period.id,
            }
        return {}

    def _action_open_journal(self, cursor, user, data, context=None):
        journal_period_obj = self.pool.get('account.journal.period')
        journal_obj = self.pool.get('account.journal')
        period_obj = self.pool.get('account.period')
        model_data_obj = self.pool.get('ir.model.data')
        act_window_obj = self.pool.get('ir.action.act_window')
        if data.get('model', '') == 'account.journal.period' \
                and data.get('id'):
            journal_period = journal_period_obj.browse(cursor, user,
                    data['id'], context=context)
            journal_id = journal_period.journal.id
            period_id = journal_period.period.id
        else:
            journal_id = data['form']['journal']
            period_id = data['form']['period']
        if not journal_period_obj.search(cursor, user, [
            ('journal', '=', journal_id),
            ('period', '=', period_id),
            ], context=context):
            journal = journal_obj.browse(cursor, user, journal_id,
                    context=context)
            period = period_obj.browse(cursor, user, period_id,
                    context=context)
            journal_period_obj.create(cursor, user, {
                'name': journal.name + ' - ' + period.name,
                'journal': journal.id,
                'period': period.id,
                }, context=context)

        model_data_ids = model_data_obj.search(cursor, user, [
            ('fs_id', '=', 'act_move_line_form'),
            ('module', '=', 'account'),
            ('inherit', '=', False),
            ], limit=1, context=context)
        model_data = model_data_obj.browse(cursor, user, model_data_ids[0],
                context=context)
        res = act_window_obj.read(cursor, user, model_data.db_id, context=context)
        # Remove name to use the one from view_header_get
        del res['name']
        res['domain'] = str([
            ('journal', '=', journal_id),
            ('period', '=', period_id),
            ])
        res['context'] = str({
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

    def _action_open_account(self, cursor, user, data, context=None):
        if context is None:
            context = {}
        model_data_obj = self.pool.get('ir.model.data')
        act_window_obj = self.pool.get('ir.action.act_window')
        fiscalyear_obj = self.pool.get('account.fiscalyear')

        if not context.get('fiscalyear'):
            fiscalyear_ids = fiscalyear_obj.search(cursor, user, [
                ('state', '=', 'open'),
                ], context=context)
        else:
            fiscalyear_ids = [context['fiscalyear']]

        period_ids = []
        for fiscalyear in fiscalyear_obj.browse(cursor, user, fiscalyear_ids,
                context=context):
            for period in fiscalyear.periods:
                period_ids.append(period.id)

        model_data_ids = model_data_obj.search(cursor, user, [
            ('fs_id', '=', 'act_move_line_form'),
            ('module', '=', 'account'),
            ('inherit', '=', False),
            ], limit=1, context=context)
        model_data = model_data_obj.browse(cursor, user, model_data_ids[0],
                context=context)
        res = act_window_obj.read(cursor, user, model_data.db_id, context=context)
        res['domain'] = [
            ('period', 'in', period_ids),
            ('account', '=', data['id']),
            ]
        if context.get('posted'):
            res['domain'].append(('move.state', '=', 'posted'))
        res['domain'] = str(res['domain'])
        res['context'] = str({'fiscalyear': context.get('fiscalyear')})
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

    def default_date(self, cursor, user, context=None):
        date_obj = self.pool.get('ir.date')
        return date_obj.today(cursor, user, context=context)

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

    def _check_writeoff(self, cursor, user, data, context=None):
        line_obj = self.pool.get('account.move.line')
        currency_obj = self.pool.get('currency.currency')

        company = None
        amount = Decimal('0.0')
        for line in line_obj.browse(cursor, user, data['ids'],
                context=context):
            amount += line.debit - line.credit
            if not company:
                company = line.account.company
        if not company:
            return 'end'
        if currency_obj.is_zero(cursor, user, company.currency, amount):
            return 'reconcile'
        return 'writeoff'

    def _reconcile(self, cursor, user, data, context=None):
        line_obj = self.pool.get('account.move.line')

        if data['form']:
            journal_id = data['form'].get('journal')
            date = data['form'].get('date')
            account_id = data['form'].get('account')
        else:
            journal_id = False
            date = False
            account_id = False
        line_obj.reconcile(cursor, user, data['ids'], journal_id, date,
                account_id, context=context)
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

    def _unreconcile(self, cursor, user, data, context=None):
        line_obj = self.pool.get('account.move.line')
        reconciliation_obj = self.pool.get('account.move.reconciliation')

        lines = line_obj.browse(cursor, user, data['ids'], context=context)
        reconciliation_ids = [x.reconciliation.id for x in lines \
                if x.reconciliation]
        if reconciliation_ids:
            reconciliation_obj.delete(cursor, user, reconciliation_ids,
                    context=context)
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

    def _action_open_reconcile_lines(self, cursor, user, data, context=None):
        model_data_obj = self.pool.get('ir.model.data')
        act_window_obj = self.pool.get('ir.action.act_window')

        model_data_ids = model_data_obj.search(cursor, user, [
            ('fs_id', '=', 'act_move_line_form'),
            ('module', '=', 'account'),
            ('inherit', '=', False),
            ], limit=1, context=context)
        model_data = model_data_obj.browse(cursor, user, model_data_ids[0],
                context=context)
        res = act_window_obj.read(cursor, user, model_data.db_id, context=context)
        res['domain'] = str([
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

    def default_from_date(self, cursor, user, context=None):
        date_obj = self.pool.get('ir.date')
        return datetime.date(
                date_obj.today(cursor, user, context=context).year, 1, 1)

    def default_to_date(self, cursor, user, context=None):
        date_obj = self.pool.get('ir.date')
        return date_obj.today(cursor, user, context=context)

    def default_company(self, cursor, user, context=None):
        if context is None:
            context = {}
        company_obj = self.pool.get('company.company')
        if context.get('company'):
            return context['company']
        return False

    def default_posted(self, cursor, user, context=None):
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

    def _get_objects(self, cursor, user, ids, model, datas, context):
        move_obj = self.pool.get('account.move')

        clause = [
            ('date', '>=', datas['form']['from_date']),
            ('date', '<=', datas['form']['to_date']),
            ]
        if datas['form']['posted']:
            clause.append(('state', '=', 'posted'))
        move_ids = move_obj.search(cursor, user, clause,
                order=[('date', 'ASC'), ('reference', 'ASC'), ('id', 'ASC')],
                context=context)
        return move_obj.browse(cursor, user, move_ids, context=context)

    def parse(self, cursor, user, report, objects, datas, context):
        if context is None:
            context = {}
        company_obj = self.pool.get('company.company')
        context = context.copy()

        company = company_obj.browse(cursor, user,
                datas['form']['company'], context=context)

        context['company'] = company
        context['digits'] = company.currency.digits
        context['from_date'] = datas['form']['from_date']
        context['to_date'] = datas['form']['to_date']

        return super(GeneralJournal, self).parse(cursor, user, report,
                objects, datas, context)

GeneralJournal()
