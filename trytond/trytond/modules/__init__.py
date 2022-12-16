# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
import sys
import itertools
import logging
from functools import reduce
import imp
import operator
import ConfigParser
from glob import iglob

from sql import Table
from sql.functions import CurrentTimestamp

import trytond.tools as tools
from trytond.config import config
from trytond.transaction import Transaction
from trytond.cache import Cache
from trytond import backend
import trytond.convert as convert

logger = logging.getLogger(__name__)

ir_module = Table('ir_module')
ir_model_data = Table('ir_model_data')

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
            level_modules = [(name, module) for name, module in self.items()
                if module.depth == level]
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

        # __init__ is called even if Node already exists
        if not hasattr(self, 'info'):
            self.info = None
        if not hasattr(self, 'childs'):
            self.childs = []
        if not hasattr(self, 'depth'):
            self.depth = 0

    def add_child(self, name):
        node = Node(name, self.graph)
        node.depth = max(self.depth + 1, node.depth)
        if node not in self.all_childs():
            self.childs.append(node)
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


def get_module_info(name):
    "Return the content of the tryton.cfg"
    module_config = ConfigParser.ConfigParser()
    with tools.file_open(os.path.join(name, 'tryton.cfg')) as fp:
        module_config.readfp(fp)
        directory = os.path.dirname(fp.name)
    info = dict(module_config.items('tryton'))
    info['directory'] = directory
    for key in ('depends', 'extras_depend', 'xml'):
        if key in info:
            info[key] = info[key].strip().splitlines()
    return info


def create_graph(module_list):
    graph = Graph()
    packages = []

    for module in module_list:
        info = get_module_info(module)
        packages.append((module, info.get('depends', []),
                info.get('extras_depend', []), info))

    current, later = set([x[0] for x in packages]), set()
    all_packages = set(current)
    while packages and current > later:
        package, deps, xdep, info = packages[0]

        # if all dependencies of 'package' are already in the graph,
        # add 'package' in the graph
        all_deps = deps + [x for x in xdep if x in all_packages]
        if reduce(lambda x, y: x and y in graph, all_deps, True):
            if package not in current:
                packages.pop(0)
                continue
            later.clear()
            current.remove(package)
            graph.add_node(package, all_deps)
            node = Node(package, graph)
            node.info = info
        else:
            later.add(package)
            packages.append((package, deps, xdep, info))
        packages.pop(0)

    missings = set()
    for package, deps, _, _ in packages:
        if package not in later:
            continue
        missings |= set((x for x in deps if x not in graph))
    if missings:
        raise Exception('Missing dependencies: %s' % list(missings
                - set((p[0] for p in packages))))
    return graph, packages, later


def is_module_to_install(module, update):
    if module in update:
        return True
    return False


def load_module_graph(graph, pool, update=None, lang=None):
    if lang is None:
        lang = [config.get('database', 'language')]
    if update is None:
        update = []
    modules_todo = []
    models_to_update_history = set()

    with Transaction().connection.cursor() as cursor:
        modules = [x.name for x in graph]
        cursor.execute(*ir_module.select(ir_module.name, ir_module.state,
                where=ir_module.name.in_(modules)))
        module2state = dict(cursor.fetchall())

        for package in graph:
            module = package.name
            if module not in MODULES:
                continue
            logger.info(module)
            classes = pool.fill(module)
            if update:
                pool.setup(classes)
            package_state = module2state.get(module, 'uninstalled')
            if (is_module_to_install(module, update)
                    or (update
                        and package_state in ('to install', 'to upgrade'))):
                if package_state not in ('to install', 'to upgrade'):
                    if package_state == 'installed':
                        package_state = 'to upgrade'
                    elif package_state != 'to remove':
                        package_state = 'to install'
                for child in package.childs:
                    module2state[child.name] = package_state
                for type in classes.keys():
                    for cls in classes[type]:
                        logger.info('%s:register %s', module, cls.__name__)
                        cls.__register__(module)
                for model in classes['model']:
                    if hasattr(model, '_history'):
                        models_to_update_history.add(model.__name__)

                # Instanciate a new parser for the package:
                tryton_parser = convert.TrytondXmlHandler(pool=pool,
                    module=module, module_state=package_state)

                for filename in package.info.get('xml', []):
                    filename = filename.replace('/', os.sep)
                    logger.info('%s:loading %s', module, filename)
                    # Feed the parser with xml content:
                    with tools.file_open(OPJ(module, filename), 'rb') as fp:
                        tryton_parser.parse_xmlstream(fp)

                modules_todo.append((module, list(tryton_parser.to_delete)))

                localedir = '%s/%s' % (package.info['directory'], 'locale')
                for filename in itertools.chain(
                        iglob('%s/*.po' % localedir),
                        iglob('%s/override/*.po' % localedir)):
                    filename = filename.replace('/', os.sep)
                    lang2 = os.path.splitext(os.path.basename(filename))[0]
                    if lang2 not in lang:
                        continue
                    logger.info('%s:loading %s', module,
                        filename[len(package.info['directory']) + 1:])
                    Translation = pool.get('ir.translation')
                    Translation.translation_import(lang2, module, filename)

                if package_state == 'to remove':
                    continue
                cursor.execute(*ir_module.select(ir_module.id,
                        where=(ir_module.name == package.name)))
                try:
                    module_id, = cursor.fetchone()
                    cursor.execute(*ir_module.update([ir_module.state],
                            ['installed'], where=(ir_module.id == module_id)))
                except TypeError:
                    cursor.execute(*ir_module.insert(
                            [ir_module.create_uid, ir_module.create_date,
                                ir_module.name, ir_module.state],
                            [[0, CurrentTimestamp(), package.name,
                                    'installed'],
                                ]))
                module2state[package.name] = 'installed'

            Transaction().connection.commit()

        if not update:
            pool.setup()

        for model_name in models_to_update_history:
            model = pool.get(model_name)
            if model._history:
                logger.info('history:update %s', model.__name__)
                model._update_history_table()

        # Vacuum :
        while modules_todo:
            (module, to_delete) = modules_todo.pop()
            convert.post_import(pool, module, to_delete)
    logger.info('all modules loaded')


