# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from functools import wraps

from sql.operators import NotIn

from trytond.cache import Cache
from trytond.exceptions import UserError
from trytond.i18n import gettext
from trytond.model import ModelView, ModelSQL, fields, Unique, sequence_ordered
from trytond.model.exceptions import AccessError
from trytond.modules import get_module_list, get_module_info
from trytond.wizard import Wizard, StateView, Button, StateTransition, \
    StateAction
from trytond import backend
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval
from trytond.rpc import RPC


class DeactivateDependencyError(UserError):
    pass


def filter_state(state):
    def filter(func):
        @wraps(func)
        def wrapper(cls, modules):
            modules = [m for m in modules if m.state == state]
            return func(cls, modules)
        return wrapper
    return filter


class Module(ModelSQL, ModelView):
    "Module"
    __name__ = "ir.module"
    name = fields.Char("Name", readonly=True, required=True)
    version = fields.Function(fields.Char('Version'), 'get_version')
    dependencies = fields.One2Many('ir.module.dependency',
        'module', 'Dependencies', readonly=True)
    parents = fields.Function(fields.One2Many('ir.module', None, 'Parents'),
        'get_parents')
    childs = fields.Function(fields.One2Many('ir.module', None, 'Childs'),
        'get_childs')
    state = fields.Selection([
        ('not activated', 'Not Activated'),
        ('activated', 'Activated'),
        ('to upgrade', 'To be upgraded'),
        ('to remove', 'To be removed'),
        ('to activate', 'To be activated'),
        ], string='State', readonly=True)

    @classmethod
    def __setup__(cls):
        super(Module, cls).__setup__()
        table = cls.__table__()
        cls._sql_constraints = [
            ('name_uniq', Unique(table, table.name),
                'The name of the module must be unique!'),
        ]
        cls._order.insert(0, ('name', 'ASC'))
        cls.__rpc__.update({
                'on_write': RPC(instantiate=0),
                })
        cls._buttons.update({
                'activate': {
                    'invisible': Eval('state') != 'not activated',
                    'depends': ['state'],
                    },
                'activate_cancel': {
                    'invisible': Eval('state') != 'to activate',
                    'depends': ['state'],
                    },
                'deactivate': {
                    'invisible': Eval('state') != 'activated',
                    'depends': ['state'],
                    },
                'deactivate_cancel': {
                    'invisible': Eval('state') != 'to remove',
                    'depends': ['state'],
                    },
                'upgrade': {
                    'invisible': Eval('state') != 'activated',
                    'depends': ['state'],
                    },
                'upgrade_cancel': {
                    'invisible': Eval('state') != 'to upgrade',
                    'depends': ['state'],
                    },
                })

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        sql_table = cls.__table__()
        model_data_sql_table = ModelData.__table__()
        cursor = Transaction().connection.cursor()

        # Migration from 3.6: remove double module
        old_table = 'ir_module_module'
        if backend.TableHandler.table_exist(old_table):
            backend.TableHandler.table_rename(old_table, cls._table)

        super(Module, cls).__register__(module_name)

        # Migration from 4.0: rename installed to activated
        cursor.execute(*sql_table.update(
                [sql_table.state], ['activated'],
                where=sql_table.state == 'installed'))
        cursor.execute(*sql_table.update(
                [sql_table.state], ['not activated'],
                where=sql_table.state == 'uninstalled'))

        # Migration from 4.6: register buttons on ir module
        button_fs_ids = [
            'module_activate_button',
            'module_activate_cancel_button',
            'module_deactivate_button',
            'module_deactivate_cancel_button',
            'module_upgrade_button',
            'module_upgrade_cancel_button',
            ]
        cursor.execute(*model_data_sql_table.update(
                [model_data_sql_table.module], ['ir'],
                where=((model_data_sql_table.module == 'res')
                    & (model_data_sql_table.fs_id.in_(button_fs_ids)))))

    @staticmethod
    def default_state():
        return 'not activated'

    def get_version(self, name):
        return get_module_info(self.name).get('version', '')

    @classmethod
    def get_parents(cls, modules, name):
        parent_names = list(set(d.name for m in modules
                    for d in m.dependencies))
        parents = cls.search([
                ('name', 'in', parent_names),
                ])
        name2id = dict((m.name, m.id) for m in parents)
        return dict((m.id, [name2id[d.name] for d in m.dependencies])
            for m in modules)

    @classmethod
    def get_childs(cls, modules, name):
        child_ids = dict((m.id, []) for m in modules)
        name2id = dict((m.name, m.id) for m in modules)
        childs = cls.search([
                ('dependencies.name', 'in', list(name2id.keys())),
                ])
        for child in childs:
            for dep in child.dependencies:
                if dep.name in name2id:
                    child_ids[name2id[dep.name]].append(child.id)
        return child_ids

    @classmethod
    def delete(cls, records):
        for module in records:
            if module.state in (
                    'activated',
                    'to upgrade',
                    'to remove',
                    'to activate',
                    ):
                raise AccessError(gettext('ir.msg_module_delete_state'))
        return super(Module, cls).delete(records)

    @classmethod
    def on_write(cls, modules):
        dependencies = set()

        def get_parents(module):
            parents = set(p.id for p in module.parents)
            for p in module.parents:
                parents.update(get_parents(p))
            return parents

        def get_childs(module):
            childs = set(c.id for c in module.childs)
            for c in module.childs:
                childs.update(get_childs(c))
            return childs

        for module in modules:
            dependencies.update(get_parents(module))
            dependencies.update(get_childs(module))
        return list(dependencies)

    @classmethod
    @ModelView.button
    @filter_state('not activated')
    def activate(cls, modules):
        modules_activated = set(modules)

        def get_parents(module):
            parents = set(p for p in module.parents)
            for p in module.parents:
                parents.update(get_parents(p))
            return parents

        for module in modules:
            modules_activated.update((m for m in get_parents(module)
                    if m.state == 'not activated'))
        cls.write(list(modules_activated), {
                'state': 'to activate',
                })

    @classmethod
    @ModelView.button
    @filter_state('activated')
    def upgrade(cls, modules):
        modules_activated = set(modules)

        def get_childs(module):
            childs = set(c for c in module.childs)
            for c in module.childs:
                childs.update(get_childs(c))
            return childs

        for module in modules:
            modules_activated.update((m for m in get_childs(module)
                    if m.state == 'activated'))
        cls.write(list(modules_activated), {
                'state': 'to upgrade',
                })

    @classmethod
    @ModelView.button
    @filter_state('to activate')
    def activate_cancel(cls, modules):
        cls.write(modules, {
                'state': 'not activated',
                })

    @classmethod
    @ModelView.button
    @filter_state('activated')
    def deactivate(cls, modules):
        pool = Pool()
        Module = pool.get('ir.module')
        Dependency = pool.get('ir.module.dependency')
        module_table = Module.__table__()
        dep_table = Dependency.__table__()
        cursor = Transaction().connection.cursor()
        for module in modules:
            cursor.execute(*dep_table.join(module_table,
                    condition=(dep_table.module == module_table.id)
                    ).select(module_table.state, module_table.name,
                    where=(dep_table.name == module.name)
                    & NotIn(
                        module_table.state, ['not activated', 'to remove'])))
            res = cursor.fetchall()
            if res:
                raise DeactivateDependencyError(
                    gettext('ir.msg_module_deactivate_dependency'),
                    '\n'.join('\t%s: %s' % (x[0], x[1]) for x in res))
        cls.write(modules, {'state': 'to remove'})

    @classmethod
    @ModelView.button
    @filter_state('to remove')
    def deactivate_cancel(cls, modules):
        cls.write(modules, {'state': 'not activated'})

    @classmethod
    @ModelView.button
    @filter_state('to upgrade')
    def upgrade_cancel(cls, modules):
        cls.write(modules, {'state': 'activated'})

    @classmethod
    def update_list(cls):
        'Update the list of available packages'
        count = 0
        module_names = get_module_list()

        modules = cls.search([])
        name2id = dict((m.name, m.id) for m in modules)
        cls.delete([m for m in modules
                if m.state != 'activated' and m.name not in module_names])

        # iterate through activated modules and mark them as being so
        for name in module_names:
            if name in name2id:
                module = cls(name2id[name])
                tryton = get_module_info(name)
                cls._update_dependencies(module, tryton.get('depends', []))
                continue

            tryton = get_module_info(name)
            if not tryton:
                continue
            module, = cls.create([{
                        'name': name,
                        'state': 'not activated',
                        }])
            count += 1
            cls._update_dependencies(module, tryton.get('depends', []))
        return count

    @classmethod
    def _update_dependencies(cls, module, depends=None):
        pool = Pool()
        Dependency = pool.get('ir.module.dependency')
        Dependency.delete([x for x in module.dependencies
            if x.name not in depends])
        if depends is None:
            depends = []
        # Restart Browse Cache for deleted dependencies
        module = cls(module.id)
        dependency_names = [x.name for x in module.dependencies]
        to_create = []
        for depend in depends:
            if depend not in dependency_names:
                to_create.append({
                        'module': module.id,
                        'name': depend,
                        })
        if to_create:
            Dependency.create(to_create)


