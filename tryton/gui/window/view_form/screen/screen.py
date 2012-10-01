#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Screen"
import gobject
import copy
import xml.dom.minidom
import tryton.rpc as rpc
from tryton.gui.window.view_form.model.group import Group
from tryton.gui.window.view_form.view.screen_container import ScreenContainer
from tryton.gui.window.view_form.widget_search import Form
from tryton.signal_event import SignalEvent
from tryton.common import node_attributes
from tryton.config import CONFIG
import tryton.common as common


class Screen(SignalEvent):
    "Screen"

    def __init__(self, model_name, window, view_ids=None, mode=None,
            context=None, views_preload=None, domain=None, row_activate=None,
            limit=None, readonly=False, exclude_field=None, sort=None,
            search_value=None, alternate_view=False):
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
        self.view_ids = view_ids
        self.parent = None
        self.parent_name = None
        self.exclude_field = exclude_field
        self.__window = window
        self.__group = None
        self.new_group()
        self.__current_record = None
        self.current_record = None
        self.screen_container = ScreenContainer()
        self.screen_container.alternate_view = alternate_view
        self.filter_widget = None
        self.widget = self.screen_container.widget_get()
        self.__current_view = 0
        self.limit = limit
        self.search_value = search_value
        self.fields_view_tree = None
        self.sort = sort
        self.view_to_load = []

        if mode:
            self.view_to_load = mode[1:]
            view_id = False
            if view_ids:
                view_id = view_ids.pop(0)
            view = self.add_view_id(view_id, mode[0])
            self.screen_container.set(view.widget)
        self.display()

    def __repr__(self):
        return '<Screen %s at %s>' % (self.model_name, id(self))

    def search_active(self, active=True):
        if active and not self.parent:
            if not self.filter_widget:
                if not self.fields_view_tree:
                    ctx = {}
                    ctx.update(rpc.CONTEXT)
                    ctx.update(self.context)
                    try:
                        self.fields_view_tree = rpc.execute('model',
                                self.model_name, 'fields_view_get', False,
                                'tree', ctx)
                    except Exception:
                        return
                self.filter_widget = Form(self.fields_view_tree,
                        self.model_name, self.window, self.domain,
                        (self, self.search_filter), self.context)
                self.screen_container.add_filter(self.filter_widget.widget,
                        self.search_filter, self.search_clear,
                        self.search_prev, self.search_next)
                self.filter_widget.set_limit(self.limit)
                self.filter_widget.value = self.search_value
            self.screen_container.show_filter()
        else:
            self.screen_container.hide_filter()

    def search_prev(self, widget=None):
        self.filter_widget.prev()
        self.search_filter()

    def search_next(self, widget=None):
        self.filter_widget.next()
        self.search_filter()

    def search_clear(self, widget=None):
        self.filter_widget.clear()
        self.clear()

    def search_filter(self, widget=None, only_ids=False):
        limit = None
        offset = 0
        values = []
        if self.filter_widget:
            limit = self.filter_widget.get_limit()
            offset = self.filter_widget.get_offset()
            values = self.filter_widget.value
        else:
            values = [('id', 'in', [x.id for x in self.group])]
        ctx = {}
        ctx.update(rpc.CONTEXT)
        ctx.update(self.context)
        if values:
            if self.domain:
                values = ['AND', values, self.domain]
        else:
            values = self.domain
        try:
            try:
                ids = rpc.execute('model', self.model_name, 'search', values,
                        offset, limit, self.sort, ctx)
            except Exception, exception:
                common.process_exception(exception, self.window)
                ids = rpc.execute('model', self.model_name, 'search', values,
                        offset, limit, self.sort, ctx)
            if not only_ids:
                if len(ids) == limit:
                    try:
                        self.search_count = rpc.execute('model',
                                self.model_name, 'search_count', values, ctx)
                    except Exception, exception:
                        common.process_exception(exception, self.window)
                        self.search_count = rpc.execute('model',
                                self.model_name, 'search_count', values, ctx)
                else:
                    self.search_count = len(ids)
        except Exception:
            ids = []
        self.screen_container.but_prev.set_sensitive(bool(offset))
        if (len(ids) == limit
                and self.search_count > limit + offset):
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
        self.group = Group(self.model_name, {}, self.window, domain=self.domain,
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
            offset = int(self.filter_widget.get_offset())
        except Exception:
            offset = 0
        try:
            pos = self.group.index(record) + offset + 1
        except ValueError:
            pos = []
            i = record
            while i:
                pos.append(i.group.index(i) + 1)
                i = i.parent
            pos.reverse()
            pos = tuple(pos)
        self.signal('record-message', (pos or 0, len(self.group) + offset,
            self.search_count, record and record.id))
        attachment_count = 0
        if record and record.attachment_count > 0:
            attachment_count = record.attachment_count
        self.signal('attachment-count', attachment_count)
        # update attachment-count after 1 second
        gobject.timeout_add(1000, self.update_attachment, record)
        return True

    current_record = property(__get_current_record, __set_current_record)

    def __get_window(self):
        return self.__window

    def __set_window(self, window):
        self.group.window = window
        self.__window = window

    window = property(__get_window, __set_window)

    def update_attachment(self, record):
        if record != self.current_record:
            return False
        if record and self.signal_connected('attachment-count'):
            attachment_count = record.get_attachment_count()
            self.signal('attachment-count', attachment_count)
        return False

    def destroy(self):
        for view in self.views:
            view.destroy()
        self.group.signal_unconnect(self)
        self.group.destroy()
        self.parent = None
        self.__window = None
        self.__group = None
        self.__current_record = None
        self.screen_container = None
        self.widget = None

    def default_row_activate(self):
        from tryton.action import Action
        if (self.current_view.view_type == 'tree' and
                self.current_view.widget_tree.keyword_open):
            return Action.exec_keyword('tree_open', self.window, {
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
                    view_id, view_type,
                    self.parent and False or CONFIG['form.toolbar'],
                    ctx)
            try:
                view = rpc.execute(*args)
            except Exception, exception:
                view = common.process_exception(exception, self.window, *args)
                if not view:
                    return
        return self.add_view(view, display, toolbar=view.get('toolbar', False),
                context=context)

    def add_view(self, view, display=False, toolbar=None, context=None):
        if toolbar is None:
            toolbar = {}
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

        parser = WidgetParse(parent=self.parent, window=self.window)
        view = parser.parse(self, xml_dom, self.group.fields, toolbar=toolbar,
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
        self.current_view.set_value()
        res = False
        if self.current_view.view_type != 'tree':
            res = self.current_record and self.current_record.modified
        else:
            for record in self.group:
                if record.modified:
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
        res = False
        reload_ids = []
        if self.current_view.view_type == 'form' and self.current_record:
            record_id = self.current_record.id
            if delete and record_id > 0:
                context = {}
                context.update(rpc.CONTEXT)
                context.update(self.context)
                context['_timestamp'] = self.current_record.get_timestamp()
                reload_ids = self.group.on_write_ids([record_id])
                if reload_ids and record_id in reload_ids:
                    reload_ids.remove(record_id)
                args = ('model', self.model_name, 'delete', [record_id],
                        context)
                try:
                    res = rpc.execute(*args)
                except Exception, exception:
                    res = common.process_exception(exception, self.window,
                            *args)
                if not res:
                    return False
            self.current_view.set_cursor()
            record = self.current_record
            idx = record.group.index(record)
            record.group.remove(record, remove=remove,
                force_remove=force_remove)

            if delete:
                if (record.parent and
                        record.parent.model_name == record.model_name):
                    record.parent.save()

            if record.group:
                idx = min(idx, len(record.group) - 1)
                self.current_record = record.group[idx]
            elif (record.parent and
                    record.parent.model_name == record.model_name):
                self.current_record = record.parent
            else:
                self.current_record = None
            if reload_ids:
                self.group.root_group.reload(reload_ids)
            self.display()
            res = True
        if self.current_view.view_type == 'tree':
            records = self.current_view.selected_records()
            saved_records = [r for r in records if r.id >= 0]
            if delete and saved_records:
                context = {}
                context.update(rpc.CONTEXT)
                context.update(self.context)
                context['_timestamp'] = {}
                for record in saved_records:
                    context['_timestamp'].update(record.get_timestamp())
                reload_ids = self.group.on_write_ids([x.id for x in saved_records])
                if reload_ids:
                    for record in saved_records:
                        if record.id in reload_ids:
                            reload_ids.remove(record.id)
                args = ('model', self.model_name, 'delete',
                        [x.id for x in saved_records], context)
                try:
                    res = rpc.execute(*args)
                except Exception, exception:
                    res = common.process_exception(exception, self.window,
                            *args)
                if not res:
                    return False
            if not records:
                return True
            path = self.current_view.store.on_get_path(records[0])
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

            if path[-1] > 0:
                path = path[:-1] + (path[-1] - 1,)
            else:
                path = path[:-1]
            if path:
                iter_ = self.current_view.store.get_iter(path)
                self.current_record = self.current_view.store.get_value(iter_, 0)
            elif len(self.group):
                self.current_record = self.group[0]
            if reload_ids:
                self.group.root_group.reload(reload_ids)
            self.current_view.set_cursor()
            self.display()
            res = True
        self.request_set()
        return res

    def load(self, ids, set_cursor=True, modified=False):
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