def get_module_list():
    module_list = set()
    if os.path.exists(MODULES_PATH) and os.path.isdir(MODULES_PATH):
        for file in os.listdir(MODULES_PATH):
            if file.startswith('.'):
                continue
            if file == '__pycache__':
                continue
            if os.path.isdir(OPJ(MODULES_PATH, file)):
                module_list.add(file)
    update_egg_modules()
    module_list.update(EGG_MODULES.keys())
    module_list.add('ir')
    module_list.add('res')
    module_list.add('tests')
    return list(module_list)


def register_classes():
    '''
    Import modules to register the classes in the Pool
    '''
    import trytond.ir
    trytond.ir.register()
    import trytond.res
    trytond.res.register()
    import trytond.tests
    trytond.tests.register()

    for package in create_graph(get_module_list())[0]:
        module = package.name
        logger.info('%s:registering classes', module)

        if module in ('ir', 'res', 'tests'):
            MODULES.append(module)
            continue

        if os.path.isdir(OPJ(MODULES_PATH, module)):
            mod_path = MODULES_PATH
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
        else:
            raise Exception('Couldn\'t find module %s' % module)
        mod_file, pathname, description = imp.find_module(module,
                [mod_path])
        the_module = imp.load_module('trytond.modules.' + module,
            mod_file, pathname, description)
        # Some modules register nothing in the Pool
        if hasattr(the_module, 'register'):
            the_module.register()
        if mod_file is not None:
            mod_file.close()
        MODULES.append(module)


def load_modules(database_name, pool, update=None, lang=None):
    res = True

    def _load_modules():
        global res
        TableHandler = backend.get('TableHandler')
        transaction = Transaction()

        with transaction.connection.cursor() as cursor:
            # Migration from 3.6: remove double module
            old_table = 'ir_module_module'
            new_table = 'ir_module'
            if TableHandler.table_exist(old_table):
                TableHandler.table_rename(old_table, new_table)
            if update:
                cursor.execute(*ir_module.select(ir_module.name,
                        where=ir_module.state.in_(('installed', 'to install',
                                'to upgrade', 'to remove'))))
            else:
                cursor.execute(*ir_module.select(ir_module.name,
                        where=ir_module.state.in_(('installed', 'to upgrade',
                                'to remove'))))
            module_list = [name for (name,) in cursor.fetchall()]
            if update:
                module_list += update
            graph = create_graph(module_list)[0]

            load_module_graph(graph, pool, update, lang)

            if update:
                cursor.execute(*ir_module.select(ir_module.name,
                        where=(ir_module.state == 'to remove')))
                fetchall = cursor.fetchall()
                if fetchall:
                    for (mod_name,) in fetchall:
                        # TODO check if ressource not updated by the user
                        cursor.execute(*ir_model_data.select(
                                ir_model_data.model, ir_model_data.db_id,
                                where=(ir_model_data.module == mod_name),
                                order_by=ir_model_data.id.desc))
                        for rmod, rid in cursor.fetchall():
                            Model = pool.get(rmod)
                            Model.delete([Model(rid)])
                        Transaction().connection.commit()
                    cursor.execute(*ir_module.update([ir_module.state],
                            ['uninstalled'],
                            where=(ir_module.state == 'to remove')))
                    Transaction().connection.commit()
                    res = False

                Module = pool.get('ir.module')
                Module.update_list()
        # Need to commit to unlock SQLite database
        transaction.commit()
        Cache.resets(database_name)

    if not Transaction().connection:
        with Transaction().start(database_name, 0):
            _load_modules()
    else:
        with Transaction().new_transaction(), \
                Transaction().set_user(0), \
                Transaction().reset_context():
            _load_modules()

    return res
