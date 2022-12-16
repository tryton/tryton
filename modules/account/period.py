# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.i18n import gettext
from trytond.model import ModelView, ModelSQL, Workflow, fields
from trytond.model.exceptions import AccessError
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.const import OPERATORS

from .exceptions import (PeriodNotFoundError, ClosePeriodError,
    PeriodDatesError, PeriodSequenceError)

_STATES = {
    'readonly': Eval('state') != 'open',
}
_DEPENDS = ['state']


class Period(Workflow, ModelSQL, ModelView):
    'Period'
    __name__ = 'account.period'
    name = fields.Char('Name', required=True)
    start_date = fields.Date('Starting Date', required=True, states=_STATES,
        domain=[('start_date', '<=', Eval('end_date', None))],
        depends=_DEPENDS + ['end_date'], select=True)
    end_date = fields.Date('Ending Date', required=True, states=_STATES,
        domain=[('end_date', '>=', Eval('start_date', None))],
        depends=_DEPENDS + ['start_date'], select=True)
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
        required=True, states=_STATES, depends=_DEPENDS, select=True)
    state = fields.Selection([
            ('open', 'Open'),
            ('close', 'Close'),
            ('locked', 'Locked'),
            ], 'State', readonly=True, required=True)
    post_move_sequence = fields.Many2One('ir.sequence', 'Post Move Sequence',
        domain=[
            ('code', '=', 'account.move'),
            ['OR',
                ('company', '=', None),
                ('company', '=', Eval('company', -1)),
                ],
            ],
        depends=['company'])
    type = fields.Selection([
            ('standard', 'Standard'),
            ('adjustment', 'Adjustment'),
            ], 'Type', required=True,
        states=_STATES, depends=_DEPENDS, select=True)
    company = fields.Function(fields.Many2One('company.company', 'Company',),
        'on_change_with_company', searcher='search_company')
    icon = fields.Function(fields.Char("Icon"), 'get_icon')

    @classmethod
    def __setup__(cls):
        super(Period, cls).__setup__()
        cls._order.insert(0, ('start_date', 'ASC'))
        cls._transitions |= set((
                ('open', 'close'),
                ('close', 'locked'),
                ('close', 'open'),
                ))
        cls._buttons.update({
                'close': {
                    'invisible': Eval('state') != 'open',
                    'depends': ['state'],
                    },
                'reopen': {
                    'invisible': Eval('state') != 'close',
                    'depends': ['state'],
                    },
                'lock': {
                    'invisible': Eval('state') != 'close',
                    'depends': ['state'],
                    },
                })

    @staticmethod
    def default_state():
        return 'open'

    @staticmethod
    def default_type():
        return 'standard'

    @fields.depends('fiscalyear', '_parent_fiscalyear.company')
    def on_change_with_company(self, name=None):
        if self.fiscalyear:
            return self.fiscalyear.company.id

    @classmethod
    def search_company(cls, name, clause):
        return [('fiscalyear.' + clause[0],) + tuple(clause[1:])]

    def get_icon(self, name):
        return {
            'open': 'tryton-account-open',
            'close': 'tryton-account-close',
            'locked': 'tryton-account-block',
            }.get(self.state)

    @classmethod
    def validate(cls, periods):
        super(Period, cls).validate(periods)
        for period in periods:
            period.check_dates()
            period.check_fiscalyear_dates()
            period.check_post_move_sequence()

    def check_dates(self):
        if self.type != 'standard':
            return True
        transaction = Transaction()
        connection = transaction.connection
        transaction.database.lock(connection, self._table)
        table = self.__table__()
        cursor = connection.cursor()
        cursor.execute(*table.select(table.id,
                where=(((table.start_date <= self.start_date)
                        & (table.end_date >= self.start_date))
                    | ((table.start_date <= self.end_date)
                        & (table.end_date >= self.end_date))
                    | ((table.start_date >= self.start_date)
                        & (table.end_date <= self.end_date)))
                & (table.fiscalyear == self.fiscalyear.id)
                & (table.type == 'standard')
                & (table.id != self.id)))
        period_id = cursor.fetchone()
        if period_id:
            overlapping_period = self.__class__(period_id[0])
            raise PeriodDatesError(
                gettext('account.msg_period_overlap',
                    first=self.rec_name,
                    second=overlapping_period.rec_name))

    def check_fiscalyear_dates(self):
        if (self.start_date < self.fiscalyear.start_date
                or self.end_date > self.fiscalyear.end_date):
            raise PeriodDatesError(
                gettext('account.msg_period_fiscalyear_dates',
                    period=self.rec_name,
                    fiscalyear=self.fiscalyear.rec_name))

    def check_post_move_sequence(self):
        if not self.post_move_sequence:
            return
        periods = self.search([
                ('post_move_sequence', '=', self.post_move_sequence.id),
                ('fiscalyear', '!=', self.fiscalyear.id),
                ])
        if periods:
            raise PeriodSequenceError(
                gettext('account.msg_period_same_sequence',
                    first=self.rec_name,
                    second=periods[0].rec_name))

    @classmethod
    def find(cls, company_id, date=None, exception=True, test_state=True):
        '''
        Return the period for the company_id
            at the date or the current date.
        If exception is set the function will raise an exception
            if no period is found.
        If test_state is true, it will search on non-closed periods
        '''
        pool = Pool()
        Date = pool.get('ir.date')
        Lang = pool.get('ir.lang')

        if not date:
            date = Date.today()
        clause = [
            ('start_date', '<=', date),
            ('end_date', '>=', date),
            ('fiscalyear.company', '=', company_id),
            ('type', '=', 'standard'),
            ]
        if test_state:
            clause.append(('state', '=', 'open'))
        periods = cls.search(clause, order=[('start_date', 'DESC')], limit=1)
        if not periods:
            if exception:
                lang = Lang.get()
                raise PeriodNotFoundError(
                    gettext('account.msg_no_period_date',
                        date=lang.strftime(date)))
            else:
                return None
        return periods[0].id

    @classmethod
    def _check(cls, periods):
        Move = Pool().get('account.move')
        moves = Move.search([
                ('period', 'in', [p.id for p in periods]),
                ], limit=1)
        if moves:
            raise AccessError(
                gettext('account.msg_modify_delete_period_moves',
                    period=moves[0].period.rec_name))

    @classmethod
    def search(cls, args, offset=0, limit=None, order=None, count=False,
            query=False):
        args = args[:]

        def process_args(args):
            i = 0
            while i < len(args):
                # add test for xmlrpc and pyson that doesn't handle tuple
                if ((
                            isinstance(args[i], tuple)
                            or (isinstance(args[i], list) and len(args[i]) > 2
                                and args[i][1] in OPERATORS))
                        and args[i][0] in ('start_date', 'end_date')
                        and isinstance(args[i][2], (list, tuple))):
                    if not args[i][2][0]:
                        args[i] = ('id', '!=', '0')
                    else:
                        period = cls(args[i][2][0])
                        args[i] = (args[i][0], args[i][1],
                            getattr(period, args[i][2][1]))
                elif isinstance(args[i], list):
                    process_args(args[i])
                i += 1
        process_args(args)
        return super(Period, cls).search(args, offset=offset, limit=limit,
            order=order, count=count, query=query)

    @classmethod
    def create(cls, vlist):
        FiscalYear = Pool().get('account.fiscalyear')
        vlist = [x.copy() for x in vlist]
        for vals in vlist:
            if vals.get('fiscalyear'):
                fiscalyear = FiscalYear(vals['fiscalyear'])
                if fiscalyear.state != 'open':
                    raise AccessError(
                        gettext('account.msg_create_period_closed_fiscalyear',
                            fiscalyear=fiscalyear.rec_name))
                if not vals.get('post_move_sequence'):
                    vals['post_move_sequence'] = (
                        fiscalyear.post_move_sequence.id)
        return super(Period, cls).create(vlist)

    @classmethod
    def write(cls, *args):
        Move = Pool().get('account.move')
        actions = iter(args)
        args = []
        for periods, values in zip(actions, actions):
            for key, value in values.items():
                if key in ('start_date', 'end_date', 'fiscalyear'):
                    def modified(period):
                        if key in ['start_date', 'end_date']:
                            return getattr(period, key) != value
                        else:
                            return period.fiscalyear .id != value
                    cls._check(list(filter(modified, periods)))
                    break
            if values.get('state') == 'open':
                for period in periods:
                    if period.fiscalyear.state != 'open':
                        raise AccessError(
                            gettext(
                                'account.msg_open_period_closed_fiscalyear',
                                period=period.rec_name,
                                fiscalyear=period.fiscalyear.rec_name))
            if values.get('post_move_sequence'):
                for period in periods:
                    if (period.post_move_sequence
                            and period.post_move_sequence.id
                            != values['post_move_sequence']):
                        if Move.search([
                                    ('period', '=', period.id),
                                    ('state', '=', 'posted'),
                                    ]):
                            raise AccessError(
                                gettext('account'
                                    '.msg_change_period_post_move_sequence',
                                    period=period.rec_name))
            args.extend((periods, values))
        super(Period, cls).write(*args)

    @classmethod
    def delete(cls, periods):
        cls._check(periods)
        super(Period, cls).delete(periods)

    @classmethod
    @ModelView.button
    @Workflow.transition('close')
    def close(cls, periods):
        pool = Pool()
        JournalPeriod = pool.get('account.journal.period')
        Move = pool.get('account.move')
        transaction = Transaction()
        database = transaction.database
        connection = transaction.connection

        # Lock period to be sure no new period will be created in between.
        database.lock(connection, JournalPeriod._table)

        unposted_moves = Move.search([
                ('period', 'in', [p.id for p in periods]),
                ('state', '!=', 'posted'),
                ], limit=1)
        if unposted_moves:
            unposted_move, = unposted_moves
            raise ClosePeriodError(
                gettext('account.msg_close_period_non_posted_moves',
                    period=unposted_move.period.rec_name,
                    moves=unposted_move.rec_name))
        journal_periods = JournalPeriod.search([
            ('period', 'in', [p.id for p in periods]),
            ])
        JournalPeriod.close(journal_periods)

    @classmethod
    @ModelView.button
    @Workflow.transition('open')
    def reopen(cls, periods):
        "Re-open period"
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('locked')
    def lock(cls, periods):
        pass

    @property
    def post_move_sequence_used(self):
        return self.post_move_sequence or self.fiscalyear.post_move_sequence