class ModuleDependency(ModelSQL, ModelView):
    "Module dependency"
    __name__ = "ir.module.dependency"
    name = fields.Char('Name')
    module = fields.Many2One('ir.module', 'Module', select=True,
       ondelete='CASCADE', required=True)
    state = fields.Function(fields.Selection([
                ('not activated', 'Not Activated'),
                ('activated', 'Activated'),
                ('to upgrade', 'To be upgraded'),
                ('to remove', 'To be removed'),
                ('to activate', 'To be activated'),
                ('unknown', 'Unknown'),
                ], 'State', readonly=True), 'get_state')

    @classmethod
    def __setup__(cls):
        super(ModuleDependency, cls).__setup__()
        table = cls.__table__()
        cls._sql_constraints += [
            ('name_module_uniq', Unique(table, table.name, table.module),
                'Dependency must be unique by module!'),
        ]

    @classmethod
    def __register__(cls, module_name):
        # Migration from 3.6: remove double module
        old_table = 'ir_module_module_dependency'
        if backend.TableHandler.table_exist(old_table):
            backend.TableHandler.table_rename(old_table, cls._table)

        super(ModuleDependency, cls).__register__(module_name)

    def get_state(self, name):
        pool = Pool()
        Module = pool.get('ir.module')
        dependencies = Module.search([
                ('name', '=', self.name),
                ])
        if dependencies:
            return dependencies[0].state
        else:
            return 'unknown'


