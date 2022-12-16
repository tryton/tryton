#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.modules import create_graph, get_module_list, get_module_info
from trytond.wizard import Wizard, StateView, Button, StateTransition, \
    StateAction
from trytond.backend import TableHandler
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval
from trytond.rpc import RPC

__all__ = [
    'Module', 'ModuleDependency', 'ModuleConfigWizardItem',
    'ModuleConfigWizardFirst', 'ModuleConfigWizardOther', 'ModuleConfigWizard',
    'ModuleInstallUpgradeStart', 'ModuleInstallUpgradeDone',
    'ModuleInstallUpgrade', 'ModuleConfig',
    ]


class Module(ModelSQL, ModelView):
    "Module"
    __name__ = "ir.module.module"
    name = fields.Char("Name", readonly=True, required=True)
    version = fields.Function(fields.Char('Version'), 'get_version')
    dependencies = fields.One2Many('ir.module.module.dependency',
        'module', 'Dependencies', readonly=True)
    parents = fields.Function(fields.One2Many('ir.module.module', None,
            'Parents'), 'get_parents')
    childs = fields.Function(fields.One2Many('ir.module.module', None,
            'Childs'), 'get_childs')
    state = fields.Selection([
        ('uninstalled', 'Not Installed'),
        ('installed', 'Installed'),
        ('to upgrade', 'To be upgraded'),
        ('to remove', 'To be removed'),
        ('to install', 'To be installed'),
        ], string='State', readonly=True)

    @classmethod
    def __setup__(cls):
        super(Module, cls).__setup__()
        cls._sql_constraints = [
            ('name_uniq', 'unique (name)',
                'The name of the module must be unique!'),
        ]
        cls._order.insert(0, ('name', 'ASC'))
        cls.__rpc__.update({
                'on_write': RPC(instantiate=0),
                })
        cls._error_messages.update({
            'delete_state': ('You can not remove a module that is installed '
                    'or will be installed'),
            'missing_dep': 'Missing dependencies %s for module "%s"',
            'uninstall_dep': ('The modules you are trying to uninstall '
                    'depends on installed modules:'),
            })
        cls._buttons.update({
                'install': {
                    'invisible': Eval('state') != 'uninstalled',
                    },
                'install_cancel': {
                    'invisible': Eval('state') != 'to install',
                    },
                'uninstall': {
                    'invisible': Eval('state') != 'installed',
                    },
                'uninstall_cancel': {
                    'invisible': Eval('state') != 'to remove',
                    },
                'upgrade': {
                    'invisible': Eval('state') != 'installed',
                    },
                'upgrade_cancel': {
                    'invisible': Eval('state') != 'to upgrade',
                    },
                })

    @staticmethod
    def default_state():
        return 'uninstalled'

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
        names = [m.name for m in modules]
        childs = cls.search([
                ('dependencies.name', 'in', names),
                ])
        for child in childs:
            for dep in child.dependencies:
                if dep.module.id in child_ids:
                    child_ids[dep.module.id].append(child.id)
        return child_ids

    @classmethod
    def delete(cls, records):
        for module in records:
            if module.state in (
                    'installed',
                    'to upgrade',
                    'to remove',
                    'to install',
                    ):
                cls.raise_user_error('delete_state')
        return super(Module, cls).delete(records)

    @classmethod
    def on_write(cls, modules):
        ids = set()
        graph, packages, later = create_graph(get_module_list())
        for module in modules:
            if module.name not in graph:
                continue

            def get_parents(module):
                parents = set(p.name for p in module.parents)
                for p in module.parents:
                    parents.update(get_parents(p))
                return parents
            dependencies = get_parents(module)

            def get_childs(module):
                childs = set(c.name for c in module.childs)
                for c in module.childs:
                    childs.update(get_childs(c))
                return childs
            dependencies.update(get_childs(module))
            ids |= set(x.id for x in cls.search([
                        ('name', 'in', list(dependencies)),
                        ]))
        return list(ids)

    @classmethod
    @ModelView.button
    def install(cls, modules):
        graph, packages, later = create_graph(get_module_list())
        for module in modules:
            if module.name not in graph:
                missings = []
                for package, deps, xdep, info in packages:
                    if package == module.name:
                        missings = [x for x in deps if x not in graph]
                cls.raise_user_error('missing_dep', (missings, module.name))

            def get_parents(module):
                parents = set(p.name for p in module.parents)
                for p in module.parents:
                    parents.update(get_parents(p))
                return parents
            dependencies = list(get_parents(module))
            modules_install = cls.search([
                    ('name', 'in', dependencies),
                    ('state', '=', 'uninstalled'),
                    ])
            cls.write(modules_install + [module], {
                    'state': 'to install',
                    })

    @classmethod
    @ModelView.button
    def upgrade(cls, modules):
        graph, packages, later = create_graph(get_module_list())
        for module in modules:
            if module.name not in graph:
                missings = []
                for package, deps, xdep, info in packages:
                    if package == module.name:
                        missings = [x for x in deps if x not in graph]
                cls.raise_user_error('missing_dep', (missings, module.name))

            def get_childs(name, graph):
                childs = set(x.name for x in graph[name].childs)
                childs2 = set()
                for child in childs:
                    childs2.update(get_childs(child, graph))
                childs.update(childs2)
                return childs
            dependencies = list(get_childs(module.name, graph))
            modules_installed = cls.search([
                    ('name', 'in', dependencies),
                    ('state', '=', 'installed'),
                    ])
            cls.write(modules_installed + [module], {
                    'state': 'to upgrade',
                    })

    @classmethod
    @ModelView.button
    def install_cancel(cls, modules):
        cls.write(modules, {
                'state': 'uninstalled',
                })

    @classmethod
    @ModelView.button
    def uninstall(cls, modules):
        cursor = Transaction().cursor
        for module in modules:
            cursor.execute('SELECT m.state, m.name '
                'FROM ir_module_module_dependency d '
                'JOIN ir_module_module m on (d.module = m.id) '
                'WHERE d.name = %s '
                    'AND m.state not in '
                    '(\'uninstalled\', \'to remove\')',
                (module.name,))
            res = cursor.fetchall()
            if res:
                cls.raise_user_error('uninstall_dep',
                        error_description='\n'.join(
                            '\t%s: %s' % (x[0], x[1]) for x in res))
        cls.write(modules, {'state': 'to remove'})

    @classmethod
    @ModelView.button
    def uninstall_cancel(cls, modules):
        cls.write(modules, {'state': 'installed'})

    @classmethod
    @ModelView.button
    def upgrade_cancel(cls, modules):
        cls.write(modules, {'state': 'installed'})

    @classmethod
    def update_list(cls):
        'Update the list of available packages'
        count = 0
        module_names = get_module_list()

        modules = cls.search([])
        name2module = dict((m.name, m) for m in modules)

        # iterate through installed modules and mark them as being so
        for name in module_names:
            if name in name2module:
                module = name2module[name]
                tryton = get_module_info(name)
                cls._update_dependencies(module, tryton.get('depends', []))
                continue

            tryton = get_module_info(name)
            if not tryton:
                continue
            module, = cls.create([{
                        'name': name,
                        'state': 'uninstalled',
                        }])
            count += 1
            cls._update_dependencies(module, tryton.get('depends', []))
        return count

    @classmethod
    def _update_dependencies(cls, module, depends=None):
        pool = Pool()
        Dependency = pool.get('ir.module.module.dependency')
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
    __name__ = "ir.module.module.dependency"
    name = fields.Char('Name')
    module = fields.Many2One('ir.module.module', 'Module', select=True,
       ondelete='CASCADE', required=True)
    state = fields.Function(fields.Selection([
                ('uninstalled', 'Not Installed'),
                ('installed', 'Installed'),
                ('to upgrade', 'To be upgraded'),
                ('to remove', 'To be removed'),
                ('to install', 'To be installed'),
                ('unknown', 'Unknown'),
                ], 'State', readonly=True), 'get_state')

    @classmethod
    def __setup__(cls):
        super(ModuleDependency, cls).__setup__()
        cls._sql_constraints += [
            ('name_module_uniq', 'UNIQUE(name, module)',
                'Dependency must be unique by module!'),
        ]

    def get_state(self, name):
        pool = Pool()
        Module = pool.get('ir.module.module')
        dependencies = Module.search([
                ('name', '=', self.name),
                ])
        if dependencies:
            return dependencies[0].state
        else:
            return 'unknown'


