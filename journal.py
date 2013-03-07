#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard, StateTransition
from trytond.backend import TableHandler
from trytond.pyson import Eval, Bool
from trytond.transaction import Transaction
from trytond.pool import Pool

__all__ = ['JournalType', 'JournalView', 'JournalViewColumn', 'Journal',
    'JournalPeriod', 'CloseJournalPeriod', 'ReOpenJournalPeriod']

STATES = {
    'readonly': Eval('state') == 'close',
}
DEPENDS = ['state']

_ICONS = {
    'open': 'tryton-open',
    'close': 'tryton-readonly',
}


class JournalType(ModelSQL, ModelView):
    'Journal Type'
    __name__ = 'account.journal.type'
    name = fields.Char('Name', size=None, required=True, translate=True)
    code = fields.Char('Code', size=None, required=True)

    @classmethod
    def __setup__(cls):
        super(JournalType, cls).__setup__()
        cls._sql_constraints += [
            ('code_uniq', 'UNIQUE(code)', 'The code must be unique.'),
            ]
        cls._order.insert(0, ('code', 'ASC'))


class JournalView(ModelSQL, ModelView):
    'Journal View'
    __name__ = 'account.journal.view'
    name = fields.Char('Name', size=None, required=True)
    columns = fields.One2Many('account.journal.view.column', 'view', 'Columns')

    @classmethod
    def __setup__(cls):
        super(JournalView, cls).__setup__()
        cls._order.insert(0, ('name', 'ASC'))


class JournalViewColumn(ModelSQL, ModelView):
    'Journal View Column'
    __name__ = 'account.journal.view.column'
    name = fields.Char('Name', size=None, required=True)
    field = fields.Many2One('ir.model.field', 'Field', required=True,
            domain=[('model.model', '=', 'account.move.line')])
    view = fields.Many2One('account.journal.view', 'View', select=True)
    sequence = fields.Integer('Sequence', select=True,
        order_field='(%(table)s.sequence IS NULL) %(order)s, '
        '%(table)s.sequence %(order)s')
    required = fields.Boolean('Required')
    readonly = fields.Boolean('Readonly')

    @classmethod
    def __setup__(cls):
        super(JournalViewColumn, cls).__setup__()
        cls._order.insert(0, ('sequence', 'ASC'))

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor
        table = TableHandler(cursor, cls, module_name)

        super(JournalViewColumn, cls).__register__(module_name)

        # Migration from 2.4: drop required on sequence
        table.not_null_action('sequence', action='remove')

    @staticmethod
    def default_required():
        return False

    @staticmethod
    def default_readonly():
        return False


class Journal(ModelSQL, ModelView):
    'Journal'
    __name__ = 'account.journal'
    name = fields.Char('Name', size=None, required=True, translate=True)
    code = fields.Char('Code', size=None)
    active = fields.Boolean('Active', select=True)
    type = fields.Selection('get_types', 'Type', required=True)
    view = fields.Many2One('account.journal.view', 'View')
    centralised = fields.Boolean('Centralised counterpart')
    update_posted = fields.Boolean('Allow cancelling moves')
    sequence = fields.Property(fields.Many2One('ir.sequence', 'Sequence',
            domain=[('code', '=', 'account.journal')],
            context={'code': 'account.journal'},
            states={
                'required': Bool(Eval('context', {}).get('company', 0)),
                }))
    credit_account = fields.Property(fields.Many2One('account.account',
            'Default Credit Account', domain=[
                ('kind', '!=', 'view'),
                ('company', '=', Eval('context', {}).get('company', 0)),
                ],
            states={
                'required': ((Eval('centralised', False)
                        | (Eval('type') == 'cash'))
                    & Bool(Eval('context', {}).get('company', 0))),
                'invisible': ~Eval('context', {}).get('company', 0),
                }, depends=['type', 'centralised']))
    debit_account = fields.Property(fields.Many2One('account.account',
            'Default Debit Account', domain=[
                ('kind', '!=', 'view'),
                ('company', '=', Eval('context', {}).get('company', 0)),
                ],
            states={
                'required': ((Eval('centralised', False)
                        | (Eval('type') == 'cash'))
                    & Bool(Eval('context', {}).get('company', 0))),
                'invisible': ~Eval('context', {}).get('company', 0),
                }, depends=['type', 'centralised']))

    @classmethod
    def __setup__(cls):
        super(Journal, cls).__setup__()
        cls._order.insert(0, ('name', 'ASC'))

    @classmethod
    def __register__(cls, module_name):
        super(Journal, cls).__register__(module_name)
        cursor = Transaction().cursor
        table = TableHandler(cursor, cls, module_name)

        # Migration from 1.0 sequence Many2One change into Property
        if table.column_exist('sequence'):
            Property = Pool().get('ir.property')
            cursor.execute('SELECT id, sequence FROM "' + cls._table + '"')
            with Transaction().set_user(0):
                for journal_id, sequence_id in cursor.fetchall():
                    Property.set('sequence', cls._name,
                            journal_id, (sequence_id and
                                'ir.sequence,' + str(sequence_id) or False))
            table.drop_column('sequence', exception=True)

    @staticmethod
    def default_active():
        return True

    @staticmethod
    def default_centralised():
        return False

    @staticmethod
    def default_update_posted():
        return False

    @staticmethod
    def default_sequence():
        return None

    @staticmethod
    def get_types():
        Type = Pool().get('account.journal.type')
        types = Type.search([])
        return [(x.code, x.name) for x in types]

    @classmethod
    def search_rec_name(cls, name, clause):
        journals = cls.search([
                ('code',) + clause[1:],
                ], limit=1, order=[])
        if journals:
            return [('code',) + clause[1:]]
        return [(cls._rec_name,) + clause[1:]]


