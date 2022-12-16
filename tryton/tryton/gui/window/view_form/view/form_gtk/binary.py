# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gettext
import os
from urllib.request import urlopen
from urllib.parse import urlparse, unquote

from gi.repository import Gdk, Gtk

from tryton.common import common
from tryton.common import file_selection, Tooltips, file_open, file_write
from tryton.common.entry_position import reset_position
from .widget import Widget

_ = gettext.gettext


class BinaryMixin(Widget):

    def __init__(self, view, attrs):
        super(BinaryMixin, self).__init__(view, attrs)
        self.filename = attrs.get('filename')

    def toolbar(self):
        'Return HBox with the toolbar'
        hbox = Gtk.HBox(spacing=0)
        tooltips = Tooltips()

        self.but_save_as = Gtk.Button()
        self.but_save_as.set_image(common.IconFactory.get_image(
                'tryton-save', Gtk.IconSize.SMALL_TOOLBAR))
        self.but_save_as.set_relief(Gtk.ReliefStyle.NONE)
        self.but_save_as.connect('clicked', self.save_as)
        tooltips.set_tip(self.but_save_as, _('Save As...'))
        hbox.pack_start(self.but_save_as, expand=False, fill=False, padding=0)

        self.but_select = Gtk.Button()
        self.but_select.set_image(common.IconFactory.get_image(
                'tryton-search', Gtk.IconSize.SMALL_TOOLBAR))
        self.but_select.set_relief(Gtk.ReliefStyle.NONE)
        self.but_select.connect('clicked', self.select)
        target_entry = Gtk.TargetEntry.new('text/uri-list', 0, 0)
        self.but_select.drag_dest_set(Gtk.DestDefaults.ALL, [
                target_entry,
                ],
            Gdk.DragAction.MOVE | Gdk.DragAction.COPY)
        self.but_select.connect(
            'drag-data-received', self.select_drag_data_received)
        tooltips.set_tip(self.but_select, _('Select...'))
        hbox.pack_start(self.but_select, expand=False, fill=False, padding=0)

        self.but_clear = Gtk.Button()
        self.but_clear.set_image(common.IconFactory.get_image(
                'tryton-clear', Gtk.IconSize.SMALL_TOOLBAR))
        self.but_clear.set_relief(Gtk.ReliefStyle.NONE)
        self.but_clear.connect('clicked', self.clear)
        tooltips.set_tip(self.but_clear, _('Clear'))
        hbox.pack_start(self.but_clear, expand=False, fill=False, padding=0)

        tooltips.enable()
        return hbox

    @property
    def filename_field(self):
        return self.record.group.fields.get(self.filename)

    @property
    def filters(self):
        filter_all = Gtk.FileFilter()
        filter_all.set_name(_('All files'))
        filter_all.add_pattern("*")
        return [filter_all]

    @property
    def preview(self):
        return False

    def update_buttons(self, value):
        if value:
            self.but_save_as.show()
            self.but_select.hide()
            self.but_clear.show()
        else:
            self.but_save_as.hide()
            self.but_select.show()
            self.but_clear.hide()

    def select(self, widget=None):
        if not self.field:
            return
        filename = file_selection(
            _('Select'), preview=self.preview, filters=self.filters)
        if filename:
            self._set_uri('file:///' + filename)

    def select_drag_data_received(
            self, widget, context, x, y, selection, info, timestamp):
        if not self.field:
            return
        for uri in selection.get_uris():
            self._set_uri(uri)

    def _set_uri(self, uri):
        uri = unquote(uri)
        self.field.set_client(self.record, urlopen(uri).read())
        if self.filename_field:
            self.filename_field.set_client(self.record,
                os.path.basename(urlparse(uri).path))

    def get_data(self):
        if hasattr(self.field, 'get_data'):
            data = self.field.get_data(self.record)
        else:
            data = self.field.get(self.record)
        if isinstance(data, str):
            data = data.encode('utf-8')
        return data

    def open_(self, widget=None):
        if not self.filename_field:
            return
        filename = self.filename_field.get(self.record)
        if not filename:
            return
        file_path = file_write(filename, self.get_data())
        root, type_ = os.path.splitext(filename)
        if type_:
            type_ = type_[1:]
        file_open(file_path, type_)

    def save_as(self, widget=None):
        filename = ''
        if self.filename_field:
            filename = self.filename_field.get(self.record)
        filename = file_selection(_('Save As...'), filename=filename,
            action=Gtk.FileChooserAction.SAVE)
        if filename:
            with open(filename, 'wb') as fp:
                fp.write(self.get_data())

    def clear(self, widget=None):
        if self.filename_field:
            self.filename_field.set_client(self.record, None)
        self.field.set_client(self.record, None)


