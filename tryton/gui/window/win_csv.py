# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import locale
import os
import sys

import gtk
import gobject
import gettext

from tryton.common import center_window
from tryton.config import TRYTON_ICON
from tryton.gui.window.nomodal import NoModal

_ = gettext.gettext

encodings = ["ascii", "big5", "big5hkscs", "cp037", "cp424", "cp437", "cp500",
    "cp720", "cp737", "cp775", "cp850", "cp852", "cp855", "cp856", "cp857",
    "cp858", "cp860", "cp861", "cp862", "cp863", "cp864", "cp865", "cp866",
    "cp869", "cp874", "cp875", "cp932", "cp949", "cp950", "cp1006", "cp1026",
    "cp1140", "cp1250", "cp1251", "cp1252", "cp1253", "cp1254", "cp1255",
    "cp1256", "cp1257", "cp1258", "euc_jp", "euc_jis_2004", "euc_jisx0213",
    "euc_kr", "gb2312", "gbk", "gb18030", "hz", "iso2022_jp", "iso2022_jp_1",
    "iso2022_jp_2", "iso2022_jp_2004", "iso2022_jp_3", "iso2022_jp_ext",
    "iso2022_kr", "latin_1", "iso8859_2", "iso8859_3", "iso8859_4",
    "iso8859_5", "iso8859_6", "iso8859_7", "iso8859_8", "iso8859_9",
    "iso8859_10", "iso8859_13", "iso8859_14", "iso8859_15", "iso8859_16",
    "johab", "koi8_r", "koi8_u", "mac_cyrillic", "mac_greek", "mac_iceland",
    "mac_latin2", "mac_roman", "mac_turkish", "ptcp154", "shift_jis",
    "shift_jis_2004", "shift_jisx0213", "utf_32", "utf_32_be", "utf_32_le",
    "utf_16", "utf_16_be", "utf_16_le", "utf_7", "utf_8", "utf_8_sig"]