class JournalPeriod(ModelSQL, ModelView):
    'Journal - Period'
    __name__ = 'account.journal.period'
    name = fields.Char('Name', size=None, required=True)
    journal = fields.Many2One('account.journal', 'Journal', required=True,
            ondelete='CASCADE', states=STATES, depends=DEPENDS)
    period = fields.Many2One('account.period', 'Period', required=True,
            ondelete='CASCADE', states=STATES, depends=DEPENDS)
    icon = fields.Function(fields.Char('Icon'), 'get_icon')
    active = fields.Boolean('Active', select=True, states=STATES,
        depends=DEPENDS)
    state = fields.Selection([
        ('open', 'Open'),
        ('close', 'Close'),
        ], 'State', readonly=True, required=True)

    @classmethod
    def __setup__(cls):
        super(JournalPeriod, cls).__setup__()
        cls._sql_constraints += [
            ('journal_period_uniq', 'UNIQUE(journal, period)',
                'You can only open one journal per period.'),
            ]
        cls._order.insert(0, ('name', 'ASC'))
        cls._error_messages.update({
                'modify_del_journal_period': ('You can not modify/delete '
                        'journal - period "%s" because it has moves.'),
                'create_journal_period': ('You can not create a '
                        'journal - period on closed period "%s".'),
                'open_journal_period': ('You can not open '
                    'journal - period "%(journal_period)s" because period '
                    '"%(period)s" is closed.'),
                })

    @staticmethod
    def default_active():
        return True

    @staticmethod
    def default_state():
        return 'open'

    def get_icon(self, name):
        return _ICONS.get(self.state, '')

    @classmethod
    def _check(cls, periods):
        Move = Pool().get('account.move')
        for period in periods:
            moves = Move.search([
                    ('journal', '=', period.journal.id),
                    ('period', '=', period.period.id),
                    ], limit=1)
            if moves:
                cls.raise_user_error('modify_del_journal_period', (
                        period.rec_name,))

    @classmethod
    def create(cls, vlist):
        Period = Pool().get('account.period')
        for vals in vlist:
            if vals.get('period'):
                period = Period(vals['period'])
                if period.state == 'close':
                    cls.raise_user_error('create_journal_period', (
                            period.rec_name,))
        return super(JournalPeriod, cls).create(vlist)

    @classmethod
    def write(cls, periods, vals):
        if vals != {'state': 'close'} \
                and vals != {'state': 'open'}:
            cls._check(periods)
        if vals.get('state') == 'open':
            for journal_period in periods:
                if journal_period.period.state == 'close':
                    cls.raise_user_error('open_journal_period', {
                            'journal_period': journal_period.rec_name,
                            'period': journal_period.period.rec_name,
                            })
        super(JournalPeriod, cls).write(periods, vals)

    @classmethod
    def delete(cls, periods):
        cls._check(periods)
        super(JournalPeriod, cls).delete(periods)

    @classmethod
    def close(cls, periods):
        '''
        Close journal - period
        '''
        cls.write(periods, {
                'state': 'close',
                })

    @classmethod
    def open_(cls, periods):
        "Open journal - period"
        cls.write(periods, {
                'state': 'open',
                })


class CloseJournalPeriod(Wizard):
    'Close Journal - Period'
    __name__ = 'account.journal.period.close'
    start_state = 'close'
    close = StateTransition()

    def transition_close(self):
        JournalPeriod = Pool().get('account.journal.period')
        JournalPeriod.close(
            JournalPeriod.browse(Transaction().context['active_ids']))
        return 'end'


class ReOpenJournalPeriod(Wizard):
    'Re-Open Journal - Period'
    __name__ = 'account.journal.period.reopen'
    start_state = 'reopen'
    reopen = StateTransition()

    def transition_reopen(self):
        JournalPeriod = Pool().get('account.journal.period')
        JournalPeriod.open_(
            JournalPeriod.browse(Transaction().context['active_ids']))
        return 'end'
