#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
"Journal"

from trytond.osv import fields, OSV
from trytond.wizard import Wizard, WizardOSV

STATES = {
    'readonly': "state == 'close'",
}
_ICONS = {
    'open': 'tryton-open',
    'close': 'tryton-readonly',
}


class Type(OSV):
    'Journal Type'
    _name = 'account.journal.type'
    _description = __doc__
    name = fields.Char('Name', size=None, required=True, translate=True)
    code = fields.Char('Code', size=None, required=True)

    def __init__(self):
        super(Type, self).__init__()
        self._sql_constraints += [
            ('code_uniq', 'UNIQUE(code)', 'Code must be unique!'),
        ]
        self._order.insert(0, ('code', 'ASC'))

Type()


class View(OSV):
    'Journal View'
    _name = 'account.journal.view'
    _description = __doc__
    name = fields.Char('Name', size=None, required=True)
    columns = fields.One2Many('account.journal.view.column', 'view', 'Columns')

    def __init__(self):
        super(View, self).__init__()
        self._order.insert(0, ('name', 'ASC'))

View()


class Column(OSV):
    'Journal View Column'
    _name = 'account.journal.view.column'
    _description = __doc__
    name = fields.Char('Name', size=None, required=True)
    field = fields.Many2One('ir.model.field', 'Field', required=True,
            domain="[('model.model', '=', 'account.move.line')]")
    view = fields.Many2One('account.journal.view', 'View', select=1)
    sequence = fields.Integer('Sequence', select=2)
    required = fields.Boolean('Required')
    readonly = fields.Boolean('Readonly')

    def __init__(self):
        super(Column, self).__init__()
        self._order.insert(0, ('sequence', 'ASC'))

    def default_required(self, cursor, user, context=None):
        return False

    def default_readonly(self, cursor, user, context=None):
        return False

Column()


class Journal(OSV):
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
    sequence = fields.Many2One('ir.sequence', 'Sequence', required=True,
            domain="[('code', '=', 'account.journal')]")
    credit_account = fields.Property(type='many2one',
            relation='account.account', string='Default Credit Account',
            domain="[('kind', '!=', 'view'), " \
                    "('company', '=', context.get('company'))]",
            states={
                'required': "centralised or " \
                        "(type == 'cash' and context.get('company'))",
                'invisible': "not context.get('company')",
            })
    debit_account = fields.Property(type='many2one',
            relation='account.account', string='Default Debit Account',
            domain="[('kind', '!=', 'view'), " \
                    "('company', '=', context.get('company'))]",
            states={
                'required': "centralised or " \
                        "(type == 'cash' and context.get('company'))",
                'invisible': "not context.get('company')",
            })

    def __init__(self):
        super(Journal, self).__init__()
        self._order.insert(0, ('name', 'ASC'))

    def default_active(self, cursor, user, context=None):
        return True

    def default_centralised(self, cursor, user, context=None):
        return False

    def default_update_posted(self, cursor, user, context=None):
        return False

    def get_types(self, cursor, user, context=None):
        type_obj = self.pool.get('account.journal.type')
        type_ids = type_obj.search(cursor, user, [], context=context)
        types = type_obj.browse(cursor, user, type_ids, context=context)
        return [(x.code, x.name) for x in types]

    def name_search(self, cursor, user, name='', args=None, operator='ilike',
            context=None, limit=None):
        if name:
            ids = self.search(cursor, user,
                    [('code', 'like', name + '%')] + args,
                    limit=limit, context=context)
            if not ids:
                ids = self.search(cursor, user,
                        [(self._rec_name, operator, name)] + args,
                        limit=limit, context=context)
        else:
            ids = self.search(cursor, user, args, limit=limit, context=context)
        res = self.name_get(cursor, user, ids, context=context)
        return res

Journal()


class Period(OSV):
    'Journal - Period'
    _name = 'account.journal.period'
    _description = __doc__

    name = fields.Char('Name', size=None, required=True)
    journal = fields.Many2One('account.journal', 'Journal', required=True,
            ondelete='CASCADE', states=STATES)
    period = fields.Many2One('account.period', 'Period', required=True,
            ondelete='CASCADE', states=STATES)
    icon = fields.Function('get_icon', string='Icon', type='char')
    active = fields.Boolean('Active', select=2, states=STATES)
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

    def default_active(self, cursor, user, context=None):
        return True

    def default_state(self, cursor, user, context=None):
        return 'open'

    def get_icon(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for period in self.browse(cursor, user, ids, context=context):
            res[period.id] = _ICONS.get(period.state, '')
        return res

    def _check(self, cursor, user, ids, context=None):
        move_obj = self.pool.get('account.move')
        for period in self.browse(cursor, user, ids, context=context):
            move_ids = move_obj.search(cursor, user, [
                ('journal', '=', period.journal.id),
                ('period', '=', period.period.id),
                ], limit=1, context=context)
            if move_ids:
                self.raise_user_error(cursor, 'modify_del_journal_period',
                        context=context)
        return

    def create(self, cursor, user, vals, context=None):
        period_obj = self.pool.get('account.period')
        if vals.get('period'):
            period = period_obj.browse(cursor, user, vals['period'],
                    context=context)
            if period.state == 'close':
                self.raise_user_error(cursor, 'create_journal_period',
                        context=context)
        return super(Period, self).create(cursor, user, vals, context=context)

    def write(self, cursor, user, ids, vals, context=None):
        if vals != {'state': 'close'} \
                and vals != {'state': 'open'}:
            self._check(cursor, user, ids, context=context)
        if vals.get('state') == 'open':
            for journal_period in self.browse(cursor, user, ids,
                    context=context):
                if journal_period.period.state == 'close':
                    self.raise_user_error(cursor, 'open_journal_period',
                            context=context)
        return super(Period, self).write(cursor, user, ids, vals,
                context=context)

    def delete(self, cursor, user, ids, context=None):
        self._check(cursor, user, ids, context=context)
        return super(Period, self).delete(cursor, user, ids, vals,
                context=context)

    def close(self, cursor, user, ids, context=None):
        '''
        Close journal - period

        :param cursor: the database cursor
        :param user: the user id
        :param ids: the journal - period ids
        :param context: the context
        '''
        self.write(cursor, user, ids, {
            'state': 'close',
            }, context=context)

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

    def _close(self, cursor, user, data, context=None):
        journal_period_obj = self.pool.get('account.journal.period')
        journal_period_obj.close(cursor, user, data['ids'],
                context=context)
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

    def _reopen(self, cursor, user, data, context=None):
        journal_period_obj = self.pool.get('account.journal.period')
        journal_period_obj.write(cursor, user, data['ids'], {
            'state': 'open',
            }, context=context)
        return {}

ReOpenPeriod()