class ModuleConfigWizardItem(ModelSQL, ModelView):
    "Config wizard to run after installing module"
    __name__ = 'ir.module.module.config_wizard.item'
    _rec_name = 'action'
    action = fields.Many2One('ir.action', 'Action', required=True,
        readonly=True)
    sequence = fields.Integer('Sequence', required=True)
    state = fields.Selection([
        ('open', 'Open'),
        ('done', 'Done'),
        ], string='State', required=True, select=True)

    @classmethod
    def __setup__(cls):
        super(ModuleConfigWizardItem, cls).__setup__()
        cls._order.insert(0, ('sequence', 'ASC'))

    @classmethod
    def __register__(cls, module_name):
        table = TableHandler(Transaction().cursor, cls, module_name)

        # Migrate from 2.2 remove name
        table.drop_column('name')

        super(ModuleConfigWizardItem, cls).__register__(module_name)

    @staticmethod
    def default_state():
        return 'open'

    @staticmethod
    def default_sequence():
        return 10


class ModuleConfigWizardFirst(ModelView):
    'Module Config Wizard First'
    __name__ = 'ir.module.module.config_wizard.first'


class ModuleConfigWizardOther(ModelView):
    'Module Config Wizard Other'
    __name__ = 'ir.module.module.config_wizard.other'

    percentage = fields.Float('Percentage', readonly=True)

    @staticmethod
    def default_percentage():
        pool = Pool()
        Item = pool.get('ir.module.module.config_wizard.item')
        done = Item.search([
            ('state', '=', 'done'),
            ], count=True)
        all = Item.search([], count=True)
        return 100.0 * done / all


