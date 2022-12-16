#This file is part of Tryton.  The COPYRIGHT file at the top level of this
#repository contains the full copyright notices and license terms.
import gtk
import gobject
import gettext
import tryton.common as common
import tryton.rpc as rpc
import types
from tryton.config import TRYTON_ICON
import csv
import tempfile
import os

_ = gettext.gettext


class WinExport(object):
    "Window export"

    def __init__(self, model, ids, parent, context=None):
        self.dialog = gtk.Dialog(
                title= _("Export to CSV"),
                parent=parent,
                flags=gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT
                | gtk.WIN_POS_CENTER_ON_PARENT)
        self.dialog.set_icon(TRYTON_ICON)

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
        button_select.connect_after('clicked',  self.sig_sel)
        vbox_buttons.pack_start(button_select, False, False, 0)

        button_unselect = gtk.Button(_("_Remove"), stock=None,
                use_underline=True)
        button_unselect.set_alignment(0.0, 0.0)
        img_button = gtk.Image()
        img_button.set_from_stock('tryton-list-remove', gtk.ICON_SIZE_BUTTON)
        button_unselect.set_image(img_button)
        button_unselect.connect_after('clicked',  self.sig_unsel)
        vbox_buttons.pack_start(button_unselect, False, False, 0)

        button_unselect_all = gtk.Button(_("Clear"), stock=None,
                use_underline=True)
        button_unselect_all.set_alignment(0.0, 0.0)
        img_button = gtk.Image()
        img_button.set_from_stock('tryton-clear', gtk.ICON_SIZE_BUTTON)
        button_unselect_all.set_image(img_button)
        button_unselect_all.connect_after('clicked',  self.sig_unsel_all)
        vbox_buttons.pack_start(button_unselect_all, False, False, 0)

        hseparator_buttons = gtk.HSeparator()
        vbox_buttons.pack_start(hseparator_buttons, False, True, 0)

        button_save_export = gtk.Button(_("Save Export"), stock=None,
                use_underline=True)
        button_save_export.set_alignment(0.0, 0.0)
        img_button = gtk.Image()
        img_button.set_from_stock('tryton-save', gtk.ICON_SIZE_BUTTON)
        button_save_export.set_image(img_button)
        button_save_export.connect_after('clicked',  self.add_predef)
        vbox_buttons.pack_start(button_save_export, False, False, 0)

        button_del_export = gtk.Button(_("Delete Export"), stock=None,
                use_underline=True)
        button_del_export.set_alignment(0.0, 0.0)
        img_button = gtk.Image()
        img_button.set_from_stock('tryton-delete', gtk.ICON_SIZE_BUTTON)
        button_del_export.set_image(img_button)
        button_del_export.connect_after('clicked',  self.remove_predef)
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
        self.dialog.show_all()

        self.ids = ids
        self.model = model
        self.fields_data = {}
        self.context = context

        self.parent = parent

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
        self.view2.set_model(self.model2)
        self.view1.show_all()
        self.view2.show_all()

        self.wid_action = combo_saveas
        self.wid_write_field_names = checkbox_add_field_names
        self.wid_action.set_active(0)

        # Creating the predefined export view
        self.pref_export = gtk.TreeView()
        self.pref_export.append_column(gtk.TreeViewColumn(_('Name'),
            gtk.CellRendererText(), text=2))
        scrolledwindow_exports.add(self.pref_export)

        self.pref_export.connect("row-activated", self.sel_predef)

        # Fill the predefined export tree view and show everything
        self.predef_model = gtk.ListStore(
                gobject.TYPE_INT,
                gobject.TYPE_PYOBJECT,
                gobject.TYPE_STRING)
        self.fill_predefwin()
        self.pref_export.show_all()

    def model_populate(self, fields, parent_node=None, prefix_field='',
            prefix_name=''):
        fields_order = fields.keys()
        fields_order.sort(lambda x, y: -cmp(fields[x].get('string', ''),
            fields[y].get('string', '')))
        for field in fields_order:
            self.fields_data[prefix_field + field] = fields[field]
            name = fields[field]['string'] or field
            if prefix_field:
                self.fields_data[prefix_field + field]['string'] = '%s%s' % \
                    (prefix_name, self.fields_data[prefix_field +
                        field]['string'])
            node = self.model1.insert(parent_node, 0, [name, prefix_field +
                field, (fields[field].get('required', False) and
                    common.COLORS['required']) or 'white'])
            self.fields[prefix_field + field] = (name,
                    fields[field].get('relation'))
            if fields[field].get('relation'):
                self.model1.insert(node, 0, [None, '', 'white'])

    def _get_fields(self, model):
        args = ('model', model, 'fields_get', None, rpc.CONTEXT)
        try:
            return rpc.execute(*args)
        except Exception, exception:
            return common.process_exception(exception, self.parent, *args)

    def on_row_expanded(self, treeview, iter, path):
        child = self.model1.iter_children(iter)
        if self.model1.get_value(child, 0) is None:
            prefix_field = self.model1.get_value(iter, 1)
            _, model = self.fields[prefix_field]
            name = self.fields_data[prefix_field]['string']
            self.model_populate(self._get_fields(model), iter, prefix_field +
                    '/', name + '/')
            self.model1.remove(child)

    def sig_sel(self, widget=None):
        sel = self.view1.get_selection()
        sel.selected_foreach(self._sig_sel_add)

    def _sig_sel_add(self, store, path, iter):
        relation = self.fields[store.get_value(iter, 1)][1]
        if relation:
            return
        num = self.model2.append()
        name = self.fields_data[store.get_value(iter, 1)]['string']
        self.model2.set(num, 0, name, 1, store.get_value(iter, 1))

    def sig_unsel(self, widget=None):
        store, paths = self.view2.get_selection().get_selected_rows()
        while paths:
            store.remove(store.get_iter(paths[0]))
            store, paths = self.view2.get_selection().get_selected_rows()

    def sig_unsel_all(self, widget=None):
        self.model2.clear()

    def fill_predefwin(self):
        args = ('model', 'ir.export', 'search',
                [('resource', '=', self.model)], 0, None, None, rpc.CONTEXT)
        try:
            export_ids = rpc.execute(*args)
        except Exception, exception:
            export_ids = common.process_exception(exception, self.parent,
                    *args)
            if not export_ids:
                return
        args = ('model', 'ir.export', 'read', export_ids, None, rpc.CONTEXT)
        try:
            exports = rpc.execute(*args)
        except Exception, exception:
            exports = common.process_exception(exception, self.parent, *args)
            if not exports:
                return
        args = ('model', 'ir.export.line', 'read',
                sum((x['export_fields'] for x in exports), []), None,
                rpc.CONTEXT)
        try:
            lines = rpc.execute(*args)
        except Exception, exception:
            lines = common.process_exception(exception, self.parent, *args)
            if not lines:
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

    def add_predef(self, widget):
        name = common.ask(_('What is the name of this export?'), self.parent)
        if not name:
            return
        iter = self.model2.get_iter_root()
        fields = []
        while iter:
            field_name = self.model2.get_value(iter, 1)
            fields.append(field_name)
            iter = self.model2.iter_next(iter)
        args = ('model', 'ir.export', 'create', {
            'name': name,
            'resource': self.model,
            'export_fields': [('create', {
                'name': x,
                }) for x in fields],
            }, rpc.CONTEXT)
        try:
            new_id = rpc.execute(*args)
        except Exception, exception:
            new_ids = common.process_exception(exception, self.dialog, *args)
            if not new_id:
                return
        self.predef_model.append((
            new_id,
            fields,
            name))
        self.pref_export.set_model(self.predef_model)

    def remove_predef(self, widget):
        sel = self.pref_export.get_selection().get_selected()
        if sel is None:
            return None
        (model, i) = sel
        if not i:
            return None
        export_id = model.get_value(i, 0)
        args = ('model', 'ir.export', 'delete', export_id, rpc.CONTEXT)
        try:
            rpc.execute(*args)
        except Exception, exception:
            if not common.process_exception(exception, self.dialog, *args):
                return
        for i in range(len(self.predef_model)):
            if self.predef_model[i][0] == export_id:
                del self.predef_model[i]
                break
        self.pref_export.set_model(self.predef_model)

    def sel_predef(self, widget, path, column):
        self.model2.clear()
        for field in self.predef_model[path[0]][1]:
            if field not in self.fields_data:
                iter = self.model1.get_iter_first()
                prefix = ''
                for parent in field.split('/')[:-1]:
                    while iter:
                        if self.model1.get_value(iter, 1) == \
                                (prefix + parent):
                            self.on_row_expanded(self.view1, iter,
                                    self.model1.get_path(iter))
                            iter = self.model1.iter_children(iter)
                            prefix = parent + '/'
                            break
                        else:
                            iter = self.model1.iter_next(iter)

            if field not in self.fields_data:
                continue
            self.model2.append((self.fields_data[field]['string'], field))

    def run(self):
        button = self.dialog.run()
        if button == gtk.RESPONSE_OK:
            fields = []
            fields2 = []
            iter = self.model2.get_iter_root()
            while iter:
                fields.append(self.model2.get_value(iter, 1))
                fields2.append(self.model2.get_value(iter, 0))
                iter = self.model2.iter_next(iter)
            action = self.wid_action.get_active()
            self.parent.present()
            self.dialog.destroy()
            result = self.datas_read(self.ids, self.model, fields,
                    context=self.context)

            if action == 0:
                fileno, fname = tempfile.mkstemp('.csv', 'tryton_')
                self.export_csv(fname, fields2, result,
                        self.wid_write_field_names.get_active(), popup=False)
                os.close(fileno)
                common.file_open(fname, 'csv', self.parent)
            else:
                fname = common.file_selection(_('Save As...'),
                        parent=self.parent,
                        action=gtk.FILE_CHOOSER_ACTION_SAVE)
                if fname:
                    self.export_csv(fname, fields2, result,
                            self.wid_write_field_names.get_active())
            return True
        else:
            self.parent.present()
            self.dialog.destroy()
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
                    if type(val) == types.StringType:
                        row.append(val.replace('\n',' ').replace('\t',' '))
                    else:
                        row.append(val)
                writer.writerow(row)
            file_p.close()
            if popup:
                if len(result) == 1:
                    common.message(_('%d record saved!') % len(result),
                            self.parent)
                else:
                    common.message(_('%d records saved!') % len(result),
                            self.parent)
            return True
        except Exception, exception:
            common.warning(_("Operation failed!\nError message:\n%s") \
                     % (exception[0],), self.parent, _('Error'))
            return False

    def datas_read(self, ids, model, fields, context=None):
        if context is None:
            context = {}
        ctx = context.copy()
        ctx.update(rpc.CONTEXT)
        try:
            datas = rpc.execute('model', model,
                    'export_data', ids, fields, ctx)
        except Exception, exception:
            common.process_exception(exception, self.dialog)
            return []
        return datas
