#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard
from trytond.backend import TableHandler
from trytond.pyson import Eval, Bool
from trytond.transaction import Transaction
from trytond.pool import Pool

STATES = {
    'readonly': Eval('state') == 'close',
}
DEPENDS = ['state']

_ICONS = {
    'open': 'tryton-open',
    'close': 'tryton-readonly',
}


class Type(ModelSQL, ModelView):
    'Journal Type'
    _name = 'account.journal.type'
    _description = __doc__
    name = fields.Char('Name', size=None, required=True, translate=True)
    code = fields.Char('Code', size=None, required=True)

    def __init__(self):
        super(Type, self).__init__()
        self._sql_constraints += [
            ('code_uniq', 'UNIQUE(code)', 'The code must be unique!'),
        ]
        self._order.insert(0, ('code', 'ASC'))

Type()


class View(ModelSQL, ModelView):
    'Journal View'
    _name = 'account.journal.view'
    _description = __doc__
    name = fields.Char('Name', size=None, required=True)
    columns = fields.One2Many('account.journal.view.column', 'view', 'Columns')

    def __init__(self):
        super(View, self).__init__()
        self._order.insert(0, ('name', 'ASC'))

View()


class Column(ModelSQL, ModelView):
    'Journal View Column'
    _name = 'account.journal.view.column'
    _description = __doc__
    name = fields.Char('Name', size=None, required=True)
    field = fields.Many2One('ir.model.field', 'Field', required=True,
            domain=[('model.model', '=', 'account.move.line')])
    view = fields.Many2One('account.journal.view', 'View', select=1)
    sequence = fields.Integer('Sequence', select=2)
    required = fields.Boolean('Required')
    readonly = fields.Boolean('Readonly')

    def __init__(self):
        super(Column, self).__init__()
        self._order.insert(0, ('sequence', 'ASC'))

    def default_required(self):
        return False

    def default_readonly(self):
        return False

Column()


class Journal(ModelSQL, ModelView):
    'Journal'
    _name = 'account.journal'
    _description = __doc__

    name = fields.Char('Name', size=None, required=True, translate=True)
    code = fields.Char('Code', size=None)
    active = fields.Boolean('Active', select=2)
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

    def __init__(self):
        super(Journal, self).__init__()
        self._order.insert(0, ('name', 'ASC'))

    def init(self, module_name):
        super(Journal, self).init(module_name)
        cursor = Transaction().cursor
        table = TableHandler(cursor, self, module_name)

        # Migration from 1.0 sequence Many2One change into Property
        if table.column_exist('sequence'):
            property_obj = Pool().get('ir.property')
            cursor.execute('SELECT id, sequence FROM "' + self._table +'"')
            with Transaction().set_user(0):
                for journal_id, sequence_id in cursor.fetchall():
                    property_obj.set('sequence', self._name,
                            journal_id, (sequence_id and
                                'ir.sequence,' + str(sequence_id) or False))
            table.drop_column('sequence', exception=True)

    def default_active(self):
        return True

    def default_centralised(self):
        return False

    def default_update_posted(self):
        return False

    def default_sequence(self):
        return False

    def get_types(self):
        type_obj = Pool().get('account.journal.type')
        type_ids = type_obj.search([])
        types = type_obj.browse(type_ids)
        return [(x.code, x.name) for x in types]

    def search_rec_name(self, name, clause):
        ids = self.search([
            ('code',) + clause[1:],
            ], limit=1, order=[])
        if ids:
            return [('code',) + clause[1:]]
        return [(self._rec_name,) + clause[1:]]

Journal()


class Period(ModelSQL, ModelView):
    'Journal - Period'
    _name = 'account.journal.period'
    _description = __doc__

    name = fields.Char('Name', size=None, required=True)
    journal = fields.Many2One('account.journal', 'Journal', required=True,
            ondelete='CASCADE', states=STATES, depends=DEPENDS)
    period = fields.Many2One('account.period', 'Period', required=True,
            ondelete='CASCADE', states=STATES, depends=DEPENDS)
    icon = fields.Function(fields.Char('Icon'), 'get_icon')
    active = fields.Boolean('Active', select=2, states=STATES, depends=DEPENDS)
    state = fields.Selection([
        ('open', 'Open'),
        ('close', 'Close'),
        ], 'State', readonly=True, required=True)

    def __init__(self):
        super(Period, self).__init__()
        self._sql_constraints += [
            ('journal_period_uniq', 'UNIQUE(journal, period)',
                'You can only open one journal per period!'),
        ]
        self._order.insert(0, ('name', 'ASC'))
        self._error_messages.update({
            'modify_del_journal_period': 'You can not modify/delete ' \
                    'a journal - period with moves!',
            'create_journal_period': 'You can not create ' \
                    'a journal - period on a closed period!',
            'open_journal_period': 'You can not open ' \
                    'a journal - period from a closed period!',
            })

    def default_active(self):
        return True

    def default_state(self):
        return 'open'

    def get_icon(self, ids, name):
        res = {}
        for period in self.browse(ids):
            res[period.id] = _ICONS.get(period.state, '')
        return res

    def _check(self, ids):
        move_obj = Pool().get('account.move')
        for period in self.browse(ids):
            move_ids = move_obj.search([
                ('journal', '=', period.journal.id),
                ('period', '=', period.period.id),
                ], limit=1)
            if move_ids:
                self.raise_user_error('modify_del_journal_period')
        return

    def create(self, vals):
        period_obj = Pool().get('account.period')
        if vals.get('period'):
            period = period_obj.browse(vals['period'])
            if period.state == 'close':
                self.raise_user_error('create_journal_period')
        return super(Period, self).create(vals)

    def write(self, ids, vals):
        if vals != {'state': 'close'} \
                and vals != {'state': 'open'}:
            self._check(ids)
        if vals.get('state') == 'open':
            for journal_period in self.browse(ids):
                if journal_period.period.state == 'close':
                    self.raise_user_error('open_journal_period')
        return super(Period, self).write(ids, vals)

    def delete(self, ids):
        self._check(ids)
        return super(Period, self).delete(ids)

    def close(self, ids):
        '''
        Close journal - period

        :param ids: the journal - period ids
        '''
        self.write(ids, {
            'state': 'close',
            })

Period()


class ClosePeriod(Wizard):
    'Close Journal - Period'
    _name = 'account.journal.close_period'
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
        journal_period_obj = Pool().get('account.journal.period')
        journal_period_obj.close(data['ids'])
        return {}

ClosePeriod()


class ReOpenPeriod(Wizard):
    'Re-Open Journal - Period'
    _name = 'account.journal.reopen_period'
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
        journal_period_obj = Pool().get('account.journal.period')
        journal_period_obj.write(data['ids'], {
            'state': 'open',
            })
        return {}

ReOpenPeriod()
