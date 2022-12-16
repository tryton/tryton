#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Screen"
import tryton.rpc as rpc
from tryton.gui.window.view_form.model.group import Group
from tryton.gui.window.view_form.view.screen_container import ScreenContainer
from tryton.gui.window.view_form.widget_search import Form
from tryton.signal_event import SignalEvent
from tryton.common import node_attributes
from tryton.config import CONFIG
import tryton.common as common
import gobject
import copy
import xml.dom.minidom


class Screen(SignalEvent):
    "Screen"

    def __init__(self, model_name, window, view_ids=None, view_type=None,
            context=None, views_preload=None, domain=None, row_activate=None,
            limit=None, readonly=False, exclude_field=None, sort=None,
            search_value=None):
        if view_ids is None:
            view_ids = []
        if view_type is None:
            view_type = ['tree', 'form']
        if context is None:
            context = {}
        if views_preload is None:
            views_preload = {}
        if domain is None:
            domain = []

        super(Screen, self).__init__()

        self.search_count = 0
        if not row_activate:
            # TODO change for a function that switch to form view
            self.row_activate = self.switch_view
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
        self.__window = window
        self.__group = None
        self.group = Group(model_name, {}, self.window, context=self.context,
                readonly=readonly)
        self.__current_record = None
        self.current_record = None
        self.screen_container = ScreenContainer()
        self.filter_widget = None
        self.widget = self.screen_container.widget_get()
        self.__current_view = 0
        self.limit = limit
        self.search_value = search_value
        self.fields_view_tree = None
        self.exclude_field = exclude_field
        self.sort = sort
        self.view_to_load = []

        if view_type:
            self.view_to_load = view_type[1:]
            view_id = False
            if view_ids:
                view_id = view_ids.pop(0)
            view = self.add_view_id(view_id, view_type[0])
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
                    except:
                        return
                self.filter_widget = Form(self.fields_view_tree['arch'],
                        self.fields_view_tree['fields'], self.model_name,
                        self.window, self.domain, (self, self.search_filter),
                        self.context)
                self.screen_container.add_filter(self.filter_widget.widget,
                        self.search_filter, self.search_clear)
                self.filter_widget.set_limit(self.limit)
                self.filter_widget.value = self.search_value
            self.screen_container.show_filter()
        else:
            self.screen_container.hide_filter()

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
        except:
            ids = []
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
        self.__group.signal_connect(self, 'record-modified', self._record_modified)
        self.__group.signal_connect(self, 'group-changed', self._group_changed)
        self.__group.add_fields(fields)

    group = property(__get_group, __set_group)

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
        except:
            offset = 0
        try:
            pos = self.group.index(record)
        except:
            pos = -1
        self.signal('record-message', (pos + offset, len(self.group) + offset,
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
            del view
        self.group.signal_unconnect(self)
        del self.views

    def switch_view(self, view_type=None, default=True, context=None):
        self.current_view.set_value()
        if self.current_record and self.current_record not in self.group:
            self.current_record = None
        if self.current_record and not self.current_record.validate():
            self.screen_container.set(self.current_view.widget)
            self.current_view.set_cursor()
            self.current_view.display()
            return
        for i in xrange(len(self.views) + len(self.view_to_load)):
            if len(self.view_to_load):
                self.load_view_to_load()
                self.__current_view = len(self.views) - 1
            else:
                self.__current_view = (self.__current_view + 1) % len(self.views)
            if not view_type:
                break
            elif self.current_view.view_type == view_type:
                break
        self.screen_container.set(self.current_view.widget)
        if self.current_record:
            self.current_record.validate_set()
        else:
            if self.current_view.view_type == 'form':
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
            return self.add_view(self.views_preload[view_type]['arch'],
                    self.views_preload[view_type]['fields'], display,
                    toolbar=self.views_preload[view_type].get('toolbar', False),
                    context=context)
        else:
            ctx = {}
            ctx.update(rpc.CONTEXT)
            ctx.update(self.context)
            args = ('model', self.model_name, 'fields_view_get',
                    view_id, view_type, ctx,
                    self.parent and False or CONFIG['form.toolbar'])
            try:
                view = rpc.execute(*args)
            except Exception, exception:
                view = common.process_exception(exception, self.window, *args)
                if not view:
                    return
            return self.add_view(view['arch'], view['fields'], display,
                    toolbar=view.get('toolbar', False), context=context)

    def add_view(self, arch, fields, display=False, toolbar=None, context=None):
        if toolbar is None:
            toolbar = {}
        xml_dom = xml.dom.minidom.parseString(arch)

        for dom in common.filter_domain(self.domain):
            if '.' in dom[0]:
                field1, field2 = dom[0].split('.', 1)
            else:
                field1, field2 = dom[0], 'id'
            if field1 in fields:
                field_dom = fields[field1].setdefault('domain', [])
                if dom[1] in ('child_of', 'not child_of') \
                        and field2 == 'id':
                    dom = copy.copy(dom)
                    if len(dom) == 4:
                        field2 = dom[3]
                        dom = (dom[0], dom[1], dom[2])
                    else:
                        field2 = field1
                if isinstance(field_dom, basestring):
                    fields[field1]['domain'] = '[' \
                            + str(tuple([field2] + list(dom[1:]))) \
                            + ',' + field_dom + ']'
                else:
                    fields[field1]['domain'] = [
                            tuple([field2] + list(dom[1:])),
                            field_dom]
                if dom[1] == '!=' and dom[2] == False:
                    fields[field1]['required'] = True

        for node in xml_dom.childNodes:
            if node.localName == 'tree':
                self.fields_view_tree = {'arch': arch, 'fields': fields}

        from tryton.gui.window.view_form.view.widget_parse import WidgetParse
        if self.current_record and (self.current_record not in self.group):
            self.group.append(self.current_record)
        self.group.add_fields(fields, context=context)

        if self.exclude_field:
            if self.exclude_field in self.group.fields:
                field = self.group.fields[self.exclude_field]
                field.attrs['states'] = {'invisible': True}
                field.attrs['readonly'] = True
                field.attrs['invisible'] = True
                field.attrs['tree_invisible'] = True
                field.attrs['exclude_field'] = True

        parser = WidgetParse(parent=self.parent, window=self.window)
        view = parser.parse(self, xml_dom, self.group.fields, toolbar=toolbar)

        self.views.append(view)

        if display:
            self.__current_view = len(self.views) - 1
            self.screen_container.set(self.current_view.widget)
            if self.current_record:
                self.current_record.validate_set()
            else:
                if self.current_view.view_type == 'form':
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
        record = self.group.new(default, self.domain, ctx)
        self.group.add(record, self.new_model_position())
        self.current_record = record
        self.current_record.validate_set()
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
            return False
        self.current_view.set_value()
        obj_id = False
        if self.current_record.validate():
            obj_id = self.current_record.save(force_reload=True)
        else:
            self.current_view.set_cursor()
            self.current_view.display()
            return False
        if self.current_view.view_type == 'tree':
            for record in self.group:
                if record.is_modified():
                    if record.validate():
                        obj_id = record.save(force_reload=True)
                    else:
                        self.current_view.set_cursor()
                        self.current_record = record
                        self.current_view.set_cursor()
                        self.display()
                        return False
            self.current_view.set_cursor()
        self.display()
        if self.current_record not in self.group:
            self.group.add(self.current_record, modified=False)
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

    def is_modified(self):
        self.current_view.set_value()
        res = False
        if self.current_view.view_type != 'tree':
            res = self.current_record and self.current_record.is_modified()
        else:
            for record in self.group:
                if record.is_modified():
                    res = True
        return res

    def reload(self, writen=False):
        ids = self.sel_ids_get()
        self.group.reload(ids)
        if writen:
            self.group.writen(ids)
        if self.parent:
            self.parent.reload()
        self.display()
        self.request_set()

    def remove(self, delete=False, remove=False):
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
            if self.current_record in self.group:
                idx = self.group.index(self.current_record)
                self.group.remove(self.current_record, remove=remove)
                if self.group:
                    idx = min(idx, len(self.group) - 1)
                    self.current_record = self.group[idx]
                else:
                    self.current_record = None
            if reload_ids:
                self.group.reload(reload_ids)
            self.display()
            res = True
        if self.current_view.view_type == 'tree':
            ids = self.current_view.sel_ids_get()
            if delete and ids:
                context = {}
                context.update(rpc.CONTEXT)
                context.update(self.context)
                context['_timestamp'] = {}
                for record_id in ids:
                    record = self.group.get(record_id)
                    context['_timestamp'].update(record.get_timestamp())
                reload_ids = self.group.on_write_ids(ids)
                if reload_ids:
                    for record_id in ids:
                        if record_id in reload_ids:
                            reload_ids.remove(record_id)
                args = ('model', self.model_name, 'delete', ids,
                        context)
                try:
                    res = rpc.execute(*args)
                except Exception, exception:
                    res = common.process_exception(exception, self.window,
                            *args)
                if not res:
                    return False
            sel_records = self.current_view.selected_records()
            if not sel_records:
                return True
            idx = self.group.index(sel_records[0])
            for record in sel_records:
                # set current model to None to prevent __select_changed
                # to save the previous_model as it can be already deleted.
                self.current_record = None
                self.group.remove(record, remove=remove, signal=False)
            # send record-changed only once
            record.signal('record-changed')
            if self.group:
                idx = min(idx, len(self.group) - 1)
                self.current_record = self.group[idx]
            else:
                self.current_record = None
            if reload_ids:
                self.group.reload(reload_ids)
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
            self.current_view.display()
            self.current_view.widget.set_sensitive(
                    bool(self.group \
                            or (self.current_view.view_type != 'form') \
                            or self.current_record))
            self.search_active(self.current_view.view_type \
                    in ('tree', 'graph', 'calendar'))
            if set_cursor:
                self.current_view.set_cursor(reset_view=False)

    def display_next(self):
        self.current_view.set_value()
        self.current_view.set_cursor(reset_view=False)
        if self.current_record in self.group:
            idx = self.group.index(self.current_record)
            inc = 1
            if self.current_view.view_type == 'tree':
                start, end = self.current_view.widget_tree.get_visible_range()
                inc += end[0] - start[0]
                if inc >= 4 and (end[0] + 1) < len(self.group):
                    inc -= 3
                vadjustment = self.current_view.widget_tree.get_vadjustment()
                vadjustment.value = vadjustment.value + vadjustment.page_increment
            idx = idx + inc
            if idx >= len(self.group):
                idx = len(self.group) - 1
            self.current_record = self.group[idx]
        else:
            self.current_record = self.group[0] if len(self.group) else None
        self.current_view.set_cursor(reset_view=False)
        if self.current_record:
            self.current_record.validate_set()
        self.display()

    def display_prev(self):
        self.current_view.set_value()
        self.current_view.set_cursor(reset_view=False)
        if self.current_record in self.group:
            inc = 1
            if self.current_view.view_type == 'tree':
                range = self.current_view.widget_tree.get_visible_range()
                if range:
                    start, end = range
                    inc += end[0] - start[0]
                    if inc >= 4 and start[0] > 0:
                        inc -= 3
                    vadjustment = \
                            self.current_view.widget_tree.get_vadjustment()
                    if vadjustment.value:
                        vadjustment.value = vadjustment.value - \
                                vadjustment.page_increment
            idx = self.group.index(self.current_record) - inc
            if idx < 0:
                idx = 0
            self.current_record = self.group[idx]
        else:
            self.current_record = self.group[-1] if len(self.group) else None
        self.current_view.set_cursor(reset_view=False)
        if self.current_record:
            self.current_record.validate_set()
        self.display()

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
