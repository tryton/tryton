#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import os, sys, imp
import itertools
import traceback
import logging
import contextlib
from functools import reduce
import imp
import operator
from trytond.backend import Database
import trytond.tools as tools
from trytond.config import CONFIG
from trytond.transaction import Transaction
from trytond.cache import Cache
import trytond.convert as convert

OPJ = os.path.join
MODULES_PATH = os.path.abspath(os.path.dirname(__file__))

MODULES = []

EGG_MODULES = {}

def update_egg_modules():
    global EGG_MODULES
    try:
        import pkg_resources
        for ep in pkg_resources.iter_entry_points('trytond.modules'):
            mod_name = ep.module_name.split('.')[-1]
            EGG_MODULES[mod_name] = ep
    except ImportError:
        pass
update_egg_modules()


class Graph(dict):

    def add_node(self, name, deps):
        for i in [Node(x, self) for x in deps]:
            i.add_child(name)
        if not deps:
            Node(name, self)

    def __iter__(self):
        level = 0
        done = set(self.keys())
        while done:
            level_modules = [(name, module) for name, module in self.items() \
                    if module.depth==level]
            for name, module in level_modules:
                done.remove(name)
                yield module
            level += 1

    def __str__(self):
        res = ''
        for i in self:
            res += str(i)
            res += '\n'
        return res


class Singleton(object):

    def __new__(cls, name, graph):
        if name in graph:
            inst = graph[name]
        else:
            inst = object.__new__(cls)
            graph[name] = inst
        return inst


class Node(Singleton):

    def __init__(self, name, graph):
        super(Node, self).__init__()
        self.name = name
        self.graph = graph
        if not hasattr(self, 'datas'):
            self.datas = None
        if not hasattr(self, 'childs'):
            self.childs = []
        if not hasattr(self, 'depth'):
            self.depth = 0

    def add_child(self, name):
        node = Node(name, self.graph)
        node.depth = max(self.depth + 1, node.depth)
        if node not in self.all_childs():
            self.childs.append(node)
        for attr in ('init', 'update'):
            if hasattr(self, attr):
                setattr(node, attr, True)
        self.childs.sort(key=operator.attrgetter('name'))

    def all_childs(self):
        res = []
        for child in self.childs:
            res.append(child)
            res += child.all_childs()
        return res

    def has_child(self, name):
        return Node(name, self.graph) in self.childs or \
                bool([c for c in self.childs if c.has_child(name)])

    def __setattr__(self, name, value):
        super(Node, self).__setattr__(name, value)
        if name in ('init', 'update'):
            for child in self.childs:
                setattr(child, name, value)
        if name == 'depth':
            for child in self.childs:
                setattr(child, name, value + 1)

    def __iter__(self):
        return itertools.chain(iter(self.childs),
                *[iter(x) for x in self.childs])

    def __str__(self):
        return self.pprint()

    def pprint(self, depth=0):
        res = '%s\n' % self.name
        for child in self.childs:
            res += '%s`-> %s' % ('    ' * depth, child.pprint(depth + 1))
        return res

def create_graph(module_list, force=None):
    if force is None:
        force = []
    graph = Graph()
    packages = []

    for module in module_list:
        tryton_file = OPJ(MODULES_PATH, module, '__tryton__.py')
        mod_path = OPJ(MODULES_PATH, module)
        if module in ('ir', 'workflow', 'res', 'webdav', 'test'):
            root_path = os.path.abspath(os.path.dirname(
                    os.path.dirname(__file__)))
            tryton_file = OPJ(root_path, module, '__tryton__.py')
            mod_path = OPJ(root_path, module)
        elif module in EGG_MODULES:
            ep = EGG_MODULES[module]
            tryton_file = OPJ(ep.dist.location, 'trytond', 'modules', module,
                    '__tryton__.py')
            mod_path = OPJ(ep.dist.location, 'trytond', 'modules', module)
            if not os.path.isfile(tryton_file) or not os.path.isdir(mod_path):
                # When testing modules from setuptools location is the module
                # directory
                tryton_file = OPJ(ep.dist.location, '__tryton__.py')
                mod_path = os.path.dirname(ep.dist.location)
        if os.path.isfile(tryton_file):
            with tools.file_open(tryton_file, subdir='') as fp:
                info = tools.safe_eval(fp.read())
            packages.append((module, info.get('depends', []), info))
        elif module != 'all':
            raise Exception('Module %s not found' % module)

    current, later = set([x[0] for x in packages]), set()
    while packages and current > later:
        package, deps, datas = packages[0]

        # if all dependencies of 'package' are already in the graph,
        # add 'package' in the graph
        if reduce(lambda x, y: x and y in graph, deps, True):
            if not package in current:
                packages.pop(0)
                continue
            later.clear()
            current.remove(package)
            graph.add_node(package, deps)
            node = Node(package, graph)
            node.datas = datas
            for kind in ('init', 'update'):
                if (package in CONFIG[kind]) \
                        or (('all' in CONFIG[kind]) \
                            and (package != 'test')) \
                        or (kind in force):
                    setattr(node, kind, True)
        else:
            later.add(package)
            packages.append((package, deps, datas))
        packages.pop(0)

    for package, deps, datas in packages:
        if package not in later:
            continue
        missings = [x for x in deps if x not in graph]
        raise Exception('%s unmet dependencies: %s' % (package, missings))
    return graph, packages, later

