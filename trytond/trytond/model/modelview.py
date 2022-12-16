# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from lxml import etree
from functools import wraps
import collections

from trytond.exceptions import UserError
from trytond.i18n import gettext
from trytond.model import Model, fields
from trytond.tools import ClassProperty, is_instance_method
from trytond.pyson import PYSONDecoder, PYSONEncoder
from trytond.transaction import Transaction
from trytond.cache import Cache
from trytond.pool import Pool
from trytond.rpc import RPC

from .fields import on_change_result

__all__ = ['ModelView']


class AccessButtonError(UserError):
    pass


def _find(tree, element):
    if element.tag == 'xpath':
        res = tree.xpath(element.get('expr'))
        if res:
            return res[0]
    return None


def _inherit_apply(tree, inherit):
    root_inherit = inherit.getroottree().getroot()
    for element2 in root_inherit:
        if element2.tag != 'xpath':
            continue
        element = _find(tree, element2)
        if element is not None:
            pos = element2.get('position', 'inside')
            if pos == 'replace':
                parent = element.getparent()
                if parent is None:
                    tree, = element2
                    continue
                enext = element.getnext()
                if enext is not None:
                    for child in element2:
                        index = parent.index(enext)
                        parent.insert(index, child)
                else:
                    parent.extend(list(element2))
                parent.remove(element)
            elif pos == 'replace_attributes':
                child = element2[0]
                for attr in child.attrib:
                    element.set(attr, child.get(attr))
            elif pos == 'inside':
                element.extend(list(element2))
            elif pos == 'after':
                parent = element.getparent()
                enext = element.getnext()
                if enext is not None:
                    for child in list(element2):
                        index = parent.index(enext)
                        parent.insert(index, child)
                else:
                    parent.extend(list(element2))
            elif pos == 'before':
                parent = element.getparent()
                for child in list(element2):
                    index = parent.index(element)
                    parent.insert(index, child)
            else:
                raise AttributeError(
                    'Unknown position in inherited view %s!' % pos)
        else:
            raise AttributeError(
                'Couldn\'t find tag (%s: %s) in parent view!'
                % (element2.tag, element2.get('expr')))
    return tree


