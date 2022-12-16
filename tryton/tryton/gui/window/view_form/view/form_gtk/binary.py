# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gtk
import gettext
import os
import tempfile
from tryton.common import common
from tryton.common import file_selection, Tooltips, file_open, slugify
from tryton.common.entry_position import reset_position
from tryton.common.widget_style import set_widget_style
from tryton.config import CONFIG
from .widget import Widget

_ = gettext.gettext


class BinaryMixin(Widget):

    def __init__(self, view, attrs):
        super(BinaryMixin, self).__init__(view, attrs)
        self.filename = attrs.get('filename')

    def toolbar(self):
        'Return HBox with the toolbar'
        hbox = gtk.HBox(spacing=0)
        tooltips = Tooltips()

        self.but_save_as = gtk.Button()
        img_save_as = gtk.Image()
        img_save_as.set_from_stock('tryton-save-as',
            gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.but_save_as.set_image(img_save_as)
        self.but_save_as.set_relief(gtk.RELIEF_NONE)
        self.but_save_as.connect('clicked', self.save_as)
        tooltips.set_tip(self.but_save_as, _('Save As...'))
        hbox.pack_start(self.but_save_as, expand=False, fill=False)

        self.but_select = gtk.Button()
        img_select = gtk.Image()
        img_select.set_from_stock('tryton-find', gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.but_select.set_image(img_select)
        self.but_select.set_relief(gtk.RELIEF_NONE)
        self.but_select.connect('clicked', self.select)
        tooltips.set_tip(self.but_select, _('Select...'))
        hbox.pack_start(self.but_select, expand=False, fill=False)

        self.but_clear = gtk.Button()
        img_clear = gtk.Image()
        img_clear.set_from_stock('tryton-clear', gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.but_clear.set_image(img_clear)
        self.but_clear.set_relief(gtk.RELIEF_NONE)
        self.but_clear.connect('clicked', self.clear)
        tooltips.set_tip(self.but_clear, _('Clear'))
        hbox.pack_start(self.but_clear, expand=False, fill=False)

        tooltips.enable()
        return hbox

    @property
    def filename_field(self):
        return self.record.group.fields.get(self.filename)

    @property
    def filters(self):
        filter_all = gtk.FileFilter()
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
        filters = self.filters

        filename = file_selection(_('Select'), preview=self.preview,
            filters=filters)
        if filename:
            self.field.set_client(self.record, open(filename, 'rb').read())
            if self.filename_field:
                self.filename_field.set_client(self.record,
                    os.path.basename(filename))

    def open_(self, widget=None):
        if not self.filename_field:
            return
        filename = self.filename_field.get(self.record)
        if not filename:
            return
        dtemp = tempfile.mkdtemp(prefix='tryton_')
        root, ext = os.path.splitext(filename)
        filename = ''.join([slugify(root), os.extsep, slugify(ext)])
        file_path = os.path.join(dtemp, filename)
        with open(file_path, 'wb') as fp:
            if hasattr(self.field, 'get_data'):
                fp.write(self.field.get_data(self.record))
            else:
                fp.write(self.field.get(self.record))
        root, type_ = os.path.splitext(filename)
        if type_:
            type_ = type_[1:]
        file_open(file_path, type_)

    def save_as(self, widget=None):
        filename = ''
        if self.filename_field:
            filename = self.filename_field.get(self.record)
        filename = file_selection(_('Save As...'), filename=filename,
            action=gtk.FILE_CHOOSER_ACTION_SAVE)
        if filename:
            with open(filename, 'wb') as fp:
                if hasattr(self.field, 'get_data'):
                    fp.write(self.field.get_data(self.record))
                else:
                    fp.write(self.field.get(self.record))

    def clear(self, widget=None):
        if self.filename_field:
            self.filename_field.set_client(self.record, None)
        self.field.set_client(self.record, None)


class Binary(BinaryMixin, Widget):
    "Binary"

    def __init__(self, view, attrs):
        super(Binary, self).__init__(view, attrs)

        self.widget = gtk.HBox(spacing=0)
        self.wid_size = gtk.Entry()
        self.wid_size.set_width_chars(10)
        self.wid_size.set_alignment(1.0)
        self.wid_size.props.sensitive = False
        if self.filename and attrs.get('filename_visible'):
            self.wid_text = gtk.Entry()
            self.wid_text.set_property('activates_default', True)
            self.wid_text.connect('focus-out-event',
                lambda x, y: self._focus_out())
            self.wid_text.connect_after('key_press_event', self.sig_key_press)
            self.wid_text.connect('icon-press', self.sig_icon_press)
            self.widget.pack_start(self.wid_text, expand=True, fill=True)
        else:
            self.wid_text = None
        self.mnemonic_widget = self.wid_text
        self.widget.pack_start(self.wid_size, expand=not self.filename,
            fill=True)

        self.widget.pack_start(self.toolbar(), expand=False, fill=False)

    def _readonly_set(self, value):
        self.but_select.set_sensitive(not value)
        self.but_clear.set_sensitive(not value)
        if self.wid_text:
            self.wid_text.set_editable(not value)
            set_widget_style(self.wid_text, not value)
        if value and CONFIG['client.fast_tabbing']:
            self.widget.set_focus_chain([])
        else:
            self.widget.unset_focus_chain()

    def sig_key_press(self, widget, event, *args):
        editable = self.wid_text and self.wid_text.get_editable()
        if event.keyval == gtk.keysyms.F3 and editable:
            self.sig_new(widget)
            return True
        elif event.keyval == gtk.keysyms.F2:
            if self.filename:
                self.sig_open(widget)
            else:
                self.sig_save_as(widget)
            return True
        return False

    def sig_icon_press(self, widget, icon_pos, event):
        if icon_pos == gtk.ENTRY_ICON_PRIMARY:
            self.open_()

    def display(self, record, field):
        super(Binary, self).display(record, field)
        if not field:
            if self.wid_text:
                self.wid_text.set_text('')
            self.wid_size.set_text('')
            self.but_save_as.hide()
            return False
        if hasattr(field, 'get_size'):
            size = field.get_size(record)
        else:
            size = len(field.get(record))
        self.wid_size.set_text(common.humanize(size or 0))
        reset_position(self.wid_size)
        if self.wid_text:
            self.wid_text.set_text(self.filename_field.get(record) or '')
            reset_position(self.wid_text)
            if size:
                stock, tooltip = 'tryton-open', _("Open...")
            else:
                stock, tooltip = None, ''
            pos = gtk.ENTRY_ICON_PRIMARY
            self.wid_text.set_icon_from_stock(pos, stock)
            self.wid_text.set_icon_tooltip_text(pos, tooltip)
        self.update_buttons(bool(size))
        return True

    def set_value(self, record, field):
        if self.wid_text:
            self.filename_field.set_client(self.record,
                    self.wid_text.get_text() or False)
        return
