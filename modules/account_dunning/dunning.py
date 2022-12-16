# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from collections import defaultdict
from itertools import groupby

from sql import Literal, Null

from trytond.model import (
    Model, ModelSQL, ModelView, Unique, fields, sequence_ordered)
from trytond.modules.currency.fields import Monetary
from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.wizard import (
    Button, StateAction, StateTransition, StateView, Wizard)


class Procedure(ModelSQL, ModelView):
    'Account Dunning Procedure'
    __name__ = 'account.dunning.procedure'
    name = fields.Char('Name', required=True, translate=True,
        help="The main identifier of the Dunning Procedure.")
    levels = fields.One2Many('account.dunning.level', 'procedure', 'Levels')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('name', 'ASC'))


class Level(sequence_ordered(), ModelSQL, ModelView):
    'Account Dunning Level'
    __name__ = 'account.dunning.level'
    procedure = fields.Many2One('account.dunning.procedure', 'Procedure',
        required=True, select=True)
    overdue = fields.TimeDelta('Overdue',
        help="When the level should be applied.")

    @classmethod
    def __register__(cls, module_name):
        transaction = Transaction()
        cursor = transaction.connection.cursor()
        update = transaction.connection.cursor()
        table = cls.__table_handler__(module_name)
        sql_table = cls.__table__()

        super(Level, cls).__register__(module_name)

        # Migration from 4.0: change days into timedelta overdue
        if table.column_exist('days'):
            cursor.execute(*sql_table.select(sql_table.id, sql_table.days,
                    where=sql_table.days != Null))
            for id_, days in cursor:
                overdue = datetime.timedelta(days)
                update.execute(*sql_table.update(
                        [sql_table.overdue],
                        [overdue],
                        where=sql_table.id == id_))
            table.drop_column('days')

    def get_rec_name(self, name):
        return '%s@%s' % (self.procedure.levels.index(self),
            self.procedure.rec_name)

    def test(self, line, date):
        if self.overdue is not None:
            return (date - line.maturity_date) >= self.overdue


_STATES = {
    'readonly': Eval('state') != 'draft',
    }


