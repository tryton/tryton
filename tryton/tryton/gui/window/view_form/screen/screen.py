#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Screen"
import xml.dom.minidom
from tryton.rpc import RPCProxy
import tryton.rpc as rpc
from tryton.gui.window.view_form.model.group import ModelRecordGroup
from tryton.gui.window.view_form.view.screen_container import ScreenContainer
from tryton.gui.window.view_form.widget_search import Form
from tryton.signal_event import SignalEvent
from tryton.common import node_attributes
import gobject
import tryton.common as common
import copy


class Screen(SignalEvent):
    "Screen"

    def __init__(self, model_name, window, view_ids=None, view_type=None,
            parent=None, parent_name='', context=None, views_preload=None,
            tree_saves=True, domain=None, create_new=False, row_activate=None,
            hastoolbar=False, default_get=None, show_search=False, limit=None,
            readonly=False, form=None, exclude_field=None, sort=None,
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
        if default_get is None:
            default_get = {}

        super(Screen, self).__init__()

        self.__current_model = None
        self.show_search = show_search
        self.search_count = 0
        self.hastoolbar = hastoolbar
        self.default_get = default_get
        if not row_activate:
            # TODO change for a function that switch to form view
            self.row_activate = self.switch_view
        else:
            self.row_activate = row_activate
        self.create_new = create_new
        self.name = model_name
        self.domain = domain
        self.views_preload = views_preload
        self.resource = model_name
        self.rpc = RPCProxy(model_name)
        self.context = context
        self.views = []
        self.fields = {}
        self.view_ids = view_ids
        self.models = None
        self.parent = parent
        self.parent_name = parent_name
        self.window = window
        models = ModelRecordGroup(model_name, self.fields, self.window,
                parent=self.parent, parent_name=parent_name, context=self.context,
                readonly=readonly)
        self.models_set(models)
        self.current_model = None
        self.screen_container = ScreenContainer()
        self.filter_widget = None
        self.widget = self.screen_container.widget_get()
        self.__current_view = 0
        self.tree_saves = tree_saves
        self.limit = limit
        self.search_value = search_value
        self.form = form
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

    def search_active(self, active=True):
        if active and self.show_search:
            if not self.filter_widget:
                if not self.fields_view_tree:
                    ctx = {}
                    ctx.update(rpc.CONTEXT)
                    ctx.update(self.context)
                    try:
                        self.fields_view_tree = rpc.execute('model',
                                self.name, 'fields_view_get', False,
                                'tree', ctx)
                    except:
                        return
                self.filter_widget = Form(self.fields_view_tree['arch'],
                        self.fields_view_tree['fields'], self.name, self.window,
                        self.domain, (self, self.search_filter), self.context)
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
            values = [('id', 'in', [x.id for x in self.models])]
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
                ids = rpc.execute('model', self.name, 'search', values,
                        offset, limit, self.sort, ctx)
            except Exception, exception:
                common.process_exception(exception, self.window)
                ids = rpc.execute('model', self.name, 'search', values,
                        offset, limit, self.sort, ctx)
            if not only_ids:
                if len(ids) == limit:
                    try:
                        self.search_count = rpc.execute('model', self.name,
                                'search_count', values, ctx)
                    except Exception, exception:
                        common.process_exception(exception, self.window)
                        self.search_count = rpc.execute('model', self.name,
                                'search_count', values, ctx)
                else:
                    self.search_count = len(ids)
        except:
            ids = []
        if only_ids:
            return ids
        self.clear()
        self.load(ids)
        return True

    def models_set(self, models):
        if self.models:
            self.models.signal_unconnect(self)
        self.models = models
        self.parent = models.parent
        self.parent_name = models.parent_name
        if len(models.models):
            self.current_model = models.models[0]
        else:
            self.current_model = None
        self.models.signal_connect(self, 'record-cleared', self._record_cleared)
        self.models.signal_connect(self, 'record-changed', self._record_changed)
        self.models.signal_connect(self, 'record-modified', self._record_modified)
        self.models.signal_connect(self, 'model-changed', self._model_changed)
        models.add_fields(self.fields, models)
        self.fields.update(models.fields)

    def _record_cleared(self, model_group, signal, *args):
        for view in self.views:
            view.reload = True

    def _record_changed(self, model_group, signal, *args):
        for view in self.views:
            view.signal_record_changed(signal[0], model_group.models,
                    signal[1], *args)

    def _record_modified(self, model_group, signal, *args):
        self.signal('record-modified')

    def _model_changed(self, model_group, model):
        if self.parent:
            self.parent.signal('record-changed', self.parent)
        self.display()

    def _get_current_model(self):
        return self.__current_model

    #
    # Check more or less fields than in the screen !
    #
    def _set_current_model(self, value):
        self.__current_model = value
        try:
            offset = int(self.filter_widget.get_offset())
        except:
            offset = 0
        try:
            pos = self.models.models.index(value)
        except:
            pos = -1
        self.signal('record-message', (pos + offset,
            len(self.models.models or []) + offset,
            self.search_count,
            value and value.id))
        attachment_count = 0
        if value and value.attachment_count > 0:
            attachment_count = value.attachment_count
        self.signal('attachment-count', attachment_count)
        # update attachment-count after 1 second
        gobject.timeout_add(1000, self.update_attachment, value)
        return True
    current_model = property(_get_current_model, _set_current_model)

    def update_attachment(self, model):
        if model != self.__current_model:
            return False
        if model and self.signal_connected('attachment-count'):
            attachment_count = model.get_attachment_count()
            self.signal('attachment-count', attachment_count)
        return False

    def destroy(self):
        for view in self.views:
            view.destroy()
            del view
        #del self.current_model
        self.models.signal_unconnect(self)
        del self.models
        del self.views

    def switch_view(self):
        self.current_view.set_value()
        if self.current_model and self.current_model not in self.models.models:
            self.current_model = None
        if len(self.view_to_load):
            self.load_view_to_load()
            self.__current_view = len(self.views) - 1
        else:
            self.__current_view = (self.__current_view + 1) % len(self.views)
        self.screen_container.set(self.current_view.widget)
        if self.current_model:
            self.current_model.validate_set()
        else:
            if self.current_view.view_type == 'form':
                self.new()
        self.current_view.set_cursor()
        self.current_view.cancel()
        self.display()
        # TODO: set True or False accoring to the type

    def load_view_to_load(self):
        if len(self.view_to_load):
            if self.view_ids:
                view_id = self.view_ids.pop(0)
                view_type = self.view_to_load.pop(0)
            else:
                view_id = False
                view_type = self.view_to_load.pop(0)
            self.add_view_id(view_id, view_type)

    def add_view_custom(self, arch, fields, display=False, toolbar=None):
        return self.add_view(arch, fields, display, True, toolbar=toolbar)

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
            try:
                view = self.rpc.fields_view_get(view_id, view_type, ctx,
                        self.hastoolbar)
            except Exception, exception:
                common.process_exception(exception, self.window)
                view = self.rpc.fields_view_get(view_id, view_type, ctx,
                        self.hastoolbar)
            if self.exclude_field:
                if self.exclude_field in view['fields']:
                    view['fields'][self.exclude_field]['states'] = {'invisible': True}
                    view['fields'][self.exclude_field]['readonly'] = True
                    view['fields'][self.exclude_field]['invisible'] = True
                    view['fields'][self.exclude_field]['tree_invisible'] = True
                    view['fields'][self.exclude_field]['exclude_field'] = True
            return self.add_view(view['arch'], view['fields'], display,
                    toolbar=view.get('toolbar', False), context=context)

    def add_view(self, arch, fields, display=False, custom=False, toolbar=None,
            context=None):
        if toolbar is None:
            toolbar = {}
        def _parse_fields(node, fields):
            if node.nodeType == node.ELEMENT_NODE:
                if node.localName == 'field':
                    attrs = node_attributes(node)
                    fields[str(attrs['name'])].update(attrs)
            for node2 in node.childNodes:
                _parse_fields(node2, fields)
        xml_dom = xml.dom.minidom.parseString(arch)
        _parse_fields(xml_dom, fields)

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
        models = self.models.models
        if self.current_model and (self.current_model not in models):
            models = models + [self.current_model]
        if custom:
            self.models.add_fields_custom(fields, self.models)
        else:
            self.models.add_fields(fields, self.models, context=context)

        self.fields = self.models.fields

        parser = WidgetParse(parent=self.parent, window=self.window)
        view = parser.parse(self, xml_dom, self.fields, toolbar=toolbar)

        self.views.append(view)

        if display:
            self.__current_view = len(self.views) - 1
            self.current_view.display()
            self.screen_container.set(view.widget)
        return view

    def editable_get(self):
        if hasattr(self.current_view, 'widget_tree'):
            if hasattr(self.current_view.widget_tree, 'editable'):
                return self.current_view.widget_tree.editable
        return False

    def new(self, default=True, context=None):
        if self.models.readonly:
            return
        if context is None:
            context = {}
        if self.current_view and ((self.current_view.view_type == 'tree' \
                and not (hasattr(self.current_view.widget_tree, 'editable') \
                    and self.current_view.widget_tree.editable)) \
                or self.current_view.view_type == 'graph'):
            for i in range(len(self.views)):
                self.switch_view()
                if self.current_view.view_type == 'form':
                    break
            if self.current_view.view_type != 'form':
                return None
        ctx = {}
        ctx.update(rpc.CONTEXT)
        ctx.update(self.context)
        ctx.update(context)
        model = self.models.model_new(default, self.domain, ctx)
        if (not self.current_view) \
                or self.current_view.model_add_new \
                or self.create_new:
            self.models.model_add(model, self.new_model_position())
        self.current_model = model
        self.current_model.validate_set()
        self.display()
        if self.current_view:
            self.current_view.set_cursor(new=True)
        self.request_set()
        return self.current_model

    def new_model_position(self):
        position = -1
        if self.current_view and self.current_view.view_type == 'tree' \
                and hasattr(self.current_view.widget_tree, 'editable') \
                    and self.current_view.widget_tree.editable == 'top':
            position = 0
        return position

    def set_on_write(self, func_name):
        if func_name:
            self.models.on_write.add(func_name)

    def cancel_current(self):
        if self.current_model:
            self.current_model.cancel()
            if self.current_model.id < 0:
                self.remove()
        if self.current_view:
            self.current_view.cancel()

    def save_current(self):
        if not self.current_model:
            return False
        self.current_view.set_value()
        obj_id = False
        if self.current_model.validate():
            obj_id = self.current_model.save(force_reload=True)
        else:
            self.current_view.set_cursor()
            self.current_view.display()
            return False
        if self.current_view.view_type == 'tree':
            for model in self.models.models:
                if model.is_modified():
                    if model.validate():
                        obj_id = model.save(force_reload=True)
                    else:
                        self.current_view.set_cursor()
                        self.current_model = model
                        self.current_view.set_cursor()
                        self.display()
                        return False
            self.current_view.set_cursor()
            self.display()
        if self.current_model not in self.models:
            self.models.model_add(self.current_model, modified=False)
        self.request_set()
        return obj_id

    def _get_current_view(self):
        if not len(self.views):
            return None
        return self.views[self.__current_view]
    current_view = property(_get_current_view)

    def get(self, get_readonly=True, includeid=False, check_load=True,
            get_modifiedonly=False):
        if not self.current_model:
            return None
        self.current_view.set_value()
        return self.current_model.get(get_readonly=get_readonly,
                includeid=includeid, check_load=check_load,
                get_modifiedonly=get_modifiedonly)

    def is_modified(self):
        if not self.current_model:
            return False
        self.current_view.set_value()
        res = False
        if self.current_view.view_type != 'tree':
            res = self.current_model.is_modified()
        else:
            for model in self.models.models:
                if model.is_modified():
                    res = True
        return res

    def reload(self, writen=False):
        ids = self.sel_ids_get()
        self.models.reload(ids)
        if writen:
            self.models.writen(ids)
        if self.parent:
            self.parent.reload()
        self.display()
        self.request_set()

    def remove(self, delete=False, remove=False):
        res = False
        reload_ids = []
        if self.current_view.view_type == 'form' and self.current_model:
            obj_id = self.current_model.id
            if delete and obj_id > 0:
                context = {}
                context.update(rpc.CONTEXT)
                context.update(self.context)
                context['_timestamp'] = self.current_model.get_timestamp()
                try:
                    reload_ids = self.models.on_write_ids([obj_id])
                    if reload_ids and obj_id in reload_ids:
                        reload_ids.remove(obj_id)
                    if not self.rpc.delete([obj_id], context):
                        return False
                except Exception, exception:
                    common.process_exception(exception, self.window)
                    return False
            self.current_view.set_cursor()
            if self.current_model in self.models.models:
                idx = self.models.models.index(self.current_model)
                self.models.remove(self.current_model, remove=remove)
                if self.models.models:
                    idx = min(idx, len(self.models.models)-1)
                    self.current_model = self.models.models[idx]
                else:
                    self.current_model = None
            if reload_ids:
                self.models.reload(reload_ids)
            self.display()
            res = True
        if self.current_view.view_type == 'tree':
            ids = self.current_view.sel_ids_get()
            if delete and ids:
                context = {}
                context.update(rpc.CONTEXT)
                context.update(self.context)
                context['_timestamp'] = {}
                for obj_id in ids:
                    model = self.models.get_by_id(obj_id)
                    context['_timestamp'].update(model.get_timestamp())
                try:
                    reload_ids = self.models.on_write_ids(ids)
                    if reload_ids:
                        for obj_id in ids:
                            if obj_id in reload_ids:
                                reload_ids.remove(obj_id)
                    if not self.rpc.delete(ids, context):
                        return False
                except Exception, exception:
                    common.process_exception(exception, self.window)
                    return False
            sel_models = self.current_view.sel_models_get()
            if not sel_models:
                return True
            idx = self.models.models.index(sel_models[0])
            for model in sel_models:
                # set current model to None to prevent __select_changed
                # to save the previous_model as it can be already deleted.
                self.current_model = None
                self.models.remove(model, remove=remove, signal=False)
            # send record-changed only once
            model.signal('record-changed', model.parent)
            if self.models.models:
                idx = min(idx, len(self.models.models)-1)
                self.current_model = self.models.models[idx]
            else:
                self.current_model = None
            if reload_ids:
                self.models.reload(reload_ids)
            self.current_view.set_cursor()
            self.display()
            res = True
        self.request_set()
        return res

    def load(self, ids, set_cursor=True, modified=False):
        self.models.load(ids, display=False, modified=modified)
        self.current_view.reset()
        if ids:
            self.display(ids[0])
        else:
            self.current_model = None
            self.display()
        if set_cursor:
            self.current_view.set_cursor()
        self.request_set()

    def display(self, res_id=None, set_cursor=False):
        if res_id:
            self.current_model = self.models[res_id]
        if self.views:
            #XXX To remove when calendar will be implemented
            if self.current_view.view_type == 'calendar' and \
                    len(self.views) > 1:
                self.switch_view()
            self.current_view.display()
            self.current_view.widget.set_sensitive(
                    bool(self.models.models \
                            or (self.current_view.view_type != 'form') \
                            or self.current_model))
            self.search_active(self.current_view.view_type \
                    in ('tree', 'graph', 'calendar'))
            if set_cursor:
                self.current_view.set_cursor(reset_view=False)

    def display_next(self):
        self.current_view.set_value()
        self.current_view.set_cursor(reset_view=False)
        if self.current_model in self.models.models:
            idx = self.models.models.index(self.current_model)
            idx = (idx+1) % len(self.models.models)
            self.current_model = self.models.models[idx]
        else:
            self.current_model = len(self.models.models) \
                    and self.models.models[0]
        self.current_view.set_cursor(reset_view=False)
        if self.current_model:
            self.current_model.validate_set()
        self.display()

    def display_prev(self):
        self.current_view.set_value()
        self.current_view.set_cursor(reset_view=False)
        if self.current_model in self.models.models:
            idx = self.models.models.index(self.current_model)-1
            if idx < 0:
                idx = len(self.models.models)-1
            self.current_model = self.models.models[idx]
        else:
            self.current_model = len(self.models.models) \
                    and self.models.models[-1]
        self.current_view.set_cursor(reset_view=False)
        if self.current_model:
            self.current_model.validate_set()
        self.display()

    def sel_ids_get(self):
        return self.current_view.sel_ids_get()

    def id_get(self):
        if not self.current_model:
            return False
        return self.current_model.id

    def ids_get(self):
        return [x.id for x in self.models if x.id]

    def clear(self):
        self.current_model = None
        self.models.clear()

    def on_change(self, fieldname, attr):
        self.current_model.on_change(fieldname, attr)
        self.display()

    def request_set(self):
        if self.name == 'res.request':
            from tryton.gui.main import Main
            Main.get_main().request_set()
