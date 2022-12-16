#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import os
from trytond.model import ModelView, ModelSQL, fields
import trytond.tools as tools
from trytond.modules import MODULES_PATH, create_graph, get_module_list
from trytond.wizard import Wizard
from trytond.backend import Database
from trytond.pool import Pool
from trytond.transaction import Transaction


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
            'button_install': True,
            'button_install_cancel': True,
            'button_uninstall': True,
            'button_uninstall_cancel': True,
            'button_upgrade': True,
            'button_upgrade_cancel': True,
            'on_write': False,
        })
        self._error_messages.update({
            'delete_state': 'You can not remove a module that is installed ' \
                    'or will be installed',
            'missing_dep': 'Missing dependencies %s for module "%s"',
            'uninstall_dep': 'The modules you are trying to uninstall ' \
                    'depends on installed modules:',
            })

    def default_state(self):
        return 'uninstalled'

    @staticmethod
    def get_module_info(name):
        "Return the content of the __tryton__.py"
        try:
            if name in ['ir', 'workflow', 'res', 'webdav']:
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
            def get_parents(name, graph):
                parents = set()
                for node in graph:
                    if graph[name] in node.childs:
                        parents.add(node.name)
                for parent in parents.copy():
                    parents.update(get_parents(parent, graph))
                return parents
            dependencies = get_parents(module.name, graph)
            def get_childs(name, graph):
                childs = set(x.name for x in graph[name].childs)
                childs2 = set()
                for child in childs:
                    childs2.update(get_childs(child, graph))
                childs.update(childs2)
                return childs
            dependencies.update(get_childs(module.name, graph))
            res += self.search([
                ('name', 'in', list(dependencies)),
                ])
        return list({}.fromkeys(res))

    def state_install(self, ids):
        graph, packages, later = create_graph(get_module_list())
        for module in self.browse(ids):
            if module.name not in graph:
                missings = []
                for package, deps, datas in packages:
                    if package == module.name:
                        missings = [x for x in deps if x not in graph]
                self.raise_user_error('missing_dep', (missings, module.name))
            def get_parents(name, graph):
                parents = set()
                for node in graph:
                    if graph[name] in node.childs:
                        parents.add(node.name)
                for parent in parents.copy():
                    parents.update(get_parents(parent, graph))
                return parents
            dependencies = list(get_parents(module.name, graph))
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
                for package, deps, datas in packages:
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

    def button_install(self, ids):
        return self.state_install(ids)

    def button_install_cancel(self, ids):
        self.write(ids, {
            'state': 'uninstalled',
            })
        return True

    def button_uninstall(self, ids):
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

    def button_uninstall_cancel(self, ids):
        self.write(ids, {'state': 'installed'})
        return True

    def button_upgrade(self, ids):
        return self.state_upgrade(ids)

    def button_upgrade_cancel(self, ids):
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

                if name in ['ir', 'workflow', 'res', 'webdav']:
                    mod_path = os.path.join(
                            os.path.dirname(MODULES_PATH), name)
                else:
                    mod_path = os.path.join(MODULES_PATH, name)

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
    module = fields.Many2One('ir.module.module', 'Module', select=1,
       ondelete='CASCADE', required=True)
    state = fields.Function(fields.Selection([
        ('uninstalled','Not Installed'),
        ('installed','Installed'),
        ('to upgrade','To be upgraded'),
        ('to remove','To be removed'),
        ('to install','To be installed'),
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
    name = fields.Char('Name', required=True, readonly=True)
    sequence= fields.Integer('Sequence')
    state = fields.Selection([
        ('open', 'Open'),
        ('done', 'Done'),
        ], string='State', required=True, select=1)

    def __init__(self):
        super(ModuleConfigWizardItem, self).__init__()
        self._order.insert(0, ('sequence', 'ASC'))

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


class ModuleConfigWizard(Wizard):
    'Run config wizards'
    _name = 'ir.module.module.config_wizard'
    states = {
        'init': {
            'result': {
                'type': 'choice',
                'next_state': '_first',
            },
        },
        'first': {
            'result': {
                'type': 'form',
                'object': 'ir.module.module.config_wizard.first',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('wizard', 'Ok', 'tryton-ok', True),
                ],
            },
        },
        'wizard': {
            'result': {
                'type': 'action',
                'action': '_action_wizard',
                'state': 'next',
            },
        },
        'next': {
            'result': {
                'type': 'choice',
                'next_state': '_next',
            },
        },
    }

    def _first(self, data):
        res = self._next(data)
        if res == 'wizard':
            return 'first'
        return res

    def _action_wizard(self, data):
        pool = Pool()
        item_obj = pool.get('ir.module.module.config_wizard.item')
        item_ids = item_obj.search([
            ('state', '=', 'open'),
            ], limit=1)
        if item_ids:
            item = item_obj.browse(item_ids[0])
            item_obj.write(item.id, {
                'state': 'done',
                })
            return {
                    'type': 'ir.action.wizard',
                    'wiz_name': item.name,
                    }
        return {}

    def _next(self, data):
        pool = Pool()
        item_obj = pool.get('ir.module.module.config_wizard.item')
        item_ids = item_obj.search([
            ('state', '=', 'open'),
            ])
        if item_ids:
            return 'wizard'
        return 'end'

ModuleConfigWizard()


class ModuleInstallUpgradeInit(ModelView):
    'Module Install Upgrade Init'
    _name = 'ir.module.module.install_upgrade.init'
    _description = __doc__
    module_info = fields.Text('Modules to update', readonly=True)

ModuleInstallUpgradeInit()


class ModuleInstallUpgradeStart(ModelView):
    'Module Install Upgrade Start'
    _name = 'ir.module.module.install_upgrade.start'
    _description = __doc__

ModuleInstallUpgradeStart()


class ModuleInstallUpgrade(Wizard):
    "Install / Upgrade modules"
    _name = 'ir.module.module.install_upgrade'

    def _get_install(self, data):
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

    def _upgrade_module(self, data):
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
            new_wizard = pool.get('ir.module.module.install_upgrade',
                    type='wizard')
            new_wizard._lock.acquire()
            new_wizard._datas[data['_wiz_id']] = self._datas[data['_wiz_id']]
            new_wizard._lock.release()
        return {}

    states = {
        'init': {
            'actions': ['_get_install'],
            'result': {
                'type': 'form',
                'object': 'ir.module.module.install_upgrade.init',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('start', 'Start Upgrade', 'tryton-ok', True),
                ],
            },
        },
        'start': {
            'actions': ['_upgrade_module'],
            'result': {
                'type': 'form',
                'object': 'ir.module.module.install_upgrade.start',
                'state': [
                    ('config', 'Ok', 'tryton-ok', True),
                ],
            },
        },
        'config': {
            'result': {
                'type': 'action',
                'action': '_config',
                'state': 'end',
            },
        },
    }

    def _config(self, data):
        return {
                'type': 'ir.action.wizard',
                'wiz_name': 'ir.module.module.config_wizard',
                }

ModuleInstallUpgrade()


class ModuleConfig(Wizard):
    'Configure Modules'
    _name = 'ir.module.module.config'
    states = {
        'init': {
            'result': {
                'type': 'action',
                'action': '_action_open',
                'state': 'end',
            },
        },
    }

    def _action_open(self, datas):
        pool = Pool()
        model_data_obj = pool.get('ir.model.data')
        act_window_obj = pool.get('ir.action.act_window')
        act_window_id = model_data_obj.get_id('ir', 'act_module_form')
        res = act_window_obj.read(act_window_id)
        return res

ModuleConfig()