class Binary(BinaryMixin, Widget):
    "Binary"

    def __init__(self, view, attrs):
        super(Binary, self).__init__(view, attrs)

        self.widget = Gtk.HBox(spacing=0)
        self.wid_size = Gtk.Entry()
        self.wid_size.set_width_chars(self.default_width_chars)
        self.wid_size.set_alignment(1.0)
        self.wid_size.props.sensitive = False
        if self.filename and attrs.get('filename_visible'):
            self.wid_text = Gtk.Entry()
            self.wid_text.set_property('activates_default', True)
            self.wid_text.connect('focus-out-event',
                lambda x, y: self._focus_out())
            self.wid_text.connect_after('key_press_event', self.sig_key_press)
            self.wid_text.connect('icon-press', self.sig_icon_press)
            self.widget.pack_start(
                self.wid_text, expand=True, fill=True, padding=0)
        else:
            self.wid_text = None
        self.mnemonic_widget = self.wid_text
        self.widget.pack_start(
            self.wid_size, expand=not self.filename, fill=True, padding=0)

        self.widget.pack_start(
            self.toolbar(), expand=False, fill=False, padding=0)

    def _readonly_set(self, value):
        self.but_select.set_sensitive(not value)
        self.but_clear.set_sensitive(not value)
        if self.wid_text:
            self.wid_text.set_editable(not value)

    def sig_key_press(self, widget, event, *args):
        editable = self.wid_text and self.wid_text.get_editable()
        if event.keyval == Gdk.KEY_F3 and editable:
            self.sig_new(widget)
            return True
        elif event.keyval == Gdk.KEY_F2:
            if self.filename:
                self.sig_open(widget)
            else:
                self.sig_save_as(widget)
            return True
        return False

    def sig_icon_press(self, widget, icon_pos, event):
        if icon_pos == Gtk.EntryIconPosition.PRIMARY:
            self.open_()

    def display(self):
        super(Binary, self).display()
        if not self.field:
            if self.wid_text:
                self.wid_text.set_text('')
            self.wid_size.set_text('')
            self.but_save_as.hide()
            return False
        if hasattr(self.field, 'get_size'):
            size = self.field.get_size(self.record)
        else:
            size = len(self.field.get(self.record))
        self.wid_size.set_text(common.humanize(size or 0))
        reset_position(self.wid_size)
        if self.wid_text:
            self.wid_text.set_text(self.filename_field.get(self.record) or '')
            reset_position(self.wid_text)
            if size:
                icon, tooltip = 'tryton-open', _("Open...")
            else:
                icon, tooltip = None, ''
            pos = Gtk.EntryIconPosition.PRIMARY
            if icon:
                pixbuf = common.IconFactory.get_pixbuf(
                    icon, Gtk.IconSize.MENU)
            else:
                pixbuf = None
            self.wid_text.set_icon_from_pixbuf(pos, pixbuf)
            self.wid_text.set_icon_tooltip_text(pos, tooltip)
        self.update_buttons(bool(size))
        return True

    def set_value(self):
        if self.wid_text:
            self.filename_field.set_client(self.record,
                    self.wid_text.get_text() or False)
        return
