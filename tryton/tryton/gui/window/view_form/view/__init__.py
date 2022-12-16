# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gettext
from collections import defaultdict

from tryton.common import node_attributes

_ = gettext.gettext
list_ = list  # list builtins is overridden by import .list


class View(object):
    view_type = None
    widget = None
    mnemonic_widget = None
    view_id = None
    modified = None
    editable = None
    children_field = None
    scroll = None
    xml_parser = None

    def __init__(self, view_id, screen, xml):
        self.view_id = view_id
        self.screen = screen
        self.widgets = defaultdict(list_)
        self.state_widgets = []
        self.attributes = node_attributes(xml)
        screen.set_on_write(self.attributes.get('on_write'))

        if self.xml_parser:
            self.xml_parser(
                self, self.screen.exclude_field,
                {k: f.attrs for k, f in self.screen.group.fields.items()}
                ).parse(xml)

    def set_value(self):
        raise NotImplementedError

    def get_fields(self):
        raise NotImplementedError

    @property
    def record(self):
        return self.screen.current_record

    @record.setter
    def record(self, value):
        self.screen.current_record = value

    @property
    def group(self):
        return self.screen.group

    @property
    def selected_records(self):
        return []

    def get_buttons(self):
        raise NotImplementedError

    @staticmethod
    def parse(screen, view_id, view_type, xml, children_field):
        from .list import ViewTree
        from .form import ViewForm
        from .graph import ViewGraph
        from .calendar_ import ViewCalendar
        from .list_form import ViewListForm

        root, = xml.childNodes
        if view_type == 'tree':
            return ViewTree(view_id, screen, root, children_field)
        elif view_type == 'form':
            return ViewForm(view_id, screen, root)
        elif view_type == 'graph':
            return ViewGraph(view_id, screen, root)
        elif view_type == 'calendar':
            return ViewCalendar(view_id, screen, root)
        elif view_type == 'list-form':
            return ViewListForm(view_id, screen, root)


class XMLViewParser:

    def __init__(self, view, exclude_field, field_attrs):
        self.view = view
        self.exclude_field = exclude_field
        self.field_attrs = field_attrs

    def _node_attributes(self, node):
        node_attrs = node_attributes(node)
        if 'name' in node_attrs:
            field = self.field_attrs.get(node_attrs['name'], {})
        else:
            field = {}

        for name in ['readonly', 'homogeneous']:
            if name in node_attrs:
                node_attrs[name] = bool(int(node_attrs[name]))
        for name in [
                'yexpand', 'yfill', 'xexpand', 'xfill', 'colspan', 'position',
                'height', 'width', 'expand']:
            if name in node_attrs:
                node_attrs[name] = int(node_attrs[name])
        for name in ['xalign', 'yalign']:
            if name in node_attrs:
                node_attrs[name] = float(node_attrs[name])

        if field:
            node_attrs.setdefault('widget', field['type'])
            if node.tagName == 'label' and 'string' not in node_attrs:
                node_attrs['string'] = field['string'] + _(':')
            if node.tagName == 'field' and 'help' not in node_attrs:
                node_attrs['help'] = field['help']
            for name in [
                    'relation', 'domain', 'selection', 'string', 'states',
                    'relation_field', 'views', 'invisible', 'add_remove',
                    'sort', 'context', 'size', 'filename', 'autocomplete',
                    'translate', 'create', 'delete', 'selection_change_with',
                    'schema_model', 'required']:
                if name in field:
                    node_attrs.setdefault(name, field[name])
        return node_attrs

    def parse(self, node):
        node_attrs = self._node_attributes(node)
        if node.nodeType != node.ELEMENT_NODE:
            return
        parser = getattr(self, '_parse_%s' % node.tagName)
        parser(node, node_attrs)
