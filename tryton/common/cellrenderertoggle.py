# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gtk
import gobject


class CellRendererToggle(gtk.CellRendererToggle):
    __gproperties__ = {
        'visible': (gobject.TYPE_INT, 'Visible',
            'Visible', 0, 10, 0, gobject.PARAM_READWRITE),
        }

    def __init__(self):
        gtk.CellRendererToggle.__init__(self)
        self.__visible = True

    def set_sensitive(self, value):
        self.set_property('sensitive', value)

    def do_set_property(self, prop, value):
        if prop.name == 'visible':
            self.__visible = value
            return
        gtk.CellRendererToggle.do_set_property(self, prop, value)

    def do_get_property(self, prop):
        if prop.name == 'visible':
            return self.__visible
        return gtk.CellRendererToggle.do_get_property(self, prop)

    def do_render(self, window, widget, background_area, cell_area,
            expose_area, flags):
        if not self.__visible:
            return
        gtk.CellRendererToggle.do_render(self, window, widget,
            background_area, cell_area, expose_area, flags)

    def do_activate(self, event, widget, path, background_area, cell_area,
            flags):
        if not self.__visible:
            return
        if not event:
            event = gtk.gdk.Event(gtk.keysyms.KP_Space)
        return gtk.CellRendererToggle.do_activate(self, event, widget, path,
            background_area, cell_area, flags)

    def do_start_editing(self, event, widget, path, background_area,
            cell_area, flags):
        if not self.__visible:
            return
        return gtk.CellRendererToggle.do_start_editing(event, widget, path,
            background_area, cell_area, flags)

gobject.type_register(CellRendererToggle)