def load_module_graph(graph, pool, lang=None):
    if lang is None:
        lang = ['en_US']
    modules_todo = []
    models_to_update_history = set()
    logger = logging.getLogger('modules')
    cursor = Transaction().cursor

    modules = [x.name for x in graph]
    cursor.execute('SELECT name, state FROM ir_module_module ' \
            'WHERE name in (' + ','.join(('%s',) * len(modules)) + ')',
            modules)
    module2state = {}
    for name, state in cursor.fetchall():
        module2state[name] = state

    for package in graph:
        module = package.name
        if module not in MODULES:
            continue
        logger.info(module)
        sys.stdout.flush()
        objects = pool.instanciate(module)
        package_state = module2state.get(module, 'uninstalled')
        idref = {}
        if hasattr(package, 'init') \
                or hasattr(package, 'update') \
                or (package_state in ('to install', 'to upgrade')):

            for type in objects.keys():
                for obj in objects[type]:
                    logger.info('%s:init %s' % (module, obj._name))
                    obj.init(module)
            for model in objects['model']:
                if hasattr(model, '_history'):
                    models_to_update_history.add(model._name)

            #Instanciate a new parser for the package:
            tryton_parser = convert.TrytondXmlHandler(pool=pool, module=module)

            for filename in package.datas.get('xml', []):
                filename = filename.replace('/', os.sep)
                mode = 'update'
                if hasattr(package, 'init') or package_state == 'to install':
                    mode = 'init'
                logger.info('%s:loading %s' % (module, filename))
                ext = os.path.splitext(filename)[1]
                if ext == '.sql':
                    if mode == 'init':
                        with tools.file_open(OPJ(module, filename)) as fp:
                            queries = fp.read().split(';')
                        for query in queries:
                            new_query = ' '.join(query.split())
                            if new_query:
                                cursor.execute(new_query)
                else:
                    # Feed the parser with xml content:
                    with tools.file_open(OPJ(module, filename)) as fp:
                        tryton_parser.parse_xmlstream(fp)

            modules_todo.append((module, list(tryton_parser.to_delete)))

            for filename in package.datas.get('translation', []):
                filename = filename.replace('/', os.sep)
                lang2 = os.path.splitext(os.path.basename(filename))[0]
                if lang2 not in lang:
                    continue
                logger.info('%s:loading %s' % (module, filename))
                with tools.file_open(OPJ(module, filename)) as trans_file:
                    po_path = trans_file.name
                translation_obj = pool.get('ir.translation')
                translation_obj.translation_import(lang2, module, po_path)

            cursor.execute("UPDATE ir_module_module SET state = 'installed' " \
                    "WHERE name = %s", (package.name,))
            module2state[package.name] = 'installed'

        # Create missing reports
        from trytond.report import Report
        report_obj = pool.get('ir.action.report')
        report_ids = report_obj.search([
            ('module', '=', module),
            ])
        report_names = pool.object_name_list(type='report')
        for report in report_obj.browse(report_ids):
            report_name = report.report_name
            if report_name not in report_names:
                report = object.__new__(Report)
                report._name = report_name
                pool.add(report, type='report')
                report.__init__()

        cursor.commit()

    for model_name in models_to_update_history:
        model = pool.get(model_name)
        if model._history:
            logger.info('history:update %s' % model._name)
            model._update_history_table()

    # Vacuum :
    while modules_todo:
        (module, to_delete) = modules_todo.pop()
        convert.post_import(pool, module, to_delete)


    cursor.commit()

def get_module_list():
    module_list = set()
    if os.path.exists(MODULES_PATH) and os.path.isdir(MODULES_PATH):
        for file in os.listdir(MODULES_PATH):
            if file.startswith('.'):
                continue
            if os.path.isdir(OPJ(MODULES_PATH, file)):
                module_list.add(file)
    update_egg_modules()
    module_list.update(EGG_MODULES.keys())
    module_list.add('ir')
    module_list.add('workflow')
    module_list.add('res')
    module_list.add('webdav')
    module_list.add('test')
    return list(module_list)

