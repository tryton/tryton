'Period'

from trytond.osv import fields, OSV, ExceptORM
from trytond.wizard import Wizard
import datetime

_STATES = {
    'readonly': "state == 'close'",
}


class Period(OSV):
    'Period'
    _name = 'account.period'
    _description = __doc__
    _order = 'start_date'

    name = fields.Char('Name', size=None, required=True)
    code = fields.Char('Code', size=None)
    start_date = fields.Date('Starting Date', required=True, states=_STATES)
    end_date = fields.Date('Ending Date', required=True, states=_STATES)
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
            required=True, states=_STATES)
    state = fields.Selection([
        ('open', 'Open'),
        ('close', 'Close'),
        ], 'State', readonly=True, required=True)
    post_move_sequence =fields.Many2One('ir.sequence', 'Post Move Sequence',
            required=True, domain="[('code', '=', 'account.move')]")

    def __init__(self):
        super(Period, self).__init__()
        self._constraints += [
            ('check_dates',
                'Error! You can not have 2 periods that overlaps!',
                ['start_date', 'end_date']),
            ('check_post_move_sequence',
                'Error! You must have different post move sequence ' \
                        'per fiscal year!', ['post_move_sequence']),
        ]

    def default_state(self, cursor, user, context=None):
        return 'open'

    def check_dates(self, cursor, user, ids):
        for period in self.browse(cursor, user, ids):
            cursor.execute('SELECT id ' \
                    'FROM ' + self._table + ' ' \
                    'WHERE ((start_date <= %s AND end_date >= %s) ' \
                            'OR (start_date <= %s AND end_date >= %s) ' \
                            'OR (start_date >= %s AND end_date <= %s)) ' \
                        'AND id != %s',
                    (period.start_date, period.start_date,
                        period.end_date, period.end_date,
                        period.start_date, period.end_date,
                        period.id))
            if cursor.rowcount:
                return False
        return True

    def check_post_move_sequence(self, cursor, user, ids):
        for period in self.browse(cursor, user, ids):
            if self.search(cursor, user, [
                ('post_move_sequence', '=', period.post_move_sequence.id),
                ('fiscalyear', '!=', period.fiscalyear.id),
                ]):
                return False
        return True

    def find(self, cursor, user, date=None, exception=True, context=None):
        '''
        Return the period for the date or the current date.
        If exception is set the function will raise an exception
            if any period is found.
        '''
        if not date:
            date = datetime.date.today()
        ids = self.search(cursor, user, [
            ('start_date', '<=', date),
            ('end_date', '>=', date),
            ], order='start_date DESC', limit=1, context=context)
        if not ids:
            if exception:
                raise ExceptORM('Error', 'No period defined for this date!')
            else:
                return False
        return ids[0]

    def _check(self, cursor, user, ids, context=None):
        move_obj = self.pool.get('account.move')
        move_ids = move_obj.search(cursor, user, [
            ('period', 'in', ids),
            ], limit=1, context=context)
        if move_ids:
            raise ExceptORM('UserError', 'You can not modify/delete ' \
                    'a period with moves!')
        return

    def search(self, cursor, user, args, offset=0, limit=None, order=None,
            context=None, count=False, query_string=False):
        args = args[:]
        i = 0
        while i < len(args):
            if args[i][0] in ('start_date', 'end_date'):
                if isinstance(args[i][2], (list, tuple)):
                    if not args[i][2][0]:
                        args[i] = ('id', '!=', '0')
                    else:
                        period = self.browse(cursor, user, args[i][2][0],
                                context=context)
                        args[i] = (args[i][0], args[i][1], period[args[i][2][1]])
            i += 1
        return super(Period, self).search(cursor, user, args, offset=offset,
                limit=limit, order=order, context=context, count=count,
                query_string=query_string)

    def create(self, cursor, user, vals, context=None):
        fiscalyear_obj = self.pool.get('account.fiscalyear')
        if vals.get('fiscalyear'):
            fiscalyear = fiscalyear_obj.browse(cursor, user, vals['fiscalyear'],
                    context=context)
            if fiscalyear.state == 'close':
                raise ExceptORM('UserError', 'You can not create ' \
                        'a period on a closed fiscal year!')
            if not vals.get('post_move_sequence'):
                vals['post_move_sequence'] = fiscalyear.post_move_sequence.id
        return super(Period, self).create(cursor, user, vals, context=context)

    def write(self, cursor, user, ids, vals, context=None):
        move_obj = self.pool.get('account.move')
        if vals != {'state': 'close'} \
                and vals != {'state': 'open'}:
            self._check(cursor, user, ids, context=context)
        if vals.get('state') == 'open':
            for period in self.browse(cursor, user, ids,
                    context=context):
                if period.fiscalyear.state == 'close':
                    raise ExceptORM('UserError', 'You can not open ' \
                            'a period from a closed fiscal year!')
        if vals.get('post_move_sequence'):
            for period in self.browse(cursor, user, ids, context=context):
                if period.post_move_sequence and \
                        period.post_move_sequence.id != \
                        vals['post_move_sequence']:
                    if move_obj.search(cursor, user, [
                        ('period', '=', period.id),
                        ('state', '=', 'posted'),
                        ], context=context):
                        raise ExceptORM('UserError', 'You can not change ' \
                                'the post move sequence \n' \
                                'if there is already posted move in the period')
        return super(Period, self).write(cursor, user, ids, vals,
                context=context)

    def unlink(self, cursor, user, ids, context=None):
        self._check(cursor, user, ids, context=context)
        return super(Period, self).unlink(cursor, user, ids,
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
            raise ExceptORM('UserError', 'You can not close ' \
                    'a period with non posted moves!')
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
