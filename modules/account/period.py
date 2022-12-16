#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields, OPERATORS
from trytond.wizard import Wizard
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.pool import Pool

_STATES = {
    'readonly': Eval('state') == 'close',
}
_DEPENDS = ['state']


class Period(ModelSQL, ModelView):
    'Period'
    _name = 'account.period'
    _description = __doc__

    name = fields.Char('Name', required=True)
    code = fields.Char('Code')
    start_date = fields.Date('Starting Date', required=True, states=_STATES,
        depends=_DEPENDS, select=1)
    end_date = fields.Date('Ending Date', required=True, states=_STATES,
        depends=_DEPENDS, select=1)
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
        required=True, states=_STATES, depends=_DEPENDS, select=1)
    state = fields.Selection([
        ('open', 'Open'),
        ('close', 'Close'),
        ], 'State', readonly=True, required=True)
    post_move_sequence =fields.Many2One('ir.sequence', 'Post Move Sequence',
            required=True, domain=[('code', '=', 'account.move')],
            context={'code': 'account.move'}, states={
            'required': False,
            })
    type = fields.Selection([
            ('standard', 'Standard'),
            ('adjustment', 'Adjustment'),
            ], 'Type', required=True,
        states=_STATES, depends=_DEPENDS, select=1)
    company = fields.Function(fields.Many2One('company.company', 'Company',),
        'get_company', searcher='search_company')

    def __init__(self):
        super(Period, self).__init__()
        self._constraints += [
            ('check_dates', 'periods_overlaps'),
            ('check_fiscalyear_dates', 'fiscalyear_dates'),
            ('check_post_move_sequence', 'check_move_sequence'),
        ]
        self._order.insert(0, ('start_date', 'ASC'))
        self._error_messages.update({
            'no_period_date': 'No period defined for this date!',
            'modify_del_period_moves': 'You can not modify/delete ' \
                    'a period with moves!',
            'create_period_closed_fiscalyear': 'You can not create ' \
                    'a period on a closed fiscal year!',
            'open_period_closed_fiscalyear': 'You can not open ' \
                    'a period from a closed fiscal year!',
            'change_post_move_sequence': 'You can not change ' \
                    'the post move sequence ' \
                    'if there is already posted moves in the period',
            'close_period_non_posted_move': 'You can not close ' \
                    'a period with non posted moves!',
            'periods_overlaps': 'You can not have two overlapping periods!',
            'check_move_sequence': 'You must have different ' \
                    'post move sequences per fiscal year ' \
                    'and in the same company!',
            'fiscalyear_dates': 'The period dates must be in ' \
                    'the fiscal year dates',
            })

    def default_state(self):
        return 'open'

    def default_type(self):
        return 'standard'

    def get_company(self, ids, name):
        result = {}
        for period in self.browse(ids):
            result[period.id] = period.fiscalyear.company.id
        return result

    def search_company(self, name, clause):
        return [('fiscalyear.%s' % name,) + tuple(clause[1:])]

    def check_dates(self, ids):
        cursor = Transaction().cursor
        for period in self.browse(ids):
            if period.type != 'standard':
                continue
            cursor.execute('SELECT id ' \
                    'FROM "' + self._table + '" ' \
                    'WHERE ((start_date <= %s AND end_date >= %s) ' \
                            'OR (start_date <= %s AND end_date >= %s) ' \
                            'OR (start_date >= %s AND end_date <= %s)) ' \
                        'AND fiscalyear = %s ' \
                        'AND type = \'standard\' ' \
                        'AND id != %s',
                    (period.start_date, period.start_date,
                        period.end_date, period.end_date,
                        period.start_date, period.end_date,
                        period.fiscalyear.id, period.id))
            if cursor.fetchone():
                return False
        return True

    def check_fiscalyear_dates(self, ids):
        for period in self.browse(ids):
            if period.start_date < period.fiscalyear.start_date \
                    or period.end_date > period.fiscalyear.end_date:
                return False
        return True

    def check_post_move_sequence(self, ids):
        for period in self.browse(ids):
            if self.search([
                ('post_move_sequence', '=', period.post_move_sequence.id),
                ('fiscalyear', '!=', period.fiscalyear.id),
                ]):
                return False
            if period.post_move_sequence.company \
                    and period.post_move_sequence.company.id != \
                    period.fiscalyear.company.id:
                return False
        return True

    def find(self, company_id, date=None, exception=True, test_state=True):
        '''
        Return the period for the company_id
            at the date or the current date.
        If exception is set the function will raise an exception
            if any period is found.

        :param company_id: the company id
        :param date: the date searched
        :param exception: a boolean to raise or not an exception
        :param test_state: a boolean if true will search on non-closed periods
        :return: the period id found or False
        '''
        date_obj = Pool().get('ir.date')

        if not date:
            date = date_obj.today()
        clause = [
            ('start_date', '<=', date),
            ('end_date', '>=', date),
            ('fiscalyear.company', '=', company_id),
            ('type', '=', 'standard'),
            ]
        if test_state:
            clause.append(('state', '!=', 'close'))
        ids = self.search(clause, order=[('start_date', 'DESC')], limit=1)
        if not ids:
            if exception:
                self.raise_user_error('no_period_date')
            else:
                return False
        return ids[0]

    def _check(self, ids):
        move_obj = Pool().get('account.move')
        if isinstance(ids, (int, long)):
            ids = [ids]
        move_ids = move_obj.search([
            ('period', 'in', ids),
            ], limit=1)
        if move_ids:
            self.raise_user_error('modify_del_period_moves')
        return

    def search(self, args, offset=0, limit=None, order=None, count=False,
            query_string=False):
        args = args[:]
        def process_args(args):
            i = 0
            while i < len(args):
                # add test for xmlrpc and pyson that doesn't handle tuple
                if (isinstance(args[i], tuple) \
                        or (isinstance(args[i], list) and len(args[i]) > 2 \
                        and args[i][1] in OPERATORS)) \
                        and args[i][0] in ('start_date', 'end_date') \
                        and isinstance(args[i][2], (list, tuple)):
                    if not args[i][2][0]:
                        args[i] = ('id', '!=', '0')
                    else:
                        period = self.browse(args[i][2][0])
                        args[i] = (args[i][0], args[i][1], period[args[i][2][1]])
                elif isinstance(args[i], list):
                    process_args(args[i])
                i += 1
        process_args(args)
        return super(Period, self).search(args, offset=offset, limit=limit,
                order=order, count=count, query_string=query_string)

    def create(self, vals):
        fiscalyear_obj = Pool().get('account.fiscalyear')
        vals = vals.copy()
        if vals.get('fiscalyear'):
            fiscalyear = fiscalyear_obj.browse(vals['fiscalyear'])
            if fiscalyear.state == 'close':
                self.raise_user_error('create_period_closed_fiscalyear')
            if not vals.get('post_move_sequence'):
                vals['post_move_sequence'] = fiscalyear.post_move_sequence.id
        return super(Period, self).create(vals)

    def write(self, ids, vals):
        move_obj = Pool().get('account.move')
        for key in vals.keys():
            if key in ('start_date', 'end_date', 'fiscalyear'):
                self._check(ids)
                break
        if vals.get('state') == 'open':
            for period in self.browse(ids):
                if period.fiscalyear.state == 'close':
                    self.raise_user_error('open_period_closed_fiscalyear')
        if vals.get('post_move_sequence'):
            for period in self.browse(ids):
                if period.post_move_sequence and \
                        period.post_move_sequence.id != \
                        vals['post_move_sequence']:
                    if move_obj.search([
                        ('period', '=', period.id),
                        ('state', '=', 'posted'),
                        ]):
                        self.raise_user_error('change_post_move_sequence')
        return super(Period, self).write(ids, vals)

    def delete(self, ids):
        self._check(ids)
        return super(Period, self).delete(ids)

    def close(self, ids):
        journal_period_obj = Pool().get('account.journal.period')
        move_obj = Pool().get('account.move')

        if isinstance(ids, (int, long)):
            ids = [ids]

        if move_obj.search([
            ('period', 'in', ids),
            ('state', '!=', 'posted'),
            ]):
            self.raise_user_error('close_period_non_posted_move')
        #First close the period to be sure
        #it will not have new journal.period created between.
        self.write(ids, {
            'state': 'close',
            })
        journal_period_ids = journal_period_obj.search([
            ('period', 'in', ids),
            ])
        journal_period_obj.close(journal_period_ids)

Period()


class ClosePeriod(Wizard):
    'Close Period'
    _name = 'account.period.close_period'
    states = {
        'init': {
            'actions': ['_close'],
            'result': {
                'type': 'state',
                'state': 'end',
            },
        },
    }

    def _close(self, data):
        period_obj = Pool().get('account.period')
        period_obj.close(data['ids'])
        return {}

ClosePeriod()


class ReOpenPeriod(Wizard):
    'Re-Open Period'
    _name = 'account.period.reopen_period'
    states = {
        'init': {
            'actions': ['_reopen'],
            'result': {
                'type': 'state',
                'state': 'end',
            },
        },
    }

    def _reopen(self, data):
        period_obj = Pool().get('account.period')
        period_obj.write(data['ids'], {
            'state': 'open',
            })
        return {}

ReOpenPeriod()