def register_classes(reload_p=False):
    '''
    Import modules to register the classes in the Pool

    :param reload_p: reload modules instead of import it
    '''
    if not reload_p:
        import trytond.ir
        import trytond.workflow
        import trytond.res
        import trytond.webdav
        import trytond.test
    else:
        for module in ('trytond.model', 'trytond.report', 'trytond.wizard',
                'trytond.ir', 'trytond.workflow', 'trytond.res',
                'trytond.webdav', 'trytond.test'):
            for i in sys.modules.keys():
                if i.startswith(module) \
                        and i != module:
                    del sys.modules[i]
            imp.reload(sys.modules[module])

    logger = logging.getLogger('modules')

    for package in create_graph(get_module_list())[0]:
        module = package.name
        logger.info('%s:registering classes' % module)

        if module in ('ir', 'workflow', 'res', 'webdav', 'test'):
            MODULES.append(module)
            continue

        if reload_p and 'trytond.modules.' + module in sys.modules:
            for i in sys.modules.keys():
                if i.startswith('trytond.modules.' + module) \
                        and i != 'trytond.modules.' + module \
                        and getattr(sys.modules[i], '_TRYTON_RELOAD', True):
                    del sys.modules[i]
            imp.reload(sys.modules['trytond.modules.' + module])
            continue

        if os.path.isdir(OPJ(MODULES_PATH, module)):
            mod_file, pathname, description = imp.find_module(module,
                    [MODULES_PATH])
            try:
                imp.load_module('trytond.modules.' + module, mod_file,
                        pathname, description)
            finally:
                if mod_file is not None:
                    mod_file.close()
        elif module in EGG_MODULES:
            ep = EGG_MODULES[module]
            mod_path = os.path.join(ep.dist.location,
                    *ep.module_name.split('.')[:-1])
            if not os.path.isdir(mod_path):
                # Find module in path
                for path in sys.path:
                    mod_path = os.path.join(path,
                            *ep.module_name.split('.')[:-1])
                    if os.path.isdir(os.path.join(mod_path, module)):
                        break
                if not os.path.isdir(os.path.join(mod_path, module)):
                    # When testing modules from setuptools location is the
                    # module directory
                    mod_path = os.path.dirname(ep.dist.location)
            mod_file, pathname, description = imp.find_module(module,
                    [mod_path])
            try:
                imp.load_module('trytond.modules.' + module, mod_file,
                        pathname, description)
            finally:
                if mod_file is not None:
                    mod_file.close()
        else:
            raise Exception('Couldn\'t find module %s' % module)
        MODULES.append(module)

def load_modules(database_name, pool, update=False, lang=None):
    res = True
    if not Transaction().cursor:
        contextmanager = Transaction().start(database_name, 0)
    else:
        contextmanager = contextlib.nested(Transaction().new_cursor(),
                Transaction().set_user(0),
                Transaction().reset_context())
    with contextmanager:
        cursor = Transaction().cursor
        force = []
        if update:
            if 'all' in CONFIG['init']:
                cursor.execute("SELECT name FROM ir_module_module " \
                        "WHERE name != \'test\'")
            else:
                cursor.execute("SELECT name FROM ir_module_module " \
                        "WHERE state IN ('installed', 'to install', " \
                            "'to upgrade', 'to remove')")
        else:
            cursor.execute("SELECT name FROM ir_module_module " \
                    "WHERE state IN ('installed', 'to upgrade', 'to remove')")
        module_list = [name for (name,) in cursor.fetchall()]
        if update:
            for module in CONFIG['init'].keys():
                if CONFIG['init'][module]:
                    module_list.append(module)
            for module in CONFIG['update'].keys():
                if CONFIG['update'][module]:
                    module_list.append(module)
        graph = create_graph(module_list, force)[0]

        try:
            load_module_graph(graph, pool, lang)
        except Exception:
            cursor.rollback()
            raise

        if update:
            cursor.execute("SELECT name FROM ir_module_module " \
                    "WHERE state IN ('to remove')")
            fetchall = cursor.fetchall()
            if fetchall:
                for (mod_name,) in fetchall:
                    #TODO check if ressource not updated by the user
                    cursor.execute('SELECT model, db_id FROM ir_model_data ' \
                            'WHERE module = %s ' \
                            'ORDER BY id DESC', (mod_name,))
                    for rmod, rid in cursor.fetchall():
                        pool.get(rmod).delete(rid)
                    cursor.commit()
                cursor.execute("UPDATE ir_module_module SET state = %s " \
                        "WHERE state IN ('to remove')", ('uninstalled',))
                cursor.commit()
                res = False

        module_obj = pool.get('ir.module.module')
        module_obj.update_list()
        cursor.commit()
    Cache.resets(database_name)
    return res
