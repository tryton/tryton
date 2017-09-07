# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gtk
import gettext
import urllib

from tryton.common import resize_pixbuf, data2pixbuf, BIG_IMAGE_SIZE
from .widget import Widget
from .binary import BinaryMixin

_ = gettext.gettext


class Image(BinaryMixin, Widget):

    def __init__(self, view, attrs):
        super(Image, self).__init__(view, attrs)

        self.height = int(attrs.get('height', 100))
        self.width = int(attrs.get('width', 300))

        self.widget = gtk.VBox(spacing=3)
        self.event = gtk.EventBox()
        self.event.drag_dest_set(gtk.DEST_DEFAULT_ALL, [
            gtk.TargetEntry.new('text/plain', 0, 0),
            gtk.TargetEntry.new('text/uri-list', 0, 1),
            gtk.TargetEntry.new("image/x-xpixmap", 0, 2)], gtk.gdk.ACTION_MOVE)
        self.event.connect('drag_motion', self.drag_motion)
        self.event.connect('drag_data_received', self.drag_data_received)

        self.image = gtk.Image()
        self.event.add(self.image)
        self.widget.pack_start(self.event, expand=True, fill=True)

        toolbar = self.toolbar()  # Set button attributes even if not display
        if not attrs.get('readonly'):
            alignment = gtk.Alignment(xalign=0.5, yalign=0.5)
            alignment.add(toolbar)
            self.widget.pack_start(alignment, expand=False, fill=False)

        self._readonly = False

        self.update_img()

    @property
    def filters(self):
        filters = super(Image, self).filters
        filter_image = gtk.FileFilter()
        filter_image.set_name(_('Images'))
        for mime in ("image/png", "image/jpeg", "image/gif"):
            filter_image.add_mime_type(mime)
        for pat in ("*.png", "*.jpg", "*.gif", "*.tif", "*.xpm"):
            filter_image.add_pattern(pat)
        filters.insert(0, filter_image)
        return filters

    def _readonly_set(self, value):
        self._readonly = value
        self.but_select.set_sensitive(not value)
        self.but_clear.set_sensitive(not value)

    def clear(self, widget=None):
        super(Image, self).clear(widget=widget)
        self.update_img()

    def drag_motion(self, widget, context, x, y, timestamp):
        if self._readonly:
            return False
        context.drag_status(gtk.gdk.ACTION_COPY, timestamp)
        return True

    def drag_data_received(self, widget, context, x, y, selection,
            info, timestamp):
        if self._readonly:
            return
        if info == 0:
            uri = selection.get_text().split('\n')[0]
            if uri:
                self.field.set_client(self.record, urllib.urlopen(uri).read())
            self.update_img()
        elif info == 1:
            uri = selection.data.split('\r\n')[0]
            if uri:
                self.field.set_client(self.record, urllib.urlopen(uri).read())
            self.update_img()
        elif info == 2:
            data = selection.get_pixbuf()
            if data:
                self.field.set_client(self.record, data)
                self.update_img()

    def update_img(self):
        value = None
        if self.field:
            value = self.field.get_client(self.record)
        if isinstance(value, (int, long)):
            if value > BIG_IMAGE_SIZE:
                value = False
            else:
                value = self.field.get_data(self.record)
        pixbuf = resize_pixbuf(data2pixbuf(value), self.width, self.height)
        self.image.set_from_pixbuf(pixbuf)
        return bool(value)

    def display(self, record, field):
        super(Image, self).display(record, field)
        value = self.update_img()
        self.update_buttons(bool(value))