class ModuleConfigWizardItem(sequence_ordered(), ModelSQL, ModelView):
    "Config wizard to run after activating a module"
    __name__ = 'ir.module.config_wizard.item'
    action = fields.Many2One('ir.action', 'Action', required=True,
        readonly=True)
    state = fields.Selection([
        ('open', 'Open'),
        ('done', 'Done'),
        ], string='State', required=True, select=True)

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        model_data = ModelData.__table__()

        # Migration from 3.6: remove double module
        old_table = 'ir_module_module_config_wizard_item'
        if backend.TableHandler.table_exist(old_table):
            backend.TableHandler.table_rename(old_table, cls._table)
        cursor.execute(*model_data.update(
                columns=[model_data.model],
                values=[cls.__name__],
                where=(model_data.model
                    == 'ir.module.module.config_wizard.item')))

        super(ModuleConfigWizardItem, cls).__register__(module_name)

        table = cls.__table_handler__(module_name)

        # Migration from 5.0: remove required on sequence
        table.not_null_action('sequence', 'remove')

    @staticmethod
    def default_state():
        return 'open'

    @staticmethod
    def default_sequence():
        return 10


class ModuleConfigWizardFirst(ModelView):
    'Module Config Wizard First'
    __name__ = 'ir.module.config_wizard.first'


class ModuleConfigWizardOther(ModelView):
    'Module Config Wizard Other'
    __name__ = 'ir.module.config_wizard.other'

    percentage = fields.Float('Percentage', readonly=True)

    @staticmethod
    def default_percentage():
        pool = Pool()
        Item = pool.get('ir.module.config_wizard.item')
        done = Item.search([
            ('state', '=', 'done'),
            ], count=True)
        all = Item.search([], count=True)
        return done / all


