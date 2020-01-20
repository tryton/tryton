# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
"Screen"
import copy
import functools
import gobject
import datetime
import calendar
import json
import collections
import urllib.parse
import xml.dom.minidom
import gettext
import logging
from operator import itemgetter

import gtk

from tryton.gui.window.view_form.model.group import Group
from tryton.gui.window.view_form.view.screen_container import ScreenContainer
from tryton.gui.window.view_form.view import View
from tryton.signal_event import SignalEvent
from tryton.config import CONFIG
from tryton.jsonrpc import JSONEncoder
from tryton.common.domain_parser import DomainParser
from tryton.common import RPCExecute, RPCException, MODELACCESS, \
    node_attributes, sur, RPCContextReload, warning
from tryton.action import Action
from tryton.pyson import PYSONDecoder

_ = gettext.gettext
logger = logging.getLogger(__name__)


class Screen(SignalEvent):
    "Screen"

    # Width of tree columns per model
    # It is shared with all connection but it is the price for speed.
    tree_column_width = collections.defaultdict(lambda: {})

    def __init__(self, model_name, **attributes):
        context = attributes.get('context', {})
        self.limit = attributes.get('limit', CONFIG['client.limit'])
        self.offset = 0
        super(Screen, self).__init__()

        self.readonly = attributes.get('readonly', False)
        if not (MODELACCESS[model_name]['write']
                or MODELACCESS[model_name]['create']):
            self.readonly = True
        self.search_count = 0
        if not attributes.get('row_activate'):
            self.row_activate = self.default_row_activate
        else:
            self.row_activate = attributes['row_activate']
        self.domain = attributes.get('domain', [])
        self.context_domain = attributes.get('context_domain')
        self.size_limit = None
        self.views_preload = attributes.get('views_preload', {})
        self.model_name = model_name
        self.views = []
        self.view_ids = attributes.get('view_ids', [])[:]
        self.parent = None
        self.parent_name = None
        self.exclude_field = attributes.get('exclude_field')
        self.filter_widget = None
        self.tree_states = collections.defaultdict(
            lambda: collections.defaultdict(lambda: None))
        self.tree_states_done = set()
        self.__group = None
        self.new_group(context or {})
        self.__current_record = None
        self.current_record = None
        self.screen_container = ScreenContainer(attributes.get('tab_domain'))
        self.screen_container.alternate_view = attributes.get(
            'alternate_view', False)
        self.widget = self.screen_container.widget_get()

        self.context_screen = None
        if attributes.get('context_model'):
            self.context_screen = Screen(
                attributes['context_model'], mode=['form'], context=context)
            self.context_screen.new()
            context_widget = self.context_screen.widget

            def walk_descendants(widget):
                yield widget
                if not hasattr(widget, 'get_children'):
                    return
                for child in widget.get_children():
                    for widget in walk_descendants(child):
                        yield widget

            for widget in reversed(list(walk_descendants(context_widget))):
                if isinstance(widget, gtk.Entry):
                    widget.connect_after(
                        'activate', self.screen_container.activate)
                elif isinstance(widget, gtk.CheckButton):
                    widget.connect_after(
                        'toggled', self.screen_container.activate)

            def remove_bin(widget):
                assert isinstance(widget, (gtk.ScrolledWindow, gtk.Viewport))
                parent = widget.get_parent()
                parent.remove(widget)
                child = widget.get_child()
                while isinstance(child, (gtk.ScrolledWindow, gtk.Viewport)):
                    child = child.get_child()
                child.get_parent().remove(child)
                parent.add(child)
                return child

            # Remove first level Viewport and ScrolledWindow to fill the Vbox
            for widget in [
                    self.context_screen.screen_container.viewport,
                    self.context_screen.current_view.widget.get_children()[0],
                    ]:
                remove_bin(widget)

            self.screen_container.filter_vbox.pack_start(
                context_widget, expand=False, fill=True)
            self.screen_container.filter_vbox.reorder_child(
                context_widget, 0)
            self.context_screen.widget.show()

        self.__current_view = 0
        self.search_value = attributes.get('search_value')
        self.fields_view_tree = {}
        self.order = self.default_order = attributes.get('order')
        self.view_to_load = []
        self._domain_parser = {}
        self.pre_validate = False
        mode = attributes.get('mode')
        if mode is None:
            mode = ['tree', 'form']
        self.view_to_load = mode[:]
        if self.view_ids or self.view_to_load:
            self.switch_view()
        self.count_tab_domain()

    def __repr__(self):
        return '<Screen %s at %s>' % (self.model_name, id(self))

    def search_active(self, active=True):
        if active and not self.parent:
            self.screen_container.set_screen(self)
            self.screen_container.show_filter()
        else:
            self.screen_container.hide_filter()

    @property
    def domain_parser(self):
        view_id = self.current_view.view_id if self.current_view else None

        if view_id in self._domain_parser:
            return self._domain_parser[view_id]

        if view_id not in self.fields_view_tree:
            try:
                self.fields_view_tree[view_id] = view_tree = RPCExecute(
                    'model', self.model_name, 'fields_view_get', False, 'tree',
                    context=self.context)
            except RPCException:
                view_tree = {
                    'fields': {},
                    }
        else:
            view_tree = self.fields_view_tree[view_id]

        fields = copy.deepcopy(view_tree['fields'])
        for name, props in fields.items():
            if props['type'] not in ('selection', 'reference'):
                continue
            if isinstance(props['selection'], (tuple, list)):
                continue
            props['selection'] = self.get_selection(props)

        if 'arch' in view_tree:
            # Filter only fields in XML view
            xml_dom = xml.dom.minidom.parseString(view_tree['arch'])
            root_node, = xml_dom.childNodes
            ofields = collections.OrderedDict()
            for node in root_node.childNodes:
                if node.nodeName != 'field':
                    continue
                attributes = node_attributes(node)
                name = attributes['name']
                # If a field is defined multiple times in the XML,
                # take only the first definition
                if name in ofields:
                    continue
                ofields[name] = fields[name]
                for attr in ['string', 'factor']:
                    if attributes.get(attr):
                        ofields[name][attr] = attributes[attr]
            fields = ofields

        if 'active' in view_tree['fields']:
            self.screen_container.but_active.show()
        else:
            self.screen_container.but_active.hide()

        # Add common fields
        for name, string, type_ in (
                ('id', _('ID'), 'integer'),
                ('create_uid', _('Creation User'), 'many2one'),
                ('create_date', _('Creation Date'), 'datetime'),
                ('write_uid', _('Modification User'), 'many2one'),
                ('write_date', _('Modification Date'), 'datetime'),
                ):
            if name not in fields:
                fields[name] = {
                    'string': string,
                    'name': name,
                    'type': type_,
                    }
                if type_ == 'datetime':
                    fields[name]['format'] = '"%H:%M:%S"'

        domain_parser = DomainParser(fields, self.context)
        self._domain_parser[view_id] = domain_parser
        return domain_parser

    def get_selection(self, props):
        try:
            change_with = props.get('selection_change_with')
            if change_with:
                selection = RPCExecute('model', self.model_name,
                    props['selection'], dict((p, None) for p in change_with))
            else:
                selection = RPCExecute('model', self.model_name,
                    props['selection'])
        except RPCException:
            selection = []
        selection.sort(key=itemgetter(1))
        return selection

    def search_prev(self, search_string):
        if self.limit:
            self.offset -= self.limit
        self.search_filter(search_string=search_string)

    def search_next(self, search_string):
        if self.limit:
            self.offset += self.limit
        self.search_filter(search_string=search_string)

    def search_complete(self, search_string):
        return list(self.domain_parser.completion(search_string))

    def search_filter(self, search_string=None, only_ids=False):
        if self.context_screen and not only_ids:
            context_record = self.context_screen.current_record
            if not context_record.validate():
                self.clear()
                self.context_screen.display(set_cursor=True)
                return False
            context = self.local_context
            screen_context = self.context_screen.get_on_change_value()
            screen_context.pop('id')
            context.update(screen_context)
            self.new_group(context)

        domain = self.search_domain(search_string, True)
        if self.context_domain:
            decoder = PYSONDecoder(self.context)
            domain = ['AND', domain, decoder.decode(self.context_domain)]
        tab_domain = self.screen_container.get_tab_domain()
        if tab_domain:
            domain = ['AND', domain, tab_domain]

        context = self.context
        if self.screen_container.but_active.get_active():
            context['active_test'] = False
        try:
            ids = RPCExecute('model', self.model_name, 'search', domain,
                self.offset, self.limit, self.order, context=context)
        except RPCException:
            ids = []
        if not only_ids:
            if self.limit is not None and len(ids) == self.limit:
                try:
                    self.search_count = RPCExecute('model', self.model_name,
                        'search_count', domain, context=context)
                except RPCException:
                    self.search_count = 0
            else:
                self.search_count = len(ids)
        self.screen_container.but_prev.set_sensitive(bool(self.offset))
        if (self.limit is not None
                and len(ids) == self.limit
                and self.search_count > self.limit + self.offset):
            self.screen_container.but_next.set_sensitive(True)
        else:
            self.screen_container.but_next.set_sensitive(False)
        if only_ids:
            return ids
        self.clear()
        self.load(ids)
        self.count_tab_domain()
        return bool(ids)

    def search_domain(self, search_string=None, set_text=False):
        domain = []
        # Test first parent to avoid calling unnecessary domain_parser
        if not self.parent and self.domain_parser:
            if search_string is not None:
                domain = self.domain_parser.parse(search_string)
            else:
                domain = self.search_value
                self.search_value = None
            if set_text:
                self.screen_container.set_text(
                    self.domain_parser.string(domain))
        else:
            domain = [('id', 'in', [x.id for x in self.group])]

        if domain:
            if self.domain:
                domain = ['AND', domain, self.domain]
        else:
            domain = self.domain

        if self.screen_container.but_active.get_active():
            if domain:
                domain = [domain, ('active', '=', False)]
            else:
                domain = [('active', '=', False)]
        if self.current_view and self.current_view.view_type == 'calendar':
            if domain:
                domain = ['AND', domain, self.current_view.current_domain()]
            else:
                domain = self.current_view.current_domain()
        return domain

    def count_tab_domain(self):
        def set_tab_counter(count, idx):
            try:
                count = count()
            except RPCException:
                count = None
            self.screen_container.set_tab_counter(count, idx)
        screen_domain = self.search_domain(self.screen_container.get_text())
        for idx, (name, domain, count) in enumerate(
                self.screen_container.tab_domain):
            if not count:
                continue
            domain = ['AND', domain, screen_domain]
            set_tab_counter(lambda: None, idx)
            RPCExecute('model', self.model_name,
                'search_count', domain, context=self.context,
                callback=functools.partial(set_tab_counter, idx=idx))

    @property
    def context(self):
        context = self.group.context
        if self.context_screen:
            context['context_model'] = self.context_screen.model_name
        return context

    @property
    def local_context(self):
        context = self.group.local_context
        if self.context_screen:
            context['context_model'] = self.context_screen.model_name
        return context

    def __get_group(self):
        return self.__group

    def __set_group(self, group):
        fields = {}
        fields_views = {}
        if self.group is not None:
            self.group.signal_unconnect(self)
            for name, field in self.group.fields.items():
                fields[name] = field.attrs
                fields_views[name] = field.views
        self.tree_states_done.clear()
        self.__group = group
        self.parent = group.parent
        self.parent_name = group.parent_name
        if self.parent:
            self.filter_widget = None
        if len(group):
            self.current_record = group[0]
        else:
            self.current_record = None
        self.__group.signal_connect(self, 'group-cleared', self._group_cleared)
        self.__group.signal_connect(self, 'group-list-changed',
                self._group_list_changed)
        self.__group.signal_connect(self, 'record-modified',
            self._record_modified)
        self.__group.signal_connect(self, 'group-changed', self._group_changed)
        self.__group.add_fields(fields)
        for name, views in fields_views.items():
            self.__group.fields[name].views.update(views)
        self.__group.exclude_field = self.exclude_field

    group = property(__get_group, __set_group)

    def new_group(self, context=None):
        context = context if context is not None else self.context
        self.group = Group(self.model_name, {}, domain=self.domain,
            context=context, readonly=self.readonly)

    def _group_cleared(self, group, signal):
        for view in self.views:
            if view.view_type == 'tree':
                view.display(force=True)

    def _group_list_changed(self, group, signal):
        for view in self.views:
            if hasattr(view, 'group_list_changed'):
                view.group_list_changed(group, signal)

    def _record_modified(self, group, signal):
        self.signal('record-modified', signal)

    def _group_changed(self, group, record):
        if not self.parent:
            self.display()
        self.signal('group-changed', record)

    def __get_current_record(self):
        if (self.__current_record is not None
                and self.__current_record.group is None):
            self.__current_record = None
        return self.__current_record

    def __set_current_record(self, record):
        self.__current_record = record
        if record:
            try:
                pos = self.group.index(record) + self.offset + 1
            except ValueError:
                # XXX offset?
                pos = record.get_index_path()
        else:
            pos = 0
        self.signal('record-message', (pos, len(self.group) + self.offset,
            self.search_count, record and record.id))
        attachment_count = 0
        if record and record.attachment_count > 0:
            attachment_count = record.attachment_count
        self.signal('attachment-count', attachment_count)
        unread_note = 0
        if record and record.unread_note > 0:
            unread_note = record.unread_note
        self.signal('unread-note', unread_note)
        # update attachment-count after 1 second
        gobject.timeout_add(1000, self.update_attachment, record)
        gobject.timeout_add(1000, self.update_note, record)
        return True

    current_record = property(__get_current_record, __set_current_record)

    def update_attachment(self, record):
        if record != self.current_record:
            return False
        if record and self.signal_connected('attachment-count'):
            attachment_count = record.get_attachment_count()
            self.signal('attachment-count', attachment_count)
        return False

    def update_note(self, record):
        if record != self.current_record:
            return False
        if record and self.signal_connected('unread-note'):
            unread_note = record.get_unread_note()
            self.signal('unread-note', unread_note)
        return False

    def destroy(self):
        self.screen_container.destroy()
        for view in self.views:
            view.destroy()
        del self.views[:]
        super(Screen, self).destroy()
        self.group.signal_unconnect(self)
        self.group.destroy()

    def default_row_activate(self):
        if (self.current_view.view_type == 'tree' and
                int(self.current_view.attributes.get('keyword_open', 0))):
            return Action.exec_keyword('tree_open', {
                'model': self.model_name,
                'id': self.current_record.id if self.current_record else None,
                'ids': [r.id for r in self.selected_records],
                }, context=self.local_context, warning=False)
        else:
            if not self.modified():
                self.switch_view(view_type='form')
            return True

    @property
    def number_of_views(self):
        return len(self.views) + len(self.view_to_load)

    def switch_view(self, view_type=None, view_id=None):
        if view_id is not None:
            view_id = int(view_id)
        if self.current_view:
            self.current_view.set_value()
            if (self.current_record and
                    self.current_record not in self.current_record.group):
                self.current_record = None
            fields = self.current_view.get_fields()
            if (self.current_record and self.current_view.editable
                    and not self.current_record.validate(fields)):
                self.screen_container.set(self.current_view.widget)
                self.set_cursor()
                self.current_view.display()
                return

        def found():
            if not self.current_view:
                return False
            elif not view_type and view_id is None:
                return False
            elif view_id is not None:
                return self.current_view.view_id == view_id
            else:
                return self.current_view.view_type == view_type
        while not found():
            if len(self.view_to_load):
                self.load_view_to_load()
                self.__current_view = len(self.views) - 1
            elif (view_id is not None
                    and view_id not in {v.view_id for v in self.views}):
                self.add_view_id(view_id, view_type)
                self.__current_view = len(self.views) - 1
                break
            else:
                self.__current_view = ((self.__current_view + 1)
                        % len(self.views))
            if not view_type and view_id is None:
                break
            if view_type and not view_id and not len(self.view_to_load):
                break
        self.screen_container.set(self.current_view.widget)
        self.display()
        # Postpone set of the cursor to ensure widgets are allocated
        gobject.idle_add(self.set_cursor)

    def load_view_to_load(self):
        if len(self.view_to_load):
            if self.view_ids:
                view_id = self.view_ids.pop(0)
            else:
                view_id = None
            view_type = self.view_to_load.pop(0)
            self.add_view_id(view_id, view_type)

    def add_view_id(self, view_id, view_type):
        if view_id and str(view_id) in self.views_preload:
            view = self.views_preload[str(view_id)]
        elif not view_id and view_type in self.views_preload:
            view = self.views_preload[view_type]
        else:
            try:
                view = RPCExecute('model', self.model_name, 'fields_view_get',
                    view_id, view_type, context=self.context)
            except RPCException:
                return
        return self.add_view(view)

    def add_view(self, view):
        arch = view['arch']
        fields = view['fields']
        view_id = view['view_id']

        xml_dom = xml.dom.minidom.parseString(arch)
        root, = xml_dom.childNodes
        if root.tagName == 'tree':
            self.fields_view_tree[view_id] = view

        # Ensure that loading is always lazy for fields on form view
        # and always eager for fields on tree or graph view
        if root.tagName == 'form':
            loading = 'lazy'
        else:
            loading = 'eager'
        for field in fields:
            if field not in self.group.fields or loading == 'eager':
                fields[field]['loading'] = loading
            else:
                fields[field]['loading'] = \
                    self.group.fields[field].attrs['loading']
        self.group.add_fields(fields)
        for field in fields:
            self.group.fields[field].views.add(view_id)
        view = View.parse(self, xml_dom, view.get('field_childs'))
        view.view_id = view_id
        self.views.append(view)

        return view

    def new(self, default=True, rec_name=None):
        previous_view = self.current_view
        if self.current_view.view_type == 'calendar':
            selected_date = self.current_view.get_selected_date()
        if self.current_view and not self.current_view.editable:
            self.switch_view('form')
            if self.current_view.view_type != 'form':
                return None
        if self.current_record:
            group = self.current_record.group
        else:
            group = self.group
        record = group.new(default, rec_name=rec_name)
        group.add(record, self.new_model_position())
        if previous_view.view_type == 'calendar':
            previous_view.set_default_date(record, selected_date)
        self.current_record = record
        self.display()
        # Postpone set of the cursor to ensure widgets are allocated
        gobject.idle_add(self.set_cursor, True)
        return self.current_record

    def new_model_position(self):
        position = -1
        if (self.current_view and self.current_view.view_type == 'tree'
                and self.current_view.attributes.get('editable') == 'top'):
            position = 0
        return position

    def set_on_write(self, func_name):
        if func_name:
            self.group.on_write.add(func_name)

    def cancel_current(self, initial_value=None):
        if self.current_record:
            self.current_record.cancel()
            if self.current_record.id < 0:
                if initial_value is not None:
                    self.current_record.reset(initial_value)
                else:
                    self.remove(records=[self.current_record])

    def save_current(self):
        if not self.current_record:
            if self.current_view.view_type == 'tree' and len(self.group):
                self.current_record = self.group[0]
            else:
                return True
        self.current_view.set_value()
        saved = False
        record_id = None
        fields = self.current_view.get_fields()
        path = self.current_record.get_path(self.group)
        if self.current_view.view_type == 'tree':
            # False value must be not saved
            saved = all((x is 0 or x > 0 for x in self.group.save()))
            record_id = self.current_record.id if self.current_record else None
        elif self.current_record.validate(fields):
            record_id = self.current_record.save(force_reload=True)
            # False value must be not saved
            saved = record_id is 0 or record_id > 0
        else:
            self.set_cursor()
            self.current_view.display()
            return False
        if path and record_id:
            path = path[:-1] + ((path[-1][0], record_id),)
        self.current_record = self.group.get_by_path(path)
        self.display()
        self.signal('record-saved')
        return saved

    def __get_current_view(self):
        if not len(self.views):
            return None
        return self.views[self.__current_view]

    current_view = property(__get_current_view)

    def set_cursor(self, new=False, reset_view=True):
        current_view = self.current_view
        if not current_view:
            return
        elif current_view.view_type in ('tree', 'form'):
            current_view.set_cursor(new=new, reset_view=reset_view)

    def get(self):
        if not self.current_record:
            return None
        self.current_view.set_value()
        return self.current_record.get()

    def get_on_change_value(self):
        if not self.current_record:
            return None
        self.current_view.set_value()
        return self.current_record.get_on_change_value()

    def modified(self):
        if self.current_view.view_type != 'tree':
            if self.current_record:
                if self.current_record.modified or self.current_record.id < 0:
                    return True
        else:
            for record in self.group:
                if record.modified or record.id < 0:
                    return True
        if self.current_view.modified:
            return True
        return False

    def reload(self, ids, written=False):
        self.group.reload(ids)
        if written:
            self.group.written(ids)
        if self.parent:
            self.parent.root_parent.reload()
        self.display()

    def unremove(self):
        records = self.selected_records
        for record in records:
            self.group.unremove(record)

    def remove(self, delete=False, remove=False, force_remove=False,
            records=None):
        records = records or self.selected_records
        if not records:
            return
        if delete:
            # Must delete children records before parent
            records.sort(key=lambda r: r.depth, reverse=True)
            if not self.group.delete(records):
                return False

        top_record = records[0]
        top_group = top_record.group
        idx = top_group.index(top_record)
        path = top_record.get_path(self.group)

        for record in records:
            # set current model to None to prevent __select_changed
            # to save the previous_model as it can be already deleted.
            self.current_record = None
            record.group.remove(record, remove=remove, signal=False,
                force_remove=force_remove)
        # send record-changed only once
        record.signal('record-changed')

        if delete:
            for record in records:
                if record in record.group.record_deleted:
                    record.group.record_deleted.remove(record)
                if record in record.group.record_removed:
                    record.group.record_removed.remove(record)
                if record.parent:
                    # Save parent without deleted children
                    record.parent.save(force_reload=False)
                record.destroy()

        if idx > 0:
            record = top_group[idx - 1]
            path = path[:-1] + ((path[-1][0], record.id,),)
        else:
            path = path[:-1]
        if path:
            self.current_record = self.group.get_by_path(path)
        elif len(self.group):
            self.current_record = self.group[0]
        self.set_cursor()
        self.display()
        return True

    def copy(self):
        ids = [r.id for r in self.selected_records]
        try:
            new_ids = RPCExecute('model', self.model_name, 'copy', ids, {},
                context=self.context)
        except RPCException:
            return False
        self.load(new_ids)
        return True

    def set_tree_state(self):
        view = self.current_view
        if view.view_type not in ('tree', 'form'):
            return
        if id(view) in self.tree_states_done:
            return
        if view.view_type == 'form' and self.tree_states_done:
            return
        if (view.view_type == 'tree'
                and not view.attributes.get('tree_state', False)):
            # Mark as done to not set later when the view_type change
            self.tree_states_done.add(id(view))
        parent = self.parent.id if self.parent else None
        if parent is not None and parent < 0:
            return
        expanded_nodes, selected_nodes = [], []
        timestamp = self.parent._timestamp if self.parent else None
        state = self.tree_states[parent][view.children_field]
        if state:
            state_timestamp, expanded_nodes, selected_nodes = state
            if (timestamp != state_timestamp
                    and view.view_type != 'form'):
                state = None
        if state is None and CONFIG['client.save_tree_state']:
            json_domain = self.get_tree_domain(parent)
            try:
                expanded_nodes, selected_nodes = RPCExecute('model',
                    'ir.ui.view_tree_state', 'get',
                    self.model_name, json_domain,
                    view.children_field)
                expanded_nodes = json.loads(expanded_nodes)
                selected_nodes = json.loads(selected_nodes)
            except RPCException:
                logger.warn(
                    _('Unable to get view tree state for %s')
                    % self.model_name)
            self.tree_states[parent][view.children_field] = (
                timestamp, expanded_nodes, selected_nodes)
        if view.view_type == 'tree':
            view.expand_nodes(expanded_nodes)
            view.select_nodes(selected_nodes)
        else:
            if selected_nodes:
                record = None
                for node in selected_nodes[0]:
                    new_record = self.group.get(node)
                    if node < 0 and -node < len(self.group):
                        # Negative id is the index of the new record
                        new_record = self.group[-node]
                    if not new_record:
                        break
                    else:
                        record = new_record
                if record and record != self.current_record:
                    self.current_record = record
                    # Force a display of the view to synchronize the
                    # widgets with the new record
                    view.display()
        self.tree_states_done.add(id(view))

    def save_tree_state(self, store=True):
        parent = self.parent.id if self.parent else None
        timestamp = self.parent._timestamp if self.parent else None
        for view in self.views:
            if view.view_type == 'form':
                for widgets in view.widgets.values():
                    for widget in widgets:
                        if hasattr(widget, 'screen'):
                            widget.screen.save_tree_state(store)
                if len(self.views) == 1 and self.current_record:
                    path = self.current_record.id
                    if path < 0:
                        path = -self.current_record.group.index(
                            self.current_record)
                    self.tree_states[parent][view.children_field] = (
                        timestamp, [], [[path]])
            elif view.view_type == 'tree':
                paths = view.get_expanded_paths()
                selected_paths = view.get_selected_paths()
                self.tree_states[parent][view.children_field] = (
                    timestamp, paths, selected_paths)
                if (store
                        and int(view.attributes.get('tree_state', False))
                        and CONFIG['client.save_tree_state']):
                    json_domain = self.get_tree_domain(parent)
                    json_paths = json.dumps(paths, separators=(',', ':'))
                    json_selected_path = json.dumps(
                        selected_paths, separators=(',', ':'))
                    try:
                        RPCExecute('model', 'ir.ui.view_tree_state', 'set',
                            self.model_name, json_domain, view.children_field,
                            json_paths, json_selected_path,
                            process_exception=False)
                    except Exception:
                        logger.warn(
                            _('Unable to set view tree state'), exc_info=True)

    def get_tree_domain(self, parent):
        if parent:
            domain = (self.domain + [(self.exclude_field, '=', parent)])
        else:
            domain = self.domain
        json_domain = json.dumps(
            domain, cls=JSONEncoder, separators=(',', ':'))
        return json_domain

    def load(self, ids, set_cursor=True, modified=False):
        self.tree_states.clear()
        self.tree_states_done.clear()
        self.group.load(ids, modified=modified)
        self.current_view.reset()
        if ids and self.current_view.view_type != 'calendar':
            self.display(ids[0])
        else:
            self.current_record = None
            self.display()
        if set_cursor:
            self.set_cursor()

    def display(self, res_id=None, set_cursor=False):
        if res_id:
            self.current_record = self.group.get(res_id)
        else:
            if (self.current_record
                    and self.current_record in self.current_record.group):
                pass
            elif self.group and self.current_view.view_type != 'calendar':
                self.current_record = self.group[0]
            else:
                self.current_record = None
        if self.views:
            self.search_active(self.current_view.view_type
                in ('tree', 'graph', 'calendar'))
            for view in self.views:
                # Always display tree view to update model
                # because view can be used even if it is not shown
                # like for save_tree_state
                if (view == self.current_view
                        or view.view_type == 'tree'
                        or view.widget.get_parent()):
                    view.display()
            self.current_view.widget.set_sensitive(
                bool(self.group
                    or (self.current_view.view_type != 'form')
                    or self.current_record))
            if set_cursor:
                self.set_cursor(reset_view=False)
        self.set_tree_state()
        # Force record-message signal
        self.current_record = self.current_record

    def display_next(self):
        view = self.current_view
        view.set_value()
        self.set_cursor(reset_view=False)
        if view.view_type == 'tree' and len(self.group):
            range_ = view.treeview.get_visible_range()
            if range_:
                start, end = range_
                vadjustment = view.treeview.get_vadjustment()
                vadjustment.props.value = min(
                    vadjustment.props.value + vadjustment.props.page_increment,
                    vadjustment.props.upper)
                model = view.treeview.get_model()
                iter_ = model.get_iter(end)
                self.current_record = model.get_value(iter_, 0)
        elif (view.view_type == 'form'
                and self.current_record
                and self.current_record.group):
            group = self.current_record.group
            record = self.current_record
            while group:
                children = record.children_group(view.children_field)
                if children:
                    record = children[0]
                    break
                idx = group.index(record) + 1
                if idx < len(group):
                    record = group[idx]
                    break
                parent = record.parent
                if not parent or record.model_name != parent.model_name:
                    break
                next = parent.next.get(id(parent.group))
                while not next:
                    parent = parent.parent
                    if not parent:
                        break
                    next = parent.next.get(id(parent.group))
                if not next:
                    break
                record = next
                break
            self.current_record = record
        elif view.view_type == 'calendar':
            record = self.current_record
            goocalendar = view.widgets.get('goocalendar')
            if goocalendar:
                date = goocalendar.selected_date
                year = date.year
                month = date.month
                start = datetime.datetime(year, month, 1)
                nb_days = calendar.monthrange(year, month)[1]
                delta = datetime.timedelta(days=nb_days)
                end = start + delta
                events = goocalendar.event_store.get_events(start, end)
                events.sort()
                if not record:
                    if events:
                        self.current_record = events[0].record
                    else:
                        self.current_record = None
                else:
                    for idx, event in enumerate(events):
                        if event.record == record:
                            next_id = idx + 1
                            if next_id < len(events):
                                self.current_record = events[next_id].record
                            break
        else:
            self.current_record = self.group[0] if len(self.group) else None
        self.set_cursor(reset_view=False)
        view.display()

    def display_prev(self):
        view = self.current_view
        view.set_value()
        self.set_cursor(reset_view=False)
        if view.view_type == 'tree' and len(self.group):
            range_ = view.treeview.get_visible_range()
            if range_:
                start, end = range_
                vadjustment = view.treeview.get_vadjustment()
                vadjustment.props.value = min(
                    vadjustment.props.value - vadjustment.props.page_increment,
                    vadjustment.props.lower)
                model = view.treeview.get_model()
                iter_ = model.get_iter(start)
                self.current_record = model.get_value(iter_, 0)
        elif (view.view_type == 'form'
                and self.current_record
                and self.current_record.group):
            group = self.current_record.group
            record = self.current_record
            idx = group.index(record) - 1
            if idx >= 0:
                record = group[idx]
                children = True
                while children:
                    children = record.children_group(view.children_field)
                    if children:
                        record = children[-1]
            else:
                parent = record.parent
                if parent and record.model_name == parent.model_name:
                    record = parent
            self.current_record = record
        elif view.view_type == 'calendar':
            record = self.current_record
            goocalendar = view.widgets.get('goocalendar')
            if goocalendar:
                date = goocalendar.selected_date
                year = date.year
                month = date.month
                start = datetime.datetime(year, month, 1)
                nb_days = calendar.monthrange(year, month)[1]
                delta = datetime.timedelta(days=nb_days)
                end = start + delta
                events = goocalendar.event_store.get_events(start, end)
                events.sort()
                if not record:
                    if events:
                        self.current_record = events[0].record
                    else:
                        self.current_record = None
                else:
                    for idx, event in enumerate(events):
                        if event.record == record:
                            prev_id = idx - 1
                            if prev_id >= 0:
                                self.current_record = events[prev_id].record
                            break
        else:
            self.current_record = self.group[-1] if len(self.group) else None
        self.set_cursor(reset_view=False)
        view.display()

    def invalid_message(self, record=None):
        if record is None:
            record = self.current_record
        domain_string = _('"%s" is not valid according to its domain')
        domain_parser = DomainParser(
            {n: f.attrs for n, f in record.group.fields.items()})
        fields = []
        for field, invalid in sorted(record.invalid_fields.items()):
            string = record.group.fields[field].attrs['string']
            if invalid == 'required' or invalid == [[field, '!=', None]]:
                fields.append(_('"%s" is required') % string)
            elif invalid == 'domain':
                fields.append(domain_string % string)
            elif invalid == 'children':
                fields.append(_('The values of "%s" are not valid') % string)
            else:
                if domain_parser.stringable(invalid):
                    fields.append(domain_parser.string(invalid))
                else:
                    fields.append(domain_string % string)
        if len(fields) > 5:
            fields = fields[:5] + ['...']
        return '\n'.join(fields)

    @property
    def selected_records(self):
        return self.current_view.selected_records

    def clear(self):
        self.current_record = None
        self.group.clear()

    def on_change(self, fieldname, attr):
        self.current_record.on_change(fieldname, attr)
        self.display()

    def get_buttons(self):
        'Return active buttons for the current view'
        def is_active(record, button):
            if button.attrs.get('type', 'class') == 'instance':
                return False
            states = record.expr_eval(button.attrs.get('states', {}))
            return not (states.get('invisible') or states.get('readonly'))

        if not self.selected_records:
            return []

        buttons = self.current_view.get_buttons()

        for record in self.selected_records:
            buttons = [b for b in buttons if is_active(record, b)]
            if not buttons:
                break
        return buttons

    def button(self, button):
        'Execute button on the selected records'
        self.current_view.set_value()
        fields = self.current_view.get_fields()
        for record in self.selected_records:
            domain = record.expr_eval(
                button.get('states', {})).get('pre_validate', [])
            if not record.validate(fields, pre_validate=domain):
                warning(self.invalid_message(record), _('Pre-validation'))
                self.display(set_cursor=True)
                if domain:
                    # Reset valid state with normal domain
                    record.validate(fields)
                return
        if button.get('confirm', False) and not sur(button['confirm']):
            return
        if button.get('type', 'class') == 'class':
            if not self.current_record.save(force_reload=False):
                return
        if button.get('type', 'class') == 'class':
            self._button_class(button)
        else:
            self._button_instance(button)

    def _button_instance(self, button):
        record = self.current_record
        args = record.expr_eval(button.get('change', []))
        values = record._get_on_change_args(args)
        try:
            changes = RPCExecute('model', self.model_name, button['name'],
                values, context=self.context)
        except RPCException:
            return
        record.set_on_change(changes)
        record.signal('record-changed')

    def _button_class(self, button):
        ids = [r.id for r in self.selected_records]
        context = self.context
        context['_timestamp'] = {}
        for record in self.selected_records:
            context['_timestamp'].update(record.get_timestamp())
        try:
            action = RPCExecute('model', self.model_name, button['name'],
                ids, context=context)
        except RPCException:
            action = None
        self.reload(ids, written=True)
        if isinstance(action, str):
            self.client_action(action)
        elif action:
            Action.execute(action, {
                    'model': self.model_name,
                    'id': self.current_record.id,
                    'ids': ids,
                    }, context=self.context, keyword=True)

    def client_action(self, action):
        access = MODELACCESS[self.model_name]
        if action == 'new':
            if access['create']:
                self.new()
        elif action == 'delete':
            if access['delete']:
                self.remove(delete=not self.parent,
                    force_remove=not self.parent)
        elif action == 'remove':
            if access['write'] and access['read'] and self.parent:
                self.remove(remove=True)
        elif action == 'copy':
            if access['create']:
                self.copy()
        elif action == 'next':
            self.display_next()
        elif action == 'previous':
            self.display_prev()
        elif action == 'close':
            from tryton.gui import Main
            Main().sig_win_close()
        elif action.startswith('switch'):
            self.switch_view(*action.split(None, 2)[1:])
        elif action == 'reload':
            if (self.current_view.view_type in ['tree', 'graph', 'calendar']
                    and not self.parent):
                self.search_filter()
        elif action == 'reload menu':
            from tryton.gui import Main
            RPCContextReload(Main().sig_win_menu)
        elif action == 'reload context':
            RPCContextReload()

    def get_url(self, name=''):
        query_string = []
        if self.domain:
            query_string.append(('domain', json.dumps(
                        self.domain, cls=JSONEncoder, separators=(',', ':'))))
        context = self.local_context  # Avoid rpc context
        if context:
            query_string.append(('context', json.dumps(
                        context, cls=JSONEncoder, separators=(',', ':'))))
        if self.context_screen:
            query_string.append(
                ('context_model', self.context_screen.model_name))
        if name:
            query_string.append(
                ('name', json.dumps(name, separators=(',', ':'))))
        path = [CONFIG['login.db'], 'model', self.model_name]
        view_ids = [v.view_id for v in self.views] + self.view_ids
        if self.current_view.view_type != 'form':
            if self.search_value:
                search_value = self.search_value
            else:
                search_string = self.screen_container.get_text()
                search_value = self.domain_parser.parse(search_string)
            if search_value:
                query_string.append(('search_value', json.dumps(
                            search_value, cls=JSONEncoder,
                            separators=(',', ':'))))
        elif self.current_record and self.current_record.id > -1:
            path.append(str(self.current_record.id))
            i = view_ids.index(self.current_view.view_id)
            view_ids = view_ids[i:] + view_ids[:i]
        if view_ids:
            query_string.append(('views', json.dumps(
                        view_ids, separators=(',', ':'))))
        query_string = urllib.parse.urlencode(query_string)
        return urllib.parse.urlunparse(('tryton',
                CONFIG['login.host'],
                '/'.join(path), query_string, '', ''))
