#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Screen"
import gobject
try:
    import simplejson as json
except ImportError:
    import json
import copy
import collections
import xml.dom.minidom
import tryton.rpc as rpc
from tryton.gui.window.view_form.model.group import Group
from tryton.gui.window.view_form.model.record import Record
from tryton.gui.window.view_form.view.screen_container import ScreenContainer
from tryton.signal_event import SignalEvent
from tryton.common import node_attributes
from tryton.config import CONFIG
import tryton.common as common
from tryton.exceptions import TrytonServerError, TrytonServerUnavailable
from tryton.jsonrpc import JSONEncoder
from tryton.common.tdp import DomainParser


class Screen(SignalEvent):
    "Screen"

    def __init__(self, model_name, view_ids=None, mode=None, context=None,
            views_preload=None, domain=None, row_activate=None, limit=None,
            readonly=False, exclude_field=None, sort=None, search_value=None,
            alternate_view=False):
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

        self.limit = limit or int(CONFIG['client.limit'])
        self.offset = 0
        super(Screen, self).__init__()

        self.readonly = readonly
        self.search_count = 0
        if not row_activate:
            self.row_activate = self.default_row_activate
        else:
            self.row_activate = row_activate
        self.domain = domain
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
        self.screen_container = ScreenContainer()
        self.screen_container.alternate_view = alternate_view
        self.widget = self.screen_container.widget_get()
        self.__current_view = 0
        self.search_value = search_value
        self.fields_view_tree = None
        self.sort = sort
        self.view_to_load = []
        self.expanded_nodes = collections.defaultdict(
            lambda: collections.defaultdict(lambda: None))
        self.domain_parser = None

        if mode:
            self.view_to_load = mode[1:]
            view_id = False
            if self.view_ids:
                view_id = self.view_ids.pop(0)
            view = self.add_view_id(view_id, mode[0])
            self.screen_container.set(view.widget)
        self.display()

    def __repr__(self):
        return '<Screen %s at %s>' % (self.model_name, id(self))

    def search_active(self, active=True):
        if active and not self.parent:
            if not self.fields_view_tree:
                ctx = {}
                ctx.update(rpc.CONTEXT)
                ctx.update(self.context)
                try:
                    self.fields_view_tree = rpc.execute('model',
                            self.model_name, 'fields_view_get', False,
                            'tree', ctx)
                except TrytonServerError:
                    return

            fields = self.fields_view_tree['fields']
            for name, props in fields.iteritems():
                if props['type'] not in ('selection', 'reference'):
                    continue
                if isinstance(props['selection'], (tuple, list)):
                    continue
                props['selection'] = self.get_selection(props)

            self.domain_parser = DomainParser(
                self.fields_view_tree['fields'])

            self.screen_container.set_screen(self)
            self.screen_container.show_filter()
        else:
            self.screen_container.hide_filter()

    def get_selection(self, props):
        try:
            selection = rpc.execute('model',
                    self.model_name, props['selection'], rpc.CONTEXT)
        except TrytonServerError, exception:
            common.process_exception(exception, None)
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
        parsed_tree = self.domain_parser.parse(search_string)
        res = list(r for r in parsed_tree.complete() \
                if r.strip() != search_string)
        return res

    def search_filter(self, search_string=None, only_ids=False):
        domain = []

        if self.domain_parser and not self.parent:
            if search_string is not None:
                domain = self.domain_parser.parse(search_string or '').domain()
            else:
                domain = self.search_value
            self.screen_container.set_text(self.domain_parser.string(domain))
        else:
            domain = [('id', 'in', [x.id for x in self.group])]

        ctx = {}
        ctx.update(rpc.CONTEXT)
        ctx.update(self.context)
        if domain:
            if self.domain:
                domain = ['AND', domain, self.domain]
        else:
            domain = self.domain
        rpc_args = ('model', self.model_name, 'search', domain, self.offset,
            self.limit, self.sort, ctx)
        try:
            ids = rpc.execute(*rpc_args)
        except TrytonServerError, exception:
            ids = (common.process_exception(exception, *rpc_args) or [])
        if not only_ids:
            if len(ids) == self.limit:
                rpc_args = ('model', self.model_name, 'search_count', domain,
                    ctx)
                try:
                    self.search_count = rpc.execute(*rpc_args)
                except TrytonServerError, exception:
                    self.search_count = (common.process_exception(exception,
                            *rpc_args) or 0)
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
        self.display()

    def __get_current_record(self):
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
        self.save_tree_state()
        for view in self.views:
            view.destroy()
        self.group.signal_unconnect(self)
        self.group.destroy()
        self.parent = None
        self.__group = None
        self.__current_record = None
        self.screen_container = None
        self.widget = None

    def default_row_activate(self):
        from tryton.action import Action

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

    def switch_view(self, view_type=None, default=True, context=None):
        if not self.parent and self.modified():
            return
        self.current_view.set_value()
        if (self.current_record and
                self.current_record not in self.current_record.group):
            self.current_record = None
        fields = self.current_view.get_fields()
        if self.current_record and not self.current_record.validate(fields):
            self.screen_container.set(self.current_view.widget)
            self.current_view.set_cursor()
            self.current_view.display()
            return
        if not view_type or self.current_view.view_type != view_type:
            for i in xrange(len(self.views) + len(self.view_to_load)):
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
        if not self.current_record and self.current_view.view_type == 'form':
            self.new(default=default, context=context)
        self.current_view.cancel()
        self.display(set_cursor=True)

    def load_view_to_load(self):
        if len(self.view_to_load):
            if self.view_ids:
                view_id = self.view_ids.pop(0)
                view_type = self.view_to_load.pop(0)
            else:
                view_id = False
                view_type = self.view_to_load.pop(0)
            self.add_view_id(view_id, view_type)

    def add_view_id(self, view_id, view_type, display=False, context=None):
        if view_type in self.views_preload:
            view = self.views_preload[view_type]
        else:
            ctx = {}
            ctx.update(rpc.CONTEXT)
            ctx.update(self.context)
            args = ('model', self.model_name, 'fields_view_get',
                    view_id, view_type, ctx)
            try:
                view = rpc.execute(*args)
            except TrytonServerError, exception:
                view = common.process_exception(exception, *args)
                if not view:
                    return
        return self.add_view(view, display, context=context)

    def add_view(self, view, display=False, context=None):
        arch = view['arch']
        fields = view['fields']

        xml_dom = xml.dom.minidom.parseString(arch)
        for node in xml_dom.childNodes:
            if node.localName == 'tree':
                self.fields_view_tree = view
            break

        # Ensure that loading is always eager for fields on tree view
        # and always lazy for fields only on form view
        if node.localName == 'tree':
            loading = 'eager'
        else:
            loading = 'lazy'
        for field in fields:
            if field not in self.group.fields:
                fields[field]['loading'] = loading
            else:
                fields[field]['loading'] = \
                    self.group.fields[field].attrs['loading']

        children_field = view.get('field_childs')

        from tryton.gui.window.view_form.view.widget_parse import WidgetParse
        self.group.add_fields(fields, context=context)

        parser = WidgetParse(parent=self.parent)
        view = parser.parse(self, xml_dom, self.group.fields,
                children_field=children_field)

        self.views.append(view)

        if display:
            self.__current_view = len(self.views) - 1
            self.screen_container.set(self.current_view.widget)
            fields = self.current_view.get_fields()
            if (not self.current_record
                and self.current_view.view_type == 'form'):
                self.new()
            self.current_view.set_cursor()
            self.current_view.cancel()
            self.display()
        return view

    def editable_get(self):
        if hasattr(self.current_view, 'widget_tree'):
            if hasattr(self.current_view.widget_tree, 'editable'):
                return self.current_view.widget_tree.editable
        return False

    def new(self, default=True, context=None):
        if self.group.readonly:
            return
        if context is None:
            context = {}
        if self.current_view and \
                ((self.current_view.view_type == 'tree' \
                and not (hasattr(self.current_view.widget_tree, 'editable') \
                    and self.current_view.widget_tree.editable)) \
                or self.current_view.view_type == 'graph'):
            prev_current_record = self.current_record
            for i in xrange(len(self.views)):
                self.switch_view()
                if self.current_view.view_type == 'form':
                    break
            if self.current_view.view_type != 'form':
                return None
            if not prev_current_record and self.current_record:
                # new already called in switch_view
                return self.current_record
        ctx = {}
        ctx.update(rpc.CONTEXT)
        ctx.update(self.context)
        ctx.update(context)
        if self.current_record:
            group = self.current_record.group
        else:
            group = self.group
        record = group.new(default, self.domain, ctx)
        group.add(record, self.new_model_position())
        self.current_record = record
        fields = None
        if self.current_view:
            fields = self.current_view.get_fields()
        self.display()
        if self.current_view:
            self.current_view.set_cursor(new=True)
        self.request_set()
        return self.current_record

    def new_model_position(self):
        position = -1
        if self.current_view and self.current_view.view_type == 'tree' \
                and hasattr(self.current_view.widget_tree, 'editable') \
                    and self.current_view.widget_tree.editable == 'top':
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
            self.current_view.set_cursor()
            self.current_view.display()
            return False
        self.signal('record-saved')
        if path and obj_id:
            path = path[:-1] + ((path[-1][0], obj_id),)
        self.current_record = self.group.get_by_path(path)
        self.display()
        self.request_set()
        return obj_id

    def __get_current_view(self):
        if not len(self.views):
            return None
        return self.views[self.__current_view]

    current_view = property(__get_current_view)

    def get(self, get_readonly=True, includeid=False, check_load=True,
            get_modifiedonly=False):
        if not self.current_record:
            return None
        self.current_view.set_value()
        return self.current_record.get(get_readonly=get_readonly,
                includeid=includeid, check_load=check_load,
                get_modifiedonly=get_modifiedonly)

    def modified(self):
        res = False
        if self.current_view.view_type != 'tree':
            if self.current_record:
                res = self.current_record.modified or self.current_record.id < 0
        else:
            for record in self.group:
                if record.modified or record.id < 0:
                    res = True
        return res

    def reload(self, written=False):
        ids = self.sel_ids_get()
        self.group.reload(ids)
        if written:
            self.group.written(ids)
        if self.parent:
            self.parent.reload()
        self.display()
        self.request_set()

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
        idx = top_record.group.index(top_record)
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
                if record.parent:
                    record.parent.save()

        if idx > 0:
            record = top_record.group[idx - 1]
            path = path[:-1] + ((path[-1][0], record.id,),)
        else:
            path = path[:-1]
        if path:
            self.current_record = self.group.get_by_path(path)
        elif len(self.group):
            self.current_record = self.group[0]
        self.current_view.set_cursor()
        self.display()
        self.request_set()
        return True

    def set_tree_state(self):
        view = self.current_view
        if (not CONFIG['client.save_tree_expanded_state']
                or not self.current_view
                or self.current_view.view_type != 'tree'
                or not self.current_view.children_field
                or not self.group):
            return
        parent = self.parent.id if self.parent else None
        expanded_nodes = self.expanded_nodes[parent][view.children_field]
        if expanded_nodes is None:
            json_domain = self.get_tree_domain(parent)
            try:
                expanded_nodes = rpc.execute('model',
                    'ir.ui.view_tree_expanded_state', 'get_expanded',
                    self.model_name, json_domain,
                    self.current_view.children_field, rpc.CONTEXT)
                expanded_nodes = json.loads(expanded_nodes)
            except TrytonServerError:
                expanded_nodes = []
            self.expanded_nodes[parent][view.children_field] = expanded_nodes
        view.expand_nodes(expanded_nodes)

    def save_tree_state(self):
        view = self.current_view
        if (not CONFIG['client.save_tree_expanded_state']
                or not view
                or view.view_type != 'tree'
                or not view.children_field
                or not (self.parent is None
                    or isinstance(self.parent, Record))):
            return
        parent = self.parent.id if self.parent else None
        paths = view.get_expanded_paths()
        self.expanded_nodes[parent][view.children_field] = paths
        json_domain = self.get_tree_domain(parent)
        json_paths = json.dumps(paths)
        try:
            rpc.execute('model', 'ir.ui.view_tree_expanded_state',
                'set_expanded', self.model_name, json_domain,
                self.current_view.children_field, json_paths, rpc.CONTEXT)
        except (TrytonServerError, TrytonServerUnavailable):
            pass

    def get_tree_domain(self, parent):
        if parent:
            domain = (self.domain + [(self.exclude_field, '=', parent)])
        else:
            domain = self.domain
        json_domain = json.dumps(domain, cls=JSONEncoder)
        return json_domain

    def load(self, ids, set_cursor=True, modified=False):
        self.expanded_nodes.clear()
        self.group.load(ids, display=False, modified=modified)
        self.current_view.reset()
        if ids:
            self.display(ids[0])
        else:
            self.current_record = None
            self.display()
        if set_cursor:
            self.current_view.set_cursor()
        self.request_set()

    def display(self, res_id=None, set_cursor=False):
        if res_id:
            self.current_record = self.group.get(res_id)
        if self.views:
            #XXX To remove when calendar will be implemented
            if self.current_view.view_type == 'calendar' and \
                    len(self.views) > 1:
                self.switch_view()
            for view in self.views:
                view.display()
            self.current_view.widget.set_sensitive(
                    bool(self.group \
                            or (self.current_view.view_type != 'form') \
                            or self.current_record))
            self.search_active(self.current_view.view_type \
                    in ('tree', 'graph', 'calendar'))
            if set_cursor:
                self.current_view.set_cursor(reset_view=False)
        self.set_tree_state()

    def display_next(self):
        view = self.current_view
        view.set_value()
        view.set_cursor(reset_view=False)
        if view.view_type == 'tree' and len(self.group):
            start, end = view.widget_tree.get_visible_range()
            vadjustment = view.widget_tree.get_vadjustment()
            vadjustment.value = vadjustment.value + vadjustment.page_increment
            store = view.store
            iter_ = store.get_iter(end)
            self.current_record = store.get_value(iter_, 0)
        elif view.view_type == 'form' and self.current_record.group:
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
        else:
            self.current_record = self.group[0] if len(self.group) else None
        view.set_cursor(reset_view=False)
        view.display()

    def display_prev(self):
        view = self.current_view
        view.set_value()
        view.set_cursor(reset_view=False)
        if view.view_type == 'tree' and len(self.group):
            start, end = view.widget_tree.get_visible_range()
            vadjustment = view.widget_tree.get_vadjustment()
            vadjustment.value = vadjustment.value - vadjustment.page_increment
            store = view.store
            iter_ = store.get_iter(start)
            self.current_record = store.get_value(iter_, 0)
        elif view.view_type == 'form' and self.current_record.group:
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
        else:
            self.current_record = self.group[-1] if len(self.group) else None
        view.set_cursor(reset_view=False)
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

    def request_set(self):
        if self.model_name == 'res.request':
            from tryton.gui.main import Main
            Main.get_main().request_set()
