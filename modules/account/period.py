# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from sql.operators import Equal, NotEqual

from trytond.cache import Cache
from trytond.const import OPERATORS
from trytond.i18n import gettext
from trytond.model import Exclude, Index, ModelSQL, ModelView, Workflow, fields
from trytond.model.exceptions import AccessError
from trytond.pool import Pool
from trytond.pyson import Eval, Id
from trytond.sql.functions import DateRange
from trytond.sql.operators import RangeOverlap
from trytond.tools import grouped_slice
from trytond.transaction import Transaction

from .exceptions import ClosePeriodError, PeriodDatesError, PeriodNotFoundError

_STATES = {
    'readonly': Eval('state') != 'open',
}


class Period(Workflow, ModelSQL, ModelView):
    __name__ = 'account.period'
    name = fields.Char('Name', required=True)
    start_date = fields.Date('Starting Date', required=True, states=_STATES,
        domain=[('start_date', '<=', Eval('end_date', None))])
    end_date = fields.Date('Ending Date', required=True, states=_STATES,
        domain=[('end_date', '>=', Eval('start_date', None))])
    fiscalyear = fields.Many2One(
        'account.fiscalyear', "Fiscal Year", required=True, ondelete='CASCADE',
        states=_STATES)
    state = fields.Selection([
            ('open', 'Open'),
            ('closed', 'Closed'),
            ('locked', 'Locked'),
            ], 'State', readonly=True, required=True, sort=False)
    move_sequence = fields.Many2One(
        'ir.sequence.strict', "Move Sequence",
        domain=[
            ('sequence_type', '=',
                Id('account', 'sequence_type_account_move')),
            ['OR',
                ('company', '=', None),
                ('company', '=', Eval('company', -1)),
                ],
            ],
        help="Used to generate the move number when posting.\n"
        "Leave empty to use the fiscal year sequence.")
    type = fields.Selection([
            ('standard', 'Standard'),
            ('adjustment', 'Adjustment'),
            ], 'Type', required=True,
        states=_STATES)
    company = fields.Function(fields.Many2One('company.company', 'Company',),
        'on_change_with_company', searcher='search_company')
    icon = fields.Function(fields.Char("Icon"), 'get_icon')
    _find_cache = Cache(__name__ + '.find', context=False)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls.__access__.add('fiscalyear')
        cls._sql_constraints += [
            ('standard_dates_overlap',
                Exclude(t,
                    (t.fiscalyear, Equal),
                    (DateRange(t.start_date, t.end_date, '[]'), RangeOverlap),
                    where=t.type == 'standard'),
                'account.msg_period_standard_overlap'),
            ('move_sequence_unique',
                Exclude(t,
                    (t.move_sequence, Equal),
                    (t.fiscalyear, NotEqual)),
                'account.msg_period_move_sequence_unique'),
            ]
        cls._sql_indexes.add(
            Index(
                t,
                (t.start_date, Index.Range()),
                (t.end_date, Index.Range()),
                order='DESC'))
        cls._order.insert(0, ('start_date', 'DESC'))
        cls._transitions |= set((
                ('open', 'closed'),
                ('closed', 'locked'),
                ('closed', 'open'),
                ))
        cls._buttons.update({
                'close': {
                    'invisible': Eval('state') != 'open',
                    'depends': ['state'],
                    },
                'reopen': {
                    'invisible': Eval('state') != 'closed',
                    'depends': ['state'],
                    },
                'lock_': {
                    'invisible': Eval('state') != 'closed',
                    'depends': ['state'],
                    },
                })

    @classmethod
    def __register__(cls, module):
        pool = Pool()
        FiscalYear = pool.get('account.fiscalyear')
        Sequence = pool.get('ir.sequence')
        SequenceStrict = pool.get('ir.sequence.strict')

        table_h = cls.__table_handler__(module)
        cursor = Transaction().connection.cursor()
        t = cls.__table__()

        migrate_move_sequence = not table_h.column_exist('move_sequence')

        super().__register__(module)
        # Migration from 6.8: rename state close to closed
        cursor.execute(
            *t.update([t.state], ['closed'], where=t.state == 'close'))

        # Migrationn from 7.4: use strict sequence
        if (table_h.column_exist('post_move_sequence')
                and migrate_move_sequence):
            table_h.not_null_action('post_move_sequence', 'remove')

            fiscalyear_h = FiscalYear.__table_handler__(module)
            fiscalyear = FiscalYear.__table__()
            old2new = {}
            fiscalyear_migrated = (
                fiscalyear_h.column_exist('post_move_sequence')
                and fiscalyear_h.column_exist('move_sequence'))
            if fiscalyear_migrated:
                cursor.execute(*fiscalyear.select(
                        fiscalyear.post_move_sequence,
                        fiscalyear.move_sequence))
                old2new.update(cursor)

            cursor.execute(*t.select(t.post_move_sequence, distinct=True))
            for sequence_id, in cursor:
                if sequence_id not in old2new:
                    sequence = Sequence(sequence_id)
                    new_sequence = SequenceStrict(
                        name=sequence.name,
                        sequence_type=sequence.sequence_type,
                        prefix=sequence.prefix,
                        suffix=sequence.suffix,
                        type=sequence.type,
                        number_next_internal=sequence.number_next_internal,
                        number_increment=sequence.number_increment,
                        padding=sequence.padding,
                        timestamp_rounding=sequence.timestamp_rounding,
                        timestamp_offset=sequence.timestamp_offset,
                        last_timestamp=sequence.last_timestamp)
                    new_sequence.save()
                    old2new[sequence_id] = new_sequence.id

            for old_id, new_id in old2new.items():
                cursor.execute(*t.update(
                        [t.move_sequence], [new_id],
                        where=t.post_move_sequence == old_id))

            if fiscalyear_migrated:
                table_h.drop_column('post_move_sequence')
                fiscalyear_h.drop_column('post_move_sequence')

    @staticmethod
    def default_state():
        return 'open'

    @staticmethod
    def default_type():
        return 'standard'

    @fields.depends('fiscalyear', '_parent_fiscalyear.company')
    def on_change_with_company(self, name=None):
        return self.fiscalyear.company if self.fiscalyear else None

    @classmethod
    def search_company(cls, name, clause):
        return [('fiscalyear.' + clause[0],) + tuple(clause[1:])]

    def get_icon(self, name):
        return {
            'open': 'tryton-account-open',
            'closed': 'tryton-account-close',
            'locked': 'tryton-account-block',
            }.get(self.state)

    @classmethod
    def validate_fields(cls, periods, field_names):
        super().validate_fields(periods, field_names)
        cls.check_fiscalyear_dates(periods, field_names)
        cls.check_move_dates(periods, field_names)

    @classmethod
    def check_fiscalyear_dates(cls, periods, field_names=None):
        if field_names and not (
                field_names & {
                    'start_date', 'end_date', 'fiscalyear'}):
            return
        for period in periods:
            fiscalyear = period.fiscalyear
            if (period.start_date < fiscalyear.start_date
                    or period.end_date > fiscalyear.end_date):
                raise PeriodDatesError(
                    gettext('account.msg_period_fiscalyear_dates',
                        period=period.rec_name,
                        fiscalyear=fiscalyear.rec_name))

    @classmethod
    def check_move_dates(cls, periods, field_names=None):
        pool = Pool()
        Move = pool.get('account.move')
        Lang = pool.get('ir.lang')
        if field_names and not (field_names & {'start_date', 'end_date'}):
            return
        lang = Lang.get()

        for sub_periods in grouped_slice(periods):
            domain = ['OR']
            for period in sub_periods:
                domain.append([
                        ('period', '=', period.id),
                        ['OR',
                            ('date', '<', period.start_date),
                            ('date', '>', period.end_date),
                            ],
                        ])
            moves = Move.search(domain, limit=1)
            if moves:
                move, = moves
                raise PeriodDatesError(
                    gettext('account.msg_period_move_dates',
                        period=move.period.rec_name,
                        move=move.rec_name,
                        move_date=lang.strftime(move.date)))

    @classmethod
    def find(cls, company, date=None, test_state=True):
        '''
        Return the period for the company at the date or the current date
        or raise PeriodNotFoundError.
        If test_state is true, it searches on non-closed periods
        '''
        pool = Pool()
        Date = pool.get('ir.date')
        Lang = pool.get('ir.lang')
        Company = pool.get('company.company')

        company_id = int(company) if company is not None else None
        if not date:
            with Transaction().set_context(company=company_id):
                date = Date.today()
        key = (company_id, date, test_state)
        period = cls._find_cache.get(key, -1)
        if period is not None and period < 0:
            clause = [
                ('start_date', '<=', date),
                ('end_date', '>=', date),
                ('fiscalyear.company', '=', company_id),
                ('type', '=', 'standard'),
                ]
            periods = cls.search(
                clause, order=[('start_date', 'DESC')], limit=1)
            if periods:
                period, = periods
            else:
                period = None
            cls._find_cache.set(key, int(period) if period else None)
        elif period is not None:
            period = cls(period)
        found = period and (not test_state or period.state == 'open')
        if not found:
            lang = Lang.get()
            if company is not None and not isinstance(company, Company):
                company = Company(company)
            if not period:
                raise PeriodNotFoundError(
                    gettext('account.msg_no_period_date',
                        date=lang.strftime(date),
                        company=company.rec_name if company else ''))
            else:
                raise PeriodNotFoundError(
                    gettext('account.msg_no_open_period_date',
                        date=lang.strftime(date),
                        period=period.rec_name,
                        company=company.rec_name if company else ''))
        else:
            return period

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
        return super().search(args, offset=offset, limit=limit,
            order=order, count=count, query=query)

    @classmethod
    def preprocess_values(cls, mode, values):
        pool = Pool()
        FiscalYear = pool.get('account.fiscalyear')
        values = super().preprocess_values(mode, values)
        if mode == 'create' and values.get('fiscalyear') is not None:
            fiscalyear = FiscalYear(values['fiscalyear'])
            if values.get('move_sequence') is None:
                values['move_sequence'] = fiscalyear.move_sequence.id
        return values

    @classmethod
    def check_modification(cls, mode, periods, values=None, external=False):
        pool = Pool()
        Move = pool.get('account.move')
        super().check_modification(
            mode, periods, values=values, external=external)
        if mode == 'create':
            for period in periods:
                if period.fiscalyear.state != 'open':
                    raise AccessError(
                        gettext('account.msg_create_period_closed_fiscalyear',
                            fiscalyear=period.fiscalyear.rec_name))
        elif mode == 'write':
            if values.get('state') == 'open':
                for period in periods:
                    if period.fiscalyear.state != 'open':
                        raise AccessError(
                            gettext(
                                'account.msg_open_period_closed_fiscalyear',
                                period=period.rec_name,
                                fiscalyear=period.fiscalyear.rec_name))
            if 'move_sequence' in values:
                for period in periods:
                    if sequence := period.move_sequence:
                        if sequence.id != values['move_sequence']:
                            if Move.search([
                                        ('period', '=', period.id),
                                        ('state', '=', 'posted'),
                                        ], limit=1, order=[]):
                                raise AccessError(gettext(
                                        'account.'
                                        'msg_change_period_move_sequence',
                                        period=period.rec_name))

    @classmethod
    def on_modification(cls, mode, periods, field_names=None):
        super().on_modification(mode, periods, field_names=field_names)
        cls._find_cache.clear()

    @classmethod
    @ModelView.button
    @Workflow.transition('closed')
    def close(cls, periods):
        pool = Pool()
        JournalPeriod = pool.get('account.journal.period')
        Move = pool.get('account.move')
        Account = pool.get('account.account')
        transaction = Transaction()

        # Lock period and move to be sure no new record will be created
        JournalPeriod.lock()
        Move.lock()

        for period in periods:
            with transaction.set_context(
                    fiscalyear=period.fiscalyear.id, date=period.end_date,
                    cumulate=True, journal=None):
                for account in Account.search([
                            ('company', '=', period.company.id),
                            ('end_date', '>=', period.start_date),
                            ('end_date', '<=', period.end_date),
                            ]):
                    if account.balance:
                        raise ClosePeriodError(
                            gettext('account.'
                                'msg_close_period_inactive_accounts',
                                account=account.rec_name,
                                period=period.rec_name))

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
        "Reopen period"
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('locked')
    def lock_(cls, periods):
        pass

    @property
    def move_sequence_used(self):
        return self.move_sequence or self.fiscalyear.move_sequence
