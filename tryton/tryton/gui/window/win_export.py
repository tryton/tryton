# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import csv
import os
import tempfile
import types

import gtk
import gobject
import gettext

import tryton.common as common
from tryton.common import RPCExecute, RPCException
from tryton.gui.window.win_csv import WinCSV

_ = gettext.gettext


class WinExport(WinCSV):
    "Window export"

    def __init__(self, model, ids, context=None):
        self.ids = ids
        self.model = model
        self.context = context
        self.fields = {}
        super(WinExport, self).__init__()
        self.dialog.set_title(_('Export to CSV'))

    def add_header(self, box):
        frame_predef_exports = gtk.Frame()
        frame_predef_exports.set_border_width(2)
        frame_predef_exports.set_shadow_type(gtk.SHADOW_NONE)
        box.pack_start(frame_predef_exports, True, True, 0)
        viewport_exports = gtk.Viewport()
        scrolledwindow_exports = gtk.ScrolledWindow()
        scrolledwindow_exports.set_policy(gtk.POLICY_AUTOMATIC,
                gtk.POLICY_AUTOMATIC)
        label_predef_exports = gtk.Label(_("<b>Predefined exports</b>"))
        label_predef_exports.set_use_markup(True)
        frame_predef_exports.set_label_widget(label_predef_exports)
        viewport_exports.add(scrolledwindow_exports)
        frame_predef_exports.add(viewport_exports)

        self.pref_export = gtk.TreeView()
        self.pref_export.append_column(gtk.TreeViewColumn(_('Name'),
            gtk.CellRendererText(), text=2))
        scrolledwindow_exports.add(self.pref_export)
        self.pref_export.connect("button-press-event", self.export_click)
        self.pref_export.connect("key-press-event", self.export_keypress)

        self.predef_model = gtk.ListStore(
                gobject.TYPE_INT,
                gobject.TYPE_PYOBJECT,
                gobject.TYPE_STRING)
        self.fill_predefwin()

    def add_buttons(self, box):
        button_save_export = gtk.Button(
            _('_Save Export'), stock=None, use_underline=True)
        button_save_export.set_alignment(0.0, 0.0)
        img_button = gtk.Image()
        img_button.set_from_stock('tryton-save', gtk.ICON_SIZE_BUTTON)
        button_save_export.set_image(img_button)
        button_save_export.set_always_show_image(True)
        button_save_export.connect_after('clicked', self.addreplace_predef)
        box.pack_start(button_save_export, False, False, 0)

        button_del_export = gtk.Button(
            _('_Delete Export'), stock=None, use_underline=True)
        button_del_export.set_alignment(0.0, 0.0)
        img_button = gtk.Image()
        img_button.set_from_stock('tryton-delete', gtk.ICON_SIZE_BUTTON)
        button_del_export.set_image(img_button)
        button_del_export.set_always_show_image(True)
        button_del_export.connect_after('clicked', self.remove_predef)
        box.pack_start(button_del_export, False, False, 0)

    def add_chooser(self, box):
        hbox_csv_export = gtk.HBox()
        box.pack_start(hbox_csv_export, False, True, 0)
        if hasattr(gtk, 'ComboBoxText'):
            self.saveas = gtk.ComboBoxText()
        else:
            self.saveas = gtk.combo_box_new_text()
        hbox_csv_export.pack_start(self.saveas, True, True, 0)
        self.saveas.append_text(_("Open"))
        self.saveas.append_text(_("Save"))
        self.saveas.set_active(0)

    def add_csv_header_param(self, table):
        self.add_field_names = gtk.CheckButton(_("Add _field names"))
        self.add_field_names.set_active(True)
        table.attach(self.add_field_names, 2, 4, 1, 2)

    def model_populate(self, fields, parent_node=None, prefix_field='',
            prefix_name=''):
        key = lambda (n, f): f.get('string') or n
        for name, field in sorted(fields.items(), key=key, reverse=True):

            string_ = field['string'] or name

            items = [(name, field, string_)]
            if field['type'] == 'selection':
                items.insert(0, ('%s.translated' % name, field,
                        _('%s (string)') % string_))
            elif field['type'] == 'reference':
                items.insert(0, ('%s.translated' % name, field,
                        _('%s (model name)') % string_))
                items.insert(0, ('%s/rec_name' % name, field,
                        _("%s (record name)") % string_))

            for name, field, string_ in items:
                path = prefix_field + name
                long_string = string_
                if prefix_field:
                    long_string = prefix_name + string_
                node = self.model1.insert(parent_node, 0,
                    [string_, path])

                self.fields[path] = (string_, long_string,
                    field.get('relation'))
                # Insert relation only to real field
                if '.' not in name:
                    if field.get('relation'):
                        self.model1.insert(node, 0, [None, ''])

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
        # Convert first into TreeIter before removing from the store
        iters = [store.get_iter(p) for p in paths]
        for i in iters:
            store.remove(i)

    def sig_unsel_all(self, *args):
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
        iter = self.model2.get_iter_first()
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

    def response(self, dialog, response):
        if response == gtk.RESPONSE_OK:
            fields = []
            fields2 = []
            iter = self.model2.get_iter_first()
            while iter:
                fields.append(self.model2.get_value(iter, 1))
                fields2.append(self.model2.get_value(iter, 0))
                iter = self.model2.iter_next(iter)
            action = self.saveas.get_active()
            try:
                data = RPCExecute('model', self.model, 'export_data',
                    self.ids, fields, context=self.context)
            except RPCException:
                data = []

            if action == 0:
                fileno, fname = tempfile.mkstemp('.csv', 'tryton_')
                self.export_csv(fname, fields2, data, popup=False)
                os.close(fileno)
                common.file_open(fname, 'csv')
            else:
                fname = common.file_selection(_('Save As...'),
                        action=gtk.FILE_CHOOSER_ACTION_SAVE)
                if fname:
                    self.export_csv(fname, fields2, data)
        self.destroy()

    def export_csv(self, fname, fields, data, popup=True):
        encoding = self.csv_enc.get_active_text() or 'UTF-8'

        try:
            writer = csv.writer(
                open(fname, 'wb+'),
                quotechar=self.get_quotechar(),
                delimiter=self.get_delimiter())
            if self.add_field_names.get_active():
                writer.writerow(fields)
            for line in data:
                row = []
                for val in line:
                    if isinstance(type(val), types.StringType):
                        val = val.replace('\n', ' ').replace('\t', ' ')
                        val = val.encode(encoding)
                    row.append(val)
                writer.writerow(row)
            if popup:
                if len(data) == 1:
                    common.message(_('%d record saved.') % len(data))
                else:
                    common.message(_('%d records saved.') % len(data))
            return True
        except IOError, exception:
            common.warning(_("Operation failed.\nError message:\n%s")
                % exception, _('Error'))
            return False

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
