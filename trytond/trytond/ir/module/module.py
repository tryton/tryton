#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import os
from trytond.model import ModelView, ModelSQL, fields
import trytond.tools as tools
from trytond.modules import create_graph, get_module_list
from trytond.wizard import Wizard, StateView, Button, StateTransition, \
    StateAction
from trytond.backend import TableHandler
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval


class Module(ModelSQL, ModelView):
    "Module"
    _name = "ir.module.module"
    _description = __doc__
    name = fields.Char("Name", readonly=True, required=True)
    shortdesc = fields.Char('Short description', readonly=True, translate=True)
    description = fields.Text("Description", readonly=True, translate=True)
    author = fields.Char("Author", readonly=True)
    website = fields.Char("Website", readonly=True)
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

    def __init__(self):
        super(Module, self).__init__()
        self._sql_constraints = [
            ('name_uniq', 'unique (name)',
                'The name of the module must be unique!'),
        ]
        self._order.insert(0, ('name', 'ASC'))
        self._rpc.update({
            'on_write': False,
        })
        self._error_messages.update({
            'delete_state': 'You can not remove a module that is installed ' \
                    'or will be installed',
            'missing_dep': 'Missing dependencies %s for module "%s"',
            'uninstall_dep': 'The modules you are trying to uninstall ' \
                    'depends on installed modules:',
            })
        self._buttons.update({
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

    def default_state(self):
        return 'uninstalled'

    @staticmethod
    def get_module_info(name):
        "Return the content of the __tryton__.py"
        try:
            if name in ['ir', 'res', 'webdav']:
                file_p = tools.file_open(os.path.join(name, '__tryton__.py'))
            else:
                file_p = tools.file_open(os.path.join(name, '__tryton__.py'))
            with file_p:
                data = file_p.read()
            info = tools.safe_eval(data)
        except Exception:
            return {}
        return info

    def get_version(self, ids, name):
        res = {}
        for module in self.browse(ids):
            res[module.id] = Module.get_module_info(
                    module.name).get('version', '')
        return res

    def get_parents(self, ids, name):
        parents = {}
        modules = self.browse(ids)
        parent_names = list(set(d.name for m in modules
                    for d in m.dependencies))
        parent_ids = self.search([
                ('name', 'in', parent_names),
                ])
        name2id = dict((m.name, m.id) for m in self.browse(parent_ids))
        for module in self.browse(ids):
            parents[module.id] = [name2id[d.name] for d in module.dependencies]
        return parents

    def get_childs(self, ids, name):
        childs = dict((i, []) for i in ids)
        modules = self.browse(ids)
        names = [m.name for m in modules]
        child_ids = self.search([
                ('dependencies.name', 'in', names),
                ])
        for child in self.browse(child_ids):
            for dep in child.dependencies:
                if dep.module.id in childs:
                    childs[dep.module.id].append(child.id)
        return childs

    def delete(self, ids):
        if not ids:
            return True
        if isinstance(ids, (int, long)):
            ids = [ids]
        for module in self.browse(ids):
            if module.state in (
                    'installed',
                    'to upgrade',
                    'to remove',
                    'to install',
                    ):
                self.raise_user_error('delete_state')
        return super(Module, self).delete(ids)

    def on_write(self, ids):
        if not ids:
            return []
        res = []
        graph, packages, later = create_graph(get_module_list())
        for module in self.browse(ids):
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
            res += self.search([
                ('name', 'in', list(dependencies)),
                ])
        return list({}.fromkeys(res))

    def state_install(self, ids):
        graph, packages, later = create_graph(get_module_list())
        for module in self.browse(ids):
            if module.name not in graph:
                missings = []
                for package, deps, xdep, info in packages:
                    if package == module.name:
                        missings = [x for x in deps if x not in graph]
                self.raise_user_error('missing_dep', (missings, module.name))

            def get_parents(module):
                parents = set(p.name for p in module.parents)
                for p in module.parents:
                    parents.update(get_parents(p))
                return parents
            dependencies = list(get_parents(module))
            module_install_ids = self.search([
                ('name', 'in', dependencies),
                ('state', '=', 'uninstalled'),
                ])
            self.write(module_install_ids + [module.id], {
                'state': 'to install',
                })

    def state_upgrade(self, ids):
        graph, packages, later = create_graph(get_module_list())
        for module in self.browse(ids):
            if module.name not in graph:
                missings = []
                for package, deps, xdep, info in packages:
                    if package == module.name:
                        missings = [x for x in deps if x not in graph]
                self.raise_user_error('missing_dep', (missings, module.name))

            def get_childs(name, graph):
                childs = set(x.name for x in graph[name].childs)
                childs2 = set()
                for child in childs:
                    childs2.update(get_childs(child, graph))
                childs.update(childs2)
                return childs
            dependencies = list(get_childs(module.name, graph))
            module_installed_ids = self.search([
                ('name', 'in', dependencies),
                ('state', '=', 'installed'),
                ])
            self.write(module_installed_ids + [module.id], {
                'state': 'to upgrade',
                })

    @ModelView.button
    def install(self, ids):
        return self.state_install(ids)

    @ModelView.button
    def install_cancel(self, ids):
        self.write(ids, {
            'state': 'uninstalled',
            })
        return True

    @ModelView.button
    def uninstall(self, ids):
        cursor = Transaction().cursor
        for module in self.browse(ids):
            cursor.execute('SELECT m.state, m.name ' \
                    'FROM ir_module_module_dependency d ' \
                    'JOIN ir_module_module m on (d.module = m.id) ' \
                    'WHERE d.name = %s ' \
                        'AND m.state not in ' \
                        '(\'uninstalled\', \'to remove\')',
                            (module.name,))
            res = cursor.fetchall()
            if res:
                self.raise_user_error('uninstall_dep',
                        error_description='\n'.join(
                            '\t%s: %s' % (x[0], x[1]) for x in res))
        self.write(ids, {'state': 'to remove'})
        return True

    @ModelView.button
    def uninstall_cancel(self, ids):
        self.write(ids, {'state': 'installed'})
        return True

    @ModelView.button
    def upgrade(self, ids):
        return self.state_upgrade(ids)

    @ModelView.button
    def upgrade_cancel(self, ids):
        self.write(ids, {'state': 'installed'})
        return True

    # update the list of available packages
    def update_list(self):
        pool = Pool()
        lang_obj = pool.get('ir.lang')
        res = 0
        with Transaction().set_context(language=False):
            lang_ids = lang_obj.search([
                ('translatable', '=', True),
                ])
            lang_codes = [x.code for x in lang_obj.browse(lang_ids)]

            module_names = get_module_list()

            module_ids = self.search([])
            modules = self.browse(module_ids)
            name2module = {}
            for module in modules:
                name2module.setdefault(module.name, {})
                name2module[module.name]['en_US'] = module
            for code in lang_codes:
                with Transaction().set_context(language=code):
                    modules = self.browse(module_ids)
                for module in modules:
                    name2module[module.name][code] = module

            # iterate through installed modules and mark them as being so
            for name in module_names:
                mod_name = name
                if mod_name in name2module.keys():
                    mod = name2module[mod_name]['en_US']
                    tryton = Module.get_module_info(mod_name)

                    if mod.description != tryton.get('description',
                            '').decode('utf-8', 'ignore') \
                            or mod.shortdesc != tryton.get('name',
                                    '').decode('utf-8', 'ignore') \
                            or mod.author != tryton.get('author',
                                    '').decode('utf-8', 'ignore') \
                            or mod.website != tryton.get('website',
                                    '').decode('utf-8', 'ignore'):
                        self.write(mod.id, {
                            'description': tryton.get('description', ''),
                            'shortdesc': tryton.get('name', ''),
                            'author': tryton.get('author', ''),
                            'website': tryton.get('website', ''),
                            })

                    for code in lang_codes:
                        mod2 = name2module[mod_name][code]
                        if mod2.description != \
                                tryton.get('description_' + code,
                                        tryton.get('description', '')
                                        ).decode('utf-8', 'ignore') \
                                or mod2.shortdesc != \
                                tryton.get('name_' + code,
                                        tryton.get('name', '')
                                        ).decode('utf-8', 'ignore'):
                            with Transaction().set_context(language=code):
                                self.write(mod.id, {
                                    'description': tryton.get(
                                        'description_' + code, ''),
                                    'shortdesc': tryton.get(
                                        'name_' + code, ''),
                                    })

                    self._update_dependencies(mod, tryton.get('depends', []))
                    continue

                tryton = Module.get_module_info(mod_name)
                if not tryton:
                    continue
                new_id = self.create({
                    'name': mod_name,
                    'state': 'uninstalled',
                    'description': tryton.get('description', ''),
                    'shortdesc': tryton.get('name', ''),
                    'author': tryton.get('author', 'Unknown'),
                    'website': tryton.get('website', ''),
                })
                for code in lang_codes:
                    with Transaction().set_context(language=code):
                        self.write(new_id, {
                            'description': tryton.get(
                                'description_' + code, ''),
                            'shortdesc': tryton.get('name_' + code, ''),
                            })
                res += 1
                name2module.setdefault(mod_name, {})
                name2module[mod_name]['en_US'] = self.browse(new_id)
                self._update_dependencies(name2module[mod_name]['en_US'],
                        tryton.get('depends', []))
        return res

    def _update_dependencies(self, module, depends=None):
        pool = Pool()
        dependency_obj = pool.get('ir.module.module.dependency')
        dependency_obj.delete([x.id for x in module.dependencies
            if x.name not in depends])
        if depends is None:
            depends = []
        # Restart Browse Cache for deleted dependencies
        module = self.browse(module.id)
        dependency_names = [x.name for x in module.dependencies]
        for depend in depends:
            if depend not in dependency_names:
                dependency_obj.create({
                    'module': module.id,
                    'name': depend,
                    })

Module()


class ModuleDependency(ModelSQL, ModelView):
    "Module dependency"
    _name = "ir.module.module.dependency"
    _description = __doc__
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

    def __init__(self):
        super(ModuleDependency, self).__init__()
        self._sql_constraints += [
            ('name_module_uniq', 'UNIQUE(name, module)',
                'Dependency must be unique by module!'),
        ]

    def get_state(self, ids, name):
        result = {}
        pool = Pool()
        module_obj = pool.get('ir.module.module')
        for dependency in self.browse(ids):
            ids = module_obj.search([
                ('name', '=', dependency.name),
                ])
            if ids:
                result[dependency.id] = module_obj.browse(ids[0]).state
            else:
                result[dependency.id] = 'unknown'
        return result

ModuleDependency()


class ModuleConfigWizardItem(ModelSQL, ModelView):
    "Config wizard to run after installing module"
    _name = 'ir.module.module.config_wizard.item'
    _description = __doc__
    _rec_name = 'action'
    action = fields.Many2One('ir.action', 'Action', required=True,
        readonly=True)
    sequence = fields.Integer('Sequence', required=True)
    state = fields.Selection([
        ('open', 'Open'),
        ('done', 'Done'),
        ], string='State', required=True, select=True)

    def __init__(self):
        super(ModuleConfigWizardItem, self).__init__()
        self._order.insert(0, ('sequence', 'ASC'))

    def init(self, module_name):
        table = TableHandler(Transaction().cursor, self, module_name)

        # Migrate from 2.2 remove name
        table.drop_column('name')

        super(ModuleConfigWizardItem, self).init(module_name)

    def default_state(self):
        return 'open'

    def default_sequence(self):
        return 10

ModuleConfigWizardItem()


class ModuleConfigWizardFirst(ModelView):
    'Module Config Wizard First'
    _name = 'ir.module.module.config_wizard.first'
    _description = __doc__

ModuleConfigWizardFirst()


class ModuleConfigWizardOther(ModelView):
    'Module Config Wizard Other'
    _name = 'ir.module.module.config_wizard.other'
    _description = __doc__

    percentage = fields.Float('Percentage', readonly=True)

    def default_percentage(self):
        pool = Pool()
        item_obj = pool.get('ir.module.module.config_wizard.item')
        done = item_obj.search([
            ('state', '=', 'done'),
            ], count=True)
        all = item_obj.search([], count=True)
        return 100.0 * done / all

ModuleConfigWizardOther()


class ModuleConfigWizard(Wizard):
    'Run config wizards'
    _name = 'ir.module.module.config_wizard'

    class ConfigStateAction(StateAction):

        def __init__(self):
            StateAction.__init__(self, None)

        def get_action(self):
            pool = Pool()
            item_obj = pool.get('ir.module.module.config_wizard.item')
            action_obj = pool.get('ir.action')
            item_ids = item_obj.search([
                ('state', '=', 'open'),
                ], limit=1)
            if item_ids:
                item = item_obj.browse(item_ids[0])
                item_obj.write(item.id, {
                    'state': 'done',
                    })
                return action_obj.get_action_values(item.action.type,
                    item.action.id)

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

    def transition_start(self, session):
        res = self.transition_action(session)
        if res == 'other':
            return 'first'
        return res

    def transition_action(self, session):
        pool = Pool()
        item_obj = pool.get('ir.module.module.config_wizard.item')
        item_ids = item_obj.search([
            ('state', '=', 'open'),
            ])
        if item_ids:
            return 'other'
        return 'end'

ModuleConfigWizard()


class ModuleInstallUpgradeStart(ModelView):
    'Module Install Upgrade Start'
    _name = 'ir.module.module.install_upgrade.start'
    _description = __doc__
    module_info = fields.Text('Modules to update', readonly=True)

ModuleInstallUpgradeStart()


class ModuleInstallUpgradeDone(ModelView):
    'Module Install Upgrade Done'
    _name = 'ir.module.module.install_upgrade.done'
    _description = __doc__

ModuleInstallUpgradeDone()


class ModuleInstallUpgrade(Wizard):
    "Install / Upgrade modules"
    _name = 'ir.module.module.install_upgrade'

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

    def default_start(self, session, fields):
        pool = Pool()
        module_obj = pool.get('ir.module.module')
        module_ids = module_obj.search([
            ('state', 'in', ['to upgrade', 'to remove', 'to install']),
            ])
        modules = module_obj.browse(module_ids)
        return {
            'module_info': '\n'.join(x.name + ': ' + x.state \
                    for x in modules),
        }

    def transition_upgrade(self, session):
        pool = Pool()
        module_obj = pool.get('ir.module.module')
        lang_obj = pool.get('ir.lang')
        with Transaction().new_cursor() as transaction:
            module_ids = module_obj.search([
                ('state', 'in', ['to upgrade', 'to remove', 'to install']),
                ])
            lang_ids = lang_obj.search([
                ('translatable', '=', True),
                ])
            lang = [x.code for x in lang_obj.browse(lang_ids)]
            transaction.cursor.commit()
        if module_ids:
            pool.init(update=True, lang=lang)
        if session:
            # Don't store session to prevent concurrent update
            for state_name in session.data:
                getattr(session, state_name).dirty = False
        return 'done'

ModuleInstallUpgrade()


class ModuleConfig(Wizard):
    'Configure Modules'
    _name = 'ir.module.module.config'

    start = StateAction('ir.act_module_form')

    def transition_start(self, session):
        return 'end'

ModuleConfig()
