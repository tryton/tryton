# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from functools import wraps

from sql.operators import NotIn

from trytond.cache import Cache
from trytond.exceptions import UserError
from trytond.i18n import gettext
from trytond.model import ModelSQL, ModelView, Unique, fields, sequence_ordered
from trytond.model.exceptions import AccessError
from trytond.modules import get_module_info, get_modules
from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.rpc import RPC
from trytond.tools import grouped_slice
from trytond.transaction import Transaction
from trytond.wizard import (
    Button, StateAction, StateTransition, StateView, Wizard)


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
        "Update the list of available modules"
        pool = Pool()
        Dependency = pool.get('ir.module.dependency')
        module_names = get_modules(with_test=Pool.test)
        for sub_module_names in grouped_slice(module_names):
            cls.delete(cls.search([
                        ('state', '!=', 'activated'),
                        ('name', 'not in', list(sub_module_names)),
                        ]))
        modules = cls.search([])
        name2module = {m.name: m for m in modules}

        for name in set(module_names) - name2module.keys():
            name2module[name] = cls(name=name, state=cls.default_state())
        cls.save(name2module.values())

        to_save, to_delete = [], []
        for module in name2module.values():
            depends = set(get_module_info(module.name).get('depends', []))
            for dependency in module.dependencies:
                if dependency.name not in depends:
                    to_delete.append(dependency)
            for name in depends - {d.name for d in module.dependencies}:
                to_save.append(Dependency(name=name, module=module))
        if to_delete:
            Dependency.delete(to_delete)
        if to_save:
            Dependency.save(to_save)


class ModuleDependency(ModelSQL, ModelView):
    "Module dependency"
    __name__ = "ir.module.dependency"
    name = fields.Char('Name')
    module = fields.Many2One('ir.module', 'Module',
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
        cls.__access__.add('module')
        table = cls.__table__()
        cls._sql_constraints += [
            ('name_module_uniq', Unique(table, table.name, table.module),
                'Dependency must be unique by module!'),
        ]

    @classmethod
    def get_state(cls, dependencies, name):
        pool = Pool()
        Module = pool.get('ir.module')
        modules = []
        names = [d.name for d in dependencies]
        for sub_names in grouped_slice(names):
            modules.extend(Module.search([
                        ('name', 'in', list(sub_names)),
                        ]))
        name2state = {m.name: m.state for m in modules}
        return {d.id: name2state.get(d.name, 'unknown') for d in dependencies}


class ModuleConfigWizardItem(sequence_ordered(), ModelSQL, ModelView):
    "Config wizard to run after activating a module"
    __name__ = 'ir.module.config_wizard.item'
    action = fields.Many2One('ir.action', 'Action', required=True,
        readonly=True)
    state = fields.Selection([
        ('open', 'Open'),
        ('done', 'Done'),
        ], string="State", required=True, sort=False)

    @classmethod
    def __register__(cls, module_name):
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

    percentage = fields.Float('Percentage', digits=(1, 2), readonly=True)

    @staticmethod
    def default_percentage():
        pool = Pool()
        Item = pool.get('ir.module.config_wizard.item')
        done = Item.search([
            ('state', '=', 'done'),
            ], count=True)
        all = Item.search([], count=True)
        return round(done / all, 2)


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
        ModelData = pool.get('ir.model.data')
        items = Item.search([
                ('state', '=', 'open'),
                ])
        if items:
            return 'other'
        items = Item.search([
                ('state', '=', 'done'),
                ], order=[('write_date', 'DESC')], limit=1)
        if items:
            item, = items
            # module item will re-launch the config wizard
            # so do not display the done message.
            if item.id == ModelData.get_id('ir', 'config_wizard_item_module'):
                return 'end'
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
            Button("OK", 'next_', 'tryton-ok', default=True),
            ])
    next_ = StateTransition()
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

    def transition_next_(self):
        pool = Pool()
        Item = pool.get('ir.module.config_wizard.item')
        items = Item.search([
            ('state', '=', 'open'),
            ], limit=1)
        if items:
            return 'config'
        else:
            return 'end'

    def end(self):
        return 'reload menu'


class ModuleConfig(Wizard):
    'Configure Modules'
    __name__ = 'ir.module.config'

    start = StateView('ir.module.config.start',
        'ir.module_config_start_view_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Activate", 'activate', 'tryton-ok', default=True),
            ])
    activate = StateAction('ir.act_module_activate_upgrade')

    def do_activate(self, action):
        pool = Pool()
        Module = pool.get('ir.module')
        Module.activate(list(self.start.modules))
        return action, {}

    @classmethod
    def transition_activate(cls):
        return 'end'


class ModuleConfigStart(ModelView):
    "Configure Modules"
    __name__ = 'ir.module.config.start'

    modules = fields.Many2Many(
        'ir.module', None, None, "Modules",
        domain=[
            ('name', '!=', 'tests'),
            ('state', '=', 'not activated'),
            ])
