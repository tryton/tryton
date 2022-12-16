# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gtk
import gettext
import os
import tempfile
from tryton.common import common
from tryton.common import file_selection, Tooltips, file_open, slugify
from .widget import Widget

_ = gettext.gettext


class Binary(Widget):
    "Binary"

    def __init__(self, view, attrs):
        super(Binary, self).__init__(view, attrs)

        self.filename = attrs.get('filename')

        self.tooltips = Tooltips()

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
            self.widget.pack_start(self.wid_text, expand=True, fill=True)
        else:
            self.wid_text = None
        self.widget.pack_start(self.wid_size, expand=not self.filename,
            fill=True)

        self.but_new = gtk.Button()
        img_new = gtk.Image()
        img_new.set_from_stock('tryton-find', gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.but_new.set_image(img_new)
        self.but_new.set_relief(gtk.RELIEF_NONE)
        self.but_new.connect('clicked', self.sig_new)
        self.tooltips.set_tip(self.but_new, _('Select a File...'))
        self.widget.pack_start(self.but_new, expand=False, fill=False)

        if self.filename:
            self.but_open = gtk.Button()
            img_open = gtk.Image()
            img_open.set_from_stock('tryton-open', gtk.ICON_SIZE_SMALL_TOOLBAR)
            self.but_open.set_image(img_open)
            self.but_open.set_relief(gtk.RELIEF_NONE)
            self.but_open.connect('clicked', self.sig_open)
            self.tooltips.set_tip(self.but_open, _('Open...'))
            self.widget.pack_start(self.but_open, expand=False, fill=False)
        else:
            self.but_open = None

        self.but_save_as = gtk.Button()
        img_save_as = gtk.Image()
        img_save_as.set_from_stock('tryton-save-as',
            gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.but_save_as.set_image(img_save_as)
        self.but_save_as.set_relief(gtk.RELIEF_NONE)
        self.but_save_as.connect('clicked', self.sig_save_as)
        self.tooltips.set_tip(self.but_save_as, _('Save As...'))
        self.widget.pack_start(self.but_save_as, expand=False, fill=False)

        self.but_remove = gtk.Button()
        img_remove = gtk.Image()
        img_remove.set_from_stock('tryton-clear', gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.but_remove.set_image(img_remove)
        self.but_remove.set_relief(gtk.RELIEF_NONE)
        self.but_remove.connect('clicked', self.sig_remove)
        self.tooltips.set_tip(self.but_remove, _('Clear'))
        self.widget.pack_start(self.but_remove, expand=False, fill=False)

        self.last_open_file = None

        self.tooltips.enable()

    @property
    def filename_field(self):
        return self.record.group.fields.get(self.filename)

    def _readonly_set(self, value):
        if value:
            self.but_new.hide()
            self.but_remove.hide()
            self.widget.set_focus_chain([])
        else:
            self.but_new.show()
            self.but_remove.show()
            if self.wid_text:
                focus_chain = [self.wid_text]
            elif self.filename:
                focus_chain = [self.but_new, self.but_open, self.but_save_as,
                        self.but_remove]
            else:
                focus_chain = [self.but_new, self.but_save_as, self.but_remove]
            self.widget.set_focus_chain(focus_chain)

    def sig_new(self, widget=None):
        filename = ''
        if self.last_open_file:
            last_id, last_filename = self.last_open_file
            if last_id == self.record.id:
                filename = last_filename
        filename = file_selection(_('Open...'), filename=filename)
        if filename and self.field:
            self.field.set_client(self.record, open(filename, 'rb').read())
            if self.filename_field:
                self.filename_field.set_client(self.record,
                        os.path.basename(filename))

    def sig_open(self, widget=None):
        if not self.filename_field:
            return
        dtemp = tempfile.mkdtemp(prefix='tryton_')
        filename = self.filename_field.get(self.record)
        if not filename:
            return
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
        self.last_open_file = (self.record.id, file_path)

    def sig_save_as(self, widget=None):
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

    def sig_remove(self, widget=None):
        self.field.set_client(self.record, False)

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

    def display(self, record, field):
        super(Binary, self).display(record, field)
        if not field:
            if self.wid_text:
                self.wid_text.set_text('')
            self.wid_size.set_text('')
            if self.but_open:
                self.but_open.set_sensitive(False)
            self.but_save_as.set_sensitive(False)
            return False
        if self.wid_text:
            self.wid_text.set_text(self.filename_field.get(record) or '')
        if hasattr(field, 'get_size'):
            size = field.get_size(record)
        else:
            size = len(field.get(record))
        self.wid_size.set_text(common.humanize(size or 0))
        if self.but_open:
            self.but_open.set_sensitive(bool(size))
        self.but_save_as.set_sensitive(bool(size))
        return True

    def set_value(self, record, field):
        if self.wid_text:
            self.filename_field.set_client(self.record,
                    self.wid_text.get_text() or False)
        return

    def _color_widget(self):
        if self.wid_text:
            return self.wid_text
        else:
            return self.wid_size
