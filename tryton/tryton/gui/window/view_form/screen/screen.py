#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Screen"
import copy
import gobject
import datetime
import calendar
try:
    import simplejson as json
except ImportError:
    import json
import collections
import urllib
import urlparse
import xml.dom.minidom
import gettext
import logging

from tryton.gui.window.view_form.model.group import Group
from tryton.gui.window.view_form.view.screen_container import ScreenContainer
from tryton.signal_event import SignalEvent
from tryton.config import CONFIG
from tryton.exceptions import TrytonServerError, TrytonServerUnavailable
from tryton.jsonrpc import JSONEncoder
from tryton.common.domain_parser import DomainParser
from tryton.common import RPCExecute, RPCException, MODELACCESS, \
    node_attributes, sur
from tryton.action import Action
import tryton.rpc as rpc

_ = gettext.gettext


class Screen(SignalEvent):
    "Screen"

    # Width of tree columns per model
    # It is shared with all connection but it is the price for speed.
    tree_column_width = collections.defaultdict(lambda: {})

    def __init__(self, model_name, view_ids=None, mode=None, context=None,
            views_preload=None, domain=None, row_activate=None, limit=None,
            readonly=False, exclude_field=None, order=None, search_value=None,
            tab_domain=None, alternate_view=False):
        if view_ids is None:
            view_ids = []
        if mode is None:
            mode = ['tree', 'form']
        if context is None:
            context = {}
        if views_preload is None:
            views_preload = {}
        if domain is None:
            domain = []

        self.limit = limit or CONFIG['client.limit']
        self.offset = 0
        super(Screen, self).__init__()

        self.readonly = readonly
        if not (MODELACCESS[model_name]['write']
                or MODELACCESS[model_name]['create']):
            self.readonly = True
        self.search_count = 0
        if not row_activate:
            self.row_activate = self.default_row_activate
        else:
            self.row_activate = row_activate
        self.domain = domain
        self.size_limit = None
        self.views_preload = views_preload
        self.model_name = model_name
        self.context = context
        self.views = []
        self.view_ids = view_ids[:]
        self.parent = None
        self.parent_name = None
        self.exclude_field = exclude_field
        self.filter_widget = None
        self.__group = None
        self.new_group()
        self.__current_record = None
        self.current_record = None
        self.screen_container = ScreenContainer(tab_domain)
        self.screen_container.alternate_view = alternate_view
        self.widget = self.screen_container.widget_get()
        self.__current_view = 0
        self.search_value = search_value
        self.fields_view_tree = None
        self.order = order
        self.view_to_load = []
        self.tree_states = collections.defaultdict(
            lambda: collections.defaultdict(lambda: None))
        self.tree_states_done = set()
        self.domain_parser = None
        self.pre_validate = False
        self.view_to_load = mode[:]
        if view_ids or mode:
            self.switch_view()

    def __repr__(self):
        return '<Screen %s at %s>' % (self.model_name, id(self))

    def search_active(self, active=True):
        if active and not self.parent:
            if not self.fields_view_tree:
                try:
                    self.fields_view_tree = RPCExecute('model',
                        self.model_name, 'fields_view_get', False, 'tree',
                        context=self.context)
                except RPCException:
                    return

            if not self.domain_parser:
                fields = copy.deepcopy(self.fields_view_tree['fields'])
                for name, props in fields.iteritems():
                    if props['type'] not in ('selection', 'reference'):
                        continue
                    if isinstance(props['selection'], (tuple, list)):
                        continue
                    props['selection'] = self.get_selection(props)

                # Filter only fields in XML view
                xml_dom = xml.dom.minidom.parseString(
                    self.fields_view_tree['arch'])
                root_node, = xml_dom.childNodes
                xml_fields = [node_attributes(node).get('name')
                    for node in root_node.childNodes
                    if node.nodeName == 'field']
                if hasattr(collections, 'OrderedDict'):
                    odict = collections.OrderedDict
                else:
                    odict = dict
                fields = odict((name, fields[name]) for name in xml_fields)
                for name, string, type_ in (
                        ('id', _('ID'), 'integer'),
                        ('create_uid', _('Creation User'), 'many2one'),
                        ('create_date', _('Creation Date'), 'datetime'),
                        ('write_uid', _('Modification User'), 'many2one'),
                        ('write_date', _('Modification Date'), 'datetime'),
                        ):
                    if name not in fields:
                        fields[name] = {
                            'string': string.decode('utf-8'),
                            'name': name,
                            'type': type_,
                            }
                        if type_ == 'datetime':
                            fields[name]['format'] = '"%H:%M:%S"'

                self.domain_parser = DomainParser(fields)

            self.screen_container.set_screen(self)
            self.screen_container.show_filter()
        else:
            self.screen_container.hide_filter()

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
        selection.sort(lambda x, y: cmp(x[1], y[1]))
        return selection

    def search_prev(self, search_string):
        self.offset -= self.limit
        self.search_filter(search_string=search_string)

    def search_next(self, search_string):
        self.offset += self.limit
        self.search_filter(search_string=search_string)

    def search_complete(self, search_string):
        return list(self.domain_parser.completion(search_string))

    def search_filter(self, search_string=None, only_ids=False):
        domain = []

        if self.domain_parser and not self.parent:
            if search_string is not None:
                domain = self.domain_parser.parse(search_string)
            else:
                domain = self.search_value
            self.screen_container.set_text(self.domain_parser.string(domain))
        else:
            domain = [('id', 'in', [x.id for x in self.group])]

        if domain:
            if self.domain:
                domain = ['AND', domain, self.domain]
        else:
            domain = self.domain

        if self.current_view.view_type == 'calendar':
            if domain:
                domain = ['AND', domain, self.current_view.current_domain()]
            else:
                domain = self.current_view.current_domain()

        tab_domain = self.screen_container.get_tab_domain()
        if tab_domain:
            domain = ['AND', domain, tab_domain]

        try:
            ids = RPCExecute('model', self.model_name, 'search', domain,
                self.offset, self.limit, self.order, context=self.context)
        except RPCException:
            ids = []
        if not only_ids:
            if len(ids) == self.limit:
                try:
                    self.search_count = RPCExecute('model', self.model_name,
                        'search_count', domain, context=self.context)
                except RPCException:
                    self.search_count = 0
            else:
                self.search_count = len(ids)
        self.screen_container.but_prev.set_sensitive(bool(self.offset))
        if (len(ids) == self.limit
                and self.search_count > self.limit + self.offset):
            self.screen_container.but_next.set_sensitive(True)
        else:
            self.screen_container.but_next.set_sensitive(False)
        if only_ids:
            return ids
        self.clear()
        self.load(ids)
        return bool(ids)

    def __get_group(self):
        return self.__group

    def __set_group(self, group):
        fields = {}
        if self.group is not None:
            self.group.signal_unconnect(self)
            for name, field in self.group.fields.iteritems():
                fields[name] = field.attrs
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
        self.__group.exclude_field = self.exclude_field

    group = property(__get_group, __set_group)

    def new_group(self):
        self.group = Group(self.model_name, {}, domain=self.domain,
            context=self.context, readonly=self.readonly)

    def _group_cleared(self, group, signal):
        for view in self.views:
            if hasattr(view, 'reload'):
                view.reload = True

    def _group_list_changed(self, group, signal):
        for view in self.views:
            if hasattr(view, 'group_list_changed'):
                view.group_list_changed(group, signal)

    def _record_modified(self, group, signal, *args):
        self.signal('record-modified')

    def _group_changed(self, group, record):
        if not self.parent:
            self.display()

    def __get_current_record(self):
        if (self.__current_record is not None
                and self.__current_record.group is None):
            self.__current_record = None
        return self.__current_record

    def __set_current_record(self, record):
        self.__current_record = record
        try:
            pos = self.group.index(record) + self.offset + 1
        except ValueError:
            pos = []
            i = record
            while i:
                pos.append(i.group.index(i) + 1)
                i = i.parent
            pos.reverse()
            pos = tuple(pos)
        self.signal('record-message', (pos or 0, len(self.group) + self.offset,
            self.search_count, record and record.id))
        attachment_count = 0
        if record and record.attachment_count > 0:
            attachment_count = record.attachment_count
        self.signal('attachment-count', attachment_count)
        # update attachment-count after 1 second
        gobject.timeout_add(1000, self.update_attachment, record)
        return True

    current_record = property(__get_current_record, __set_current_record)

    def update_attachment(self, record):
        if record != self.current_record:
            return False
        if record and self.signal_connected('attachment-count'):
            attachment_count = record.get_attachment_count()
            self.signal('attachment-count', attachment_count)
        return False

    def destroy(self):
        self.group.destroy()
        for view in self.views:
            view.destroy()
        super(Screen, self).destroy()
        self.parent = None
        self.__group = None
        self.__current_record = None
        self.screen_container = None
        self.widget = None

    def default_row_activate(self):
        if (self.current_view.view_type == 'tree' and
                self.current_view.widget_tree.keyword_open):
            return Action.exec_keyword('tree_open', {
                'model': self.model_name,
                'id': self.id_get(),
                'ids': [self.id_get()],
                }, context=self.context.copy(), warning=False)
        else:
            self.switch_view(view_type='form')
            return True

    @property
    def number_of_views(self):
        return len(self.views) + len(self.view_to_load)

    def switch_view(self, view_type=None):
        if self.current_view:
            if not self.parent and self.modified():
                return
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
        if not view_type or self.current_view.view_type != view_type:
            for i in xrange(self.number_of_views):
                if len(self.view_to_load):
                    self.load_view_to_load()
                    self.__current_view = len(self.views) - 1
                else:
                    self.__current_view = ((self.__current_view + 1)
                            % len(self.views))
                if not view_type:
                    break
                elif self.current_view.view_type == view_type:
                    break
        self.screen_container.set(self.current_view.widget)
        self.current_view.cancel()
        self.display()
        self.set_cursor()

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
        for node in xml_dom.childNodes:
            if node.localName == 'tree':
                self.fields_view_tree = view
            break

        # Ensure that loading is always lazy for fields on form view
        # and always eager for fields on tree or graph view
        if node.localName == 'form':
            loading = 'lazy'
        else:
            loading = 'eager'
        for field in fields:
            if field not in self.group.fields or loading == 'eager':
                fields[field]['loading'] = loading
            else:
                fields[field]['loading'] = \
                    self.group.fields[field].attrs['loading']

        children_field = view.get('field_childs')

        from tryton.gui.window.view_form.view.widget_parse import WidgetParse
        self.group.add_fields(fields)

        parser = WidgetParse(parent=self.parent)
        view = parser.parse(self, xml_dom, self.group.fields,
                children_field=children_field)
        view.view_id = view_id

        self.views.append(view)
        return view

    def new(self, default=True):
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
        record = group.new(default)
        group.add(record, self.new_model_position())
        if previous_view.view_type == 'calendar':
            previous_view.set_default_date(record, selected_date)
        self.current_record = record
        self.display()
        self.set_cursor(new=True)
        return self.current_record

    def new_model_position(self):
        position = -1
        if (self.current_view and self.current_view.view_type == 'tree'
                and hasattr(self.current_view.widget_tree, 'editable')
                and self.current_view.widget_tree.editable == 'top'):
            position = 0
        return position

    def set_on_write(self, func_name):
        if func_name:
            self.group.on_write.add(func_name)

    def cancel_current(self):
        if self.current_record:
            self.current_record.cancel()
            if self.current_record.id < 0:
                self.remove()
        if self.current_view:
            self.current_view.cancel()

    def save_current(self):
        if not self.current_record:
            if self.current_view.view_type == 'tree' and len(self.group):
                self.current_record = self.group[0]
            else:
                return True
        self.current_view.set_value()
        obj_id = False
        fields = self.current_view.get_fields()
        path = self.current_record.get_path(self.group)
        if self.current_view.view_type == 'tree':
            self.group.save()
            obj_id = self.current_record.id
        elif self.current_record.validate(fields):
            obj_id = self.current_record.save(force_reload=True)
        else:
            self.set_cursor()
            self.current_view.display()
            return False
        self.signal('record-saved')
        if path and obj_id:
            path = path[:-1] + ((path[-1][0], obj_id),)
        self.current_record = self.group.get_by_path(path)
        self.display()
        return obj_id

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
            self.parent.reload()
        self.display()

    def unremove(self):
        records = self.current_view.selected_records()
        for record in records:
            self.group.unremove(record)

    def remove(self, delete=False, remove=False, force_remove=False):
        records = None
        if self.current_view.view_type == 'form' and self.current_record:
            records = [self.current_record]
        elif self.current_view.view_type == 'tree':
            records = self.current_view.selected_records()
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

    def set_tree_state(self):
        view = self.current_view
        if (not CONFIG['client.save_tree_state']
                or not view
                or view.view_type != 'tree'
                or not self.group):
            return
        if id(view) in self.tree_states_done:
            return
        parent = self.parent.id if self.parent else None
        state = self.tree_states[parent][view.children_field]
        if state is None:
            json_domain = self.get_tree_domain(parent)
            try:
                expanded_nodes, selected_nodes = RPCExecute('model',
                    'ir.ui.view_tree_state', 'get',
                    self.model_name, json_domain,
                    self.current_view.children_field)
                expanded_nodes = json.loads(expanded_nodes)
                selected_nodes = json.loads(selected_nodes)
            except RPCException:
                logging.getLogger(__name__).warn(
                    _('Unable to get view tree state'))
                expanded_nodes = []
                selected_nodes = []
            self.tree_states[parent][view.children_field] = (
                expanded_nodes, selected_nodes)
        else:
            expanded_nodes, selected_nodes = state
        view.expand_nodes(expanded_nodes)
        view.select_nodes(selected_nodes)
        self.tree_states_done.add(id(view))

    def save_tree_state(self, store=True):
        if not CONFIG['client.save_tree_state']:
            return
        for view in self.views:
            if view.view_type == 'form':
                for widgets in view.widgets.itervalues():
                    for widget in widgets:
                        if hasattr(widget, 'screen'):
                            widget.screen.save_tree_state(store)
            elif (view.view_type == 'tree' and view.children_field):
                parent = self.parent.id if self.parent else None
                paths = view.get_expanded_paths()
                selected_paths = view.get_selected_paths()
                self.tree_states[parent][view.children_field] = (
                    paths, selected_paths)
                if store:
                    json_domain = self.get_tree_domain(parent)
                    json_paths = json.dumps(paths)
                    json_selected_path = json.dumps(selected_paths)
                    try:
                        RPCExecute('model', 'ir.ui.view_tree_state', 'set',
                            self.model_name, json_domain, view.children_field,
                            json_paths, json_selected_path,
                            process_exception=False)
                    except (TrytonServerError, TrytonServerUnavailable):
                        logging.getLogger(__name__).warn(
                            _('Unable to set view tree state'))

    def get_tree_domain(self, parent):
        if parent:
            domain = (self.domain + [(self.exclude_field, '=', parent)])
        else:
            domain = self.domain
        json_domain = json.dumps(domain, cls=JSONEncoder)
        return json_domain

    def load(self, ids, set_cursor=True, modified=False):
        self.tree_states.clear()
        self.tree_states_done.clear()
        self.group.load(ids, modified=modified)
        self.current_view.reset()
        if ids:
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
            elif self.group:
                self.current_record = self.group[0]
            else:
                self.current_record = None
        if self.views:
            self.search_active(self.current_view.view_type
                in ('tree', 'graph', 'calendar'))
            for view in self.views:
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
            start, end = view.widget_tree.get_visible_range()
            vadjustment = view.widget_tree.get_vadjustment()
            vadjustment.value = vadjustment.value + vadjustment.page_increment
            vadjustment.value = min(
                vadjustment.value + vadjustment.page_increment,
                vadjustment.get_upper())
            store = view.store
            iter_ = store.get_iter(end)
            self.current_record = store.get_value(iter_, 0)
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
                if not parent:
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
            goocalendar = view.children['goocalendar']
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
                self.current_record = len(events) and events[0].record
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
            start, end = view.widget_tree.get_visible_range()
            vadjustment = view.widget_tree.get_vadjustment()
            vadjustment.value = min(
                vadjustment.value - vadjustment.page_increment,
                vadjustment.get_lower())
            store = view.store
            iter_ = store.get_iter(start)
            self.current_record = store.get_value(iter_, 0)
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
                if parent:
                    record = parent
            self.current_record = record
        elif view.view_type == 'calendar':
            record = self.current_record
            goocalendar = view.children['goocalendar']
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
                self.current_record = len(events) and events[0].record
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

    def sel_ids_get(self):
        return self.current_view.sel_ids_get()

    def id_get(self):
        if not self.current_record:
            return False
        return self.current_record.id

    def ids_get(self):
        return [x.id for x in self.group if x.id]

    def clear(self):
        self.current_record = None
        self.group.clear()

    def on_change(self, fieldname, attr):
        self.current_record.on_change(fieldname, attr)
        self.display()

    def button(self, button):
        'Execute button on the current record'
        if button.get('confirm', False) and not sur(button['confirm']):
            return
        record = self.current_record
        if not record.save(force_reload=False):
            return
        context = record.context_get()
        try:
            action_id = RPCExecute('model', self.model_name, button['name'],
                [record.id], context=context)
        except RPCException:
            action_id = None
        if action_id:
            Action.execute(action_id, {
                    'model': self.model_name,
                    'id': record.id,
                    'ids': [record.id],
                    }, context=context)
        self.reload([record.id], written=True)

    def get_url(self):
        query_string = []
        if self.domain:
            query_string.append(('domain', json.dumps(self.domain,
                        cls=JSONEncoder)))
        if self.context:
            query_string.append(('context', json.dumps(self.context,
                        cls=JSONEncoder)))
        path = [rpc._DATABASE, 'model', self.model_name]
        view_ids = [v.view_id for v in self.views] + self.view_ids
        if self.current_view.view_type != 'form':
            search_string = self.screen_container.get_text()
            search_value = self.domain_parser.parse(search_string)
            if search_value:
                query_string.append(('search_value', json.dumps(search_value,
                            cls=JSONEncoder)))
        elif self.current_record and self.current_record.id > -1:
            path.append(str(self.current_record.id))
            i = view_ids.index(self.current_view.view_id)
            view_ids = view_ids[i:] + view_ids[:i]
        if view_ids:
            query_string.append(('views', json.dumps(view_ids)))
        query_string = urllib.urlencode(query_string)
        return urlparse.urlunparse(('tryton',
                '%s:%s' % (rpc._HOST, rpc._PORT),
                '/'.join(path), query_string, '', ''))