class WinCSV(NoModal):
    def __init__(self, *args, **kwargs):
        super(WinCSV, self).__init__(*args, **kwargs)

        self.dialog = gtk.Dialog(
            parent=self.parent, flags=gtk.DIALOG_DESTROY_WITH_PARENT)
        self.dialog.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        self.dialog.set_icon(TRYTON_ICON)
        self.dialog.set_decorated(False)
        self.dialog.connect('response', self.response)

        dialog_vbox = gtk.VBox()

        self.add_header(dialog_vbox)

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
        label_all_fields = gtk.Label(_('<b>All fields</b>'))
        label_all_fields.set_use_markup(True)
        frame_fields.set_label_widget(label_all_fields)
        hbox_mapping.pack_start(frame_fields, True, True, 0)

        vbox_buttons = gtk.VBox(False, 10)
        vbox_buttons.set_border_width(5)
        hbox_mapping.pack_start(vbox_buttons, False, True, 0)

        button_add = gtk.Button(_('_Add'), stock=None, use_underline=True)
        button_add.set_alignment(0.0, 0.0)
        img_button = gtk.Image()
        img_button.set_from_stock('tryton-list-add', gtk.ICON_SIZE_BUTTON)
        button_add.set_image(img_button)
        button_add.set_always_show_image(True)
        button_add.connect_after('clicked', self.sig_sel)
        vbox_buttons.pack_start(button_add, False, False, 0)

        button_remove = gtk.Button(
            _('_Remove'), stock=None, use_underline=True)
        button_remove.set_alignment(0.0, 0.0)
        img_button = gtk.Image()
        img_button.set_from_stock('tryton-list-remove', gtk.ICON_SIZE_BUTTON)
        button_remove.set_image(img_button)
        button_remove.set_always_show_image(True)
        button_remove.connect_after('clicked', self.sig_unsel)
        vbox_buttons.pack_start(button_remove, False, False, 0)

        button_remove_all = gtk.Button(
            _('_Clear'), stock=None, use_underline=True)
        button_remove_all.set_alignment(0.0, 0.0)
        img_button = gtk.Image()
        img_button.set_from_stock('tryton-clear', gtk.ICON_SIZE_BUTTON)
        button_remove_all.set_image(img_button)
        button_remove_all.set_always_show_image(True)
        button_remove_all.connect_after('clicked', self.sig_unsel_all)
        vbox_buttons.pack_start(button_remove_all, False, False, 0)

        hseparator_buttons = gtk.HSeparator()
        vbox_buttons.pack_start(hseparator_buttons, False, False, 3)

        self.add_buttons(vbox_buttons)

        frame_fields_selected = gtk.Frame()
        frame_fields_selected.set_shadow_type(gtk.SHADOW_NONE)
        viewport_fields_selected = gtk.Viewport()
        scrolledwindow_fields_selected = gtk.ScrolledWindow()
        scrolledwindow_fields_selected.set_policy(
            gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        viewport_fields_selected.add(scrolledwindow_fields_selected)
        frame_fields_selected.add(viewport_fields_selected)
        label_fields_selected = gtk.Label(_('<b>Fields selected</b>'))
        label_fields_selected .set_use_markup(True)
        frame_fields_selected.set_label_widget(label_fields_selected)
        hbox_mapping.pack_start(frame_fields_selected, True, True, 0)

        frame_csv_param = gtk.Frame()
        frame_csv_param.set_shadow_type(gtk.SHADOW_ETCHED_OUT)
        dialog_vbox.pack_start(frame_csv_param, False, True, 0)
        alignment_csv_param = gtk.Alignment(0.5, 0.5, 1, 1)
        alignment_csv_param.set_padding(7, 7, 7, 7)
        frame_csv_param.add(alignment_csv_param)

        vbox_csv_param = gtk.VBox()
        alignment_csv_param.add(vbox_csv_param)

        self.add_chooser(vbox_csv_param)

        expander_csv = gtk.Expander()
        vbox_csv_param.pack_start(expander_csv, False, True, 0)
        label_csv_param = gtk.Label(_('CSV Parameters'))
        expander_csv.set_label_widget(label_csv_param)
        table = gtk.Table(2, 4, False)
        table.set_border_width(8)
        table.set_row_spacings(9)
        table.set_col_spacings(8)
        expander_csv.add(table)

        label_csv_delimiter = gtk.Label(_('Delimiter:'))
        label_csv_delimiter.set_alignment(1, 0.5)
        table.attach(label_csv_delimiter, 0, 1, 0, 1)
        self.csv_delimiter = gtk.Entry()
        self.csv_delimiter.set_max_length(1)
        if os.name == 'nt' and ',' == locale.localeconv()['decimal_point']:
            delimiter = ';'
        else:
            delimiter = ','
        self.csv_delimiter.set_text(delimiter)
        self.csv_delimiter.set_width_chars(1)
        label_csv_delimiter.set_mnemonic_widget(self.csv_delimiter)
        table.attach(self.csv_delimiter, 1, 2, 0, 1)

        label_csv_quotechar = gtk.Label(_("Quote char:"))
        label_csv_quotechar.set_alignment(1, 0.5)
        table.attach(label_csv_quotechar, 2, 3, 0, 1)
        self.csv_quotechar = gtk.Entry()
        self.csv_quotechar.set_text("\"")
        self.csv_quotechar.set_width_chars(1)
        label_csv_quotechar.set_mnemonic_widget(self.csv_quotechar)
        table.attach(self.csv_quotechar, 3, 4, 0, 1)

        label_csv_enc = gtk.Label(_("Encoding:"))
        label_csv_enc.set_alignment(1, 0.5)
        table.attach(label_csv_enc, 0, 1, 1, 2)
        if hasattr(gtk, 'ComboBoxText'):
            self.csv_enc = gtk.ComboBoxText()
        else:
            self.csv_enc = gtk.combo_box_new_text()
        for i, encoding in enumerate(encodings):
            self.csv_enc.append_text(encoding)
            if ((os.name == 'nt' and encoding == 'cp1252')
                    or (os.name != 'nt' and encoding == 'utf_8')):
                self.csv_enc.set_active(i)
        label_csv_enc.set_mnemonic_widget(self.csv_enc)
        table.attach(self.csv_enc, 1, 2, 1, 2)

        self.add_csv_header_param(table)

        button_cancel = gtk.Button("gtk-cancel", stock="gtk-cancel")
        self.dialog.add_action_widget(button_cancel, gtk.RESPONSE_CANCEL)

        button_ok = gtk.Button("gtk-ok", stock="gtk-ok")
        self.dialog.add_action_widget(button_ok, gtk.RESPONSE_OK)

        self.dialog.vbox.pack_start(dialog_vbox)

        self.view1 = gtk.TreeView()
        self.view1.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self.view1.connect('row-expanded', self.on_row_expanded)
        scrolledwindow_fields.add(self.view1)
        self.view2 = gtk.TreeView()
        self.view2.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        scrolledwindow_fields_selected.add(self.view2)
        self.view1.set_headers_visible(False)
        self.view2.set_headers_visible(False)

        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn(_('Field name'), cell, text=0)
        self.view1.append_column(column)

        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn(_('Field name'), cell, text=0)
        self.view2.append_column(column)

        self.model1 = gtk.TreeStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
        self.model2 = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING)

        self.model_populate(self._get_fields(self.model))

        self.view1.set_model(self.model1)
        self.view1.connect('row-activated', self.sig_sel)
        self.view2.set_model(self.model2)
        self.view2.connect('row-activated', self.sig_unsel)

        self.dialog.show_all()
        self.show()

        self.register()

        if sys.platform != 'darwin':
            self.view2.drag_source_set(
                gtk.gdk.BUTTON1_MASK | gtk.gdk.BUTTON3_MASK,
                [gtk.TargetEntry.new(
                        'EXPORT_TREE', gtk.TARGET_SAME_WIDGET, 0)],
                gtk.gdk.ACTION_MOVE)
            self.view2.drag_dest_set(gtk.DEST_DEFAULT_ALL,
                [gtk.TargetEntry.new(
                        'EXPORT_TREE', gtk.TARGET_SAME_WIDGET, 0)],
                gtk.gdk.ACTION_MOVE)
            self.view2.connect('drag-begin', self.drag_begin)
            self.view2.connect('drag-motion', self.drag_motion)
            self.view2.connect('drag-drop', self.drag_drop)
            self.view2.connect("drag-data-get", self.drag_data_get)
            self.view2.connect('drag-data-received', self.drag_data_received)
            self.view2.connect('drag-data-delete', self.drag_data_delete)

    def drag_begin(self, treeview, context):
        return True

    def drag_motion(self, treeview, context, x, y, time):
        try:
            treeview.set_drag_dest_row(*treeview.get_dest_row_at_pos(x, y))
        except TypeError:
            treeview.set_drag_dest_row(len(treeview.get_model()) - 1,
                gtk.TREE_VIEW_DROP_AFTER)
        if hasattr(gtk.gdk, 'drag_status'):
            gtk.gdk.drag_status(context, gtk.gdk.ACTION_MOVE, time)
        else:
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
        data = ','.join(str(x) for x in data)
        selection.set(selection.get_target(), 8, data)
        return True

    def drag_data_received(self, treeview, context, x, y, selection,
            info, etime):
        treeview.emit_stop_by_name('drag-data-received')
        try:
            selection_data = selection.data
        except AttributeError:
            selection_data = selection.get_data()
        if not selection_data:
            return
        store = treeview.get_model()

        data_iters = [store.get_iter((int(i),))
            for i in selection_data.split(',')]
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
        if hasattr(gtk.gdk, 'drop_finish'):
            gtk.gdk.drop_finish(context, False, etime)
        else:
            context.drop_finish(False, etime)
        return True

    def drag_data_delete(self, treeview, context):
        treeview.emit_stop_by_name('drag-data-delete')

    def get_delimiter(self):
        return self.csv_delimiter.get_text() or ','

    def get_quotechar(self):
        return self.csv_quotechar.get_text() or '"'

    def get_encoding(self):
        return self.csv_enc.get_active_text() or 'utf_8'

    def destroy(self):
        super(WinCSV, self).destroy()
        self.dialog.destroy()

    def show(self):
        sensible_allocation = self.sensible_widget.get_allocation()
        self.dialog.resize(
            sensible_allocation.width, sensible_allocation.height)
        self.dialog.show()
        gobject.idle_add(
            center_window, self.dialog, self.parent, self.sensible_widget)

    def hide(self):
        self.dialog.hide()
