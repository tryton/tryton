# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import locale
import os
import sys
import gettext

from gi.repository import Gdk, GObject, Gtk

from tryton.common import IconFactory
from tryton.common.underline import set_underline
from tryton.config import TRYTON_ICON
from tryton.gui import Main
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

        self.dialog = Gtk.Dialog(
            transient_for=self.parent, destroy_with_parent=True)
        Main().add_window(self.dialog)
        self.dialog.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        self.dialog.set_icon(TRYTON_ICON)
        self.dialog.set_default_size(*self.default_size())
        self.dialog.connect('response', self.response)

        dialog_vbox = Gtk.VBox()

        hbox_mapping = Gtk.HBox(homogeneous=True)
        dialog_vbox.pack_start(hbox_mapping, expand=True, fill=True, padding=0)

        frame_fields = Gtk.Frame()
        frame_fields.set_shadow_type(Gtk.ShadowType.NONE)
        viewport_fields = Gtk.Viewport()
        scrolledwindow_fields = Gtk.ScrolledWindow()
        scrolledwindow_fields.set_policy(
            Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        viewport_fields.add(scrolledwindow_fields)
        frame_fields.add(viewport_fields)
        label_all_fields = Gtk.Label(
            label=_('<b>All fields</b>'), use_markup=True)
        frame_fields.set_label_widget(label_all_fields)
        hbox_mapping.pack_start(
            frame_fields, expand=True, fill=True, padding=0)

        vbox_buttons = Gtk.VBox(homogeneous=False, spacing=10)
        vbox_buttons.set_border_width(5)
        hbox_mapping.pack_start(
            vbox_buttons, expand=False, fill=True, padding=0)

        button_add = Gtk.Button(
            label=_('_Add'), stock=None, use_underline=True)
        button_add.set_image(IconFactory.get_image(
                'tryton-add', Gtk.IconSize.BUTTON))
        button_add.set_always_show_image(True)
        button_add.connect_after('clicked', self.sig_sel)
        vbox_buttons.pack_start(
            button_add, expand=False, fill=False, padding=0)

        button_remove = Gtk.Button(
            label=_('_Remove'), stock=None, use_underline=True)
        button_remove.set_image(IconFactory.get_image(
                'tryton-remove', Gtk.IconSize.BUTTON))
        button_remove.set_always_show_image(True)
        button_remove.connect_after('clicked', self.sig_unsel)
        vbox_buttons.pack_start(
            button_remove, expand=False, fill=False, padding=0)

        button_remove_all = Gtk.Button(
            label=_('_Clear'), stock=None, use_underline=True)
        button_remove_all.set_image(IconFactory.get_image(
                'tryton-clear', Gtk.IconSize.BUTTON))
        button_remove_all.set_always_show_image(True)
        button_remove_all.connect_after('clicked', self.sig_unsel_all)
        vbox_buttons.pack_start(
            button_remove_all, expand=False, fill=False, padding=0)

        hseparator_buttons = Gtk.HSeparator()
        vbox_buttons.pack_start(
            hseparator_buttons, expand=False, fill=False, padding=3)

        self.add_buttons(vbox_buttons)

        frame_fields_selected = Gtk.Frame()
        frame_fields_selected.set_shadow_type(Gtk.ShadowType.NONE)
        viewport_fields_selected = Gtk.Viewport()
        scrolledwindow_fields_selected = Gtk.ScrolledWindow()
        scrolledwindow_fields_selected.set_policy(
            Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        viewport_fields_selected.add(scrolledwindow_fields_selected)
        frame_fields_selected.add(viewport_fields_selected)
        label_fields_selected = Gtk.Label(
            label=_('<b>Fields selected</b>'), use_markup=True)
        frame_fields_selected.set_label_widget(label_fields_selected)
        hbox_mapping.pack_start(
            frame_fields_selected, expand=True, fill=True, padding=0)

        vbox_csv_param = Gtk.VBox()
        vbox_csv_param.props.margin = 7
        dialog_vbox.pack_start(
            vbox_csv_param, expand=False, fill=True, padding=0)

        self.add_chooser(vbox_csv_param)

        expander_csv = Gtk.Expander()
        vbox_csv_param.pack_start(
            expander_csv, expand=False, fill=True, padding=0)
        label_csv_param = Gtk.Label(label=_('CSV Parameters'))
        expander_csv.set_label_widget(label_csv_param)

        box = Gtk.HBox(spacing=3)
        expander_csv.add(box)

        label_csv_delimiter = Gtk.Label(
            label=_('Delimiter:'), halign=Gtk.Align.END)
        box.pack_start(label_csv_delimiter, expand=False, fill=True, padding=0)
        self.csv_delimiter = Gtk.Entry()
        self.csv_delimiter.set_max_length(1)
        if os.name == 'nt' and ',' == locale.localeconv()['decimal_point']:
            delimiter = ';'
        else:
            delimiter = ','
        self.csv_delimiter.set_text(delimiter)
        self.csv_delimiter.set_width_chars(1)
        label_csv_delimiter.set_mnemonic_widget(self.csv_delimiter)
        box.pack_start(
            self.csv_delimiter, expand=False, fill=True, padding=0)

        label_csv_quotechar = Gtk.Label(
            label=_("Quote char:"), halign=Gtk.Align.END)
        box.pack_start(label_csv_quotechar, expand=False, fill=True, padding=0)
        self.csv_quotechar = Gtk.Entry()
        self.csv_quotechar.set_text("\"")
        self.csv_quotechar.set_width_chars(1)
        label_csv_quotechar.set_mnemonic_widget(self.csv_quotechar)
        box.pack_start(self.csv_quotechar, expand=False, fill=True, padding=0)

        label_csv_enc = Gtk.Label(
            label=_("Encoding:"), halign=Gtk.Align.END)
        box.pack_start(label_csv_enc, expand=False, fill=True, padding=0)
        self.csv_enc = Gtk.ComboBoxText()
        for i, encoding in enumerate(encodings):
            self.csv_enc.append_text(encoding)
            if ((os.name == 'nt' and encoding == 'cp1252')
                    or (os.name != 'nt' and encoding == 'utf_8')):
                self.csv_enc.set_active(i)
        label_csv_enc.set_mnemonic_widget(self.csv_enc)
        box.pack_start(self.csv_enc, expand=False, fill=True, padding=0)

        self.csv_locale = Gtk.CheckButton(label=_("Use locale format"))
        self.csv_locale.set_active(True)
        box.pack_start(self.csv_locale, expand=False, fill=True, padding=0)

        self.add_csv_header_param(box)

        button_cancel = self.dialog.add_button(
            set_underline(_("Cancel")), Gtk.ResponseType.CANCEL)
        button_cancel.set_image(IconFactory.get_image(
                'tryton-cancel', Gtk.IconSize.BUTTON))

        button_ok = self.dialog.add_button(
            set_underline(_("OK")), Gtk.ResponseType.OK)
        button_ok.set_image(IconFactory.get_image(
                'tryton-ok', Gtk.IconSize.BUTTON))

        self.dialog.vbox.pack_start(
            dialog_vbox, expand=True, fill=True, padding=0)

        self.view1 = Gtk.TreeView()
        self.view1.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)
        self.view1.connect('row-expanded', self.on_row_expanded)
        scrolledwindow_fields.add(self.view1)
        self.view2 = Gtk.TreeView()
        self.view2.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)
        scrolledwindow_fields_selected.add(self.view2)
        self.view1.set_headers_visible(False)
        self.view2.set_headers_visible(False)

        cell = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn(_('Field name'), cell, text=0)
        self.view1.append_column(column)

        cell = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn(_('Field name'), cell, text=0)
        self.view2.append_column(column)

        self.model1 = Gtk.TreeStore(GObject.TYPE_STRING, GObject.TYPE_STRING)
        self.model2 = Gtk.ListStore(GObject.TYPE_STRING, GObject.TYPE_STRING)

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
                Gdk.ModifierType.BUTTON1_MASK | Gdk.ModifierType.BUTTON3_MASK,
                [Gtk.TargetEntry.new(
                        'EXPORT_TREE', Gtk.TargetFlags.SAME_WIDGET, 0)],
                Gdk.DragAction.MOVE)
            self.view2.drag_dest_set(
                Gtk.DestDefaults.ALL,
                [Gtk.TargetEntry.new(
                        'EXPORT_TREE', Gtk.TargetFlags.SAME_WIDGET, 0)],
                Gdk.DragAction.MOVE)
            self.view2.connect('drag-begin', self.drag_begin)
            self.view2.connect('drag-motion', self.drag_motion)
            self.view2.connect('drag-drop', self.drag_drop)
            self.view2.connect("drag-data-get", self.drag_data_get)
            self.view2.connect('drag-data-received', self.drag_data_received)
            self.view2.connect('drag-data-delete', self.drag_data_delete)

            drag_column = Gtk.TreeViewColumn()
            drag_column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
            cell_pixbuf = Gtk.CellRendererPixbuf()
            cell_pixbuf.props.pixbuf = IconFactory.get_pixbuf('tryton-drag')
            drag_column.pack_start(cell_pixbuf, expand=False)
            self.view2.insert_column(drag_column, 0)

    def drag_begin(self, treeview, context):
        return True

    def drag_motion(self, treeview, context, x, y, time):
        try:
            treeview.set_drag_dest_row(*treeview.get_dest_row_at_pos(x, y))
        except TypeError:
            treeview.set_drag_dest_row(
                Gtk.TreePath(len(treeview.get_model()) - 1),
                Gtk.TreeViewDropPosition.AFTER)
        Gdk.drag_status(context, Gdk.DragAction.MOVE, time)
        return True

    def drag_drop(self, treeview, context, x, y, time):
        treeview.stop_emission_by_name('drag-drop')
        return True

    def drag_data_get(self, treeview, context, selection, target_id,
            etime):
        treeview.stop_emission_by_name('drag-data-get')

        def _func_sel_get(store, path, iter_, data):
            data.append(path[0])
        data = []
        treeselection = treeview.get_selection()
        treeselection.selected_foreach(_func_sel_get, data)
        if not data:
            return
        data = ','.join(str(x) for x in data)
        selection.set(selection.get_target(), 8, data.encode('utf-8'))
        return True

    def drag_data_received(self, treeview, context, x, y, selection,
            info, etime):
        treeview.stop_emission_by_name('drag-data-received')
        try:
            selection_data = selection.data
        except AttributeError:
            selection_data = selection.get_data()
        if not selection_data:
            return
        selection_data = selection_data.decode('utf-8')
        store = treeview.get_model()

        data_iters = [store.get_iter((int(i),))
            for i in selection_data.split(',')]
        drop_info = treeview.get_dest_row_at_pos(x, y)
        if drop_info:
            path, position = drop_info
            pos = store.get_iter(path)
        else:
            pos = store.get_iter((len(store) - 1,))
            position = Gtk.TreeViewDropPosition.AFTER
        if position == Gtk.TreeViewDropPosition.AFTER:
            data_iters = reversed(data_iters)
        for item in data_iters:
            if position == Gtk.TreeViewDropPosition.BEFORE:
                store.move_before(item, pos)
            else:
                store.move_after(item, pos)
        Gdk.drop_finish(context, False, etime)
        return True

    def drag_data_delete(self, treeview, context):
        treeview.stop_emission_by_name('drag-data-delete')

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
        self.dialog.show()

    def hide(self):
        self.dialog.hide()
