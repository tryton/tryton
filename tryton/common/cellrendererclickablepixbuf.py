# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gtk
import gobject


class CellRendererClickablePixbuf(gtk.CellRendererPixbuf):
    __gsignals__ = {
        'clicked': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
            (gobject.TYPE_STRING, )),
        }

    def __init__(self):
        super(CellRendererClickablePixbuf, self).__init__()
        self.set_property('mode', gtk.CELL_RENDERER_MODE_ACTIVATABLE)

    def do_activate(self, event, widget, path, background_area, cell_area,
            flags):
        if (event
                and cell_area.x <= event.x <= cell_area.x + cell_area.width
                and cell_area.y <= event.y <= cell_area.y + cell_area.height):
            self.emit('clicked', path)

gobject.type_register(CellRendererClickablePixbuf)
