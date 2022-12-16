# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import sys
import gtk
import gobject
import gettext
import tryton.common as common
import types
from tryton.config import TRYTON_ICON
import csv
import tempfile
import os
from tryton.common import RPCExecute, RPCException
from tryton.gui.window.nomodal import NoModal

_ = gettext.gettext


class WinExport(NoModal):
    "Window export"

    def __init__(self, model, ids, context=None):
        super(WinExport, self).__init__()

        self.dialog = gtk.Dialog(title=_("Export to CSV"), parent=self.parent,
            flags=gtk.DIALOG_DESTROY_WITH_PARENT)
        self.dialog.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        self.dialog.set_icon(TRYTON_ICON)
        self.dialog.connect('response', self.response)

        vbox = gtk.VBox()
        frame_predef_exports = gtk.Frame()
        frame_predef_exports.set_border_width(2)
        frame_predef_exports.set_shadow_type(gtk.SHADOW_NONE)
        vbox.pack_start(frame_predef_exports, True, True, 0)
        viewport_exports = gtk.Viewport()
        scrolledwindow_exports = gtk.ScrolledWindow()
        scrolledwindow_exports.set_policy(gtk.POLICY_AUTOMATIC,
                gtk.POLICY_AUTOMATIC)
        label_predef_exports = gtk.Label(_("<b>Predefined exports</b>"))
        label_predef_exports.set_use_markup(True)
        frame_predef_exports.set_label_widget(label_predef_exports)
        viewport_exports.add(scrolledwindow_exports)
        frame_predef_exports.add(viewport_exports)

        hbox = gtk.HBox(True)
        vbox.pack_start(hbox, True, True, 0)

        frame_all_fields = gtk.Frame()
        frame_all_fields.set_shadow_type(gtk.SHADOW_NONE)
        hbox.pack_start(frame_all_fields, True, True, 0)
        label_all_fields = gtk.Label(_("<b>All fields</b>"))
        label_all_fields.set_use_markup(True)
        frame_all_fields.set_label_widget(label_all_fields)
        viewport_all_fields = gtk.Viewport()
        scrolledwindow_all_fields = gtk.ScrolledWindow()
        scrolledwindow_all_fields.set_policy(gtk.POLICY_AUTOMATIC,
                gtk.POLICY_AUTOMATIC)
        viewport_all_fields.add(scrolledwindow_all_fields)
        frame_all_fields.add(viewport_all_fields)

        vbox_buttons = gtk.VBox(False, 10)
        vbox_buttons.set_border_width(5)
        hbox.pack_start(vbox_buttons, False, True, 0)

        button_select = gtk.Button(_("_Add"), stock=None, use_underline=True)
        button_select.set_alignment(0.0, 0.0)
        img_button = gtk.Image()
        img_button.set_from_stock('tryton-list-add', gtk.ICON_SIZE_BUTTON)
        button_select.set_image(img_button)
        button_select.connect_after('clicked', self.sig_sel)
        vbox_buttons.pack_start(button_select, False, False, 0)

        button_unselect = gtk.Button(_("_Remove"), stock=None,
                use_underline=True)
        button_unselect.set_alignment(0.0, 0.0)
        img_button = gtk.Image()
        img_button.set_from_stock('tryton-list-remove', gtk.ICON_SIZE_BUTTON)
        button_unselect.set_image(img_button)
        button_unselect.connect_after('clicked', self.sig_unsel)
        vbox_buttons.pack_start(button_unselect, False, False, 0)

        button_unselect_all = gtk.Button(_("Clear"), stock=None,
                use_underline=True)
        button_unselect_all.set_alignment(0.0, 0.0)
        img_button = gtk.Image()
        img_button.set_from_stock('tryton-clear', gtk.ICON_SIZE_BUTTON)
        button_unselect_all.set_image(img_button)
        button_unselect_all.connect_after('clicked', self.sig_unsel_all)
        vbox_buttons.pack_start(button_unselect_all, False, False, 0)

        hseparator_buttons = gtk.HSeparator()
        vbox_buttons.pack_start(hseparator_buttons, False, True, 0)

        button_save_export = gtk.Button(_("Save Export"), stock=None,
                use_underline=True)
        button_save_export.set_alignment(0.0, 0.0)
        img_button = gtk.Image()
        img_button.set_from_stock('tryton-save', gtk.ICON_SIZE_BUTTON)
        button_save_export.set_image(img_button)
        button_save_export.connect_after('clicked', self.addreplace_predef)
        vbox_buttons.pack_start(button_save_export, False, False, 0)

        button_del_export = gtk.Button(_("Delete Export"), stock=None,
                use_underline=True)
        button_del_export.set_alignment(0.0, 0.0)
        img_button = gtk.Image()
        img_button.set_from_stock('tryton-delete', gtk.ICON_SIZE_BUTTON)
        button_del_export.set_image(img_button)
        button_del_export.connect_after('clicked', self.remove_predef)
        vbox_buttons.pack_start(button_del_export, False, False, 0)

        frame_export = gtk.Frame()
        frame_export.set_shadow_type(gtk.SHADOW_NONE)
        label_export = gtk.Label(_("<b>Fields to export</b>"))
        label_export.set_use_markup(True)
        frame_export.set_label_widget(label_export)

        alignment_export = gtk.Alignment(0.5, 0.5, 1, 1)
        alignment_export.set_padding(0, 0, 12, 0)
        frame_export.add(alignment_export)
        viewport_fields_to_export = gtk.Viewport()
        scrolledwindow_export = gtk.ScrolledWindow()
        scrolledwindow_export.set_policy(gtk.POLICY_AUTOMATIC,
                gtk.POLICY_AUTOMATIC)
        viewport_fields_to_export.add(scrolledwindow_export)
        alignment_export.add(viewport_fields_to_export)
        hbox.pack_start(frame_export, True, True, 0)

        frame_options = gtk.Frame()
        frame_options.set_border_width(2)
        label_options = gtk.Label(_("<b>Options</b>"))
        label_options.set_use_markup(True)
        frame_options.set_label_widget(label_options)
        vbox.pack_start(frame_options, False, True, 5)
        hbox_options = gtk.HBox(False, 2)
        frame_options.add(hbox_options)
        hbox_options.set_border_width(2)

        combo_saveas = gtk.combo_box_new_text()
        hbox_options.pack_start(combo_saveas, True, True, 0)
        combo_saveas.append_text(_("Open"))
        combo_saveas.append_text(_("Save"))
        vseparator_options = gtk.VSeparator()
        hbox_options.pack_start(vseparator_options, False, False, 10)

        checkbox_add_field_names = gtk.CheckButton(_("Add _field names"))
        checkbox_add_field_names.set_active(True)
        hbox_options.pack_start(checkbox_add_field_names, False, False, 0)

        button_cancel = gtk.Button("gtk-cancel", stock="gtk-cancel")
        self.dialog.add_action_widget(button_cancel, gtk.RESPONSE_CANCEL)
        button_cancel.set_flags(gtk.CAN_DEFAULT)

        button_ok = gtk.Button("gtk-ok", stock="gtk-ok")
        self.dialog.add_action_widget(button_ok, gtk.RESPONSE_OK)
        button_ok.set_flags(gtk.CAN_DEFAULT)

        self.dialog.vbox.pack_start(vbox)

        self.ids = ids
        self.model = model
        self.context = context

        self.view1 = gtk.TreeView()
        self.view1.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self.view1.connect('row-expanded', self.on_row_expanded)
        scrolledwindow_all_fields.add(self.view1)
        self.view2 = gtk.TreeView()
        self.view2.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        scrolledwindow_export.add(self.view2)
        self.view1.set_headers_visible(False)
        self.view2.set_headers_visible(False)

        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn('Field name', cell, text=0,
                background=2)
        self.view1.append_column(column)

        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn('Field name', cell, text=0)
        self.view2.append_column(column)

        self.model1 = gtk.TreeStore(gobject.TYPE_STRING, gobject.TYPE_STRING,
                gobject.TYPE_STRING)
        self.model2 = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING)

        self.fields = {}

        self.model_populate(self._get_fields(model))

        self.view1.set_model(self.model1)
        self.view1.connect('row-activated', self.sig_sel)
        self.view2.set_model(self.model2)
        self.view2.connect('row-activated', self.sig_unsel)
        if sys.platform != 'darwin':
            self.view2.drag_source_set(
                gtk.gdk.BUTTON1_MASK | gtk.gdk.BUTTON3_MASK,
                [('EXPORT_TREE', gtk.TARGET_SAME_WIDGET, 0)],
                gtk.gdk.ACTION_MOVE)
            self.view2.drag_dest_set(gtk.DEST_DEFAULT_ALL,
                [('EXPORT_TREE', gtk.TARGET_SAME_WIDGET, 0)],
                gtk.gdk.ACTION_MOVE)
            self.view2.connect('drag-begin', self.drag_begin)
            self.view2.connect('drag-motion', self.drag_motion)
            self.view2.connect('drag-drop', self.drag_drop)
            self.view2.connect("drag-data-get", self.drag_data_get)
            self.view2.connect('drag-data-received', self.drag_data_received)
            self.view2.connect('drag-data-delete', self.drag_data_delete)

        self.wid_action = combo_saveas
        self.wid_write_field_names = checkbox_add_field_names
        self.wid_action.set_active(0)

        # Creating the predefined export view
        self.pref_export = gtk.TreeView()
        self.pref_export.append_column(gtk.TreeViewColumn(_('Name'),
            gtk.CellRendererText(), text=2))
        scrolledwindow_exports.add(self.pref_export)

        self.pref_export.connect("button-press-event", self.export_click)
        self.pref_export.connect("key-press-event", self.export_keypress)

        # Fill the predefined export tree view
        self.predef_model = gtk.ListStore(
                gobject.TYPE_INT,
                gobject.TYPE_PYOBJECT,
                gobject.TYPE_STRING)
        self.fill_predefwin()

        sensible_allocation = self.sensible_widget.get_allocation()
        self.dialog.set_default_size(int(sensible_allocation.width * 0.9),
            int(sensible_allocation.height * 0.9))
        self.dialog.show_all()
        common.center_window(self.dialog, self.parent, self.sensible_widget)

        self.register()

    def model_populate(self, fields, parent_node=None, prefix_field='',
            prefix_name=''):
        key = lambda (n, f): f.get('string') or n
        for name, field in sorted(fields.items(), key=key, reverse=True):

            string_ = field['string'] or name

            items = [(name, field, string_)]
            if field['type'] == 'selection':
                items.insert(0, ('%s.translated' % name, field,
                        _('%s (string)') % string_))

            for name, field, string_ in items:
                path = prefix_field + name
                color = 'white'
                if field.get('required'):
                    color = common.COLORS['required']
                long_string = string_
                if prefix_field:
                    long_string = prefix_name + string_
                node = self.model1.insert(parent_node, 0,
                    [string_, path, color])

                self.fields[path] = (string_, long_string,
                    field.get('relation'))
                # Insert relation only to real field
                if '.' not in name:
                    if field.get('relation'):
                        self.model1.insert(node, 0, [None, '', 'white'])

    def _get_fields(self, model):
        try:
            return RPCExecute('model', model, 'fields_get', None,
                context=self.context)
        except RPCException:
            return ''

    def on_row_expanded(self, treeview, iter, path):
        child = self.model1.iter_children(iter)
        if self.model1.get_value(child, 0) is None:
            prefix_field = self.model1.get_value(iter, 1)
            string_, long_string, relation = self.fields[prefix_field]
            self.model_populate(self._get_fields(relation), iter,
                prefix_field + '/', string_ + '/')
            self.model1.remove(child)

    def sig_sel(self, *args):
        sel = self.view1.get_selection()
        sel.selected_foreach(self._sig_sel_add)

    def _sig_sel_add(self, store, path, iter):
        name = store.get_value(iter, 1)
        string_, long_string, relation = self.fields[name]
        if relation:
            return
        num = self.model2.append()
        self.model2.set(num, 0, long_string, 1, name)

    def sig_unsel(self, *args):
        store, paths = self.view2.get_selection().get_selected_rows()
        while paths:
            store.remove(store.get_iter(paths[0]))
            store, paths = self.view2.get_selection().get_selected_rows()

    def sig_unsel_all(self, widget=None):
        self.model2.clear()

    def fill_predefwin(self):
        try:
            export_ids = RPCExecute('model', 'ir.export', 'search',
                [('resource', '=', self.model)], 0, None, None,
                context=self.context)
        except RPCException:
            return
        try:
            exports = RPCExecute('model', 'ir.export', 'read', export_ids,
                None, context=self.context)
        except RPCException:
            return
        try:
            lines = RPCExecute('model', 'ir.export.line', 'read',
                sum((list(x['export_fields']) for x in exports), []), None,
                context=self.context)
        except RPCException:
            return
        id2lines = {}
        for line in lines:
            id2lines.setdefault(line['export'], []).append(line)
        for export in exports:
            self.predef_model.append((
                export['id'],
                [x['name'] for x in id2lines.get(export['id'], [])],
                export['name']))
        self.pref_export.set_model(self.predef_model)

    def addreplace_predef(self, widget):
        iter = self.model2.get_iter_root()
        fields = []
        while iter:
            field_name = self.model2.get_value(iter, 1)
            fields.append(field_name)
            iter = self.model2.iter_next(iter)
        if not fields:
            return

        selection = self.pref_export.get_selection().get_selected()
        if selection is None:
            return
        model, iter_ = selection
        if iter_ is None:
            pref_id = None
            name = common.ask(_('What is the name of this export?'))
            if not name:
                return
        else:
            pref_id = model.get_value(iter_, 0)
            name = model.get_value(iter_, 2)
            override = common.sur(_("Override '%s' definition?") % name)
            if not override:
                return
        try:
            new_id, = RPCExecute('model', 'ir.export', 'create', [{
                    'name': name,
                    'resource': self.model,
                    'export_fields': [('create', [{
                                        'name': x,
                                        } for x in fields])],
                    }], context=self.context)
            if pref_id:
                RPCExecute('model', 'ir.export', 'delete', [pref_id],
                    context=self.context)
        except RPCException:
            return
        if iter_ is None:
            self.predef_model.append((new_id, fields, name))
        else:
            model.set_value(iter_, 0, new_id)
            model.set_value(iter_, 1, fields)

    def remove_predef(self, widget):
        sel = self.pref_export.get_selection().get_selected()
        if sel is None:
            return None
        (model, i) = sel
        if not i:
            return None
        export_id = model.get_value(i, 0)
        try:
            RPCExecute('model', 'ir.export', 'delete', [export_id],
                context=self.context)
        except RPCException:
            return
        for i in range(len(self.predef_model)):
            if self.predef_model[i][0] == export_id:
                del self.predef_model[i]
                break
        self.pref_export.set_model(self.predef_model)

    def sel_predef(self, path):
        self.model2.clear()
        for name in self.predef_model[path[0]][1]:
            if name not in self.fields:
                iter = self.model1.get_iter_first()
                prefix = ''
                for parent in name.split('/')[:-1]:
                    while iter:
                        if self.model1.get_value(iter, 1) == \
                                (prefix + parent):
                            self.on_row_expanded(self.view1, iter,
                                    self.model1.get_path(iter))
                            iter = self.model1.iter_children(iter)
                            prefix += parent + '/'
                            break
                        else:
                            iter = self.model1.iter_next(iter)

            if name not in self.fields:
                continue
            self.sel_field(name)

    def sel_field(self, name):
        _, long_string, relation = self.fields[name]
        if relation:
            return
        self.model2.append((long_string, name))

    def destroy(self):
        super(WinExport, self).destroy()
        self.dialog.destroy()

    def show(self):
        self.dialog.show()

    def hide(self):
        self.dialog.hide()

    def response(self, dialog, response):
        if response == gtk.RESPONSE_OK:
            fields = []
            fields2 = []
            iter = self.model2.get_iter_root()
            while iter:
                fields.append(self.model2.get_value(iter, 1))
                fields2.append(self.model2.get_value(iter, 0))
                iter = self.model2.iter_next(iter)
            action = self.wid_action.get_active()
            self.destroy()
            try:
                result = RPCExecute('model', self.model, 'export_data',
                    self.ids, fields, context=self.context)
            except RPCException:
                result = []

            if action == 0:
                fileno, fname = tempfile.mkstemp('.csv', 'tryton_')
                self.export_csv(fname, fields2, result,
                        self.wid_write_field_names.get_active(), popup=False)
                os.close(fileno)
                common.file_open(fname, 'csv')
            else:
                fname = common.file_selection(_('Save As...'),
                        action=gtk.FILE_CHOOSER_ACTION_SAVE)
                if fname:
                    self.export_csv(fname, fields2, result,
                            self.wid_write_field_names.get_active())
            return True
        else:
            self.destroy()
            return False

    def export_csv(self, fname, fields, result, write_title=False, popup=True):
        try:
            file_p = open(fname, 'wb+')
            writer = csv.writer(file_p)
            if write_title:
                writer.writerow(fields)
            for data in result:
                row = []
                for val in data:
                    if isinstance(type(val), types.StringType):
                        row.append(val.replace('\n', ' ').replace('\t', ' '))
                    else:
                        row.append(val)
                writer.writerow(row)
            file_p.close()
            if popup:
                if len(result) == 1:
                    common.message(_('%d record saved!') % len(result))
                else:
                    common.message(_('%d records saved!') % len(result))
            return True
        except IOError, exception:
            common.warning(_("Operation failed!\nError message:\n%s")
                % exception, _('Error'))
            return False

    def drag_begin(self, treeview, context):
        return True

    def drag_motion(self, treeview, context, x, y, time):
        try:
            treeview.set_drag_dest_row(*treeview.get_dest_row_at_pos(x, y))
        except TypeError:
            treeview.set_drag_dest_row(len(treeview.get_model()) - 1,
                gtk.TREE_VIEW_DROP_AFTER)
        context.drag_status(gtk.gdk.ACTION_MOVE, time)
        return True

    def drag_drop(self, treeview, context, x, y, time):
        treeview.emit_stop_by_name('drag-drop')
        return True

    def drag_data_get(self, treeview, context, selection, target_id,
            etime):
        treeview.emit_stop_by_name('drag-data-get')

        def _func_sel_get(store, path, iter_, data):
            data.append(path[0])
        data = []
        treeselection = treeview.get_selection()
        treeselection.selected_foreach(_func_sel_get, data)
        if not data:
            return
        selection.set('STRING', 8, ','.join(str(x) for x in data))
        return True

    def drag_data_received(self, treeview, context, x, y, selection,
            info, etime):
        treeview.emit_stop_by_name('drag-data-received')
        if not selection.data:
            return
        store = treeview.get_model()

        data_iters = [store.get_iter((int(i),))
            for i in selection.data.split(',')]
        drop_info = treeview.get_dest_row_at_pos(x, y)
        if drop_info:
            path, position = drop_info
            pos = store.get_iter(path)
        else:
            pos = store.get_iter((len(store) - 1,))
            position = gtk.TREE_VIEW_DROP_AFTER
        if position == gtk.TREE_VIEW_DROP_AFTER:
            data_iters = reversed(data_iters)
        for item in data_iters:
            if position == gtk.TREE_VIEW_DROP_BEFORE:
                store.move_before(item, pos)
            else:
                store.move_after(item, pos)
        context.drop_finish(False, etime)
        return True

    def drag_data_delete(self, treeview, context):
        treeview.emit_stop_by_name('drag-data-delete')

    def export_click(self, treeview, event):
        path_at_pos = treeview.get_path_at_pos(int(event.x), int(event.y))
        if not path_at_pos or event.button != 1:
            return
        path, col, x, y = path_at_pos
        selection = treeview.get_selection()
        if event.type == gtk.gdk._2BUTTON_PRESS:
            self.sel_predef(path)
            selection.select_path(path)
            return True
        elif selection.path_is_selected(path):
            selection.unselect_path(path)
            return True

    def export_keypress(self, treeview, event):
        if event.keyval not in (gtk.keysyms.Return, gtk.keysyms.space):
            return
        model, selected = treeview.get_selection().get_selected()
        if not selected:
            return
        self.sel_predef(model.get_path(selected))
