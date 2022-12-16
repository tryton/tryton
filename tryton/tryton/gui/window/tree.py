#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Tree"
import gtk
import gettext
import tryton.common as common
from tryton.gui.window.view_tree import ViewTree, ViewTreeSC
import tryton.rpc as rpc
from tryton.config import CONFIG
from tryton.gui.window.win_export import WinExport
from window import Window
from tryton.action import Action
from tryton.signal_event import SignalEvent

_ = gettext.gettext

class Tree(SignalEvent):
    "Tree page"

    def __init__(self, model, window, res_id=False, view_id=False, domain=None,
            context=None, name=False):
        super(Tree, self).__init__()
        if domain is None:
            domain = {}
        if context is None:
            context = {}
        ctx = {}
        ctx.update(context)
        ctx.update(rpc.CONTEXT)
        if view_id:
            try:
                view_base =  rpc.execute('model', 'ir.ui.view', 'read', view_id,
                        ['model', 'type'], ctx)
            except Exception, exception:
                common.process_exception(exception, window)
                raise
            try:
                view = rpc.execute('model', view_base['model'],
                        'fields_view_get', view_id, view_base['type'], ctx)
            except Exception, exception:
                common.process_exception(exception, window)
                raise
        else:
            try:
                view = rpc.execute('model', model, 'fields_view_get', False,
                        'tree', ctx)
            except Exception, exception:
                common.process_exception(exception, window)
                raise

        self.widget = gtk.VBox()

        hpaned = gtk.HPaned()
        hpaned.set_position(220)

        self.toolbar_vpaned = gtk.VPaned()
        self.toolbar_vpaned.set_position(400)

        self.toolbar = gtk.Toolbar()
        self.toolbar.set_orientation(gtk.ORIENTATION_VERTICAL)
        self.toolbar.set_style(gtk.TOOLBAR_BOTH_HORIZ)
        self.toolbar_vpaned.add1(self.toolbar)

        self.toolbar_vpaned.add1(self.toolbar_vpaned)

        scrolledwindow = gtk.ScrolledWindow()
        scrolledwindow.set_policy(gtk.POLICY_AUTOMATIC,
                gtk.POLICY_AUTOMATIC)
        viewport = gtk.Viewport()
        viewport.set_shadow_type(gtk.SHADOW_ETCHED_IN)

        vbox = gtk.VBox()

        toolbar = gtk.Toolbar()
        toolbar.set_style(gtk.TOOLBAR_ICONS)
        toolitem = gtk.ToolItem()
        self.toolitem_label = gtk.Label()
        toolitem.add(self.toolitem_label)
        toolbar.insert(toolitem, -1)
        addbutton = gtk.ToolButton('tryton-list-add')
        addbutton.connect('clicked', self.sc_add)
        toolbar.insert(addbutton, -1)
        removebutton = gtk.ToolButton('tryton-list-remove')
        removebutton.connect('clicked', self.sc_del)
        toolbar.insert(removebutton, -1)
        vbox.pack_start(toolbar, expand=False)

        self.treeview_sc = gtk.TreeView()
        self.treeview_sc.set_reorderable(False)
        self.treeview_sc.set_headers_visible(False)
        vbox.pack_start(self.treeview_sc)

        viewport.add(vbox)

        scrolledwindow.add(viewport)

        self.toolbar_vpaned.add2(scrolledwindow)

        hpaned.add1(self.toolbar_vpaned)

        viewport = gtk.Viewport()
        viewport.set_shadow_type(gtk.SHADOW_ETCHED_IN)

        self.scrolledwindow = gtk.ScrolledWindow()
        self.scrolledwindow.set_policy(gtk.POLICY_AUTOMATIC,
                gtk.POLICY_AUTOMATIC)
        viewport.add(self.scrolledwindow)

        hpaned.add2(viewport)

        self.widget.pack_start(hpaned)
        self.widget.show_all()

        self.model = view['model'] or model
        self.domain2 = domain
        if view.get('field_childs', False):
            self.domain = []
        else:
            self.domain = domain
        self.view = view
        self.window = window

        self.context = context

        self.tree_res = ViewTree(view, [], self.window, True,
                context=context)
        self.tree_res.view.connect('row-activated', self.sig_activate)
        self.tree_res.view.connect('key_press_event', self.sig_key_press)
        self.tree_res.view.connect_after('test-expand-row',
                self.sig_test_expand_row)

        if not name:
            self.name = self.tree_res.name
        else:
            self.name = name

        if CONFIG['client.modepda']:
            self.toolbar_vpaned.hide()

        self.treeview_sc.connect('row-activated', self.sc_go)
        self.tree_sc = ViewTreeSC(self.treeview_sc, self.model, self.window)
        self.handlers = {
            'but_new': self.sig_new,
            'but_reload': self.sig_reload,
            'but_switch': self.sig_edit,
            'but_action': self.sig_action,
            'but_print': self.sig_print,
            'but_save_as': self.sig_save_as,
            'but_close': self.sig_close,
        }

        self.scrolledwindow.add(self.tree_res.widget_get())
        self.sig_reload()

        self.tree_res.view.grab_focus()
        if self.tree_res.view.get_model().get_iter_root():
            self.tree_res.view.grab_focus()
            selection = self.tree_res.view.get_selection()
            selection.select_path((0))

    def sig_reload(self, widget=None):
        self.toolitem_label.set_text(_('Shortcuts'))
        try:
            ctx = {}
            ctx.update(self.context)
            ctx.update(rpc.CONTEXT)
            args = ('model', self.model, 'search', self.domain2, 0, None,
                    None, ctx)
            ids = rpc.execute(*args)
        except Exception, exception:
            ids = common.process_exception(exception, self.window, *args)
            if not ids:
                return
        if self.tree_res.toolbar and not CONFIG['client.modepda']:

            icon_name = 'icon'
            for child in self.toolbar.get_children():
                self.toolbar.remove(child)
            ctx = {}
            ctx.update(rpc.CONTEXT)
            try:
                args = ('model', self.view['model'], 'read', ids,
                        ['name', icon_name], ctx)
                results = rpc.execute(*args)
            except Exception, exception:
                results = common.process_exception(exception, self.window, *args)
                if not results:
                    return
            results.sort(lambda x, y: cmp(ids.index(x['id']),
                ids.index(y['id'])))
            radiotb = None
            for res in results:
                radiotb = gtk.RadioToolButton(group=radiotb)
                radiotb.set_label_widget(gtk.Label(res['name']))

                icon = gtk.Image()
                try:
                    icon.set_from_stock(res[icon_name],
                            gtk.ICON_SIZE_BUTTON)
                except:
                    pass

                hbox = gtk.HBox(spacing=6)
                hbox.pack_start(icon)
                hbox.pack_start(gtk.Label(res['name']))
                radiotb.set_icon_widget(hbox)
                radiotb.show_all()
                radiotb.set_data('id', res['id'])
                radiotb.connect('clicked', self.menu_main_clicked)
                self.menu_main_clicked(radiotb, focus=False)
                self.toolbar.insert(radiotb, -1)
                radiotb.child.connect('key_press_event', self.menu_main_key_press)
        else:
            self.tree_res.ids = ids
            self.tree_res.reload()
            self.toolbar.hide()
            self.toolbar_vpaned.set_position(-1)
        self.tree_res.view.grab_focus()
        if self.tree_res.view.get_model().get_iter_root():
            self.tree_res.view.grab_focus()
            selection = self.tree_res.view.get_selection()
            selection.select_path((0))
        self.tree_sc.update()

    def menu_main_clicked(self, widget, focus=True):
        if widget.get_active():
            obj_id = widget.get_data('id')
            args = ('model', self.model, 'read', obj_id,
                    [self.view['field_childs']], rpc.CONTEXT)
            try:
                ids = rpc.execute(*args)[self.view['field_childs']]
            except Exception, exception:
                res = common.process_exception(exception, self.window, *args)
                if not res:
                    return False
                ids = res[self.view['field_childs']]
                if not ids:
                    return False

            self.tree_res.ids = ids
            self.tree_res.reload()

            self.sig_action('tree_open', obj_id=obj_id, warning=False)
            if focus:
                if self.tree_res.view.get_model().get_iter_root():
                    self.tree_res.view.grab_focus()
                    selection = self.tree_res.view.get_selection()
                    selection.unselect_all()
                    selection.select_path((0))
                    self.tree_res.view.set_cursor((0))
        return False

    def menu_main_key_press(self, widget, event):
        if event.keyval == gtk.keysyms.Right:
            if self.tree_res.view.get_model().get_iter_root():
                self.tree_res.view.grab_focus()
                selection = self.tree_res.view.get_selection()
                selection.unselect_all()
                selection.select_path((0))
                self.tree_res.view.set_cursor((0))
                return True

    def sig_print(self):
        self.sig_action('form_print')

    def sig_action(self, keyword='tree_action', obj_id=None, warning=True):
        ids = self.ids_get()
        if not obj_id and ids and len(ids):
            obj_id = ids[0]
        if obj_id:
            ctx = self.context.copy()
            if 'active_ids' in ctx:
                del ctx['active_ids']
            if 'active_id' in ctx:
                del ctx['active_id']
            return Action.exec_keyword(keyword, self.window, {
                'model': self.model,
                'id': obj_id,
                'ids':ids,
                }, context=ctx, warning=warning)
        else:
            common.message(_('No record selected!'), self.window)
        return False

    def sig_activate(self, widget, iter, path):
        if not self.sig_action('tree_open', warning=False):
            if self.tree_res.view.row_expanded(iter):
                self.tree_res.view.collapse_row(iter)
            else:
                self.tree_res.view.expand_row(iter, False)
            if self.model != 'ir.ui.menu':
                self.sig_edit()

    def sig_key_press(self, widget, event):
        if event.keyval == gtk.keysyms.Left:
            selection = self.tree_res.view.get_selection()
            model, paths = selection.get_selected_rows()
            if len(paths) == 1:
                if not self.tree_res.view.row_expanded(paths[0]):
                    if len(paths[0]) > 1:
                        new_path = paths[0][:-1]
                        selection.select_path(new_path)
                        self.tree_res.view.collapse_row(new_path)
                    elif self.tree_res.toolbar:
                        for child in self.toolbar.get_children():
                            if child.get_active():
                                child.child.grab_focus()
                                break
            for path in paths:
                self.tree_res.view.collapse_row(path)
            return True
        elif event.keyval == gtk.keysyms.Right:
            model, paths = self.tree_res.view.get_selection()\
                    .get_selected_rows()
            for path in paths:
                self.tree_res.view.expand_row(path, False)
            return True

    def sig_test_expand_row(self, widget, iter, path):
        model = self.tree_res.view.get_model()
        iter_children = model.iter_children(iter)
        if iter_children and model.get(iter_children, 0)[0] in model.to_reload:
            hostname = rpc._SOCK.hostname
            port = rpc._SOCK.port
            while True:
                password = common.ask(_('Password:'), self.window,
                        visibility=False)
                if password is None:
                    return True
                res = rpc.login(rpc._USERNAME, password, hostname, port,
                        rpc._DATABASE)
                if res == -1:
                    common.message(_('Connection error!\n' \
                            'Unable to connect to the server!'), self.window)
                    return True
                if res < 0:
                    continue
                return False
        return False

    def sig_new(self):
        Window.create(None, self.model, domain=self.domain, window=self.window,
                context=self.context, mode=['form', 'tree'])

    def sig_edit(self):
        obj_ids = self.ids_get()
        if not obj_ids:
            obj_ids = []
        if self.tree_res.toolbar:
            for child in self.toolbar.get_children():
                if child.get_active():
                    obj_ids.append(child.get_data('id'))
        mode = ['form', 'tree']
        if len(obj_ids) > 1:
            mode = ['tree', 'form']
        Window.create(None, self.model, obj_ids, self.domain,
                window=self.window, context=self.context,
                mode=mode)

    def sc_del(self, widget):
        obj_id = self.tree_sc.sel_id_get()
        if obj_id is not None:
            sc_id = int(self.tree_sc.value_get(2))
            try:
                rpc.execute('model', 'ir.ui.view_sc', 'delete', sc_id,
                        rpc.CONTEXT)
            except Exception, exception:
                common.process_exception(exception, self.window)
        self.tree_sc.update()

    def sc_add(self, widget):
        ids = self.ids_get()
        if len(ids):
            try:
                res = rpc.execute('model', self.model, 'read', ids,
                        ['rec_name'], rpc.CONTEXT)
                for obj in res:
                    obj_id = obj['id']
                    name = obj['rec_name']
                    user = rpc._USER
                    rpc.execute('model', 'ir.ui.view_sc', 'create', {
                                'resource': self.model,
                                'user_id': user,
                                'res_id': obj_id,
                                'name': name,
                                }, rpc.CONTEXT)
            except Exception, exception:
                common.process_exception(exception, self.window)
        self.tree_sc.update()

    def sc_go(self, widget=None, *args):
        obj_id = self.tree_sc.sel_id_get()
        if obj_id is not None:
            self.sig_action(keyword='tree_open', obj_id=obj_id)

    def ids_get(self):
        res = self.tree_res.sel_ids_get()
        return res

    def id_get(self):
        res = self.tree_res.sel_id_get()
        return res

    def sig_save_as(self, widget=None):
        win = WinExport(self.model, self.ids_get(), self.window,
                context=self.context)
        win.run()

    def sig_close(self):
        return True