class Dunning(ModelSQL, ModelView):
    'Account Dunning'
    __name__ = 'account.dunning'
    company = fields.Many2One('company.company', 'Company', required=True,
        help="Make the dunning belong to the company.",
        select=True,
        states=_STATES)
    line = fields.Many2One('account.move.line', 'Line', required=True,
        help="The receivable line to dun for.",
        domain=[
            ('account.type.receivable', '=', True),
            ('account.company', '=', Eval('company', -1)),
            ['OR',
                ('debit', '>', 0),
                ('credit', '<', 0),
                ],
            ],
        states=_STATES)
    procedure = fields.Many2One('account.dunning.procedure', 'Procedure',
        required=True, states=_STATES)
    level = fields.Many2One('account.dunning.level', 'Level', required=True,
        domain=[
            ('procedure', '=', Eval('procedure', -1)),
            ],
        states=_STATES)
    date = fields.Date(
        "Date", readonly=True,
        states={
            'invisible': Eval('state') == 'draft',
            },
        help="When the dunning reached the level.")
    age = fields.Function(fields.TimeDelta(
            "Age",
            states={
                'invisible': Eval('state') == 'draft',
            },
            help="How long the dunning has been at the level."),
        'get_age')
    blocked = fields.Boolean('Blocked',
        help="Check to block further levels of the procedure.")
    state = fields.Selection([
            ('draft', 'Draft'),
            ('waiting', "Waiting"),
            ('final', "Final"),
            ], 'State', readonly=True, sort=False)
    active = fields.Function(fields.Boolean('Active'), 'get_active',
        searcher='search_active')
    party = fields.Function(fields.Many2One(
            'party.party', 'Party',
            context={
                'company': Eval('company', -1),
                },
            depends={'company'}),
        'get_line_field', searcher='search_line_field')
    amount = fields.Function(Monetary(
            "Amount", currency='currency', digits='currency'),
        'get_amount')
    currency = fields.Function(fields.Many2One(
            'currency.currency', "Currency"), 'get_line_field')
    maturity_date = fields.Function(fields.Date('Maturity Date'),
        'get_line_field', searcher='search_line_field')
    amount_second_currency = fields.Function(Monetary(
            'Amount Second Currency',
            currency='second_currency', digits='second_currency',
            states={
                'invisible': Eval('currency') == Eval('second_currency'),
                }),
        'get_amount_second_currency')
    second_currency = fields.Function(fields.Many2One('currency.currency',
            'Second Currency'), 'get_second_currency')

    @classmethod
    def __setup__(cls):
        super(Dunning, cls).__setup__()
        table = cls.__table__()
        cls._sql_constraints = [
            ('line_unique', Unique(table, table.line),
                'account_dunning.msg_dunning_line_unique'),
            ]
        cls._active_field = 'active'
        cls._buttons.update({
                'reschedule': {
                    'invisible': ~Eval('active', True),
                    'depends': ['active'],
                    },
                })

    @classmethod
    def __register__(cls, module):
        dunning = cls.__table__()
        super().__register__(module)
        cursor = Transaction().connection.cursor()

        # Migration from 4.8: rename done state into waiting
        cursor.execute(*dunning.update(
                [dunning.state], ['waiting'],
                where=dunning.state == 'done'))

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_state():
        return 'draft'

    def get_age(self, name):
        pool = Pool()
        Date = pool.get('ir.date')
        if self.date:
            with Transaction().set_context(company=self.company.id):
                return Date.today() - self.date

    @classmethod
    def order_age(cls, tables):
        pool = Pool()
        Date = pool.get('ir.date')
        table, _ = tables[None]
        return [Literal(Date.today()) - table.date]

    def get_active(self, name):
        return not self.line.reconciliation

    def get_line_field(self, name):
        value = getattr(self.line, name)
        if isinstance(value, Model):
            return value.id
        else:
            return value

    @classmethod
    def search_line_field(cls, name, clause):
        return [('line.' + clause[0],) + tuple(clause[1:])]

    def get_amount(self, name):
        return self.line.debit - self.line.credit

    def get_amount_second_currency(self, name):
        amount = self.line.debit - self.line.credit
        if self.line.amount_second_currency:
            return self.line.amount_second_currency.copy_sign(amount)
        else:
            return amount

    def get_second_currency(self, name):
        if self.line.second_currency:
            return self.line.second_currency.id
        else:
            return self.line.account.company.currency.id

    @classmethod
    def search_active(cls, name, clause):
        reverse = {
            '=': '!=',
            '!=': '=',
            }
        if clause[1] in reverse:
            if clause[2]:
                return [('line.reconciliation', clause[1], None)]
            else:
                return [('line.reconciliation', reverse[clause[1]], None)]
        else:
            return []

    @classmethod
    def _overdue_line_domain(cls, date):
        return [
            ('account.type.receivable', '=', True),
            ('dunnings', '=', None),
            ('maturity_date', '<=', date),
            ['OR',
                ('debit', '>', 0),
                ('credit', '<', 0),
                ],
            ('party', '!=', None),
            ('reconciliation', '=', None),
            ]

    @classmethod
    def generate_dunnings(cls, date=None):
        pool = Pool()
        Date = pool.get('ir.date')
        MoveLine = pool.get('account.move.line')

        if date is None:
            date = Date.today()

        set_level = defaultdict(list)
        with Transaction().set_context(_check_access=True):
            dunnings = cls.search([
                    ('state', '=', 'waiting'),
                    ('blocked', '=', False),
                    ])
        dunnings = cls.browse(dunnings)
        for dunning in dunnings:
            procedure = dunning.procedure
            levels = procedure.levels
            levels = levels[levels.index(dunning.level) + 1:]
            if levels:
                for level in levels:
                    if level.test(dunning.line, date):
                        break
                else:
                    level = dunning.level
                if level != dunning.level:
                    set_level[level].append(dunning)
            else:
                set_level[None].append(dunning)
        to_write = []
        for level, dunnings in set_level.items():
            if level:
                to_write.extend((dunnings, {
                            'level': level.id,
                            'state': 'draft',
                            'date': None,
                            }))
            else:
                to_write.extend((dunnings, {
                            'state': 'final',
                            'date': Date.today(),
                            }))
        if to_write:
            cls.write(*to_write)

        with Transaction().set_context(_check_access=True):
            lines = MoveLine.search(cls._overdue_line_domain(date))
        lines = MoveLine.browse(lines)
        dunnings = (cls._get_dunning(line, date) for line in lines)
        cls.save([d for d in dunnings if d])

    @classmethod
    def _get_dunning(cls, line, date):
        procedure = line.dunning_procedure
        if not procedure:
            return
        for level in procedure.levels:
            if level.test(line, date):
                break
        else:
            return
        return cls(
            line=line,
            procedure=procedure,
            level=level,
            )

    @classmethod
    def process(cls, dunnings):
        pool = Pool()
        Date = pool.get('ir.date')
        for company, c_dunnings in groupby(dunnings, key=lambda d: d.company):
            with Transaction().set_context(company=company.id):
                today = Date.today()
            cls.write([d for d in c_dunnings
                    if not d.blocked and d.state == 'draft'], {
                    'state': 'waiting',
                    'date': today,
                    })

    @classmethod
    @ModelView.button_action('account_dunning.act_reschedule_dunning_wizard')
    def reschedule(cls, dunnings):
        pass


class CreateDunningStart(ModelView):
    'Create Account Dunning'
    __name__ = 'account.dunning.create.start'
    date = fields.Date('Date', required=True,
        help="Create dunning up to this date.")

    @staticmethod
    def default_date():
        Date = Pool().get('ir.date')
        return Date.today()


class CreateDunning(Wizard):
    'Create Account Dunning'
    __name__ = 'account.dunning.create'
    start = StateView('account.dunning.create.start',
        'account_dunning.dunning_create_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Create', 'create_', 'tryton-ok', default=True),
            ])
    create_ = StateAction('account_dunning.act_dunning_form')

    def do_create_(self, action):
        pool = Pool()
        Dunning = pool.get('account.dunning')
        Dunning.generate_dunnings(date=self.start.date)
        return action, {}


class ProcessDunningStart(ModelView):
    'Create Account Dunning'
    __name__ = 'account.dunning.process.start'


class ProcessDunning(Wizard):
    'Process Account Dunning'
    __name__ = 'account.dunning.process'
    start = StateView('account.dunning.process.start',
        'account_dunning.dunning_process_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Process', 'process', 'tryton-ok', default=True),
        ])
    process = StateTransition()

    @classmethod
    def __setup__(cls):
        super(ProcessDunning, cls).__setup__()

        # _actions is the list that define the order of each state to process
        # after the 'process' state.
        cls._actions = ['process']

    def next_state(self, state):
        "Return the next state for the current state"
        try:
            i = self._actions.index(state)
            return self._actions[i + 1]
        except (ValueError, IndexError):
            return 'end'

    def transition_process(self):
        self.model.process(self.records)
        return self.next_state('process')


class RescheduleDunning(Wizard):
    "Reschedule Account Dunning"
    __name__ = 'account.dunning.reschedule'
    start = StateAction('account.act_reschedule_lines_wizard')

    def do_start(self, action):
        return action, {
            'ids': [self.record.line.id],
            'model': 'account.move.line',
            }
