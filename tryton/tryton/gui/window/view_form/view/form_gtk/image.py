#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gtk
import gettext
import os
from base64 import encodestring, decodestring
from tryton.common import file_selection, Tooltips
from tryton.config import PIXMAPS_DIR
from interface import WidgetInterface
import urllib

_ = gettext.gettext

NOIMAGE = file(os.path.join(PIXMAPS_DIR, 'tryton-noimage.png'), 'rb').read()


class Image(WidgetInterface):

    def __init__(self, window, parent, model, attrs=None):
        super(Image, self).__init__(window, parent, model, attrs=attrs)

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

        self.alignment = gtk.Alignment(xalign=0.5, yalign=0.5)
        self.hbox = gtk.HBox(spacing=0)
        self.but_add = gtk.Button()
        img_add = gtk.Image()
        img_add.set_from_stock('tryton-open', gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.but_add.set_image(img_add)
        self.but_add.set_relief(gtk.RELIEF_NONE)
        self.but_add.connect('clicked', self.sig_add)
        self.tooltips.set_tip(self.but_add, _('Set Image'))
        self.hbox.pack_start(self.but_add, expand=False, fill=False)

        self.but_save_as = gtk.Button()
        img_save_as = gtk.Image()
        img_save_as.set_from_stock('tryton-save', gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.but_save_as.set_image(img_save_as)
        self.but_save_as.set_relief(gtk.RELIEF_NONE)
        self.but_save_as.connect('clicked', self.sig_save_as)
        self.tooltips.set_tip(self.but_save_as, _('Save As'))
        self.hbox.pack_start(self.but_save_as, expand=False, fill=False)

        self.but_remove = gtk.Button()
        img_remove = gtk.Image()
        img_remove.set_from_stock('tryton-clear', gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.but_remove.set_image(img_remove)
        self.but_remove.set_relief(gtk.RELIEF_NONE)
        self.but_remove.connect('clicked', self.sig_remove)
        self.tooltips.set_tip(self.but_remove, _('Clear'))
        self.hbox.pack_start(self.but_remove, expand=False, fill=False)

        self.alignment.add(self.hbox)
        self.widget.pack_start(self.alignment, expand=False, fill=False)

        self.tooltips.enable()

        self._readonly = False

        self.update_img()

    def grab_focus(self):
        return self.image.grab_focus()

    def _readonly_set(self, value):
        self._readonly = value
        self.but_add.set_sensitive(not value)
        self.but_save_as.set_sensitive(not value)
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

        filename = file_selection(_('Open...'), parent=self._window,
                preview=True, filters=[filter_image, filter_all])
        if filename:
            self._view.modelfield.set_client(self._view.model,
                    encodestring(file(filename, 'rb').read()))
            self.update_img()

    def sig_save_as(self, widget):
        filename = file_selection(_('Save As...'), parent=self._window,
                action=gtk.FILE_CHOOSER_ACTION_SAVE)
        if filename:
            file(filename, 'wb').write(decodestring(
                self._view.modelfield.get_client(self._view.model)))

    def sig_remove(self, widget):
        self._view.modelfield.set_client(self._view.model, False)
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
                self._view.modelfield.set_client(self._view.model,
                        encodestring(urllib.urlopen(uri).read()))
            self.update_img()
        elif info == 1:
            uri = selection.data.split('\r\n')[0]
            if uri:
                self._view.modelfield.set_client(self._view.model,
                        encodestring(urllib.urlopen(uri).read()))
            self.update_img()
        elif info == 2:
            data = selection.get_pixbuf()
            if data:
                self._view.modelfield.set_client(self._view.model,
                        encodestring(data))
                self.update_img()

    def update_img(self):
        value = None
        if self._view:
            value = self._view.modelfield.get_client(self._view.model)
        if not value:
            data = NOIMAGE
        else:
            data = decodestring(value)

        pixbuf = None
        for ftype in ('jpeg', 'gif', 'png', 'bmp'):
            try:
                loader = gtk.gdk.PixbufLoader(ftype)
                loader.write(data, len(data))
                loader.close()
                pixbuf = loader.get_pixbuf()
            except:
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

    def display(self, model, model_field):
        if not model_field:
            return False
        super(Image, self).display(model, model_field)
        self.update_img()
