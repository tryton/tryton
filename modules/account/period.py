#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
'Period'
from trytond.model import ModelView, ModelSQL, fields, OPERATORS
from trytond.wizard import Wizard
from trytond.pyson import Equal, Eval

_STATES = {
    'readonly': Equal(Eval('state'), 'close'),
}


class Period(ModelSQL, ModelView):
    'Period'
    _name = 'account.period'
    _description = __doc__

    name = fields.Char('Name', required=True)
    code = fields.Char('Code')
    start_date = fields.Date('Starting Date', required=True, states=_STATES,
            select=1)
    end_date = fields.Date('Ending Date', required=True, states=_STATES,
            select=1)
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
            required=True, states=_STATES, select=1)
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
        ], 'Type', required=True, states=_STATES, select=1)

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

    def default_state(self, cursor, user, context=None):
        return 'open'

    def default_type(self, cursor, user, context=None):
        return 'standard'

    def check_dates(self, cursor, user, ids):
        for period in self.browse(cursor, user, ids):
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

    def check_fiscalyear_dates(self, cursor, user, ids):
        for period in self.browse(cursor, user, ids):
            if period.start_date < period.fiscalyear.start_date \
                    or period.end_date > period.fiscalyear.end_date:
                return False
        return True

    def check_post_move_sequence(self, cursor, user, ids):
        for period in self.browse(cursor, user, ids):
            if self.search(cursor, user, [
                ('post_move_sequence', '=', period.post_move_sequence.id),
                ('fiscalyear', '!=', period.fiscalyear.id),
                ]):
                return False
            if period.post_move_sequence.company \
                    and period.post_move_sequence.company.id != \
                    period.fiscalyear.company.id:
                return False
        return True

    def find(self, cursor, user, company_id, date=None, exception=True,
            test_state=True, context=None):
        '''
        Return the period for the company_id
            at the date or the current date.
        If exception is set the function will raise an exception
            if any period is found.

        :param cursor: the database cursor
        :param user: the user id
        :param company_id: the company id
        :param date: the date searched
        :param exception: a boolean to raise or not an exception
        :param test_state: a boolean if true will search on non-closed periods
        :param context: the context
        :return: the period id found or False
        '''
        date_obj = self.pool.get('ir.date')

        if not date:
            date = date_obj.today(cursor, user, context=context)
        clause = [
            ('start_date', '<=', date),
            ('end_date', '>=', date),
            ('fiscalyear.company', '=', company_id),
            ('type', '=', 'standard'),
            ]
        if test_state:
            clause.append(('state', '!=', 'close'))
        ids = self.search(cursor, user, clause, order=[('start_date', 'DESC')],
                limit=1, context=context)
        if not ids:
            if exception:
                self.raise_user_error(cursor, 'no_period_date',
                        context=context)
            else:
                return False
        return ids[0]

    def _check(self, cursor, user, ids, context=None):
        move_obj = self.pool.get('account.move')
        if isinstance(ids, (int, long)):
            ids = [ids]
        move_ids = move_obj.search(cursor, user, [
            ('period', 'in', ids),
            ], limit=1, context=context)
        if move_ids:
            self.raise_user_error(cursor, 'modify_del_period_moves',
                    context=context)
        return

    def search(self, cursor, user, args, offset=0, limit=None, order=None,
            context=None, count=False, query_string=False):
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
                        period = self.browse(cursor, user, args[i][2][0],
                                context=context)
                        args[i] = (args[i][0], args[i][1], period[args[i][2][1]])
                elif isinstance(args[i], list):
                    process_args(args[i])
                i += 1
        process_args(args)
        return super(Period, self).search(cursor, user, args, offset=offset,
                limit=limit, order=order, context=context, count=count,
                query_string=query_string)

    def create(self, cursor, user, vals, context=None):
        fiscalyear_obj = self.pool.get('account.fiscalyear')
        vals = vals.copy()
        if vals.get('fiscalyear'):
            fiscalyear = fiscalyear_obj.browse(cursor, user, vals['fiscalyear'],
                    context=context)
            if fiscalyear.state == 'close':
                self.raise_user_error(cursor,
                        'create_period_closed_fiscalyear', context=context)
            if not vals.get('post_move_sequence'):
                vals['post_move_sequence'] = fiscalyear.post_move_sequence.id
        return super(Period, self).create(cursor, user, vals, context=context)

    def write(self, cursor, user, ids, vals, context=None):
        move_obj = self.pool.get('account.move')
        for key in vals.keys():
            if key in ('start_date', 'end_date', 'fiscalyear'):
                self._check(cursor, user, ids, context=context)
                break
        if vals.get('state') == 'open':
            for period in self.browse(cursor, user, ids,
                    context=context):
                if period.fiscalyear.state == 'close':
                    self.raise_user_error(cursor,
                            'open_period_closed_fiscalyear', context=context)
        if vals.get('post_move_sequence'):
            for period in self.browse(cursor, user, ids, context=context):
                if period.post_move_sequence and \
                        period.post_move_sequence.id != \
                        vals['post_move_sequence']:
                    if move_obj.search(cursor, user, [
                        ('period', '=', period.id),
                        ('state', '=', 'posted'),
                        ], context=context):
                        self.raise_user_error(cursor,
                                'change_post_move_sequence', context=context)
        return super(Period, self).write(cursor, user, ids, vals,
                context=context)

    def delete(self, cursor, user, ids, context=None):
        self._check(cursor, user, ids, context=context)
        return super(Period, self).delete(cursor, user, ids,
                context=context)

    def close(self, cursor, user, ids, context=None):
        journal_period_obj = self.pool.get('account.journal.period')
        move_obj = self.pool.get('account.move')

        if isinstance(ids, (int, long)):
            ids = [ids]

        if move_obj.search(cursor, user, [
            ('period', 'in', ids),
            ('state', '!=', 'posted'),
            ], context=context):
            self.raise_user_error(cursor, 'close_period_non_posted_move',
                    context=context)
        #First close the period to be sure
        #it will not have new journal.period created between.
        self.write(cursor, user, ids, {
            'state': 'close',
            }, context=context)
        journal_period_ids = journal_period_obj.search(cursor, user, [
            ('period', 'in', ids),
            ], context=context)
        journal_period_obj.close(cursor, user, journal_period_ids,
                context=context)
        return

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

    def _close(self, cursor, user, data, context=None):
        period_obj = self.pool.get('account.period')
        period_obj.close(cursor, user, data['ids'], context=context)
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

    def _reopen(self, cursor, user, data, context=None):
        period_obj = self.pool.get('account.period')
        period_obj.write(cursor, user, data['ids'], {
            'state': 'open',
            }, context=context)
        return {}

ReOpenPeriod()