def on_change(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        result = func(self, *args, **kwargs)
        assert result is None, func
        return self
    wrapper.on_change = True
    return wrapper


class ModelView(Model):
    """
    Define a model with views in Tryton.
    """
    __slots__ = ()
    __modules_list = None  # Cache for the modules list sorted by dependency
    _fields_view_get_cache = Cache('modelview.fields_view_get')
    _view_toolbar_get_cache = Cache('modelview.view_toolbar_get')

    @staticmethod
    def _reset_modules_list():
        ModelView.__modules_list = None

    @ClassProperty
    @classmethod
    def _modules_list(cls):
        from trytond.modules import create_graph, get_module_list
        if ModelView.__modules_list:
            return ModelView.__modules_list
        graph = create_graph(get_module_list())
        ModelView.__modules_list = [x.name for x in graph] + [None]
        return ModelView.__modules_list

    @classmethod
    def __setup__(cls):
        super(ModelView, cls).__setup__()
        cls.__rpc__['fields_view_get'] = RPC(cache=dict(days=1))
        cls.__rpc__['view_toolbar_get'] = RPC(cache=dict(days=1))
        cls.__rpc__['on_change'] = RPC(instantiate=0)
        cls.__rpc__['on_change_with'] = RPC(instantiate=0)
        cls._buttons = {}

        fields_ = {}
        for name in dir(cls):
            if name.startswith('__'):
                continue
            attr = getattr(cls, name)
            if isinstance(attr, fields.Field):
                fields_[name] = attr

        methods = {
            '_done': set(),
            'depends': collections.defaultdict(set),
            'depend_methods': collections.defaultdict(set),
            'change': collections.defaultdict(set),
            }
        cls.__change_buttons = methods['change']

        def set_methods(name):
            if name in methods['_done']:
                return
            methods['_done'].add(name)
            for parent_cls in cls.__mro__:
                parent_meth = getattr(parent_cls, name, None)
                if not parent_meth:
                    continue
                for attr in ['depends', 'depend_methods', 'change']:
                    if isinstance(parent_meth, property):
                        parent_value = getattr(parent_meth.fget, attr, set())
                        parent_value |= getattr(parent_meth.fset, attr, set())
                    else:
                        parent_value = getattr(parent_meth, attr, set())
                    if parent_value:
                        methods[attr][name] |= parent_value

        def setup_field(field_name, field, attribute):
            if attribute == 'selection_change_with':
                if isinstance(
                        getattr(field, 'selection', None), str):
                    function_name = field.selection
                else:
                    return
            else:
                function_name = '%s_%s' % (attribute, field_name)
            function = getattr(cls, function_name, None)
            if not function:
                return

            set_methods(function_name)
            setattr(field, attribute, methods['depends'][function_name])

            meth_names = list(methods['depend_methods'][function_name])
            meth_done = set()
            while meth_names:
                meth_name = meth_names.pop()
                method = getattr(cls, meth_name)
                assert callable(method) or isinstance(method, property), \
                    "%s.%s not callable or property" % (cls, meth_name)
                set_methods(meth_name)
                setattr(field, attribute,
                    getattr(field, attribute) | methods['depends'][meth_name])
                meth_names += list(
                    methods['depend_methods'][meth_name] - meth_done)
                meth_done.add(meth_name)

            if (attribute == 'on_change'
                    and not getattr(function, 'on_change', None)):
                # Decorate on_change to always return self
                setattr(cls, function_name, on_change(function))

        for name, field in fields_.items():
            for attribute in [
                    'on_change',
                    'on_change_with',
                    'autocomplete',
                    'selection_change_with',
                    ]:
                setup_field(name, field, attribute)

    @classmethod
    def __post_setup__(cls):
        super(ModelView, cls).__post_setup__()

        # Update __rpc__
        for field_name, field in cls._fields.items():
            field.set_rpc(cls)

        for button in cls._buttons:
            if not is_instance_method(cls, button):
                cls.__rpc__.setdefault(button,
                    RPC(readonly=False, instantiate=0))
            else:
                cls.__rpc__.setdefault(button,
                    RPC(instantiate=0, result=on_change_result))

            for parent_cls in cls.__mro__:
                parent_meth = getattr(parent_cls, button, None)
                if not parent_meth:
                    continue
                cls.__change_buttons[button] |= getattr(
                    parent_meth, 'change', set())

    @classmethod
    def fields_view_get(cls, view_id=None, view_type='form', level=None):
        '''
        Return a view definition.
        If view_id is None the first one will be used of view_type.
        The definition is a dictionary with keys:
           - model: the model name
           - type: the type of the view
           - view_id: the id of the view
           - arch: the xml description of the view
           - fields: a dictionary with the definition of each field in the view
           - field_childs: the name of the childs field for tree
        '''
        key = (cls.__name__, view_id, view_type, level)
        result = cls._fields_view_get_cache.get(key)
        if result:
            return result
        result = {'model': cls.__name__}
        pool = Pool()
        View = pool.get('ir.ui.view')

        view = None
        inherit_view_id = None
        if view_id:
            view = View(view_id)
        else:
            domain = [
                ('model', '=', cls.__name__),
                ['OR',
                    ('inherit', '=', None),
                    ('inherit.model', '!=', cls.__name__),
                    ],
                ]
            views = View.search(domain)
            views = [v for v in views if v.rng_type == view_type]
            if views:
                view = views[0]
        if view:
            if view.inherit:
                inherit_view_id = view.id
                view = view.inherit

        # if a view was found
        if view:
            result['type'] = view.rng_type
            result['view_id'] = view_id
            result['arch'] = view.arch
            result['field_childs'] = view.field_childs

            # Check if view is not from an inherited model
            if view.model != cls.__name__:
                Inherit = pool.get(view.model)
                result['arch'] = Inherit.fields_view_get(view.id)['arch']
                real_view_id = inherit_view_id
            else:
                real_view_id = view.id

            # get all views which inherit from (ie modify) this view
            views = View.search([
                    'OR', [
                        ('inherit', '=', real_view_id),
                        ('model', '=', cls.__name__),
                        ], [
                        ('id', '=', real_view_id),
                        ('inherit', '!=', None),
                        ],
                    ])
            raise_p = False
            while True:
                try:
                    views.sort(key=lambda x:
                        cls._modules_list.index(x.module or None))
                    break
                except ValueError:
                    if raise_p:
                        raise
                    # There is perhaps a new module in the directory
                    ModelView._reset_modules_list()
                    raise_p = True
            parser = etree.XMLParser(remove_comments=True)
            tree = etree.fromstring(result['arch'], parser=parser)
            for view in views:
                if view.domain:
                    if not PYSONDecoder({'context': Transaction().context}
                            ).decode(view.domain):
                        continue
                if not view.arch or not view.arch.strip():
                    continue
                tree_inherit = etree.fromstring(view.arch, parser=parser)
                tree = _inherit_apply(tree, tree_inherit)
            result['arch'] = etree.tostring(
                tree, encoding='utf-8').decode('utf-8')

        # otherwise, build some kind of default view
        else:
            if view_type == 'form':
                res = cls.fields_get()
                xml = '''<?xml version="1.0"?>''' \
                    '''<form col="4">'''
                for i in res:
                    if i in ('create_uid', 'create_date',
                            'write_uid', 'write_date', 'id', 'rec_name'):
                        continue
                    if res[i]['type'] not in ('one2many', 'many2many'):
                        xml += '<label name="%s"/>' % (i,)
                        xml += '<field name="%s"/>' % (i,)
                        if res[i]['type'] == 'text':
                            xml += "<newline/>"
                    else:
                        xml += '<field name="%s" colspan="4"/>' % (i,)
                xml += "</form>"
            elif view_type == 'tree':
                field = 'id'
                if cls._rec_name in cls._fields:
                    field = cls._rec_name
                xml = '''<?xml version="1.0"?>''' \
                    '''<tree><field name="%s"/></tree>''' \
                    % (field,)
            else:
                xml = ''
            result['type'] = view_type
            result['arch'] = xml
            result['field_childs'] = None
            result['view_id'] = view_id

        if level is None:
            level = 1 if result['type'] == 'tree' else 0

        # Update arch and compute fields from arch
        parser = etree.XMLParser(remove_blank_text=True)
        tree = etree.fromstring(result['arch'], parser)
        xarch, xfields = cls._view_look_dom_arch(
            tree, result['type'], result['field_childs'], level=level)
        result['arch'] = xarch
        result['fields'] = xfields

        cls._fields_view_get_cache.set(key, result)
        return result

    @classmethod
    def view_toolbar_get(cls):
        """
        Returns the model specific actions and exports.
        A dictionary with keys:
            - print: a list of available reports
            - action: a list of available actions
            - relate: a list of available relations
            - exports: a list of available exports
        """
        pool = Pool()
        Action = pool.get('ir.action.keyword')
        Export = pool.get('ir.export')
        Email = pool.get('ir.email.template')
        key = cls.__name__
        result = cls._view_toolbar_get_cache.get(key)
        if result:
            return result
        prints = Action.get_keyword('form_print', (cls.__name__, -1))
        actions = Action.get_keyword('form_action', (cls.__name__, -1))
        relates = Action.get_keyword('form_relate', (cls.__name__, -1))
        exports = Export.search_read(
            [('resource', '=', cls.__name__)],
            fields_names=['name', 'export_fields.name'])
        emails = Email.search_read(
            [('model.model', '=', cls.__name__)],
            fields_names=['name'])
        result = {
            'print': prints,
            'action': actions,
            'relate': relates,
            'exports': exports,
            'emails': emails,
            }
        cls._view_toolbar_get_cache.set(key, result)
        return result

    @classmethod
    def view_attributes(cls):
        'Return a list of xpath, attribute name and value'
        return []

    @classmethod
    def _view_look_dom_arch(cls, tree, type, field_children=None, level=0):
        pool = Pool()
        ModelAccess = pool.get('ir.model.access')
        FieldAccess = pool.get('ir.model.field.access')

        encoder = PYSONEncoder()
        view_depends = []
        for xpath, attribute, value, *extra in cls.view_attributes():
            depends = []
            if extra:
                depends, = extra
            nodes = tree.xpath(xpath)
            for element in nodes:
                element.set(attribute, encoder.encode(value))
            if nodes and depends:
                view_depends.extend(depends)

        fields_width = {}
        tree_root = tree.getroottree().getroot()

        # Find field without read access
        fread_accesses = FieldAccess.check(cls.__name__,
                list(cls._fields.keys()), 'read', access=True)
        fields_to_remove = set(
            x for x, y in fread_accesses.items() if not y)

        # Find relation field without read access
        for name, field in cls._fields.items():
            if not ModelAccess.check_relation(cls.__name__, name, mode='read'):
                fields_to_remove.add(name)

        checked = set()
        while checked < fields_to_remove:
            to_check = fields_to_remove - checked
            for name, field in cls._fields.items():
                for field_to_remove in to_check:
                    if field_to_remove in field.depends:
                        fields_to_remove.add(name)
            checked |= to_check

        buttons_to_remove = set()
        for name, definition in cls._buttons.items():
            if fields_to_remove & set(definition.get('depends', [])):
                buttons_to_remove.add(name)

        field_xpath = ('//field[@name="%(name)s"]'
            '| //label[@name="%(name)s"] | //page[@name="%(name)s"]'
            '| //group[@name="%(name)s"] | //separator[@name="%(name)s"]')
        button_xpath = '//button[@name="%(name)s"]'
        # Remove field and button without read acces
        for xpath, names in (
                (field_xpath, fields_to_remove),
                (button_xpath, buttons_to_remove),
                ):
            for name in names:
                path = xpath % {'name': name}
                for i, element in enumerate(tree.xpath(path)):
                    if type == 'tree' or element.tag == 'page':
                        parent = element.getparent()
                        parent.remove(element)
                    elif type == 'form':
                        element.tag = 'label'
                        colspan = element.attrib.get('colspan')
                        element.attrib.clear()
                        element.attrib['id'] = 'hidden %s-%s' % (name, i)
                        if colspan is not None:
                            element.attrib['colspan'] = colspan

        # Remove empty pages
        if type == 'form':
            for page in tree.xpath('//page[not(descendant::*)]'):
                page.getparent().remove(page)

        if type == 'tree' and Transaction().context.get('view_tree_width'):
            ViewTreeWidth = pool.get('ir.ui.view_tree_width')
            viewtreewidth_ids = ViewTreeWidth.search([
                ('model', '=', cls.__name__),
                ('user', '=', Transaction().user),
                ])
            for viewtreewidth in ViewTreeWidth.browse(viewtreewidth_ids):
                if viewtreewidth.width > 0:
                    fields_width[viewtreewidth.field] = viewtreewidth.width

        fields_def = cls.__view_look_dom(tree_root, type,
                fields_width=fields_width)

        if hasattr(cls, 'active'):
            fields_def.setdefault('active', {'name': 'active'})

        if field_children:
            fields_def.setdefault(field_children, {'name': field_children})
            if field_children in cls._fields:
                field = cls._fields[field_children]
                if hasattr(field, 'field'):
                    fields_def.setdefault(field.field, {'name': field.field})

        for depend in view_depends:
            if depend not in fields_to_remove:
                fields_def.setdefault(depend, {'name': depend})

        field_names = list(fields_def.keys())
        while field_names:
            field_name = field_names.pop()
            if field_name in cls._fields:
                field = cls._fields[field_name]
            else:
                continue
            for depend in field.depends:
                if depend not in fields_def:
                    fields_def[depend] = {'name': depend}
                    field_names.append(depend)

        arch = etree.tostring(
            tree, encoding='utf-8', pretty_print=False).decode('utf-8')
        # Do not call fields_def without fields as it returns all fields
        if fields_def:
            fields2 = cls.fields_get(list(fields_def.keys()), level=level)
        else:
            fields2 = {}
        for field in fields_def:
            if field in fields2:
                fields2[field].update(fields_def[field])
        return arch, fields2

    @classmethod
    def __view_look_dom(cls, element, type, fields_width=None,
            _fields_attrs=None):
        pool = Pool()
        Translation = pool.get('ir.translation')
        ModelData = pool.get('ir.model.data')
        ModelAccess = pool.get('ir.model.access')
        Button = pool.get('ir.model.button')
        User = pool.get('res.user')
        ActionWindow = pool.get('ir.action.act_window')

        if fields_width is None:
            fields_width = {}
        if _fields_attrs is None:
            fields_attrs = {}
        else:
            fields_attrs = _fields_attrs

        def set_view_ids(element):
            view_ids = []
            if element.get('view_ids'):
                for view_id in element.get('view_ids').split(','):
                    try:
                        view_ids.append(int(view_id))
                    except ValueError:
                        view_ids.append(ModelData.get_id(*view_id.split('.')))
                element.attrib['view_ids'] = ','.join(map(str, view_ids))
            return view_ids

        def get_relation(field):
            if hasattr(field, 'model_name'):
                return field.model_name
            elif hasattr(field, 'get_target'):
                return field.get_target().__name__

        def get_views(relation, widget, view_ids, mode):
            Relation = pool.get(relation)
            views = {}
            if widget in {'one2many', 'many2many'}:
                # Prefetch only the first view to prevent infinite loop
                if view_ids:
                    for view_id in view_ids:
                        view = Relation.fields_view_get(view_id=view_id)
                        views[str(view_id)] = view
                        break
                else:
                    for view_type in mode:
                        views[view_type] = (
                            Relation.fields_view_get(view_type=view_type))
                        break
            return views

        for attr in ('name', 'icon', 'symbol'):
            if not element.get(attr):
                continue
            fields_attrs.setdefault(element.get(attr), {})

        if element.tag == 'field' and type in ['tree', 'form']:
            for attr in ('name', 'icon'):
                fname = element.get(attr)
                if not fname:
                    continue
                view_ids = set_view_ids(element)
                if type != 'form':
                    continue
                field = cls._fields[fname]
                relation = get_relation(field)
                if not relation:
                    continue
                mode = (
                    element.attrib.pop('mode', None) or 'tree,form').split(',')
                widget = element.attrib.get('widget', field._type)
                views = get_views(relation, widget, view_ids, mode)
                element.attrib['mode'] = ','.join(mode)
                fields_attrs[fname].setdefault('views', {}).update(views)

            if type == 'tree' and element.get('name') in fields_width:
                element.set('width', str(fields_width[element.get('name')]))

        encoder = PYSONEncoder()
        if element.tag == 'button':
            button_name = element.attrib['name']
            if button_name in cls._buttons:
                states = cls._buttons[button_name]
            else:
                states = {}
            groups = set(User.get_groups())
            button_attr = Button.get_view_attributes(
                cls.__name__, button_name)
            for attr, value in button_attr.items():
                if not element.get(attr):
                    element.set(attr, value or '')
            button_groups = Button.get_groups(cls.__name__, button_name)
            if ((button_groups and not groups & button_groups)
                    or (not button_groups
                        and not ModelAccess.check(
                            cls.__name__, 'write', raise_exception=False))):
                states = states.copy()
                states['readonly'] = True
            element.set('states', encoder.encode(states))

            button_rules = Button.get_rules(cls.__name__, button_name)
            if button_rules:
                element.set('rule', '1')

            change = cls.__change_buttons[button_name]
            if change:
                change = list(change)
                # Add id to change if the button is not cached
                # Not having the id increase the efficiency of the cache
                if cls.__rpc__[button_name].cache:
                    change.append('id')
                element.set('change', encoder.encode(change))
            if not is_instance_method(cls, button_name):
                element.set('type', 'class')
            else:
                element.set('type', 'instance')

            for depend in states.get('depends', []):
                fields_attrs.setdefault(depend, {})

        if element.tag == 'link':
            link_name = element.attrib['name']
            action_id = ModelData.get_id(*link_name.split('.'))
            try:
                action, = ActionWindow.search([('id', '=', action_id)])
            except ValueError:
                action = None
            if (not action
                    or not action.res_model
                    or not ModelAccess.check(
                        action.res_model, 'read', raise_exception=False)):
                element.tag = 'label'
                colspan = element.attrib.get('colspan')
                link_name = element.attrib['name']
                element.attrib.clear()
                element.attrib['id'] = link_name
                if colspan is not None:
                    element.attrib['colspan'] = colspan
            else:
                element.attrib['id'] = str(action.action.id)

        # translate view
        if Transaction().language != 'en':
            for attr in ('string', 'sum', 'confirm', 'help'):
                if element.get(attr):
                    trans = Translation.get_source(cls.__name__, 'view',
                            Transaction().language, element.get(attr))
                    if trans:
                        element.set(attr, trans)

        if element.tag == 'tree' and element.get('sequence'):
            fields_attrs.setdefault(element.get('sequence'), {})

        if element.tag == 'calendar':
            for attr in ['dtstart', 'dtend', 'color', 'background_color']:
                if element.get(attr):
                    fields_attrs.setdefault(element.get(attr), {})

        for field in element:
            fields_attrs = cls.__view_look_dom(field, type,
                fields_width=fields_width, _fields_attrs=fields_attrs)
        return fields_attrs

    @staticmethod
    def button(func):
        @wraps(func)
        def wrapper(cls, records, *args, **kwargs):
            pool = Pool()
            ModelAccess = pool.get('ir.model.access')
            Button = pool.get('ir.model.button')
            ButtonClick = pool.get('ir.model.button.click')
            User = pool.get('res.user')

            transaction = Transaction()
            check_access = transaction.context.get('_check_access')

            assert len(records) == len(set(records)), "Duplicate records"

            if (transaction.user != 0) and check_access:
                ModelAccess.check(cls.__name__, 'read')
                groups = set(User.get_groups())
                button_groups = Button.get_groups(cls.__name__,
                    func.__name__)
                if button_groups:
                    if not groups & button_groups:
                        raise AccessButtonError(
                            gettext('ir.msg_access_button_error',
                                button=func.__name__,
                                model=cls.__name__))
                else:
                    ModelAccess.check(cls.__name__, 'write')

            with Transaction().set_context(_check_access=False):
                if (transaction.user != 0) and check_access:
                    button_rules = Button.get_rules(
                        cls.__name__, func.__name__)
                    if button_rules:
                        clicks = ButtonClick.register(
                            cls.__name__, func.__name__, records)
                        records = [r for r in records
                            if all(br.test(r, clicks.get(r.id, []))
                                for br in button_rules)]
                # Reset click after filtering in case the button also has rules
                names = Button.get_reset(cls.__name__, func.__name__)
                if names:
                    ButtonClick.reset(cls.__name__, names, records)
                return func(cls, records, *args, **kwargs)
        return wrapper

    @staticmethod
    def button_action(action):
        def decorator(func):
            func = ModelView.button(func)

            @wraps(func)
            def wrapper(*args, **kwargs):
                pool = Pool()
                ModelData = pool.get('ir.model.data')
                Action = pool.get('ir.action')

                value = func(*args, **kwargs)

                module, fs_id = action.split('.')
                action_id = Action.get_action_id(
                    ModelData.get_id(module, fs_id))
                if value:
                    action_value = Action(action_id).get_action_value()
                    action_value.update(value)
                    return action_value
                else:
                    return action_id
            return wrapper
        return decorator

    @staticmethod
    def button_change(*fields):
        def decorator(func):
            func = on_change(func)
            func.change = set(fields)
            return func
        return decorator

    def on_change(self, fieldnames):
        for fieldname in sorted(fieldnames):
            method = getattr(self, 'on_change_%s' % fieldname, None)
            if method:
                method()
        # XXX remove backward compatibility
        return [self._changed_values]

    def on_change_with(self, fieldnames):
        changes = {}
        for fieldname in fieldnames:
            method_name = 'on_change_with_%s' % fieldname
            changes[fieldname] = getattr(self, method_name)()
        return changes

    @property
    def _changed_values(self):
        """Return the values changed since the instantiation.
        By default, the value of a field is its internal representation except:
            - for Many2One and One2One field: the id.
            - for Reference field: the string model,id
            - for Many2Many: the list of ids
            - for One2Many: a dictionary composed of three keys:
                - add: a list of tuple, the first element is the index where
                  the new line is added, the second element is
                  `_default_values`
                - update: a list of dictionary of `_changed_values` including
                  the `id`
                - remove: a list of ids
        """
        from .modelstorage import ModelStorage
        changed = {}
        init_values = self._init_values or self._record()
        if not self._values:
            return changed
        init_record = self.__class__(self.id)
        for fname, value in self._values._items():
            field = self._fields[fname]
            # Always test key presence in case value is None
            if (fname in init_values
                    and value == init_values[fname]
                    and field._type != 'one2many'):
                continue
            if field._type in ('many2one', 'one2one', 'reference'):
                if value:
                    if isinstance(value, ModelStorage):
                        changed['%s.' % fname] = {
                            'rec_name': value.rec_name,
                            }
                    if value.id is None:
                        # Don't consider temporary instance as a change
                        continue
                    if field._type == 'reference':
                        value = str(value)
                    else:
                        value = value.id
            elif field._type in ['one2many', 'many2many']:
                targets = value
                if fname in init_values:
                    init_targets = init_values._get(fname)
                else:
                    init_targets = getattr(init_record, fname, [])
                value = collections.defaultdict(list)
                previous = [t.id for t in init_targets if t.id]
                for i, target in enumerate(targets):
                    if (field._type == 'one2many'
                            and field.field
                            and target._values):
                        t_values = target._values._copy()
                        # Don't look at reverse field
                        target._values._pop(field.field, None)
                    else:
                        t_values = None
                    try:
                        if target.id in previous:
                            previous.remove(target.id)
                            if isinstance(target, ModelView):
                                target_changed = target._changed_values
                                if target_changed:
                                    target_changed['id'] = target.id
                                    value['update'].append(target_changed)
                        else:
                            if isinstance(target, ModelView):
                                # Ensure initial values are returned because
                                # target was instantiated on server side.
                                target_init_values = target._init_values
                                target._init_values = None
                                try:
                                    added_values = target._changed_values
                                finally:
                                    target._init_values = target_init_values
                            else:
                                added_values = target._default_values
                            added_values['id'] = target.id
                            value['add'].append((i, added_values))
                    finally:
                        if t_values:
                            target._values = t_values
                if previous:
                    to_delete, to_remove = [], []
                    deleted = removed = None
                    if self._deleted:
                        deleted = self._deleted[fname]
                    if self._removed:
                        removed = self._removed[fname]
                    for id_ in previous:
                        if deleted and id_ in deleted:
                            to_delete.append(id_)
                        elif removed and id_ in removed:
                            to_remove.append(id_)
                        elif field._type == 'one2many':
                            to_delete.append(id_)
                        else:
                            to_remove.append(id_)
                    if to_delete:
                        value['delete'] = to_delete
                    if to_remove:
                        value['remove'] = to_remove
                if not value:
                    continue
                value = dict(value)
            changed[fname] = value
        return changed
