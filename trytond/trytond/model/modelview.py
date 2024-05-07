# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import collections
from functools import wraps

from lxml import etree

from trytond.cache import Cache
from trytond.exceptions import UserError
from trytond.i18n import gettext
from trytond.pool import Pool
from trytond.pyson import PYSONEncoder
from trytond.rpc import RPC, RPCReturnException
from trytond.tools import is_instance_method, likify
from trytond.transaction import Transaction, check_access, without_check_access

from . import fields
from .fields import on_change_result
from .model import Model

__all__ = ['ModelView']


class AccessButtonError(UserError):
    pass


class ButtonActionException(RPCReturnException):
    "Exception to launch action instead of executing button."

    def __init__(self, action, value=None):
        super().__init__()
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        Action = pool.get('ir.action')

        module, fs_id = action.split('.')
        action_id = Action.get_action_id(
            ModelData.get_id(module, fs_id))
        self.value = Action(action_id).get_action_value()
        if value:
            self.value.update(value)

    def result(self):
        return self.value


def set_visible(node, fields, loading='eager'):
    "Set loading to visible fields"
    if node.tag == 'group':
        if node.attrib.get('expandable', '1') == '1':
            for child in node:
                set_visible(child, fields, loading)
    elif node.tag == 'notebook':
        if len(node) > 0:
            set_visible(node[0], fields, loading)
    elif node.tag == 'field':
        if node.attrib['name'] in fields:
            node.attrib['loading'] = 'eager'
    else:
        for child in node:
            set_visible(child, fields, loading)


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
    _fields_view_get_cache = Cache('modelview.fields_view_get')
    _view_toolbar_get_cache = Cache(
        'modelview.view_toolbar_get', context=False)

    @classmethod
    def __setup__(cls):
        super(ModelView, cls).__setup__()
        cls.__rpc__['fields_view_get'] = RPC(cache=dict(days=1))
        cls.__rpc__['view_toolbar_get'] = RPC(cache=dict(days=1))
        cls.__rpc__['on_change'] = RPC(instantiate=0, result=on_change_result)
        cls.__rpc__['on_change_with'] = RPC(
            instantiate=0, result=on_change_result)
        cls.__rpc__['on_change_notify'] = RPC(instantiate=0)
        cls.__rpc__['on_scan_code'] = RPC(
            instantiate=0, result=on_change_result)
        cls.__rpc__['autocomplete'] = RPC()
        cls._buttons = {}

        fields_ = {}
        for name in dir(cls):
            if name.startswith('__'):
                continue
            attr = getattr(cls, name)
            if isinstance(attr, fields.Field):
                fields_[name] = attr

    @classmethod
    def __post_setup__(cls):
        super(ModelView, cls).__post_setup__()

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

        for name, field in cls._fields.items():
            for attribute in [
                    'on_change',
                    'on_change_with',
                    'autocomplete',
                    'selection_change_with',
                    ]:
                setup_field(name, field, attribute)

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

            meth_names = set()
            meth_done = set()
            for parent_cls in cls.__mro__:
                parent_meth = getattr(parent_cls, button, None)
                if not parent_meth:
                    continue
                cls.__change_buttons[button] |= getattr(
                    parent_meth, 'change', set())
                meth_names |= getattr(parent_meth, 'change_methods', set())
            while meth_names:
                meth_name = meth_names.pop()
                method = getattr(cls, meth_name)
                assert callable(method) or isinstance(method, property), \
                    "%s.%s not callable or property" % (cls, meth_name)
                set_methods(meth_name)
                cls.__change_buttons[button] |= methods['depends'][meth_name]
                meth_names |= (
                    methods['depend_methods'][meth_name] - meth_done)
                meth_done.add(meth_name)

        for func_name, depends_attr in [
                ('on_change_notify', '_on_change_notify_depends'),
                ('on_scan_code', '_on_scan_code_depends'),
                ]:
            set_methods(func_name)
            setattr(cls, depends_attr, methods['depends'][func_name])
            meth_names = list(methods['depend_methods'][func_name])
            meth_done = set()
            while meth_names:
                meth_name = meth_names.pop()
                method = getattr(cls, meth_name)
                assert callable(method) or isinstance(method, property), \
                    "%s.%s not callable or property" % (cls, meth_name)
                set_methods(meth_name)
                setattr(
                    cls, depends_attr,
                    getattr(cls, depends_attr) | methods['depends'][meth_name])
                meth_names += list(
                    methods['depend_methods'][meth_name] - meth_done)
                meth_done.add(meth_name)

        cls.on_scan_code = on_change(cls.on_scan_code)

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
        pool = Pool()
        User = pool.get('res.user')

        key = (User.get_groups(), cls.__name__, view_id, view_type, level)
        result = cls._fields_view_get_cache.get(key)
        if result:
            return result
        result = {'model': cls.__name__}
        pool = Pool()
        View = pool.get('ir.ui.view')

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
                view_id = view.id
            else:
                view = None

        # if a view was found
        if view:
            result = view.view_get(model=cls.__name__)

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
                if cls._buttons:
                    xml += '<group id="buttons" col="-1" colspan="4">'
                    for button in cls._buttons:
                        xml += '<button name="%s"/>' % button
                    xml += '</group>'
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
            result['view_id'] = view_id
            result['arch'] = xml
            result['field_childs'] = None
        result['model'] = cls.__name__

        if level is None:
            level = 1 if result['type'] == 'tree' else 0

        # Update arch and compute fields from arch
        parser = etree.XMLParser(
            remove_blank_text=True, resolve_entities=False)
        tree = etree.fromstring(result['arch'], parser)
        result['arch'], result['fields'] = cls.parse_view(
            tree, result['type'], view_id=view_id,
            field_children=result['field_childs'], level=level)

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
        User = pool.get('res.user')
        groups = User.get_groups()
        key = (Transaction().language, groups, cls.__name__)
        result = cls._view_toolbar_get_cache.get(key)
        if result:
            return result
        prints = Action.get_keyword('form_print', (cls.__name__, -1))
        actions = Action.get_keyword('form_action', (cls.__name__, -1))
        relates = Action.get_keyword('form_relate', (cls.__name__, -1))
        exports = Export.search_read(
            [('resource', '=', cls.__name__)],
            fields_names=['name', 'header', 'records', 'export_fields.name'])
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
    def parse_view(
            cls, tree, type, view_id=None, field_children=None, level=0,
            view_depends=None):
        """
        Return sanitized XML and the corresponding fields definition
        """
        pool = Pool()
        ModelAccess = pool.get('ir.model.access')
        FieldAccess = pool.get('ir.model.field.access')

        tree_root = tree.getroottree().getroot()
        readonly_view = (
            tree_root.tag == 'board'
            or (tree_root.tag == 'tree'
                and not int(tree_root.attrib.get('editable', '0'))))

        encoder = PYSONEncoder()
        if view_depends is None:
            view_depends = []
        else:
            view_depends = view_depends.copy()
        with Transaction().set_context(view_id=view_id):
            for xpath, attribute, value, *extra in cls.view_attributes():
                if readonly_view and attribute in {'required', 'readonly'}:
                    continue
                depends = []
                if extra:
                    depends, = extra
                nodes = tree.xpath(xpath)
                for element in nodes:
                    element.set(attribute, encoder.encode(value))
                if nodes and depends:
                    view_depends.extend(depends)

        fields_width = {}
        fields_optional = {}
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

        if type == 'form':
            for page in tree.xpath('//page[not(descendant::*)]'):
                page.getparent().remove(page)

            set_visible(tree,
                {fname for fname, field in cls._fields.items()
                    if field._type in {'one2many', 'many2many'}})

        if type == 'tree':
            user = Transaction().user
            if Transaction().context.get('view_tree_width'):
                ViewTreeWidth = pool.get('ir.ui.view_tree_width')
                viewtreewidths = ViewTreeWidth.search([
                    ('model', '=', cls.__name__),
                    ('user', '=', user),
                    ])
                for viewtreewidth in viewtreewidths:
                    if viewtreewidth.width > 0:
                        fields_width[viewtreewidth.field] = viewtreewidth.width

            if view_id:
                ViewTreeOptional = pool.get('ir.ui.view_tree_optional')
                viewtreeoptionals = ViewTreeOptional.search([
                        ('view_id', '=', view_id),
                        ('user', '=', user),
                        ])
                fields_optional = {o.field: o.value for o in viewtreeoptionals}

        fields_def = cls.__parse_fields(
            tree_root, type,
            fields_width=fields_width,
            fields_optional=fields_optional)

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

        for field_name in field_names:
            if field_name not in cls._fields:
                continue
            field = cls._fields[field_name]
            field_depends = field.display_depends.copy()
            if not readonly_view:
                field_depends |= field.edition_depends
            if 'context' in field_depends and 'context' not in cls._fields:
                field_depends.discard('context')
            for depend in (field_depends - fields_to_remove):
                if depend not in fields_def:
                    fields_def[depend] = {'name': depend}
                    field_names.append(depend)

        arch = etree.tostring(
            tree, encoding='utf-8', pretty_print=False).decode('utf-8')
        # Do not call fields_def without fields as it returns all fields
        if fields_def:
            # Prevent clients calling fields_view_get to get 'id' definition
            fields_def.setdefault('id', {'name': 'id'})
            fields2 = cls.fields_get(list(fields_def.keys()), level=level)
        else:
            fields2 = {}
        for field in fields_def:
            if field in fields2:
                fields2[field].update(fields_def[field])
        return arch, fields2

    @classmethod
    def __parse_fields(
            cls, element, type, fields_width=None, fields_optional=None,
            _fields_attrs=None):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        ModelAccess = pool.get('ir.model.access')
        Button = pool.get('ir.model.button')
        User = pool.get('res.user')
        ActionWindow = pool.get('ir.action.act_window')

        if fields_width is None:
            fields_width = {}
        if fields_optional is None:
            fields_optional = {}
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

            if type == 'tree':
                if element.get('name') in fields_width:
                    element.set(
                        'width', str(fields_width[element.get('name')]))
                if element.get('optional'):
                    if element.get('name') in fields_optional:
                        optional = str(int(
                                fields_optional[element.get('name')]))
                        element.set('optional', optional)

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
                with check_access():
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

        if element.tag == 'form' and element.get('scan_code'):
            element.set('scan_code_depends', encoder.encode(
                    list(cls._on_scan_code_depends)))

        if element.tag == 'tree' and element.get('sequence'):
            fields_attrs.setdefault(element.get('sequence'), {})

        if element.tag == 'calendar':
            for attr in ['dtstart', 'dtend', 'color', 'background_color']:
                if element.get(attr):
                    fields_attrs.setdefault(element.get(attr), {})

        for field in element:
            fields_attrs = cls.__parse_fields(
                field, type,
                fields_width=fields_width,
                fields_optional=fields_optional,
                _fields_attrs=fields_attrs)
        return fields_attrs

    @staticmethod
    def button(func):
        @wraps(func)
        def wrapper(cls, records, *args, **kwargs):
            from .modelstorage import ModelStorage
            pool = Pool()
            ModelAccess = pool.get('ir.model.access')
            Button = pool.get('ir.model.button')
            ButtonClick = pool.get('ir.model.button.click')
            User = pool.get('res.user')

            transaction = Transaction()
            check_access = transaction.check_access

            assert len(records) == len(set(records)), "Duplicate records"

            if (transaction.user != 0) and check_access:
                ModelAccess.check(cls.__name__, 'read')
                if issubclass(cls, ModelStorage):
                    # Check record rule access
                    cls.read([r.id for r in records
                            if r.id is not None and r.id >= 0],
                        ['id'])
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

            if check_access and issubclass(cls, ModelStorage):
                cls.log(records, 'button', func.__name__)
            with without_check_access():
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
    def button_change(*fields, **kwargs):
        methods = kwargs.pop('methods', None)
        assert not kwargs

        def decorator(func):
            func = on_change(func)
            func.change = set(fields)
            if methods:
                func.change_methods = set(methods)
            return func
        return decorator

    @on_change
    def on_change_with(self, fieldnames):
        for fieldname in fieldnames:
            method_name = 'on_change_with_%s' % fieldname
            value = getattr(self, method_name)()
            setattr(self, fieldname, value)

    @on_change
    def on_change(self, fieldnames):
        for fieldname in sorted(fieldnames):
            method = getattr(self, 'on_change_%s' % fieldname, None)
            if method:
                method()

    def on_change_notify(self):
        """Return a list of type and message couples.
        Available types are info, warning and error.
        """
        return []

    def on_scan_code(self, code):
        pass

    @classmethod
    def autocomplete(cls, text, domain=None, limit=None, order=None):
        from .modelstorage import ModelStorage
        result = []
        if domain is None:
            domain = []
        domain = [domain, ('rec_name', 'ilike', likify(text))]
        if issubclass(cls, ModelStorage):
            result = cls.search_read(
                domain, limit=limit, order=order, fields_names=['rec_name'])
            result = [
                {'id': r['id'], 'name': r['rec_name'], 'defaults': None}
                for r in result]
        return result

    @property
    def _changed_values(self):
        """Return the values changed since the instantiation.
        By default, the value of a field is its internal representation except:
            - for Many2One and One2One field: the id.
            - for Reference field: the string model,id
            - for One2Many and Many2Many: a dictionary composed of three keys:
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
                    and field._type not in {'one2many', 'many2many'}):
                continue
            if field._type in ('many2one', 'one2one', 'reference'):
                if value:
                    if (isinstance(value, ModelStorage)
                            and value.id and value.id >= 0):
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
                elif isinstance(field, fields.Function):
                    init_targets = []
                else:
                    assert hasattr(init_record, fname), (init_record, fname)
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