class ModuleConfigWizardDone(ModelView):
    'Module Config Wizard Done'
    __name__ = 'ir.module.config_wizard.done'


class ModuleConfigWizard(Wizard):
    'Run config wizards'
    __name__ = 'ir.module.config_wizard'

    class ConfigStateAction(StateAction):

        def __init__(self):
            StateAction.__init__(self, None)

        def get_action(self):
            pool = Pool()
            Item = pool.get('ir.module.config_wizard.item')
            Action = pool.get('ir.action')
            items = Item.search([
                ('state', '=', 'open'),
                ], limit=1)
            if items:
                item = items[0]
                Item.write([item], {
                        'state': 'done',
                        })
                return Action.get_action_values(item.action.type,
                    [item.action.id])[0]

    start = StateTransition()
    first = StateView('ir.module.config_wizard.first',
        'ir.module_config_wizard_first_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('OK', 'action', 'tryton-ok', default=True),
            ])
    other = StateView('ir.module.config_wizard.other',
        'ir.module_config_wizard_other_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Next', 'action', 'tryton-forward', default=True),
            ])
    action = ConfigStateAction()
    done = StateView('ir.module.config_wizard.done',
        'ir.module_config_wizard_done_view_form', [
            Button('OK', 'end', 'tryton-ok', default=True),
            ])

    def transition_start(self):
        res = self.transition_action()
        if res == 'other':
            return 'first'
        return res

    def transition_action(self):
        pool = Pool()
        Item = pool.get('ir.module.config_wizard.item')
        items = Item.search([
                ('state', '=', 'open'),
                ])
        if items:
            return 'other'
        return 'done'

    def end(self):
        return 'reload menu'


class ModuleActivateUpgradeStart(ModelView):
    'Module Activate Upgrade Start'
    __name__ = 'ir.module.activate_upgrade.start'
    module_info = fields.Text('Modules to update', readonly=True)


class ModuleActivateUpgradeDone(ModelView):
    'Module Activate Upgrade Done'
    __name__ = 'ir.module.activate_upgrade.done'


class ModuleActivateUpgrade(Wizard):
    "Activate / Upgrade modules"
    __name__ = 'ir.module.activate_upgrade'

    start = StateView('ir.module.activate_upgrade.start',
        'ir.module_activate_upgrade_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Start Upgrade', 'upgrade', 'tryton-ok', default=True),
            ])
    upgrade = StateTransition()
    done = StateView('ir.module.activate_upgrade.done',
        'ir.module_activate_upgrade_done_view_form', [
            Button('OK', 'config', 'tryton-ok', default=True),
            ])
    config = StateAction('ir.act_module_config_wizard')

    @classmethod
    def check_access(cls):
        # Use new transaction to prevent lock when activating modules
        with Transaction().new_transaction():
            super(ModuleActivateUpgrade, cls).check_access()

    @staticmethod
    def default_start(fields):
        pool = Pool()
        Module = pool.get('ir.module')
        modules = Module.search([
                ('state', 'in', ['to upgrade', 'to remove', 'to activate']),
                ])
        return {
            'module_info': '\n'.join(x.name + ': ' + x.state
                for x in modules),
            }

    def __init__(self, session_id):
        pass

    def _save(self):
        pass

    def transition_upgrade(self):
        pool = Pool()
        Module = pool.get('ir.module')
        Lang = pool.get('ir.lang')
        transaction = Transaction()
        with transaction.new_transaction():
            modules = Module.search([
                ('state', 'in', ['to upgrade', 'to remove', 'to activate']),
                ])
            update = [m.name for m in modules]
            langs = Lang.search([
                ('translatable', '=', True),
                ])
            lang = [x.code for x in langs]
        if update:
            pool.init(update=update, lang=lang)
            Cache.refresh_pool(transaction)
        return 'done'


class ModuleConfig(Wizard):
    'Configure Modules'
    __name__ = 'ir.module.config'

    start = StateAction('ir.act_module_form')

    @staticmethod
    def transition_start():
        return 'end'
