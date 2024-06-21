# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
from pathlib import Path

from gi.repository import Gdk, GLib, Gtk

try:
    from gi.repository import EvinceDocument, EvinceView
    EvinceDocument.init()
except ImportError:
    EvinceDocument = EvinceView = None

from tryton.common import data2pixbuf, resize_pixbuf

from .binary import BinaryMixin
from .widget import Widget

logger = logging.getLogger(__name__)


class Document(BinaryMixin, Widget):
    expand = True

    def __init__(self, view, attrs):
        super().__init__(view, attrs)

        self.widget = Gtk.VBox(spacing=3)
        self.image = Gtk.DrawingArea()
        self.widget.pack_start(
            self.image, expand=True, fill=True, padding=0)

        if EvinceView:
            self.evince_view = EvinceView.View()
            self.evince_scroll = Gtk.ScrolledWindow()
            self.evince_scroll.add(self.evince_view)
            self.widget.pack_start(
                self.evince_scroll, expand=True, fill=True, padding=0)
        else:
            self.evince_view = self.evince_scroll = None

    def _draw(self, drawing_area, cr, pixbuf):
        width = drawing_area.get_allocated_width()
        height = drawing_area.get_allocated_height()
        pixbuf = resize_pixbuf(pixbuf, width, height)
        width = (width - pixbuf.get_width()) / 2
        height = (height - pixbuf.get_height()) / 2
        Gdk.cairo_set_source_pixbuf(cr, pixbuf, width, height)
        cr.paint()

    def display(self):
        super().display()
        if self.field and self.record:
            data = self.field.get_data(self.record)
        else:
            data = None

        if not data:
            self.image.hide()
            if self.evince_view:
                self.evince_view.set_model(EvinceView.DocumentModel())
                self.evince_scroll.hide()
            return

        pixbuf = data2pixbuf(data)
        if pixbuf:
            try:
                self.image.disconnect_by_func(self._draw)
            except TypeError:
                pass
            self.image.connect('draw', self._draw, pixbuf)
            self.image.queue_draw()
            self.image.show()
            if self.evince_view:
                self.evince_view.set_model(EvinceView.DocumentModel())
                self.evince_scroll.hide()
        else:
            self.image.hide()
            if self.evince_view:
                self.evince_scroll.show()
                suffix = None
                if self.filename_field:
                    filename = self.filename_field.get(self.record)
                    if filename:
                        suffix = Path(filename).suffix
                filename = Path(self.field.get_filename(self.record, suffix))
                try:
                    document = (
                        EvinceDocument.Document.factory_get_document_full(
                            filename.as_uri(),
                            EvinceDocument.DocumentLoadFlags.NONE))
                    model = EvinceView.DocumentModel()
                    model.set_document(document)
                    self.evince_view.set_model(model)
                except GLib.GError:
                    logger.warning(
                        f"Could not open document {filename}",
                        exc_info=True)
                    self.evince_view.set_model(EvinceView.DocumentModel())
                    self.evince_scroll.hide()
