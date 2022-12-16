#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gtk
import glib
import gettext
import os
import tempfile
from tryton.common import file_selection, Tooltips, file_open
from tryton.config import PIXMAPS_DIR
from interface import WidgetInterface
import urllib

_ = gettext.gettext

NOIMAGE = open(os.path.join(PIXMAPS_DIR, 'tryton-noimage.png'), 'rb').read()


class Image(WidgetInterface):

    def __init__(self, field_name, model_name, attrs=None):
        super(Image, self).__init__(field_name, model_name, attrs=attrs)

        self.filename = attrs.get('filename')
        self.height = int(attrs.get('img_height', 100))
        self.width = int(attrs.get('img_width', 300))

        self.widget = gtk.VBox(spacing=3)
        self.event = gtk.EventBox()
        self.event.drag_dest_set(gtk.DEST_DEFAULT_ALL, [
            ('text/plain', 0, 0),
            ('text/uri-list', 0, 1),
            ("image/x-xpixmap", 0, 2)], gtk.gdk.ACTION_MOVE)
        self.event.connect('drag_motion', self.drag_motion)
        self.event.connect('drag_data_received', self.drag_data_received)

        self.tooltips = Tooltips()

        self.image = gtk.Image()
        self.event.add(self.image)
        self.widget.pack_start(self.event, expand=True, fill=True)

        if not attrs.get('readonly'):
            alignment = gtk.Alignment(xalign=0.5, yalign=0.5)
            hbox = gtk.HBox(spacing=0)
            self.but_add = gtk.Button()
            img_add = gtk.Image()
            img_add.set_from_stock('tryton-find', gtk.ICON_SIZE_SMALL_TOOLBAR)
            self.but_add.set_image(img_add)
            self.but_add.set_relief(gtk.RELIEF_NONE)
            self.but_add.connect('clicked', self.sig_add)
            self.tooltips.set_tip(self.but_add, _('Select an Image...'))
            hbox.pack_start(self.but_add, expand=False, fill=False)

            if self.filename:
                self.but_open = gtk.Button()
                img_open = gtk.Image()
                img_open.set_from_stock('tryton-open',
                    gtk.ICON_SIZE_SMALL_TOOLBAR)
                self.but_open.set_image(img_open)
                self.but_open.set_relief(gtk.RELIEF_NONE)
                self.but_open.connect('clicked', self.sig_open)
                self.tooltips.set_tip(self.but_open, _('Open...'))
                hbox.pack_start(self.but_open, expand=False, fill=False)
            else:
                self.but_open = None

            self.but_save_as = gtk.Button()
            img_save_as = gtk.Image()
            img_save_as.set_from_stock('tryton-save',
                gtk.ICON_SIZE_SMALL_TOOLBAR)
            self.but_save_as.set_image(img_save_as)
            self.but_save_as.set_relief(gtk.RELIEF_NONE)
            self.but_save_as.connect('clicked', self.sig_save_as)
            self.tooltips.set_tip(self.but_save_as, _('Save As...'))
            hbox.pack_start(self.but_save_as, expand=False, fill=False)

            self.but_remove = gtk.Button()
            img_remove = gtk.Image()
            img_remove.set_from_stock('tryton-clear',
                gtk.ICON_SIZE_SMALL_TOOLBAR)
            self.but_remove.set_image(img_remove)
            self.but_remove.set_relief(gtk.RELIEF_NONE)
            self.but_remove.connect('clicked', self.sig_remove)
            self.tooltips.set_tip(self.but_remove, _('Clear'))
            hbox.pack_start(self.but_remove, expand=False, fill=False)

            alignment.add(hbox)
            self.widget.pack_start(alignment, expand=False, fill=False)
        else:
            self.but_add = None
            self.but_open = None
            self.but_save_as = None
            self.but_remove = None

        self.tooltips.enable()

        self._readonly = False

        self.update_img()

    @property
    def filename_field(self):
        return self.record.group.fields.get(self.filename)

    def grab_focus(self):
        return self.image.grab_focus()

    def _readonly_set(self, value):
        self._readonly = value
        if self.but_add:
            self.but_add.set_sensitive(not value)
        if self.but_open:
            self.but_open.set_sensitive(not value)
        if self.but_save_as:
            self.but_save_as.set_sensitive(not value)
        if self.but_remove:
            self.but_remove.set_sensitive(not value)

    def sig_add(self, widget):
        filter_all = gtk.FileFilter()
        filter_all.set_name(_('All files'))
        filter_all.add_pattern("*")

        filter_image = gtk.FileFilter()
        filter_image.set_name(_('Images'))
        for mime in ("image/png", "image/jpeg", "image/gif"):
            filter_image.add_mime_type(mime)
        for pat in ("*.png", "*.jpg", "*.gif", "*.tif", "*.xpm"):
            filter_image.add_pattern(pat)

        filename = file_selection(_('Open...'), preview=True,
            filters=[filter_image, filter_all])
        if filename:
            self.field.set_client(self.record, open(filename, 'rb').read())
            if self.filename_field:
                self.filename_field.set_client(self.record,
                        os.path.basename(filename))
            self.update_img()

    def sig_open(self, widget=None):
        if not self.filename_field:
            return
        dtemp = tempfile.mkdtemp(prefix='tryton_')
        filename = self.filename_field.get(self.record).replace(
                os.sep, '_').replace(os.altsep or os.sep, '_')
        file_path = os.path.join(dtemp, filename)
        with open(file_path, 'wb') as fp:
            fp.write(self.field.get_data(self.record))
        root, type_ = os.path.splitext(filename)
        if type_:
            type_ = type_[1:]
        file_open(file_path, type_)

    def sig_save_as(self, widget):
        filename = ''
        if self.filename_field:
            filename = self.filename_field.get(self.record)
        filename = file_selection(_('Save As...'), filename=filename,
            action=gtk.FILE_CHOOSER_ACTION_SAVE)
        if filename:
            with open(filename, 'wb') as fp:
                fp.write(self.field.get_data(self.record))

    def sig_remove(self, widget):
        self.field.set_client(self.record, False)
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
            if value > 10 ** 6:
                value = False
            else:
                value = self.field.get_data(self.record)
        if not value:
            data = NOIMAGE
        else:
            data = value

        pixbuf = None
        for ftype in ('jpeg', 'gif', 'png', 'bmp', 'svg'):
            try:
                loader = gtk.gdk.PixbufLoader(ftype)
                loader.write(data, len(data))
                loader.close()
                pixbuf = loader.get_pixbuf()
            except glib.GError:
                continue
            if pixbuf:
                break
        if not pixbuf:
            loader = gtk.gdk.PixbufLoader('png')
            loader.write(NOIMAGE, len(NOIMAGE))
            loader.close()
            pixbuf = loader.get_pixbuf()

        img_height = pixbuf.get_height()
        if img_height > self.height:
            height = self.height
        else:
            height = img_height

        img_width = pixbuf.get_width()
        if img_width > self.width:
            width = self.width
        else:
            width = img_width

        if (img_width / width) < (img_height / height):
            width = float(img_width) / float(img_height) * float(height)
        else:
            height = float(img_height) / float(img_width) * float(width)

        scaled = pixbuf.scale_simple(int(width), int(height),
                gtk.gdk.INTERP_BILINEAR)
        self.image.set_from_pixbuf(scaled)

    def display(self, record, field):
        if not field:
            return False
        super(Image, self).display(record, field)
        self.update_img()
