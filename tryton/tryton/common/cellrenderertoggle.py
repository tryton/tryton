# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gtk
import gobject


class CellRendererToggle(gtk.GenericCellRenderer):
    __gproperties__ = {
        'activatable': (gobject.TYPE_INT, 'Activatable',
            'Activatable', 0, 10, 0, gobject.PARAM_READWRITE),
        'visible': (gobject.TYPE_INT, 'Visible',
            'Visible', 0, 10, 0, gobject.PARAM_READWRITE),
        }

    __gsignals__ = {
        'toggled': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
            (gobject.TYPE_STRING, )),
        }

    def __init__(self):
        self.__gobject_init__()
        self._renderer = gtk.CellRendererToggle()
        self._renderer.connect('toggled', self._sig_toggled)
        self.set_property("mode", self._renderer.get_property("mode"))

        self.activatable = self._renderer.get_property('activatable')
        self.visible = True

    def set_sensitive(self, value):
        if hasattr(self._renderer, 'set_sensitive'):
            return self._renderer.set_sensitive(value)
        return self._renderer.set_property('sensitive', value)

    def do_set_property(self, pspec, value):
        setattr(self, pspec.name, value)
        if pspec.name == 'visible':
            return
        self._renderer.set_property(pspec.name, value)
        self.set_property("mode", self._renderer.get_property("mode"))

    def do_get_property(self, pspec):
        return getattr(self, pspec.name)

    def on_get_size(self, widget, cell_area):
        return self._renderer.get_size(widget, cell_area)

    def on_render(self, window, widget, background_area, cell_area,
            expose_area, flags):
        if not self.visible:
            return
        # Handle Pixmap window as pygtk failed
        if type(window) == gtk.gdk.Pixmap:
            return
        return self._renderer.render(window, widget, background_area,
                cell_area, expose_area, flags)

    def on_activate(self, event, widget, path, background_area, cell_area,
            flags):
        if not self.visible:
            return
        if not event:
            event = gtk.gdk.Event(gtk.keysyms.KP_Space)
        return self._renderer.activate(event, widget, path, background_area,
                cell_area, flags)

    def on_start_editing(self, event, widget, path, background_area,
            cell_area, flags):
        return self._renderer.start_editing(event, widget, path,
                background_area, cell_area, flags)

    def get_active(self):
        return self._renderer.get_active()

    def set_active(self, setting):
        return self._renderer.set_active(setting)

    def _sig_toggled(self, renderer, path):
        if self.activatable and self.visible:
            self.emit('toggled', path)

gobject.type_register(CellRendererToggle)
