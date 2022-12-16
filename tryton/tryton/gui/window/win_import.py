# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gtk
import gobject
import gettext
import tryton.common as common
import csv
from tryton.config import TRYTON_ICON, CONFIG
from tryton.common import RPCExecute, RPCException
from tryton.gui.window.nomodal import NoModal

_ = gettext.gettext


class WinImport(NoModal):
    "Window import"

    def __init__(self, model, context):
        super(WinImport, self).__init__()
        self.dialog = gtk.Dialog(title=_("Import from CSV"),
            parent=self.parent, flags=gtk.DIALOG_DESTROY_WITH_PARENT)
        self.dialog.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        self.dialog.set_icon(TRYTON_ICON)
        self.dialog.connect('response', self.response)

        dialog_vbox = gtk.VBox()
        hbox_mapping = gtk.HBox(True)
        dialog_vbox.pack_start(hbox_mapping, True, True, 0)

        frame_fields = gtk.Frame()
        frame_fields.set_shadow_type(gtk.SHADOW_NONE)
        viewport_fields = gtk.Viewport()
        scrolledwindow_fields = gtk.ScrolledWindow()
        scrolledwindow_fields.set_policy(gtk.POLICY_AUTOMATIC,
                gtk.POLICY_AUTOMATIC)
        viewport_fields.add(scrolledwindow_fields)
        frame_fields.add(viewport_fields)
        label_all_fields = gtk.Label(_("<b>All fields</b>"))
        label_all_fields.set_use_markup(True)
        frame_fields.set_label_widget(label_all_fields)
        hbox_mapping.pack_start(frame_fields, True, True, 0)

        vbox_buttons = gtk.VBox()
        vbox_buttons.set_border_width(5)
        hbox_mapping.pack_start(vbox_buttons, False, True, 0)

        button_add = gtk.Button(_("_Add"), stock=None, use_underline=True)
        button_add.set_alignment(0.0, 0.0)
        img_button = gtk.Image()
        img_button.set_from_stock('tryton-list-add', gtk.ICON_SIZE_BUTTON)
        button_add.set_image(img_button)
        button_add.connect_after('clicked', self.sig_sel)
        vbox_buttons.pack_start(button_add, False, False, 0)

        button_remove = gtk.Button(_("_Remove"), stock=None,
                use_underline=True)
        button_remove.set_alignment(0.0, 0.0)
        img_button = gtk.Image()
        img_button.set_from_stock('tryton-list-remove', gtk.ICON_SIZE_BUTTON)
        button_remove.set_image(img_button)
        button_remove.connect_after('clicked', self.sig_unsel)
        vbox_buttons.pack_start(button_remove, False, False, 0)

        button_remove_all = gtk.Button(_("Clear"), stock=None,
                use_underline=True)
        button_remove_all.set_alignment(0.0, 0.0)
        img_button = gtk.Image()
        img_button.set_from_stock('tryton-clear', gtk.ICON_SIZE_BUTTON)
        button_remove_all.set_image(img_button)
        button_remove_all.connect_after('clicked', self.sig_unsel_all)
        vbox_buttons.pack_start(button_remove_all, False, False, 0)

        hseparator_buttons = gtk.HSeparator()
        vbox_buttons.pack_start(hseparator_buttons, False, False, 3)

        button_autodetect = gtk.Button(_("Auto-Detect"), stock=None,
                use_underline=True)
        button_autodetect.set_alignment(0.0, 0.0)
        img_button = gtk.Image()
        img_button.set_from_stock('tryton-find', gtk.ICON_SIZE_BUTTON)
        button_autodetect.set_image(img_button)
        button_autodetect.connect_after('clicked', self.sig_autodetect)
        vbox_buttons.pack_start(button_autodetect, False, False, 0)

        frame_import = gtk.Frame()
        frame_import.set_shadow_type(gtk.SHADOW_NONE)
        viewport_import = gtk.Viewport()
        scrolledwindow_import = gtk.ScrolledWindow()
        scrolledwindow_import.set_policy(gtk.POLICY_AUTOMATIC,
                gtk.POLICY_AUTOMATIC)
        viewport_import.add(scrolledwindow_import)
        frame_import.add(viewport_import)
        label_fields_import = gtk.Label(_("<b>Fields to import</b>"))
        label_fields_import.set_use_markup(True)
        frame_import.set_label_widget(label_fields_import)
        hbox_mapping.pack_start(frame_import, True, True, 0)

        frame_csv_param = gtk.Frame(None)
        frame_csv_param.set_shadow_type(gtk.SHADOW_ETCHED_OUT)
        dialog_vbox.pack_start(frame_csv_param, False, True, 0)
        alignment_csv_param = gtk.Alignment(0.5, 0.5, 1, 1)
        alignment_csv_param.set_padding(7, 7, 7, 7)
        frame_csv_param.add(alignment_csv_param)

        vbox_csv_param = gtk.VBox()
        alignment_csv_param.add(vbox_csv_param)
        hbox_csv_import = gtk.HBox()
        vbox_csv_param.pack_start(hbox_csv_import, False, True, 4)
        label_csv_import = gtk.Label(_("File to Import:"))
        hbox_csv_import.pack_start(label_csv_import, False, False, 0)
        self.import_csv_file = gtk.FileChooserButton(_("Open..."))
        hbox_csv_import.pack_start(self.import_csv_file, True, True, 0)

        expander_csv_import = gtk.Expander(None)
        vbox_csv_param.pack_start(expander_csv_import, False, True, 0)
        label_import_csv_param = gtk.Label(_("CSV Parameters"))
        expander_csv_import.set_label_widget(label_import_csv_param)
        table = gtk.Table(2, 4, False)
        table.set_border_width(8)
        table.set_row_spacings(9)
        table.set_col_spacings(8)
        expander_csv_import.add(table)

        label_import_csv_sep = gtk.Label(_("Field Separator:"))
        label_import_csv_sep.set_alignment(1, 0.5)
        table.attach(label_import_csv_sep, 0, 1, 0, 1)
        self.import_csv_sep = gtk.Entry()
        self.import_csv_sep.set_max_length(1)
        self.import_csv_sep.set_text(",")
        self.import_csv_sep.set_width_chars(1)
        table.attach(self.import_csv_sep, 1, 2, 0, 1)

        label_import_csv_del = gtk.Label(_("Text Delimiter:"))
        label_import_csv_del.set_alignment(1, 0.5)
        table.attach(label_import_csv_del, 2, 3, 0, 1)
        self.import_csv_del = gtk.Entry()
        self.import_csv_del.set_text("\"")
        self.import_csv_del.set_width_chars(1)
        table.attach(self.import_csv_del, 3, 4, 0, 1)

        label_import_csv_enc = gtk.Label(_("Encoding:"))
        label_import_csv_enc.set_alignment(1, 0.5)
        table.attach(label_import_csv_enc, 0, 1, 1, 2)
        self.import_csv_enc = gtk.combo_box_new_text()
        self.import_csv_enc.append_text("UTF-8")
        self.import_csv_enc.append_text("Latin1")
        self.import_csv_enc.set_active(0)
        table.attach(self.import_csv_enc, 1, 2, 1, 2)

        label_import_csv_skip = gtk.Label(_("Lines to Skip:"))
        label_import_csv_skip.set_alignment(1, 0.5)
        table.attach(label_import_csv_skip, 2, 3, 1, 2)

        self.import_csv_skip_adj = gtk.Adjustment(0, 0, 100, 1, 10)
        self.import_csv_skip = gtk.SpinButton(self.import_csv_skip_adj, 1, 0)
        table.attach(self.import_csv_skip, 3, 4, 1, 2)

        button_cancel = gtk.Button("gtk-cancel", stock="gtk-cancel")
        self.dialog.add_action_widget(button_cancel, gtk.RESPONSE_CANCEL)
        button_cancel.set_flags(gtk.CAN_DEFAULT)

        button_ok = gtk.Button("gtk-ok", stock="gtk-ok")
        self.dialog.add_action_widget(button_ok, gtk.RESPONSE_OK)
        button_ok.set_flags(gtk.CAN_DEFAULT)

        self.dialog.vbox.pack_start(dialog_vbox)

        self.model = model
        self.context = context
        self.fields_data = {}

        self.import_csv_file.set_current_folder(CONFIG['client.default_path'])

        self.view1 = gtk.TreeView()
        self.view1.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self.view1.connect('row-expanded', self.on_row_expanded)
        scrolledwindow_fields.add(self.view1)
        self.view2 = gtk.TreeView()
        self.view2.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        scrolledwindow_import.add(self.view2)
        self.view1.set_headers_visible(False)
        self.view2.set_headers_visible(False)

        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn(_('Field name'), cell, text=0,
                background=2)
        self.view1.append_column(column)

        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn(_('Field name'), cell, text=0)
        self.view2.append_column(column)

        self.model1 = gtk.TreeStore(gobject.TYPE_STRING, gobject.TYPE_STRING,
                gobject.TYPE_STRING)
        self.model2 = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING)

        self.fields = {}
        self.fields_invert = {}

        self.model_populate(self._get_fields(model))

        self.view1.set_model(self.model1)
        self.view2.set_model(self.model2)

        sensible_allocation = self.sensible_widget.get_allocation()
        self.dialog.set_default_size(int(sensible_allocation.width * 0.9),
            int(sensible_allocation.height * 0.9))
        self.dialog.show_all()
        common.center_window(self.dialog, self.parent, self.sensible_widget)

        self.register()

    def model_populate(self, fields, parent_node=None, prefix_field='',
            prefix_name=''):
        fields_order = fields.keys()
        fields_order.sort(lambda x, y: -cmp(fields[x].get('string', ''),
                fields[y].get('string', '')))
        for field in fields_order:
            if not fields[field].get('readonly', False):
                self.fields_data[prefix_field + field] = fields[field]
                name = fields[field]['string'] or field
                node = self.model1.insert(parent_node, 0, [name, prefix_field +
                    field, (fields[field].get('required', False) and
                        common.COLORS['required']) or 'white'])
                name = prefix_name + name
                self.fields[prefix_field + field] = (name,
                        fields[field].get('relation'))
                self.fields_invert[name] = prefix_field + field
                if fields[field].get('relation'):
                    self.model1.insert(node, 0, [None, '', 'white'])

    def _get_fields(self, model):
        try:
            return RPCExecute('model', model, 'fields_get', None,
                context=self.context)
        except RPCException:
            return ''

    def on_row_expanded(self, treeview, iter, path):
        child = self.model1.iter_children(iter)
        # autodetect could call for node without children
        if child is None:
            return
        if self.model1.get_value(child, 0) is None:
            prefix_field = self.model1.get_value(iter, 1)
            name, model = self.fields[prefix_field]
            self.model_populate(self._get_fields(model), iter, prefix_field +
                    '/', name + '/')
            self.model1.remove(child)

    def sig_autodetect(self, widget=None):
        fname = self.import_csv_file.get_filename()
        if not fname:
            common.message(_('You must select an import file first!'))
            return True
        csvsep = self.import_csv_sep.get_text() or None
        csvdel = self.import_csv_del.get_text() or None
        csvcode = self.import_csv_enc.get_active_text() or 'UTF-8'

        self.import_csv_skip.set_value(1)
        try:
            data = csv.reader(open(fname, 'rb'), quotechar=csvdel,
                    delimiter=csvsep)
        except IOError:
            common.warning(_('Error opening CSV file'), _('Error'))
            return True
        self.sig_unsel_all()
        word = ''
        for line in data:
            for word in line:
                word = word.decode(csvcode)
                if word not in self.fields_invert and word not in self.fields:
                    iter = self.model1.get_iter_first()
                    prefix = ''
                    for parent in word.split('/')[:-1]:
                        while iter:
                            if self.model1.get_value(iter, 0) == parent or \
                                    self.model1.get_value(iter, 1) == \
                                    (prefix + parent):
                                self.on_row_expanded(self.view1, iter,
                                        self.model1.get_path(iter))
                                break
                            iter = self.model1.iter_next(iter)
                        prefix = parent + '/'
                if word in self.fields_invert:
                    name = word
                    field = self.fields_invert[word]
                elif word in self.fields:
                    name = self.fields[word][0]
                    field = word
                else:
                    common.warning(_('Error processing the file at field %s.')
                        % word, _('Error'))
                    return True
                num = self.model2.append()
                self.model2.set(num, 0, name, 1, field)
            break
        return True

    def sig_sel(self, widget=None):
        sel = self.view1.get_selection()
        sel.selected_foreach(self._sig_sel_add)

    def _sig_sel_add(self, store, path, iter):
        num = self.model2.append()
        name = self.fields[store.get_value(iter, 1)][0]
        self.model2.set(num, 0, name, 1, store.get_value(iter, 1))

    def sig_unsel(self, widget=None):
        store, paths = self.view2.get_selection().get_selected_rows()
        while paths:
            store.remove(store.get_iter(paths[0]))
            store, paths = self.view2.get_selection().get_selected_rows()

    def sig_unsel_all(self, widget=None):
        self.model2.clear()

    def destroy(self):
        super(WinImport, self).destroy()
        self.dialog.destroy()

    def show(self):
        self.dialog.show()

    def hide(self):
        self.dialog.hide()

    def response(self, dialog, response):
        if response == gtk.RESPONSE_OK:
            fields = []
            iter = self.model2.get_iter_root()
            while iter:
                fields.append(self.model2.get_value(iter, 1))
                iter = self.model2.iter_next(iter)

            csv_data = {
                'fname': self.import_csv_file.get_filename(),
                'sep': self.import_csv_sep.get_text(),
                'del': self.import_csv_del.get_text(),
                'skip': self.import_csv_skip.get_value(),
                'combo': self.import_csv_enc.get_active_text() or 'UTF-8'
            }
            self.destroy()
            if csv_data['fname']:
                self.import_csv(csv_data, fields, self.model)
        else:
            self.destroy()

    def import_csv(self, csv_data, fields, model):
        # TODO: make it works with references
        fname = csv_data['fname']
        data = list(csv.reader(open(fname, 'rb'), quotechar=csv_data['del'],
            delimiter=csv_data['sep']))[int(csv_data['skip']):]
        datas = []

        for line in data:
            if not line:
                continue
            datas.append([x.decode(csv_data['combo']).encode('utf-8')
                    for x in line])
        try:
            count = RPCExecute('model', model, 'import_data', fields, datas,
                context=self.context)
        except RPCException:
            return
        if count == 1:
            common.message(_('%d record imported!') % count)
        else:
            common.message(_('%d records imported!') % count)