class ModuleConfigWizard(Wizard):
    'Run config wizards'
    __name__ = 'ir.module.module.config_wizard'

    class ConfigStateAction(StateAction):

        def __init__(self):
            StateAction.__init__(self, None)

        def get_action(self):
            pool = Pool()
            Item = pool.get('ir.module.module.config_wizard.item')
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
    first = StateView('ir.module.module.config_wizard.first',
        'ir.module_config_wizard_first_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Ok', 'action', 'tryton-ok', default=True),
            ])
    other = StateView('ir.module.module.config_wizard.other',
        'ir.module_config_wizard_other_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Next', 'action', 'tryton-go-next', default=True),
            ])
    action = ConfigStateAction()

    def transition_start(self):
        res = self.transition_action()
        if res == 'other':
            return 'first'
        return res

    def transition_action(self):
        pool = Pool()
        Item = pool.get('ir.module.module.config_wizard.item')
        items = Item.search([
                ('state', '=', 'open'),
                ])
        if items:
            return 'other'
        return 'end'


class ModuleInstallUpgradeStart(ModelView):
    'Module Install Upgrade Start'
    __name__ = 'ir.module.module.install_upgrade.start'
    module_info = fields.Text('Modules to update', readonly=True)


class ModuleInstallUpgradeDone(ModelView):
    'Module Install Upgrade Done'
    __name__ = 'ir.module.module.install_upgrade.done'


class ModuleInstallUpgrade(Wizard):
    "Install / Upgrade modules"
    __name__ = 'ir.module.module.install_upgrade'

    start = StateView('ir.module.module.install_upgrade.start',
        'ir.module_install_upgrade_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Start Upgrade', 'upgrade', 'tryton-ok', default=True),
            ])
    upgrade = StateTransition()
    done = StateView('ir.module.module.install_upgrade.done',
        'ir.module_install_upgrade_done_view_form', [
            Button('Ok', 'config', 'tryton-ok', default=True),
            ])
    config = StateAction('ir.act_module_config_wizard')

    @staticmethod
    def default_start(fields):
        pool = Pool()
        Module = pool.get('ir.module.module')
        modules = Module.search([
                ('state', 'in', ['to upgrade', 'to remove', 'to install']),
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
        Module = pool.get('ir.module.module')
        Lang = pool.get('ir.lang')
        with Transaction().new_cursor() as transaction:
            modules = Module.search([
                ('state', 'in', ['to upgrade', 'to remove', 'to install']),
                ])
            langs = Lang.search([
                ('translatable', '=', True),
                ])
            lang = [x.code for x in langs]
            transaction.cursor.commit()
        if modules:
            pool.init(update=True, lang=lang)
        return 'done'


class ModuleConfig(Wizard):
    'Configure Modules'
    __name__ = 'ir.module.module.config'

    start = StateAction('ir.act_module_form')

    @staticmethod
    def transition_start():
        return 'end'
